from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import httpx
import os

app = Flask(__name__)

SUPABASE_URL = "https://awbnbiyxvkpkrrpzlupy.supabase.co"
SUPABASE_KEY = "sb_publicable_aUPSBdPyx5jEEhyXHfvdIQ_iW2YOoda"

sesiones = {}

def buscar_productos(producto, localidad):
    url = f"{SUPABASE_URL}/rest/v1/productos"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    params = {
        "producto": f"ilike.*{producto}*",
        "localidad": f"ilike.*{localidad}*",
        "order": "precio.asc"
    }
    r = httpx.get(url, headers=headers, params=params)
    return r.json()

@app.route("/bot", methods=["POST"])
def bot():
    numero = request.form.get("From")
    mensaje = request.form.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    if numero not in sesiones:
        sesiones[numero] = {"paso": "inicio"}

    paso = sesiones[numero]["paso"]

    if paso == "inicio":
        msg.body("👋 ¡Hola! Soy Turkito 🛒, el asistente de *Tu Mercado Digital*.\nTe ayudo a comparar precios en tu ciudad.\n\n¿Qué producto querés buscar?")
        
        sesiones[numero]["paso"] = "esperando_producto"

    elif paso == "esperando_producto":
        sesiones[numero]["producto"] = mensaje
        msg.body(f"🔍 Busco *{mensaje}*\n\n¿En qué localidad estás?\n(Ej: Santa Rosa de Calamuchita)")
        sesiones[numero]["paso"] = "esperando_localidad"

    elif paso == "esperando_localidad":
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

