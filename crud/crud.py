from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os, logging
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
import asyncio
import aiomqtt
import ssl

async def publicar_mqtt(sensor_id, subtopico, valor):
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    async with aiomqtt.Client(
        hostname=os.environ['DOMINIO'],
        port=int(os.environ['PUERTO_MQTTS']),
        username=os.environ['MQTT_USR'],
        password=os.environ['MQTT_PASS'],
        tls_context=tls_context
    ) as client:
        topico = f"{sensor_id}/{subtopico}"
        await client.publish(topico, str(valor), qos=1)
        
logging.basicConfig(
    format='%(asctime)s - CRUD - %(levelname)s - %(message)s', 
    level=logging.INFO
)


app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
# base de datos de agenda 
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
#base de datos de sensores
#app.config["MYSQL_DB"] = os.environ["MYSQL_MQTT_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME']=180

mysql = MySQL(app)


# rutas

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    """Registrar usuario"""
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        # Validación de campos
        if not usuario:
            flash("El campo usuario es obligatorio", "danger")
            return redirect(url_for('registrar'))
        elif not password:
            flash("El campo contraseña es obligatorio", "danger")
            return redirect(url_for('registrar'))

        cur = mysql.connection.cursor()

        # Verificar si ya existe el usuario
        cur.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
        existente = cur.fetchone()

        if existente:
            flash("El nombre de usuario ya está registrado", "warning")
            return redirect(url_for('registrar'))

        # Insertar nuevo usuario
        passhash = generate_password_hash(password, method='scrypt', salt_length=16)
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s, %s)", (usuario, passhash[17:]))
        mysql.connection.commit()

        flash("Cuenta creada correctamente", "success")
        logging.info("Se registró un nuevo usuario: %s", usuario)
        return redirect(url_for('index'))

    return render_template("registrar.html", ocultar_navbar=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("usuario"):
            return "el campo usuario es oblicatorio"
        # Ensure password was submitted
        elif not request.form.get("password"):
            return "el campo contraseña es oblicatorio"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows=cur.fetchone()
        if(rows):
            if (check_password_hash('scrypt:32768:8:1$' + rows[2],request.form.get("password"))):
                session.permanent = True
                session["user_id"]=request.form.get("usuario")
                logging.info("se autenticó correctamente")
                return redirect(url_for('index'))
            else:
                flash('usuario o contraseña incorrecto')
                return redirect(url_for('login'))
    return render_template("login.html", ocultar_navbar=True)

@app.route('/mqtt')
@require_login
def panel_mqtt():
    cur = mysql.connection.cursor()
    cur.execute("SELECT DISTINCT sensor_id FROM sensores_remotos.mediciones")
    sensores = [row[0] for row in cur.fetchall()]
    cur.close()
    return render_template("panel.html", sensores=sensores)

@app.route("/enviar_comando", methods=["POST"])
@require_login
def enviar_comando():
    sensor_id = request.form.get("sensor_id")
    comando = request.form.get("comando")
    valor = request.form.get("valor", "")

    if not sensor_id or not comando:
        flash("Faltan datos para enviar el comando", "danger")
        return redirect(url_for("panel_mqtt"))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        if comando == "destello":
            loop.run_until_complete(publicar_mqtt(sensor_id, "destello", "1"))
            logging.info(f"Usuario {session.get('user_id')} envió 'destello' al nodo {sensor_id}")
        elif comando == "setpoint":
            loop.run_until_complete(publicar_mqtt(sensor_id, "setpoint", valor))
            logging.info(f"Usuario {session.get('user_id')} envió 'setpoint={valor}' al nodo {sensor_id}")
        else:
            logging.warning(f"Comando desconocido: {comando}")
            flash("Comando no reconocido", "warning")
            return redirect(url_for("panel_mqtt"))

        flash(f"Comando '{comando}' enviado al nodo {sensor_id}", "success")
    except Exception as e:
        logging.error(f"Error al enviar comando MQTT: {e}")
        flash("Ocurrió un error al enviar el comando", "danger")
    finally:
        loop.close()

    return redirect(url_for("panel_mqtt"))

@app.route('/agenda')
@require_login
def index():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos')
    datos = cur.fetchall()
    cur.close()
    return render_template('index.html', contactos = datos)

@app.route('/add_contact', methods=['POST'])
@require_login
def add_contact():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO contactos (nombre, tel, email) VALUES (%s,%s,%s)"
                    , (nombre, tel, email))
        if mysql.connection.affected_rows():
            flash('Se agregó un contacto')  # usa sesión
            logging.info("se agregó un contacto")
            mysql.connection.commit()
    return redirect(url_for('index'))

@app.route('/borrar/<string:id>', methods = ['GET'])
@require_login
def borrar_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM contactos WHERE id = {0}'.format(id))
    if mysql.connection.affected_rows():
        flash('Se eliminó un contacto')  # usa sesión
        logging.info("se eliminó un contacto")
        mysql.connection.commit()
    return redirect(url_for('index'))

@app.route('/editar/<id>', methods = ['GET'])
@require_login
def conseguir_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos WHERE id = %s', (id,))
    datos = cur.fetchone()
    logging.info(datos)
    return render_template('editar-contacto.html', contacto = datos)

@app.route('/actualizar/<id>', methods=['POST'])
@require_login
def actualizar_contacto(id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE contactos SET nombre=%s, tel=%s, email=%s WHERE id=%s", (nombre, tel, email, id))
    if mysql.connection.affected_rows():
        flash('Se actualizó un contacto')  # usa sesión
        logging.info("se actualizó un contacto")
        mysql.connection.commit()
    return redirect(url_for('index'))

@app.route("/logout")
@require_login
def logout():
    session.clear()
    logging.info("el usuario {} cerró su sesión".format(session.get("user_id")))
    return redirect(url_for('index'))

@app.route("/cambiar_tema", methods=["POST"])
@require_login
def cambiar_tema():
    data = request.get_json()
    tema = data.get("tema")
    if tema in ["light", "dark"]:
        session["tema"] = tema
        logging.info(f"Tema cambiado a {tema} por el usuario {session.get('user_id')}")
    return '', 204