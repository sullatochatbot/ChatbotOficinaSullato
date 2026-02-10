# ============================================================
# WEBHOOK — CHATBOT OFICINA SULLATO
# Base Flask + WhatsApp Business API (Meta)
# ============================================================

import os
import json
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
# HOME — HEALTHCHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "CHATBOT OFICINA SULLATO ONLINE", 200

# ============================================================
# VERIFICAÇÃO DO WEBHOOK (META)
# ============================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Token inválido", 403

# ============================================================
# FUNÇÃO — ENVIO DE TEMPLATE (IMAGEM + TEXTO + OLÁ / STOP)
# ============================================================

def enviar_template_oficina(numero):
    url = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": "oficina_promocao",   # 🔥 TEMPLATE JÁ EXISTENTE
            "language": {"code": "pt_BR"}
        }
    }

    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    print("📤 TEMPLATE OFICINA:", resp.status_code, resp.text)

# ============================================================
# RECEBIMENTO DE MENSAGENS (META → FLASK)
# ============================================================

@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    data = request.get_json(silent=True) or {}

    # ====================================================
    # DISPARO VIA APPS SCRIPT (IMAGEM + TEXTO + BOTÕES)
    # ====================================================

    if (
        isinstance(data, dict)
        and data.get("origem") == "apps_script_disparo"
        and "numero" in data
    ):
        numero = data.get("numero")

        try:
            enviar_template_oficina(numero)
            return "DISPARO_TEMPLATE_OK", 200

        except Exception as e:
            print("❌ ERRO AO ENVIAR TEMPLATE:", str(e))
            return "ERRO_TEMPLATE", 500

    # ====================================================
    # FLUXO NORMAL DE ATENDIMENTO
    # ====================================================

    try:
        print("📥 RECEBIDO:", json.dumps(data, indent=2, ensure_ascii=False))

        if "entry" not in data:
            return "IGNORADO", 200

        for entry in data["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})

                messages = value.get("messages")
                contacts = value.get("contacts")

                if not messages or not contacts:
                    continue

                msg = messages[0]
                contato = contacts[0]

                numero = contato.get("wa_id")
                nome_whatsapp = contato.get("profile", {}).get("name", "Cliente")

                texto = ""

                if msg.get("type") == "text":
                    texto = msg["text"]["body"]

                elif msg.get("type") == "interactive":
                    inter = msg["interactive"]
                    if inter["type"] == "button_reply":
                        texto = inter["button_reply"]["id"]
                    elif inter["type"] == "list_reply":
                        texto = inter["list_reply"]["id"]

                if "button" in msg:
                    texto = msg["button"].get("payload") or msg["button"].get("text", "")

                if not texto:
                    texto = "undefined"

                responder_oficina(
                    numero=numero,
                    texto_digitado=texto,
                    nome_whatsapp=nome_whatsapp
                )

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("❌ ERRO NO WEBHOOK:", str(e))
        return "ERRO", 200

# ============================================================
# RUN LOCAL / RENDER
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
