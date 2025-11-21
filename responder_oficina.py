# ============================================
# responder_oficina.py — NOVA ESTRUTURA 2025
# Coleta completa → timeout 30s → resumo → salvar
# ============================================

import requests
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

# =========================
# VARIÁVEIS DE AMBIENTE
# =========================

WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

# =========================
# CONTROLE DE USUÁRIOS
# =========================

usuarios = {}  # memória ram

TIMEOUT_SEGUNDOS = 30   # reinicia se ficar parado > 30s

def obter_usuario(fone):
    """Cria ou retorna sessão do usuário."""
    agora = datetime.now()

    if fone not in usuarios:
        usuarios[fone] = {
            "estado": "inicio",
            "dados": {},
            "ultima_interacao": agora
        }
        return usuarios[fone]

    # Checar timeout
    if (agora - usuarios[fone]["ultima_interacao"]) > timedelta(seconds=TIMEOUT_SEGUNDOS):
        usuarios[fone] = {
            "estado": "inicio",
            "dados": {},
            "ultima_interacao": agora
        }

    usuarios[fone]["ultima_interacao"] = agora
    return usuarios[fone]

# =========================
# FUNÇÕES WHATSAPP
# =========================

def enviar_whatsapp(fone, mensagem):
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": fone,
        "type": "text",
        "text": {"body": mensagem}
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    requests.post(url, headers=headers, data=json.dumps(payload))

def enviar_botoes(fone, texto, botoes):
    """Enviar botões interativos."""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

    botoes_formatados = []
    for b in botoes:
        botoes_formatados.append({
            "type": "reply",
            "reply": {"id": b["id"], "title": b["title"]}
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": fone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": botoes_formatados}
        }
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    requests.post(url, headers=headers, data=json.dumps(payload))
# ============================================
# PRIMEIRA ETAPA — DADOS DO CLIENTE
# Nome → CPF → Nascimento
# ============================================

def processar_nome(fone, msg, u):
    u["dados"]["nome"] = msg.strip()
    u["estado"] = "cpf"
    enviar_whatsapp(
        fone,
        "Ótimo! 🙌\nAgora digite seu *CPF* no formato:\n👉 123.456.789-00"
    )

def processar_cpf(fone, msg, u):
    u["dados"]["cpf"] = msg.strip()
    u["estado"] = "nascimento"
    enviar_whatsapp(
        fone,
        "Perfeito! 👍\nAgora digite sua *data de nascimento* no formato:\n👉 17/02/1975"
    )

def processar_nascimento(fone, msg, u):
    u["dados"]["nascimento"] = msg.strip()
    u["estado"] = "tipo_veiculo"

    enviar_botoes(
        fone,
        "Escolha o tipo de veículo:",
        [
            {"id": "tv_passeio", "title": "Passeio"},
            {"id": "tv_utilitario", "title": "Utilitário"}
        ]
    )
# ============================================
# VEÍCULO
# ============================================

def processar_tipo_veiculo(fone, escolha, u):
    if escolha == "tv_passeio":
        u["dados"]["tipo_veiculo"] = "Passeio"
    else:
        u["dados"]["tipo_veiculo"] = "Utilitário"

    u["estado"] = "marca_modelo"
    enviar_whatsapp(
        fone,
        "Informe a *marca/modelo* no formato:\n👉 vw / amarok"
    )

def processar_marca_modelo(fone, msg, u):
    u["dados"]["marca_modelo"] = msg.strip()
    u["estado"] = "ano_modelo"
    enviar_whatsapp(
        fone,
        "Digite o *ano fab/mod* no formato:\n👉 20/21"
    )

def processar_ano_modelo(fone, msg, u):
    u["dados"]["ano_modelo"] = msg.strip()
    u["estado"] = "km"
    enviar_whatsapp(
        fone,
        "Digite a *km atual* do veículo:"
    )

def processar_km(fone, msg, u):
    u["dados"]["km"] = msg.strip()
    u["estado"] = "combustivel"
    enviar_botoes(
        fone,
        "Qual o combustível?",
        [
            {"id": "c_gasolina", "title": "Gasolina"},
            {"id": "c_alcool", "title": "Álcool"},
            {"id": "c_flex", "title": "Flex"},
            {"id": "c_diesel", "title": "Diesel S10"}
        ]
    )

def processar_combustivel(fone, escolha, u):
    mapa = {
        "c_gasolina": "Gasolina",
        "c_alcool": "Álcool",
        "c_flex": "Flex (Gasolina/Álcool)",
        "c_diesel": "Diesel S10"
    }
    u["dados"]["combustivel"] = mapa.get(escolha, "")
    u["estado"] = "cep"

    enviar_whatsapp(
        fone,
        "Digite o *CEP* no formato:\n👉 08070-001"
    )

def processar_cep(fone, msg, u):
    u["dados"]["cep"] = msg.strip()
    u["estado"] = "numero"
    enviar_whatsapp(
        fone,
        "Digite o *número* da residência:"
    )

def processar_numero(fone, msg, u):
    u["dados"]["numero"] = msg.strip()
    u["estado"] = "complemento"

    enviar_botoes(
        fone,
        "Possui complemento?",
        [
            {"id": "comp_sim", "title": "Sim"},
            {"id": "comp_nao", "title": "Não"}
        ]
    )

def processar_complemento(fone, escolha, msg, u):
    if escolha == "comp_nao":
        u["dados"]["complemento"] = ""
    else:
        u["dados"]["complemento"] = msg.strip()

    u["estado"] = "escolha_atendimento"
    enviar_botoes(
        fone,
        "Você procura por:",
        [
            {"id": "at_servicos", "title": "Serviços"},
            {"id": "at_pecas", "title": "Peças"},
            {"id": "at_mais", "title": "Mais opções"}
        ]
    )

# ============================================
# SERVIÇOS / PEÇAS / PÓS-VENDA / RETORNO
# ============================================

def processar_atendimento(fone, escolha, u):
    if escolha == "at_servicos":
        u["dados"]["tipo_registro"] = "Serviço"
        u["estado"] = "descricao_servico"
        enviar_whatsapp(fone, "Descreva o *serviço desejado* em poucas palavras:")

    elif escolha == "at_pecas":
        u["dados"]["tipo_registro"] = "Peças"
        u["estado"] = "descricao_peca"
        enviar_whatsapp(fone, "Descreva a *peça desejada*:")

    elif escolha == "at_mais":
        u["estado"] = "submenu"
        enviar_botoes(
            fone,
            "Mais opções:",
            [
                {"id": "mo_posvenda", "title": "Pós-venda"},
                {"id": "mo_retorno", "title": "Retorno"},
                {"id": "mo_voltar", "title": "Voltar"}
            ]
        )

def processar_servico(fone, msg, u):
    u["dados"]["descricao_problema"] = msg.strip()
    u["estado"] = "confirmar"
    enviar_resumo(fone, u)

def processar_peca(fone, msg, u):
    u["dados"]["descricao_peca"] = msg.strip()
    u["estado"] = "confirmar"
    enviar_resumo(fone, u)
# ============================================
# RESUMO FINAL
# ============================================

def enviar_resumo(fone, u):
    d = u["dados"]
    texto = (
        "Confira seus dados:\n\n"
        f"Nome: {d.get('nome')}\n"
        f"CPF: {d.get('cpf')}\n"
        f"Nascimento: {d.get('nascimento')}\n"
        f"Veículo: {d.get('tipo_veiculo')} - {d.get('marca_modelo')} ({d.get('ano_modelo')})\n"
        f"KM: {d.get('km')}\n"
        f"Combustível: {d.get('combustivel')}\n"
        f"CEP: {d.get('cep')}, Nº {d.get('numero')} {d.get('complemento')}\n"
    )

    if "descricao_problema" in d:
        texto += f"\nServiço: {d.get('descricao_problema')}\n"
    if "descricao_peca" in d:
        texto += f"\nPeça: {d.get('descricao_peca')}\n"

    enviar_botoes(
        fone,
        texto + "\nConfirmar os dados?",
        [
            {"id": "confirma", "title": "Confirmar"},
            {"id": "editar", "title": "Editar"}
        ]
    )

# ============================================
# SALVAR NO GOOGLE SHEETS
# ============================================

def salvar_google(u):
    dados = u["dados"].copy()
    dados["data_hora"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dados["secret"] = SECRET_KEY

    requests.post(GOOGLE_SHEETS_URL, data=dados)

# ============================================
# ROTEADOR GERAL
# ============================================

def responder_oficina(fone, msg, tipo_botao=None):
    u = obter_usuario(fone)

    est = u["estado"]

    # BOTÕES
    if tipo_botao:
        if est == "tipo_veiculo":
            return processar_tipo_veiculo(fone, tipo_botao, u)
        if est == "combustivel":
            return processar_combustivel(fone, tipo_botao, u)
        if est == "complemento":
            return processar_complemento(fone, tipo_botao, "", u)
        if est == "escolha_atendimento":
            return processar_atendimento(fone, tipo_botao, u)
        if est == "submenu":
            if tipo_botao == "mo_voltar":
                u["estado"] = "escolha_atendimento"
                return enviar_botoes(
                    fone,
                    "Você procura por:",
                    [
                        {"id": "at_servicos", "title": "Serviços"},
                        {"id": "at_pecas", "title": "Peças"},
                        {"id": "at_mais", "title": "Mais opções"},
                    ]
                )
        if tipo_botao == "confirma":
            salvar_google(u)
            enviar_whatsapp(fone, "Perfeito, seus dados foram enviados! ✔️\nA equipe entrará em contato.")
            u["estado"] = "inicio"
            u["dados"] = {}
            return

        if tipo_botao == "editar":
            u["estado"] = "inicio"
            u["dados"] = {}
            return enviar_whatsapp(fone, "Ok! Vamos começar novamente.\nDigite seu nome:")

    # TEXTO LIVRE
    if est == "inicio":
        u["estado"] = "nome"
        return enviar_whatsapp(fone, "Vamos começar! Digite seu nome completo:")

    if est == "nome":
        return processar_nome(fone, msg, u)

    if est == "cpf":
        return processar_cpf(fone, msg, u)

    if est == "nascimento":
        return processar_nascimento(fone, msg, u)

    if est == "marca_modelo":
        return processar_marca_modelo(fone, msg, u)

    if est == "ano_modelo":
        return processar_ano_modelo(fone, msg, u)

    if est == "km":
        return processar_km(fone, msg, u)

    if est == "cep":
        return processar_cep(fone, msg, u)

    if est == "numero":
        return processar_numero(fone, msg, u)

    if est == "complemento":
        return processar_complemento(fone, "", msg, u)

    if est == "descricao_servico":
        return processar_servico(fone, msg, u)

    if est == "descricao_peca":
        return processar_peca(fone, msg, u)
