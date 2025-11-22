import os
import json
from flask import Flask, request, jsonify

from responder_oficina import responder_oficina

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")


def enviar_requisicao_whatsapp(payload):
    import requests

    url = f"https://graph.facebook.com/v17.0/{os.getenv('PHONE_NUMBER_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    resposta = requests.post(url, headers=headers, json=payload)
    print("WhatsApp API Response:", resposta.text)
    return resposta.text


def enviar_texto(numero, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto}
    }
    enviar_requisicao_whatsapp(payload)


def enviar_botoes(numero, texto, botoes):
    botoes_formatados = [
        {
            "type": "reply",
            "reply": {"id": botao["id"], "title": botao["title"]}
        }
        for botao in botoes
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

    enviar_requisicao_whatsapp(payload)


# ============================================================
# WEBHOOK VERIFY
# ============================================================
@app.route("/webhook", methods=["GET"])
def verify_token():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403


# ============================================================
# RECEBIMENTO DE MENSAGENS
# ============================================================
@app.route("/webhook", methods=["POST"])
def receber_mensagens():
    dados = request.get_json()
    print("🔵 RECEBIDO:", json.dumps(dados, indent=2, ensure_ascii=False))

    try:
        entry = dados["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        mensagens = value.get("messages", [])
        if not mensagens:
            return "EVENTO IGNORADO", 200

        msg = mensagens[0]
        numero = msg["from"]
        nome_whatsapp = msg.get("profile", {}).get("name", "Cliente")

        # TEXTO
        if msg["type"] == "text":
            texto = msg["text"]["body"]

            # Chamada COMPLETA do responder_oficina (5 argumentos)
            responder_oficina(
                numero,
                nome_whatsapp,
                texto,
                "texto",
                None
            )

            return "EVENTO PROCESSADO", 200

        # BOTÕES
        if msg["type"] == "interactive":
            botao = msg["interactive"]["button_reply"]["id"]
            responder_oficina(
                numero,
                nome_whatsapp,
                botao,
                "botao",
                botao
            )
            return "EVENTO PROCESSADO", 200

        return "TIPO NÃO TRATADO", 200

    except Exception as erro:
        print("❌ ERRO NO WEBHOOK:", erro)
        return "ERRO", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
