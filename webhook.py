import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from responder_oficina import responder_oficina

load_dotenv()

app = Flask(__name__)

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")

# ============================================================
# HOME
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return "OK", 200

# ============================================================
# VERIFICAÇÃO DO WEBHOOK (META)
# ============================================================
@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Erro", 403

# ============================================================
# NORMALIZAR URL DROPBOX (CORREÇÃO CRÍTICA)
# ============================================================
def normalizar_dropbox(url):
    if not url:
        return ""
    u = url.strip()
    u = u.replace("https://www.dropbox.com", "https://dl.dropboxusercontent.com")
    u = u.replace("?dl=0", "")
    return u

# ============================================================
# ENVIO DE TEMPLATE COM IMAGEM
# ============================================================
def enviar_template_oficina(numero, imagem_url):
    url = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": "oficina_promocao",
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {
                                "link": imagem_url
                            }
                        }
                    ]
                }
            ]
        }
    }

    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers, timeout=30)
    print("📤 TEMPLATE:", r.status_code, r.text)

# ============================================================
# WEBHOOK POST
# ============================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    # ========================================================
    # DISPARO VIA APPS SCRIPT (CORRIGIDO)
    # ========================================================
    if data.get("origem") == "apps_script_disparo":
        imagem = normalizar_dropbox(data.get("imagem_url"))
        enviar_template_oficina(
            numero=data.get("numero"),
            imagem_url=imagem
        )
        return "OK", 200

    # ========================================================
    # FLUXO NORMAL WHATSAPP
    # ========================================================
    if "entry" not in data:
        return "OK", 200

    for entry in data["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            msgs = value.get("messages")
            contatos = value.get("contacts")

            if not msgs or not contatos:
                continue

            numero = contatos[0]["wa_id"]
            nome = contatos[0]["profile"]["name"]
            texto = msgs[0].get("text", {}).get("body", "")

            responder_oficina(
                numero=numero,
                texto_digitado=texto,
                nome_whatsapp=nome
            )

    return "OK", 200

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
