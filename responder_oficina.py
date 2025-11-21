# ============================================================
# responder_oficina.py — NOVA ESTRUTURA PROFISSIONAL
# Coleta completa de dados → escolha do atendimento → resumo → salvar
# ============================================================

import requests
import json
import os
from datetime import datetime
from urllib.parse import urlencode

# ---------------------------------------------
# Configurações (pegas do .env)
# ---------------------------------------------
WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

# ---------------------------------------------
# Função base para enviar mensagens pelo WhatsApp API
# ---------------------------------------------
def enviar_whatsapp(numero, mensagem):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": mensagem}
    }
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print("Erro ao enviar mensagem:", e)

# ---------------------------------------------
# Função para enviar botões
# ---------------------------------------------
def enviar_botoes(numero, texto, botoes):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    components = []

    for b in botoes:
        components.append({
            "type": "button",
            "button": {
                "type": "reply",
                "reply": {"id": b["id"], "title": b["title"]}
            }
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": components}
        }
    }

    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print("Erro ao enviar botões:", e)

# ---------------------------------------------
# Estados do fluxo
# ---------------------------------------------
ESTADOS = {
    "INICIO": "inicio",
    "NOME": "nome",
    "CPF": "cpf",
    "NASCIMENTO": "nascimento",
    "TIPO_VEICULO": "tipo_veiculo",
    "MARCA_MODELO": "marca_modelo",
    "ANO_MODELO": "ano_modelo",
    "KM": "km",
    "COMBUSTIVEL": "combustivel",
    "CEP": "cep",
    "NUMERO": "numero",
    "COMPLEMENTO": "complemento",

    # Escolha do atendimento
    "MENU_ATENDIMENTO": "menu_atendimento",

    # Fluxo — Serviços
    "SERVICO_DESCRICAO": "servico_descricao",

    # Fluxo — Peças
    "PECA_DESCRICAO": "peca_descricao",

    # Fluxo — Pós-venda
    "POSVENDA_DATA": "posvenda_data",
    "POSVENDA_PROBLEMA": "posvenda_problema",

    # Fluxo — Retorno
    "RETORNO_DATA": "retorno_data",
    "RETORNO_OS": "retorno_os",
    "RETORNO_PROBLEMA": "retorno_problema",

    # Finalização
    "CONFIRMACAO": "confirmacao"
}

# ---------------------------------------------
# Memória temporária para cada usuário 👇
# ---------------------------------------------
usuarios = {}

def obter_usuario(numero):
    if numero not in usuarios:
        usuarios[numero] = {
            "estado": ESTADOS["INICIO"],
            "dados": {}
        }
    return usuarios[numero]
# ============================================================
# PARTE 2 — Fluxo de perguntas iniciais (dados pessoais + veículo + endereço)
# ============================================================

def processar_mensagem_oficina(numero, texto):
    user = obter_usuario(numero)
    estado = user["estado"]
    dados = user["dados"]

    texto = texto.strip()

    # ---------------------------------------------------------
    # ESTADO: INICIO
    # ---------------------------------------------------------
    if estado == ESTADOS["INICIO"]:
        enviar_whatsapp(numero,
            "Olá! 😊\n\n"
            "Sou o assistente da *Sullato Oficina* e vou agilizar o seu atendimento.\n"
            "Vamos começar com alguns dados importantes.\n\n"
            "👉 *Qual o seu nome completo?*"
        )
        user["estado"] = ESTADOS["NOME"]
        return

    # ---------------------------------------------------------
    # ESTADO: NOME
    # ---------------------------------------------------------
    if estado == ESTADOS["NOME"]:
        dados["nome"] = texto
        enviar_whatsapp(numero,
            "Perfeito! 👍\n\n"
            "Agora digite seu *CPF* no formato:\n"
            "👉 123.456.789-00"
        )
        user["estado"] = ESTADOS["CPF"]
        return

    # ---------------------------------------------------------
    # ESTADO: CPF
    # ---------------------------------------------------------
    if estado == ESTADOS["CPF"]:
        dados["cpf"] = texto
        enviar_whatsapp(numero,
            "Ótimo! 🙌\n\n"
            "Digite agora sua *data de nascimento* no formato:\n"
            "👉 17/02/1975"
        )
        user["estado"] = ESTADOS["NASCIMENTO"]
        return

    # ---------------------------------------------------------
    # ESTADO: NASCIMENTO
    # ---------------------------------------------------------
    if estado == ESTADOS["NASCIMENTO"]:
        dados["nascimento"] = texto

        enviar_botoes(
            numero,
            "Qual o *tipo do veículo*?",
            [
                {"id": "tipo_passeio", "title": "Passeio"},
                {"id": "tipo_utilitario", "title": "Utilitário"}
            ]
        )
        user["estado"] = ESTADOS["TIPO_VEICULO"]
        return

    # ---------------------------------------------------------
    # ESTADO: TIPO VEÍCULO
    # ---------------------------------------------------------
    if estado == ESTADOS["TIPO_VEICULO"]:
        if texto == "tipo_passeio":
            dados["tipo_veiculo"] = "Passeio"
        elif texto == "tipo_utilitario":
            dados["tipo_veiculo"] = "Utilitário"
        else:
            enviar_whatsapp(numero, "Escolha uma das opções acima.")
            return

        enviar_whatsapp(numero,
            "Certo! Agora digite a *marca e modelo* do veículo no formato:\n"
            "👉 VW / Amarok"
        )
        user["estado"] = ESTADOS["MARCA_MODELO"]
        return

    # ---------------------------------------------------------
    # ESTADO: MARCA / MODELO
    # ---------------------------------------------------------
    if estado == ESTADOS["MARCA_MODELO"]:
        dados["marca_modelo"] = texto
        enviar_whatsapp(numero,
            "Ótimo! Agora informe o *ano de fabricação/modelo* no formato:\n"
            "👉 20/21"
        )
        user["estado"] = ESTADOS["ANO_MODELO"]
        return

    # ---------------------------------------------------------
    # ESTADO: ANO MODELO
    # ---------------------------------------------------------
    if estado == ESTADOS["ANO_MODELO"]:
        dados["ano_modelo"] = texto
        enviar_whatsapp(numero,
            "Perfeito! Digite agora a *quilometragem (KM)* do veículo:\n"
            "👉 Exemplo: 85.000"
        )
        user["estado"] = ESTADOS["KM"]
        return

    # ---------------------------------------------------------
    # ESTADO: KM
    # ---------------------------------------------------------
    if estado == ESTADOS["KM"]:
        dados["km"] = texto

        enviar_botoes(
            numero,
            "Qual o *combustível* do veículo?",
            [
                {"id": "c_gasolina", "title": "Gasolina"},
                {"id": "c_alcool", "title": "Álcool"},
                {"id": "c_flex", "title": "Flex"},
                {"id": "c_diesel", "title": "Diesel S10"}
            ]
        )
        user["estado"] = ESTADOS["COMBUSTIVEL"]
        return

    # ---------------------------------------------------------
    # ESTADO: COMBUSTÍVEL
    # ---------------------------------------------------------
    if estado == ESTADOS["COMBUSTIVEL"]:
        combustiveis = {
            "c_gasolina": "Gasolina",
            "c_alcool": "Álcool",
            "c_flex": "Flex (Gasolina/Álcool)",
            "c_diesel": "Diesel S10"
        }

        if texto not in combustiveis:
            enviar_whatsapp(numero, "Escolha uma opção válida.")
            return

        dados["combustivel"] = combustiveis[texto]

        enviar_whatsapp(numero,
            "Agora digite o *CEP* no formato:\n"
            "👉 08070-001"
        )
        user["estado"] = ESTADOS["CEP"]
        return

    # ---------------------------------------------------------
    # ESTADO: CEP
    # ---------------------------------------------------------
    if estado == ESTADOS["CEP"]:
        dados["cep"] = texto

        # Busca automática de endereço
        try:
            via_url = f"https://viacep.com.br/ws/{texto.replace('-', '')}/json/"
            r = requests.get(via_url).json()

            dados["logradouro"] = r.get("logradouro", "")
            dados["bairro"] = r.get("bairro", "")
            dados["cidade"] = r.get("localidade", "")
            dados["uf"] = r.get("uf", "")

        except:
            dados["logradouro"] = ""
            dados["bairro"] = ""
            dados["cidade"] = ""
            dados["uf"] = ""

        enviar_whatsapp(numero, "Digite agora o *número* da residência:")
        user["estado"] = ESTADOS["NUMERO"]
        return

    # ---------------------------------------------------------
    # ESTADO: NÚMERO
    # ---------------------------------------------------------
    if estado == ESTADOS["NUMERO"]:
        dados["numero"] = texto

        enviar_botoes(
            numero,
            "Possui *complemento*?",
            [
                {"id": "comp_sim", "title": "Sim"},
                {"id": "comp_nao", "title": "Não"}
            ]
        )
        user["estado"] = ESTADOS["COMPLEMENTO"]
        return

    # ---------------------------------------------------------
    # ESTADO: COMPLEMENTO
    # ---------------------------------------------------------
    if estado == ESTADOS["COMPLEMENTO"]:
        if texto == "comp_sim":
            dados["complemento"] = "Sim"
        elif texto == "comp_nao":
            dados["complemento"] = "Não"
        else:
            enviar_whatsapp(numero, "Escolha uma opção válida.")
            return

        # APÓS COMPLETAR TODOS OS DADOS → MENU DE SERVIÇOS
        enviar_botoes(
            numero,
            "*Como podemos ajudar hoje?*",
            [
                {"id": "menu_servico", "title": "Serviços"},
                {"id": "menu_peca", "title": "Peças"},
                {"id": "menu_posvenda", "title": "Pós-venda"},
                {"id": "menu_retorno", "title": "Retorno"},
                {"id": "menu_mais", "title": "Mais opções"}
            ]
        )
        user["estado"] = ESTADOS["MENU_ATENDIMENTO"]
        return
# ============================================================
# PARTE 3 — Fluxo de Serviços, Peças, Pós-venda, Retorno e Resumo
# ============================================================

def montar_resumo(dados):
    """Gera o texto final de confirmação com todos os dados coletados."""

    resumo = (
        "📄 *Resumo do atendimento*\n\n"
        f"👤 *Cliente:* {dados.get('nome')}\n"
        f"CPF: {dados.get('cpf')}\n"
        f"Nascimento: {dados.get('nascimento')}\n\n"

        f"🚗 *Veículo*: {dados.get('tipo_veiculo')}\n"
        f"Modelo: {dados.get('marca_modelo')}\n"
        f"Ano: {dados.get('ano_modelo')}\n"
        f"KM: {dados.get('km')}\n"
        f"Combustível: {dados.get('combustivel')}\n\n"

        f"📍 *Endereço:*\n"
        f"CEP: {dados.get('cep')}\n"
        f"Logradouro: {dados.get('logradouro')}\n"
        f"Nº: {dados.get('numero')}\n"
        f"Complemento: {dados.get('complemento')}\n"
        f"Bairro: {dados.get('bairro')}\n"
        f"Cidade/UF: {dados.get('cidade')} - {dados.get('uf')}\n\n"
    )

    # Dados específicos do atendimento
    if dados.get("tipo_registro") == "servico":
        resumo += f"🔧 *Serviço solicitado:* {dados.get('descricao_servico')}\n"

    elif dados.get("tipo_registro") == "peca":
        resumo += f"🧩 *Peça solicitada:* {dados.get('descricao_peca')}\n"

    elif dados.get("tipo_registro") == "posvenda":
        resumo += (
            f"📦 *Pós-venda:*\n"
            f"Data da compra: {dados.get('data_compra')}\n"
            f"Problema relatado: {dados.get('problema_posvenda')}\n"
        )

    elif dados.get("tipo_registro") == "retorno":
        resumo += (
            f"🔁 *Retorno:*\n"
            f"Data do serviço anterior: {dados.get('retorno_data')}\n"
            f"OS: {dados.get('retorno_os')}\n"
            f"Problema relatado: {dados.get('retorno_problema')}\n"
        )

    resumo += "\nConfirma os dados acima?"

    return resumo


# ============================================================
# MENU ATENDIMENTO
# ============================================================

def processar_menu_atendimento(numero, texto, user):
    dados = user["dados"]

    if texto == "menu_servico":
        dados["tipo_registro"] = "servico"
        enviar_whatsapp(
            numero,
            "Descreva em poucas palavras o *serviço* que você precisa:\n"
            "Exemplo: 'barulho na suspensão', 'troca de óleo', etc."
        )
        user["estado"] = ESTADOS["SERVICO_DESCRICAO"]
        return

    if texto == "menu_peca":
        dados["tipo_registro"] = "peca"
        enviar_whatsapp(
            numero,
            "Qual *peça* você está procurando?\n"
            "Exemplo: amortecedor, pastilha, filtro, etc."
        )
        user["estado"] = ESTADOS["PECA_DESCRICAO"]
        return

    if texto == "menu_posvenda":
        dados["tipo_registro"] = "posvenda"
        enviar_whatsapp(numero, "Qual a *data da compra* do veículo?\nExemplo: 12/03/2024")
        user["estado"] = ESTADOS["POSVENDA_DATA"]
        return

    if texto == "menu_retorno":
        dados["tipo_registro"] = "retorno"
        enviar_whatsapp(numero, "Qual a *data que o serviço foi realizado*?\nExemplo: 08/11/2025")
        user["estado"] = ESTADOS["RETORNO_DATA"]
        return

    if texto == "menu_mais":
        enviar_whatsapp(
            numero,
            "Endereços e telefones:\n\n"
            "📍 *Loja 1*: Av. São Miguel, 7900 — CEP 08070-001\n"
            "📞 (11) 2030-5081 / (11) 94054-5704\n\n"
            "📍 *Loja 2*: Av. São Miguel, 4049/4084 — CEP 03871-000\n"
            "📞 (11) 2030-5081\n\n"
            "🔧 Oficina Sullato\n"
            "📍 Rua XXXX, 123 — CEP XXXXX-XXX\n"
            "📞 (11) 99999-9999"
        )
        return


# ============================================================
# FLUXO: SERVIÇOS
# ============================================================

def fluxo_servico(numero, texto, user):
    dados = user["dados"]
    dados["descricao_servico"] = texto

    resumo = montar_resumo(dados)
    enviar_botoes(
        numero,
        resumo,
        [
            {"id": "confirmar", "title": "Confirmar"},
            {"id": "editar", "title": "Editar"}
        ]
    )

    user["estado"] = ESTADOS["CONFIRMACAO"]


# ============================================================
# FLUXO: PEÇAS
# ============================================================

def fluxo_pecas(numero, texto, user):
    dados = user["dados"]
    dados["descricao_peca"] = texto

    resumo = montar_resumo(dados)
    enviar_botoes(
        numero,
        resumo,
        [
            {"id": "confirmar", "title": "Confirmar"},
            {"id": "editar", "title": "Editar"}
        ]
    )

    user["estado"] = ESTADOS["CONFIRMACAO"]


# ============================================================
# FLUXO: PÓS-VENDA
# ============================================================

def fluxo_posvenda(numero, texto, user):
    dados = user["dados"]

    # 1ª pergunta: data da compra
    if user["estado"] == ESTADOS["POSVENDA_DATA"]:
        dados["data_compra"] = texto
        enviar_whatsapp(numero, "Descreva o *problema que ocorreu*:")
        user["estado"] = ESTADOS["POSVENDA_PROBLEMA"]
        return

    # 2ª etapa
    if user["estado"] == ESTADOS["POSVENDA_PROBLEMA"]:
        dados["problema_posvenda"] = texto

        resumo = montar_resumo(dados)
        enviar_botoes(
            numero,
            resumo,
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"}
            ]
        )
        user["estado"] = ESTADOS["CONFIRMACAO"]


# ============================================================
# FLUXO: RETORNO
# ============================================================

def fluxo_retorno(numero, texto, user):
    dados = user["dados"]

    # Etapa 1 — data do serviço anterior
    if user["estado"] == ESTADOS["RETORNO_DATA"]:
        dados["retorno_data"] = texto
        enviar_whatsapp(numero, "Qual o *número da OS*?")
        user["estado"] = ESTADOS["RETORNO_OS"]
        return

    # Etapa 2 — número OS
    if user["estado"] == ESTADOS["RETORNO_OS"]:
        dados["retorno_os"] = texto
        enviar_whatsapp(numero, "Descreva o *problema ocorrido*:")
        user["estado"] = ESTADOS["RETORNO_PROBLEMA"]
        return

    # Etapa 3 — descrição
    if user["estado"] == ESTADOS["RETORNO_PROBLEMA"]:
        dados["retorno_problema"] = texto

        resumo = montar_resumo(dados)
        enviar_botoes(
            numero,
            resumo,
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"}
            ]
        )
        user["estado"] = ESTADOS["CONFIRMACAO"]
# ============================================================
# PARTE 4 — Salvar no Google Sheets + Finalização + Roteamento
# ============================================================

def salvar_no_sheets(dados):
    """Envia todos os dados para o Apps Script."""
    payload = {
        "route": "chatbot",
        "secret": SECRET_KEY,
        "dados": dados
    }

    try:
        requests.post(GOOGLE_SHEETS_URL, json=payload)
    except Exception as e:
        print("Erro ao enviar para Sheets:", e)


def finalizar_atendimento(numero, user):
    """Mensagem final + salvar + reset"""

    dados = user["dados"]

    salvar_no_sheets(dados)

    enviar_whatsapp(
        numero,
        "Tudo certo! 🙌\n\n"
        "*Seu atendimento foi registrado com sucesso.*\n"
        "Um técnico da *Sullato Oficina* entrará em contato com você."
    )

    # reset
    user["estado"] = ESTADOS["INICIO"]
    user["dados"] = {}


# ============================================================
# CONFIRMAÇÃO FINAL (confirmar/editar)
# ============================================================

def processar_confirmacao(numero, texto, user):
    if texto == "confirmar":
        finalizar_atendimento(numero, user)
        return

    if texto == "editar":
        # volta do zero
        user["estado"] = ESTADOS["INICIO"]
        user["dados"] = {}

        enviar_whatsapp(
            numero,
            "Ok! Vamos começar novamente.\n\n"
            "👉 *Qual o seu nome completo?*"
        )
        return

    enviar_whatsapp(numero, "Escolha uma opção válida: Confirmar ou Editar.")


# ============================================================
# ROTEADOR PRINCIPAL DO FLUXO (tudo passa por aqui)
# ============================================================

def responder_oficina(numero, texto):
    user = obter_usuario(numero)
    estado = user["estado"]

    # 🔹 Se estamos no MENU_ATENDIMENTO
    if estado == ESTADOS["MENU_ATENDIMENTO"]:
        return processar_menu_atendimento(numero, texto, user)

    # 🔹 Fluxo SERVIÇO
    if estado == ESTADOS["SERVICO_DESCRICAO"]:
        return fluxo_servico(numero, texto, user)

    # 🔹 Fluxo PEÇAS
    if estado == ESTADOS["PECA_DESCRICAO"]:
        return fluxo_pecas(numero, texto, user)

    # 🔹 Fluxo PÓS-VENDA
    if estado in [ESTADOS["POSVENDA_DATA"], ESTADOS["POSVENDA_PROBLEMA"]]:
        return fluxo_posvenda(numero, texto, user)

    # 🔹 Fluxo RETORNO
    if estado in [
        ESTADOS["RETORNO_DATA"],
        ESTADOS["RETORNO_OS"],
        ESTADOS["RETORNO_PROBLEMA"]
    ]:
        return fluxo_retorno(numero, texto, user)

    # 🔹 Confirmação
    if estado == ESTADOS["CONFIRMACAO"]:
        return processar_confirmacao(numero, texto, user)

    # 🔹 Caso contrário → é uma das etapas da PARTE 2
    return processar_mensagem_oficina(numero, texto)
# ============================================================
# ADAPTADOR NOVO → antigo (chamado pelo webhook.py)
# ============================================================

def responder_evento_mensagem(data):
    try:
        change = data["changes"][0]["value"]
        messages = change.get("messages", [])
        contacts = change.get("contacts", [])

        if not messages:
            return

        msg = messages[0]

        # Número do cliente
        numero = contacts[0].get("wa_id") or msg.get("from")

        # Texto digitado OU botão clicado
        if msg.get("type") == "text":
            texto = msg["text"]["body"]

        elif msg.get("type") == "interactive":
            if "button_reply" in msg["interactive"]:
                texto = msg["interactive"]["button_reply"]["id"]
            else:
                texto = ""
        else:
            return

        # Chama o fluxo principal
        responder_oficina(numero, texto)

    except Exception as e:
        print("❌ Erro em responder_evento_mensagem:", e)
