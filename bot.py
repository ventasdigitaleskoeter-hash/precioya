from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import httpx
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://awbnbiyxvkpkrrpzlupy.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

sesiones = {}

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def buscar_productos(producto, localidad):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    params = {
        "producto": f"ilike.*{producto}*",
        "localidad": f"ilike.*{localidad}*",
        "order": "precio.asc"
    }
    r = httpx.get(url, headers=HEADERS, params=params)
    return r.json()

def buscar_comercio(numero):
    try:
        url = f"{SUPABASE_URL}/rest/v1/comercios"
        params = {"telefono_wp": f"eq.{numero}"}
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] KEY: {SUPABASE_KEY[:20] if SUPABASE_KEY else 'VACIA'}")
        r = httpx.get(url, headers=HEADERS, params=params, timeout=10)
        print(f"[DEBUG] Status: {r.status_code}")
        print(f"[DEBUG] Response: {r.text[:200]}")
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        print(f"[ERROR] buscar_comercio: {e}")
        return None

def registrar_comercio(numero, nombre, direccion, telefono):
    try:
        url = f"{SUPABASE_URL}/rest/v1/comercios"
        data = {
            "telefono_wp": numero,
            "comercio": nombre,
            "direccion": direccion,
            "telefono": str(telefono).strip(),
            "localidad": "Santa Rosa de Calamuchita"
        }
        print(f"[DEBUG] Registrando comercio: {data}")
        r = httpx.post(url, headers=HEADERS, json=data)
        print(f"[DEBUG] Status registro: {r.status_code}")
        print(f"[DEBUG] Response registro: {r.text[:200]}")
        return r.status_code == 201
    except Exception as e:
        print(f"[ERROR] registrar_comercio: {e}")
        return False

def cargar_producto(comercio, producto, marca, precio):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    data = {
        "comercio": comercio["comercio"],
        "telefono": comercio["telefono"],
        "direccion": comercio["direccion"],
        "producto": producto,
        "marca": marca,
        "precio": float(precio),
        "localidad": comercio["localidad"],
        "categoria": "otros"
    }
    r = httpx.post(url, headers=HEADERS, json=data)
    return r.status_code == 201

def actualizar_precio(comercio, producto, nuevo_precio):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    params = {
        "comercio": f"eq.{comercio['comercio']}",
        "producto": f"ilike.*{producto}*"
    }
    data = {"precio": float(nuevo_precio)}
    r = httpx.patch(url, headers=HEADERS, params=params, json=data)
    return r.status_code == 204

def eliminar_producto(comercio, producto):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    params = {
        "comercio": f"eq.{comercio['comercio']}",
        "producto": f"ilike.*{producto}*"
    }
    r = httpx.delete(url, headers=HEADERS, params=params)
    return r.status_code == 204

def mis_productos(comercio):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    params = {"comercio": f"eq.{comercio['comercio']}", "order": "producto.asc"}
    r = httpx.get(url, headers=HEADERS, params=params)
    return r.json()

@app.route("/bot", methods=["POST"])
def bot():
    numero = request.form.get("From")
    mensaje = request.form.get("Body", "").strip()
    mensaje_lower = mensaje.lower()
    resp = MessagingResponse()
    msg = resp.message()

    if numero not in sesiones:
        sesiones[numero] = {"paso": "inicio"}

    paso = sesiones[numero]["paso"]
    comercio = buscar_comercio(numero)

    # ── SIEMPRE RESETEAR CON HOLA ─────────────
    if mensaje_lower in ["hola", "hi", "buenas", "buen dia", "buenas tardes", "buenas noches", "inicio", "empezar"]:
        sesiones[numero] = {"paso": "eligiendo_rol"}
        msg.body("👋 ¡Hola! Soy *Turkito* 🛒 de *Tu Mercado Digital*.\n\n¿Cómo puedo ayudarte?\n\n1️⃣ Soy *cliente* y quiero consultar precios\n2️⃣ Soy *comerciante* y quiero gestionar mi comercio")
        return str(resp)

    # ── ELEGIR ROL ────────────────────────────
    if paso == "eligiendo_rol":
        if mensaje in ["1", "cliente"]:
            sesiones[numero]["paso"] = "esperando_producto"
            msg.body("🛒 ¡Perfecto! ¿Qué producto querés buscar?\n_(Ej: Aceite, leche, yerba...)_")
        elif mensaje in ["2", "comerciante", "soy comerciante"]:
            if comercio:
                sesiones[numero] = {"paso": "menu_comerciante"}
                msg.body(
                    f"👋 ¡Hola de nuevo *{comercio['comercio']}*!\n\n"
                    "¿Qué querés hacer? Escribí:\n\n"
                    "📦 *cargar* → agregar un producto\n"
                    "✏️ *editar* → actualizar el precio\n"
                    "🗑️ *eliminar* → borrar un producto\n"
                    "📋 *ver* → ver tus productos\n"
                    "👋 *salir* → volver al inicio"
                )
            else:
                sesiones[numero] = {"paso": "registro_nombre"}
                msg.body("🏪 ¡Bienvenido a *Tu Mercado Digital*!\n\nVamos a registrar tu comercio.\n\n¿Cuál es el *nombre* de tu comercio?")
        else:
            msg.body("Por favor elegí una opción:\n\n1️⃣ Soy *cliente*\n2️⃣ Soy *comerciante*")
        return str(resp)

    # ── REGISTRO ─────────────────────────────
    if paso == "registro_nombre":
        sesiones[numero]["nombre"] = mensaje
        sesiones[numero]["paso"] = "registro_direccion"
        msg.body(f"✅ Comercio: *{mensaje}*\n\n¿Cuál es la *dirección*?")
        return str(resp)

    if paso == "registro_direccion":
        sesiones[numero]["direccion"] = mensaje
        sesiones[numero]["paso"] = "registro_telefono"
        msg.body("📞 ¿Cuál es el *teléfono* de contacto del comercio?")
        return str(resp)

    if paso == "registro_telefono":
        ok = registrar_comercio(numero, sesiones[numero]["nombre"], sesiones[numero]["direccion"], mensaje)
        if ok:
            sesiones[numero] = {"paso": "menu_comerciante"}
            msg.body(
                "🎉 ¡Comercio registrado!\n\n"
                "¿Qué querés hacer? Escribí:\n\n"
                "📦 *cargar* → agregar un producto\n"
                "✏️ *editar* → actualizar el precio\n"
                "🗑️ *eliminar* → borrar un producto\n"
                "📋 *ver* → ver tus productos\n"
                "👋 *salir* → volver al inicio"
            )
        else:
            sesiones[numero] = {"paso": "inicio"}
            msg.body("❌ Hubo un error al registrar. Escribí *hola* para intentar de nuevo.")
        return str(resp)

    # ── MENÚ COMERCIANTE ──────────────────────
    if paso == "menu_comerciante":
        if mensaje_lower in ["cargar", "agregar", "nuevo producto", "añadir"]:
            sesiones[numero]["paso"] = "cargar_producto"
            msg.body("📦 ¿Cómo se llama el *producto*?\n(Ej: Aceite girasol)")
        elif mensaje_lower in ["editar", "actualizar", "modificar", "cambiar precio"]:
            sesiones[numero]["paso"] = "actualizar_buscar"
            msg.body("✏️ ¿Qué producto querés actualizar?\n(Ej: Aceite patito 1.5l)")
        elif mensaje_lower in ["eliminar", "borrar", "quitar"]:
            sesiones[numero]["paso"] = "eliminar_buscar"
            msg.body("🗑️ ¿Qué producto querés eliminar?\n(Ej: Aceite patito 1.5l)")
        elif mensaje_lower in ["ver", "mis productos", "listar"]:
            productos = mis_productos(comercio)
            if not productos:
                msg.body("📋 No tenés productos cargados aún.\n\nEscribí *cargar* para agregar uno.")
            else:
                texto = "📋 *Tus productos:*\n\n"
                for p in productos:
                    texto += f"• {p['producto']} {p['marca']} → *${p['precio']}*\n"
                texto += "\nEscribí *cargar*, *editar*, *eliminar* o *salir*"
                msg.body(texto)
        elif mensaje_lower in ["salir", "exit", "volver"]:
            sesiones[numero] = {"paso": "eligiendo_rol"}
            msg.body("👋 ¡Hasta luego! Escribí *hola* cuando quieras volver.")
        else:
            msg.body(
                "No entendí. Escribí:\n\n"
                "📦 *cargar* → agregar un producto\n"
                "✏️ *editar* → actualizar el precio\n"
                "🗑️ *eliminar* → borrar un producto\n"
                "📋 *ver* → ver tus productos\n"
                "👋 *salir* → volver al inicio"
            )
        return str(resp)

    # ── CARGAR PRODUCTO ───────────────────────
    if paso == "cargar_producto":
        sesiones[numero]["prod_nombre"] = mensaje
        sesiones[numero]["paso"] = "cargar_marca"
        msg.body(f"✅ Producto: *{mensaje}*\n\n¿Cuál es la *marca y presentación*?\n(Ej: Patito 1.5L)")
        return str(resp)

    if paso == "cargar_marca":
        sesiones[numero]["prod_marca"] = mensaje
        sesiones[numero]["paso"] = "cargar_precio"
        msg.body(f"✅ Marca: *{mensaje}*\n\n¿Cuál es el *precio* en pesos?")
        return str(resp)

    if paso == "cargar_precio":
        try:
            precio = float(mensaje.replace("$", "").replace(",", "."))
            comercio = buscar_comercio(numero)
            ok = cargar_producto(comercio, sesiones[numero]["prod_nombre"], sesiones[numero]["prod_marca"], precio)
            if ok:
                msg.body(
                    f"✅ ¡Producto cargado!\n\n"
                    f"📦 {sesiones[numero]['prod_nombre']} {sesiones[numero]['prod_marca']} → *${precio}*\n\n"
                    "Escribí *cargar*, *editar*, *eliminar*, *ver* o *salir*"
                )
            else:
                msg.body("❌ Error al cargar. Intentá de nuevo escribiendo *cargar*.")
            sesiones[numero]["paso"] = "menu_comerciante"
        except:
            msg.body("⚠️ Por favor ingresá solo el número del precio. Ej: *1500*")
        return str(resp)

    # ── ACTUALIZAR PRECIO ─────────────────────
    if paso == "actualizar_buscar":
        sesiones[numero]["act_producto"] = mensaje
        sesiones[numero]["paso"] = "actualizar_precio"
        msg.body(f"💰 ¿Cuál es el *nuevo precio* de *{mensaje}*?")
        return str(resp)

    if paso == "actualizar_precio":
        try:
            precio = float(mensaje.replace("$", "").replace(",", "."))
            comercio = buscar_comercio(numero)
            ok = actualizar_precio(comercio, sesiones[numero]["act_producto"], precio)
            if ok:
                msg.body(
                    f"✅ ¡Precio actualizado!\n\n"
                    f"*{sesiones[numero]['act_producto']}* → *${precio}*\n\n"
                    "Escribí *cargar*, *editar*, *eliminar*, *ver* o *salir*"
                )
            else:
                msg.body("❌ No encontré ese producto. Verificá el nombre.")
            sesiones[numero]["paso"] = "menu_comerciante"
        except:
            msg.body("⚠️ Por favor ingresá solo el número. Ej: *1600*")
        return str(resp)

    # ── ELIMINAR PRODUCTO ─────────────────────
    if paso == "eliminar_buscar":
        sesiones[numero]["del_producto"] = mensaje
        sesiones[numero]["paso"] = "eliminar_confirmar"
        msg.body(f"⚠️ ¿Confirmás que querés eliminar *{mensaje}*?\n\nEscribí *si* para confirmar o *no* para cancelar.")
        return str(resp)

    if paso == "eliminar_confirmar":
        if mensaje_lower in ["si", "sí", "confirmar", "ok"]:
            comercio = buscar_comercio(numero)
            ok = eliminar_producto(comercio, sesiones[numero]["del_producto"])
            if ok:
                msg.body(
                    f"🗑️ ¡Producto *{sesiones[numero]['del_producto']}* eliminado!\n\n"
                    "Escribí *cargar*, *editar*, *eliminar*, *ver* o *salir*"
                )
            else:
                msg.body("❌ No encontré ese producto. Verificá el nombre.")
        elif mensaje_lower in ["no", "cancelar"]:
            msg.body("❌ Eliminación cancelada.\n\nEscribí *cargar*, *editar*, *eliminar*, *ver* o *salir*")
        else:
            msg.body("Por favor respondé *si* para confirmar o *no* para cancelar.")
            return str(resp)
        sesiones[numero]["paso"] = "menu_comerciante"
        return str(resp)

    # ── BÚSQUEDA CLIENTE ──────────────────────
    if paso == "esperando_producto":
        sesiones[numero]["producto"] = mensaje
        sesiones[numero]["paso"] = "esperando_localidad"
        msg.body(f"🔍 Busco *{mensaje}*\n\n¿En qué localidad estás?\n(Ej: Santa Rosa de Calamuchita)")
        return str(resp)

    if paso == "esperando_localidad":
        producto = sesiones[numero]["producto"]
        localidad = mensaje
        resultados = buscar_productos(producto, localidad)

        if not resultados or isinstance(resultados, dict):
            msg.body(f"😔 No encontré *{producto}* en *{localidad}*.\n\n¿Qué otro producto querés buscar?")
            sesiones[numero]["paso"] = "esperando_producto"
        else:
            respuesta = f"✅ *{producto}* en {localidad}:\n\n"
            for i, p in enumerate(resultados):
                emoji = "🏆" if i == 0 else f"{i+1}."
                respuesta += f"{emoji} *{p['comercio']}*\n"
                respuesta += f"   📦 {p['marca']}\n"
                respuesta += f"   💰 ${p['precio']}\n"
                respuesta += f"   📍 {p['direccion']}\n"
                respuesta += f"   📞 {p['telefono']}\n\n"
            respuesta += "¿Querés buscar otro producto?"
            msg.body(respuesta)
            sesiones[numero]["paso"] = "esperando_producto"
        return str(resp)

    msg.body("No entendí. Escribí *hola* para empezar.")
    sesiones[numero] = {"paso": "eligiendo_rol"}
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))