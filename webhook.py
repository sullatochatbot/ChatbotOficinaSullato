import os
import json
from flask import Flask, request, jsonify
from responder_oficina import responder_oficina

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


# ============================================================
# ENVIO PADRÃO PARA A API DO WHATSAPP
# ============================================================
def enviar_whatsapp(payload):
    import requests
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    r = requests.post(url, headers=headers, json=payload)
    print("🌐 RESPOSTA WHATSAPP:", r.text)
    return r.text


def enviar_texto(numero, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    enviar_whatsapp(payload)


def enviar_botoes(numero, texto, botoes):
    botoes_formatados = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
        for b in botoes
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": botoes_formatados}
        }
    }
    enviar_whatsapp(payload)


# ============================================================
# VERIFICAÇÃO DO WEBHOOK
# ============================================================
@app.route("/webhook", methods=["GET"])
def verificar():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403


# ============================================================
# RECEBIMENTO DE MENSAGENS
# ============================================================
@app.route("/webhook", methods=["POST"])
def receber():
    dados = request.get_json()
    print("📥 RECEBIDO:", json.dumps(dados, indent=2, ensure_ascii=False))

    try:
        entry = dados.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})

        # ====== CAPTURA DE MENSAGENS (AMBAS AS FORMAS) ======
        mensagens = value.get("messages") or value.get("mensagens") or []
        if not mensagens:
            return "OK", 200

        msg = mensagens[0]
        numero = msg.get("from")

        # ====== CAPTURA DO NOME ======
        nome_whatsapp = "Cliente"

        contacts = value.get("contacts") or value.get("contactos")
        if contacts:
            profile = contacts[0].get("profile") or contacts[0].get("perfil")
            if profile:
                nome_whatsapp = (
                    profile.get("name")
                    or profile.get("Nome")
                    or "Cliente"
                )

        # ====== TEXTO ======
        if msg.get("type") == "text":
            texto = msg["text"].get("body", "")
            responder_oficina(numero, texto, nome_whatsapp)
            return "OK", 200

        # ====== BOTÃO ======
        if msg.get("type") == "interactive":
            botao = msg["interactive"].get("button_reply", {})
            botao_id = botao.get("id")
            responder_oficina(numero, botao_id, nome_whatsapp)
            return "OK", 200

        return "OK", 200

    except Exception as erro:
        print("❌ ERRO NO WEBHOOK:", erro)
        return "ERR", 500


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
