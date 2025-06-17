# 📒 Agenda & Panel MQTT con Flask

Una aplicación web unificada que combina:

- 🚀 **CRUD de contactos** (Agenda)
- 📡 **Panel de control MQTT** para Raspberry Pi Pico W
- 🔐 **Autenticación de usuarios** (registro & login)
- 🌗 **Selector de tema claro/oscuro** (Bootstrap Brite)
- 🔍 **Navegación fluida** entre Agenda y Panel MQTT
- 📋 **Historial de comandos** registrado en logs

---

## 🔎 Descripción

Este proyecto ofrece dos servicios principales bajo un mismo sistema de login:

1. **Agenda de contactos**  
   - Alta, baja, modificación de contactos (nombre, teléfono, email).
   - Interfaz Bootstrap con mensajes flash.

2. **Panel MQTT**  
   - Listado dinámico de nodos (obtenido de la tabla `mediciones` en la DB `mediciones_sensores`).
   - Envío de comandos:
     - **Setpoint** (valor numérico, por defecto 25 °C)
     - **Destello** (parpadeo LED)
   - Publicación asíncrona vía `aiomqtt` sobre TLS al broker Mosquitto.
   - Registro en consola con `logging.info` de cada comando enviado (usuario, nodo, tipo y valor).

Además incluye:
- **Registro y login** con contraseñas hasheadas (`scrypt`), validación de usuario único.
- **Modo oscuro/­claro** togglable desde la navbar, sin recarga.
- Layout inspirado en [Bootswatch Brite](https://bootswatch.com/brite/).

---

## 🛠️ Tecnología y librerías

- **Backend**: Python 3.11 + Flask  
- **Base de datos Agenda**: MariaDB/MySQL (contenedor)
- **Base de datos Sensores**: MariaDB `mediciones_sensores`  
- **ORM ligero**: Flask‑MySQLdb  
- **MQTT asíncrono**: `aiomqtt` + TLS  
- **Front-end**: Bootstrap 5.3 (Bootswatch Brite) + Bootstrap Icons  
- **Seguridad**: Werk­zeug (hashing), Flask‑Session  
- **Logging**: módulo `logging`