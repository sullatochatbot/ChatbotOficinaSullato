import os
import json
from flask import Flask, request, jsonify
from responder_oficina import responder_oficina

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")

# ============================================================
# HOME - FIX DO HEALTH CHECK DO RENDER
# ============================================================
@app.route("/", methods=["GET"])
def home():
    return "OK", 200


# ============================================================
# ENVIO PARA A API DO WHATSAPP
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
# VERIFICAÇÃO - GET /webhook
# ============================================================
@app.route("/webhook", methods=["GET"])
def verificar():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Token inválido", 403


# ============================================================
# RECEBIMENTO - POST /webhook
# ============================================================
@app.route("/webhook", methods=["POST"])
def receber():
    dados = request.get_json()
    print("📥 RECEBIDO:", json.dumps(dados, indent=2, ensure_ascii=False))

    try:
        # entry OU entrada
        entry = dados.get("entry") or dados.get("entrada")
        if not entry:
            return "OK", 200
        entry = entry[0]

        # changes OU mudanças
        change = entry.get("changes") or entry.get("mudanças")
        if not change:
            return "OK", 200
        change = change[0]

        # value OU valor
        value = change.get("value") or change.get("valor") or {}

        # messages OU mensagens
        mensagens = value.get("messages") or value.get("mensagens") or []
        if not mensagens:
            return "OK", 200

        msg = mensagens[0]

        # telefone
        numero = msg.get("from") or msg.get("de")

        # nome do WhatsApp
        nome = "Cliente"
        contatos = value.get("contacts") or value.get("contactos") or []

        if contatos:
            perfil = contatos[0].get("profile") or contatos[0].get("perfil")
            if perfil:
                nome = (
                    perfil.get("name")
                    or perfil.get("Nome")
                    or "Cliente"
                )

        # --------------------------------------------------
        # TEXTO NORMAL
        # --------------------------------------------------
        if msg.get("type") == "text" or msg.get("tipo") == "texto":
            texto = (
                msg.get("text", {}).get("body")
                or msg.get("texto", {}).get("corpo")
                or ""
            )
            responder_oficina(numero, texto, nome)
            return "OK", 200

        # --------------------------------------------------
        # BOTÕES
        # --------------------------------------------------
        if msg.get("type") == "interactive" or msg.get("tipo") == "interactive":
            interactive = msg.get("interactive", {})
            botao = (
                interactive.get("button_reply")
                or interactive.get("botao_resposta")
                or {}
            )
            botao_id = botao.get("id")
            responder_oficina(numero, botao_id, nome)
            return "OK", 200

        return "OK", 200

    except Exception as e:
        print("❌ ERRO NO WEBHOOK:", e)
        return "ERR", 500
