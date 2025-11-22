import os
import json
from flask import Flask, request
from responder_oficina import responder_oficina

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")

@app.route("/", methods=["GET"])
def home():
    return "ONLINE", 200

# ============================================================
# VERIFICAÇÃO DO WEBHOOK (META → FLASK)
# ============================================================

@app.route("/webhook", methods=["GET"])
def verificar_token():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Token inválido", 403


# ============================================================
# RECEBIMENTO DE MENSAGENS (WHATSAPP → FLASK)
# ============================================================

@app.route("/webhook", methods=["POST"])
def receber_mensagem():
    data = request.get_json()

    try:
        print("📥 RECEBIDO:", json.dumps(data, indent=2, ensure_ascii=False))

        if "entry" in data:
            for entry in data["entry"]:
                if "changes" in entry:
                    for change in entry["changes"]:
                        value = change.get("value", {})

                        messages = value.get("messages")
                        contacts = value.get("contacts")

                        if messages and contacts:

                            mensagem = messages[0]
                            contato = contacts[0]

                            numero = contato.get("wa_id")
                            nome_whatsapp = contato.get("profile", {}).get("name", "Cliente")

                            texto = ""

                            if mensagem.get("type") == "text":
                                texto = mensagem["text"]["body"]

                            # BOTÕES (interactive reply)
                            if mensagem.get("type") == "interactive":
                                if mensagem["interactive"].get("type") == "button_reply":
                                    texto = mensagem["interactive"]["button_reply"]["id"]

                            # ENTREGAR PRO CHATBOT
                            responder_oficina(numero, texto, nome_whatsapp)

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("❌ ERRO NO WEBHOOK:", str(e))
        return "ERRO", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
