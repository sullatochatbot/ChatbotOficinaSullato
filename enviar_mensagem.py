import os
import json
import requests
from dotenv import load_dotenv

# Carrega as variáveis do .env
load_dotenv()

# Dados do WhatsApp Cloud API
ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")

# ============================================================
# ENVIAR TEXTO
# ============================================================
def enviar_texto(telefone, mensagem):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": mensagem},
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload)
    print("📩 Enviar texto →", resposta_log(response))


# ============================================================
# ENVIAR BOTÕES INTERATIVOS
# ============================================================
def enviar_botoes(telefone, texto, botoes):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    botoes_formatados = []
    for btn in botoes:
        botoes_formatados.append(
            {
                "type": "reply",
                "reply": {"id": btn["id"], "title": btn["title"]},
            }
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": botoes_formatados},
        },
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload)
    print("📩 Enviar botões →", resposta_log(response))


# ============================================================
# FUNÇÃO DE LOG SIMPLIFICADA
# ============================================================
def resposta_log(response):
    try:
        return f"{response.status_code} — {response.text}"
    except:
        return str(response)
