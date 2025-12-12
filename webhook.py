import os
import json
import time
import requests
from flask import Flask, request
from responder_oficina import responder_oficina, enviar_imagem, enviar_texto

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")
WA_TOKEN = os.getenv("WA_ACCESS_TOKEN")
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")

# ============================================================
# HOME
# ============================================================
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

                    # Texto normal
                    if msg.get("type") == "text":
                        texto = msg["text"]["body"]

                    # Botões interativos
                    elif msg.get("type") == "interactive":
                        inter = msg["interactive"]
                        if inter["type"] == "button_reply":
                            texto = inter["button_reply"]["id"]
                        elif inter["type"] == "list_reply":
                            texto = inter["list_reply"]["id"]

                    # Botões herdados
                    if "button" in msg:
                        texto = msg["button"].get("payload") or msg["button"].get("text", "")

                    if not texto:
                        texto = "undefined"

                    print(f"➡️ Texto interpretado: {texto}")
                    responder_oficina(numero, texto, nome_whatsapp)

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("❌ ERRO NO WEBHOOK:", str(e))
        return "ERRO", 200


# ============================================================
# ENVIO DO TEMPLATE `oficina_disparo` (com botões Olá / Stop)
# ============================================================
def enviar_template_oficina_disparo(numero):
    url = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": "oficina_disparo",
            "language": { "code": "pt_BR" }
        }
    }

    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json=payload)
    print("📤 ENVIO TEMPLATE:", res.text)
    return res


# ============================================================
# ENDPOINT DE DISPARO — USA TEMPLATE + IMAGEM
# ============================================================
@app.route("/disparo_midia", methods=["POST"])
def disparo_midia():
    try:
        data = request.get_json()

        print("📥 DISPARO MIDIA RECEBIDO:", json.dumps(data, indent=2, ensure_ascii=False))

        numero = data.get("numero")
        imagem_url = data.get("imagem_url")

        if not numero or not imagem_url:
            return {"erro": "Payload inválido"}, 400

        # 1) Envia template com botões
        enviar_imagem(numero, imagem_url)
        time.sleep(0.7)

        # 2) Envia imagem
        enviar_template_oficina_disparo(numero)

        return {"status": "OK", "mensagem": "TEMPLATE + IMAGEM enviados"}, 200

    except Exception as e:
        print("❌ ERRO DISPARO MIDIA:", str(e))
        return {"erro": str(e)}, 500


# ============================================================
# RUN FLASK
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
