# -*- coding: utf-8 -*-
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")
OFICINA_SHEET_WEBHOOK_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
OFICINA_SHEETS_SECRET = os.getenv("OFICINA_SHEETS_SECRET")

WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{WA_PHONE_NUMBER_ID}"

TIMEOUT_SESSAO = 600
SESSOES = {}

# ============================================================
# ENVIO DE MENSAGENS
# ============================================================

def enviar_texto(numero, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "text": {"body": texto},
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    r = requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)
    print("📤 enviar_texto:", r.status_code, r.text)


def enviar_botoes(numero, texto, botoes):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in botoes
                ]
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    r = requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)
    print("📤 enviar_botoes:", r.status_code, r.text)

# ============================================================
# CONTROLE DE SESSÃO
# ============================================================

def reset_sessao(numero):
    if numero in SESSOES:
        del SESSOES[numero]


def iniciar_sessao(numero, nome_whatsapp):
    SESSOES[numero] = {
        "etapa": "menu_inicial",
        "inicio": time.time(),
        "dados": {
            "fone": numero,
            "nome_whatsapp": nome_whatsapp,
            "origem_cliente": "chatbot oficina",
        },
    }

    enviar_texto(
        numero,
        f"Olá {nome_whatsapp}! 👋\n\n"
        "Vamos iniciar seu atendimento.\n\n"
        "*Escolha uma opção:*\n"
        "1 – Serviços\n"
        "2 – Peças\n"
        "3 – Pós-venda / Garantia\n"
        "4 – Retorno Oficina\n"
        "5 – Endereço e Contato"
    )

# ============================================================
# FLUXO PRINCIPAL (INÍCIO)
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp):
    texto = (texto_digitado or "").strip().lower()
    agora = time.time()

    print("➡️ Texto interpretado:", texto)

    # ========================================================
    # 🚨 REGRA MESTRA — QUALQUER TEXTO INICIA O ATENDIMENTO
    # ========================================================
    if numero not in SESSOES:
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao = SESSOES[numero]

    # ========================================================
    # TIMEOUT
    # ========================================================
    if agora - sessao["inicio"] > TIMEOUT_SESSAO:
        enviar_texto(numero, "Sessão expirada. Vamos recomeçar 😊")
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao["inicio"] = agora
    etapa = sessao["etapa"]
    d = sessao["dados"]
    # ========================================================
    # NORMALIZAÇÃO DE RESPOSTAS
    # ========================================================

    mapa_respostas = {
        "1": "servicos",
        "2": "pecas",
        "3": "pos_venda",
        "4": "retorno_oficina",
        "5": "endereco",

        "sim": "cad_sim",
        "não": "cad_nao",
        "nao": "cad_nao",
        "cad_sim": "cad_sim",
        "cad_nao": "cad_nao",
    }

    if texto in mapa_respostas:
        texto = mapa_respostas[texto]

    # ========================================================
    # MENU INICIAL
    # ========================================================

    if etapa == "menu_inicial":

        if texto in ["servicos", "pecas", "pos_venda", "retorno_oficina"]:
            d["interesse_inicial"] = texto
            sessao["etapa"] = "ja_cadastrado"

            enviar_botoes(
                numero,
                "Você já fez atendimento conosco antes?",
                [
                    {"id": "cad_sim", "title": "Sim"},
                    {"id": "cad_nao", "title": "Não"},
                ],
            )
            return

        if texto == "endereco":
            enviar_texto(
                numero,
                "📍 *Sullato Oficina e Peças*\n\n"
                "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000\n"
                "☎️ (11) 2542-3333\n"
                "👉 https://wa.me/551125423333"
            )
            reset_sessao(numero)
            return

        enviar_texto(numero, "Por favor, escolha uma opção válida (1 a 5).")
        return

    # ========================================================
    # JÁ CADASTRADO
    # ========================================================

    if etapa == "ja_cadastrado":

        if texto == "cad_sim":
            sessao["veio_de"] = "cliente_antigo"
            sessao["etapa"] = "pergunta_cpf"
            enviar_texto(numero, "Digite seu *CPF* (ex: 123.456.789-00):")
            return

        if texto == "cad_nao":
            sessao["veio_de"] = "cliente_novo"
            sessao["etapa"] = "pergunta_nome"
            enviar_texto(numero, "Digite seu *nome completo*:")
            return

        enviar_texto(numero, "Responda usando os botões, por favor 😊")
        return

    # ========================================================
    # PERGUNTA NOME
    # ========================================================

    if etapa == "pergunta_nome":
        d["nome"] = texto.title()
        sessao["etapa"] = "pergunta_cpf"
        enviar_texto(numero, "Agora digite seu *CPF* (ex: 123.456.789-00):")
        return

    # ========================================================
    # PERGUNTA CPF
    # ========================================================

    if etapa == "pergunta_cpf":

        cpf_limpo = texto.replace(".", "").replace("-", "").replace(" ", "")

        if not (cpf_limpo.isdigit() and len(cpf_limpo) == 11):
            enviar_texto(numero, "CPF inválido. Digite no formato 123.456.789-00")
            return

        d["cpf"] = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        sessao["etapa"] = "definir_fluxo"

    # ========================================================
    # DEFINIÇÃO DE FLUXO APÓS CPF
    # ========================================================

    if etapa == "definir_fluxo":

        interesse = d.get("interesse_inicial")

        if interesse == "servicos":
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(numero, "Descreva o serviço desejado:")
            return

        if interesse == "pecas":
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(numero, "Descreva qual peça você procura:")
            return

        if interesse == "pos_venda":
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data"
            enviar_texto(numero, "Informe a data da compra do veículo:")
            return

        if interesse == "retorno_oficina":
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data"
            enviar_texto(numero, "Informe a data do serviço realizado:")
            return
    # ========================================================
    # DESCRIÇÃO – SERVIÇOS
    # ========================================================

    if etapa == "descricao_servico":
        d["descricao"] = texto
        sessao["etapa"] = "confirmacao"
        enviar_botoes(
            numero,
            "Confirma as informações do serviço?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ========================================================
    # DESCRIÇÃO – PEÇAS
    # ========================================================

    if etapa == "descricao_peca":
        d["descricao"] = texto
        sessao["etapa"] = "confirmacao"
        enviar_botoes(
            numero,
            "Confirma as informações da peça?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ========================================================
    # PÓS-VENDA
    # ========================================================

    if etapa == "posvenda_data":
        d["data_compra"] = texto
        sessao["etapa"] = "posvenda_descricao"
        enviar_texto(numero, "Descreva o problema ocorrido:")
        return

    if etapa == "posvenda_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "confirmacao"
        enviar_botoes(
            numero,
            "Confirma as informações do pós-venda?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ========================================================
    # RETORNO OFICINA
    # ========================================================

    if etapa == "retorno_data":
        d["data_servico"] = texto
        sessao["etapa"] = "retorno_descricao"
        enviar_texto(numero, "Descreva o problema encontrado após o serviço:")
        return

    if etapa == "retorno_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "confirmacao"
        enviar_botoes(
            numero,
            "Confirma as informações do retorno?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ],
        )
        return

    # ========================================================
    # CONFIRMAÇÃO FINAL
    # ========================================================

    if etapa == "confirmacao":

        if texto in ["confirmar", "ok", "confirm"]:
            try:
                payload = {
                    "secret": OFICINA_SHEETS_SECRET,
                    "route": "chatbot",
                    "dados": d,
                }
                r = requests.post(
                    OFICINA_SHEET_WEBHOOK_URL,
                    json=payload,
                    timeout=10
                )
                print("📥 Google Sheets:", r.status_code, r.text)
            except Exception as e:
                print("❌ Erro ao salvar:", e)

            enviar_texto(
                numero,
                "✅ Atendimento registrado com sucesso!\n"
                "Um técnico da Sullato entrará em contato em breve."
            )
            reset_sessao(numero)
            return

        if texto == "editar":
            sessao["etapa"] = "menu_inicial"
            enviar_texto(numero, "Sem problemas 😊 Vamos começar novamente.")
            return

        enviar_texto(numero, "Por favor, confirme ou edite usando os botões.")
        return
