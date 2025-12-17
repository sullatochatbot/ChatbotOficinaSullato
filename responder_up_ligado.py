# ============================================================
# RESPONDER UP LIGADO
# Baseado no motor da Oficina Sullato
# Fluxo por blocos • Confirmar / Editar • Sem Google Sheets (por enquanto)
# Inclui: Dados Pessoais • Endereço Residencial • Contatos • Empresa • Veículo
# ============================================================

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# VARIÁVEIS WHATSAPP
# ============================================================

WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")
WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN")

WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}"

TIMEOUT_SESSAO = 60 * 60  # 60 minutos
SESSOES = {}

# ============================================================
# FUNÇÕES DE ENVIO
# ============================================================

def enviar_texto(numero, texto):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "text": {"body": texto}
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)


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
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)


def enviar_template(numero, nome_template):
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nome_template,
            "language": {"code": "pt_BR"}
        }
    }
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)

# ============================================================
# CONTROLE DE SESSÃO
# ============================================================

def iniciar_sessao(numero, nome_whatsapp):
    SESSOES[numero] = {
        "inicio": time.time(),
        "etapa": "inicio",
        "dados": {
            "fone": numero,
            "nome_whatsapp": nome_whatsapp
        },
        "blocos_confirmados": set()
    }
    enviar_template(numero, "up_ligado_inicio")


def resetar_sessao(numero):
    if numero in SESSOES:
        del SESSOES[numero]

# ============================================================
# RESUMOS POR BLOCO
# ============================================================

def resumo_pessoal(d):
    return (
        "📄 *Dados Pessoais*\n"
        f"Nome: {d.get('nome','')}\n"
        f"CPF: {d.get('cpf','')}\n"
        f"Nascimento: {d.get('nascimento','')}\n"
        f"CNH: {d.get('cnh','')}\n"
        f"Validade CNH: {d.get('cnh_validade','')}"
    )


def resumo_endereco(d):
    return (
        "📍 *Endereço Residencial*\n"
        f"CEP: {d.get('cep','')}\n"
        f"Número: {d.get('numero','')}\n"
        f"Complemento: {d.get('complemento','')}"
    )


def resumo_contato(d):
    return (
        "📞 *Contato*\n"
        f"Telefone: {d.get('telefone','')}\n"
        f"WhatsApp: {d.get('whatsapp','')}\n"
        f"E-mail: {d.get('email','')}"
    )


def resumo_empresa(d):
    return (
        "🏢 *Empresa*\n"
        f"Empresa: {d.get('empresa_nome','')}\n"
        f"CNPJ: {d.get('cnpj','')}\n"
        f"Responsável: {d.get('empresa_responsavel','')}"
    )


def resumo_veiculo(d):
    return (
        "🚐 *Veículo*\n"
        f"Placa: {d.get('placa','')}\n"
        f"Marca/Modelo: {d.get('marca_modelo','')}\n"
        f"Ano Fab/Mod: {d.get('ano_fab_mod','')}\n"
        f"Renavam: {d.get('renavam','')}\n"
        f"Chassi: {d.get('chassi','')}"
    )

# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def responder_up_ligado(numero, texto_recebido, nome_whatsapp):
    texto = texto_recebido.strip()
    texto_lower = texto.lower()
    agora = time.time()

    if numero not in SESSOES:
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao = SESSOES[numero]

    if agora - sessao["inicio"] > TIMEOUT_SESSAO:
        enviar_texto(numero, "⏰ Sua sessão expirou. Vamos recomeçar.")
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao["inicio"] = agora
    etapa = sessao["etapa"]
    d = sessao["dados"]

    # ========================================================
    # INÍCIO — ASSOCIADO?
    # ========================================================

    if etapa == "inicio":
        if texto_lower in ["sim", "cad_sim"]:
            sessao["etapa"] = "cpf_existente"
            enviar_texto(numero, "Informe seu *CPF*:")
            return

        if texto_lower in ["não", "nao", "cad_nao"]:
            enviar_template(numero, "up_ligado_aviso_cadastro")
            sessao["etapa"] = "aguardando_inicio"
            return
        return

    if etapa == "aguardando_inicio":
        if texto_lower in ["iniciar", "iniciar_cadastro"]:
            sessao["etapa"] = "nome"
            enviar_texto(numero, "Digite seu *nome completo*:")
            return
        return

    # ========================================================
    # BLOCO 1 — DADOS PESSOAIS
    # ========================================================

    if etapa == "nome":
        d["nome"] = texto
        sessao["etapa"] = "cpf"
        enviar_texto(numero, "Informe seu *CPF*:")
        return

    if etapa == "cpf":
        d["cpf"] = texto
        sessao["etapa"] = "nascimento"
        enviar_texto(numero, "Informe sua *data de nascimento*:")
        return

    if etapa == "nascimento":
        d["nascimento"] = texto
        sessao["etapa"] = "cnh"
        enviar_texto(numero, "Informe o *número da CNH*:")
        return

    if etapa == "cnh":
        d["cnh"] = texto
        sessao["etapa"] = "cnh_validade"
        enviar_texto(numero, "Informe a *validade da CNH*:")
        return

    if etapa == "cnh_validade":
        d["cnh_validade"] = texto
        enviar_botoes(
            numero,
            resumo_pessoal(d) + "\n\nConfirma este bloco?",
            [
                {"id": "confirma_pessoal", "title": "Confirmar"},
                {"id": "editar_pessoal", "title": "Editar"}
            ]
        )
        sessao["etapa"] = "confirma_pessoal"
        return

    if etapa == "confirma_pessoal":
        if texto_lower.startswith("confirma"):
            sessao["etapa"] = "cep"
            enviar_texto(numero, "Informe o *CEP*:")
            return
        if texto_lower.startswith("editar"):
            sessao["etapa"] = "nome"
            enviar_texto(numero, "Digite novamente seu *nome completo*:")
            return

    # ========================================================
    # BLOCO 2 — ENDEREÇO RESIDENCIAL
    # ========================================================

    if etapa == "cep":
        d["cep"] = texto
        sessao["etapa"] = "numero_endereco"
        enviar_texto(numero, "Informe o *número* do endereço:")
        return

    if etapa == "numero_endereco":
        d["numero"] = texto
        sessao["etapa"] = "complemento"
        enviar_texto(numero, "Informe o *complemento* ou digite 'não':")
        return

    if etapa == "complemento":
        d["complemento"] = "" if texto_lower in ["não", "nao"] else texto
        enviar_botoes(
            numero,
            resumo_endereco(d) + "\n\nConfirma este bloco?",
            [
                {"id": "confirma_endereco", "title": "Confirmar"},
                {"id": "editar_endereco", "title": "Editar"}
            ]
        )
        sessao["etapa"] = "confirma_endereco"
        return

    if etapa == "confirma_endereco":
        if texto_lower.startswith("confirma"):
            sessao["etapa"] = "telefone"
            enviar_texto(numero, "Informe seu *telefone*:")
            return
        if texto_lower.startswith("editar"):
            sessao["etapa"] = "cep"
            enviar_texto(numero, "Informe novamente o *CEP*:")
            return

    # ========================================================
    # BLOCO 3 — CONTATO
    # ========================================================

    if etapa == "telefone":
        d["telefone"] = texto
        sessao["etapa"] = "whatsapp"
        enviar_texto(numero, "Informe seu *WhatsApp*:")
        return

    if etapa == "whatsapp":
        d["whatsapp"] = texto
        sessao["etapa"] = "email"
        enviar_texto(numero, "Informe seu *e-mail*:")
        return

    if etapa == "email":
        d["email"] = texto
        enviar_botoes(
            numero,
            resumo_contato(d) + "\n\nConfirma este bloco?",
            [
                {"id": "confirma_contato", "title": "Confirmar"},
                {"id": "editar_contato", "title": "Editar"}
            ]
        )
        sessao["etapa"] = "confirma_contato"
        return

    if etapa == "confirma_contato":
        if texto_lower.startswith("confirma"):
            sessao["etapa"] = "empresa_nome"
            enviar_texto(numero, "Informe o *nome da empresa* ou digite 'não possui':")
            return
        if texto_lower.startswith("editar"):
            sessao["etapa"] = "telefone"
            enviar_texto(numero, "Informe novamente o *telefone*:")
            return

    # ========================================================
    # BLOCO 4 — EMPRESA
    # ========================================================

    if etapa == "empresa_nome":
        if texto_lower in ["não", "nao", "não possui"]:
            d["empresa_nome"] = ""
            sessao["etapa"] = "placa"
            enviar_texto(numero, "Informe a *placa do veículo*:")
            return
        d["empresa_nome"] = texto
        sessao["etapa"] = "cnpj"
        enviar_texto(numero, "Informe o *CNPJ*:")
        return

    if etapa == "cnpj":
        d["cnpj"] = texto
        sessao["etapa"] = "empresa_responsavel"
        enviar_texto(numero, "Informe o *nome do responsável*:")
        return

    if etapa == "empresa_responsavel":
        d["empresa_responsavel"] = texto
        enviar_botoes(
            numero,
            resumo_empresa(d) + "\n\nConfirma este bloco?",
            [
                {"id": "confirma_empresa", "title": "Confirmar"},
                {"id": "editar_empresa", "title": "Editar"}
            ]
        )
        sessao["etapa"] = "confirma_empresa"
        return

    if etapa == "confirma_empresa":
        if texto_lower.startswith("confirma"):
            sessao["etapa"] = "placa"
            enviar_texto(numero, "Informe a *placa do veículo*:")
            return
        if texto_lower.startswith("editar"):
            sessao["etapa"] = "empresa_nome"
            enviar_texto(numero, "Informe novamente o *nome da empresa*:")
            return

    # ========================================================
    # BLOCO 5 — VEÍCULO
    # ========================================================

    if etapa == "placa":
        d["placa"] = texto
        sessao["etapa"] = "marca_modelo"
        enviar_texto(numero, "Informe *marca / modelo*:")
        return

    if etapa == "marca_modelo":
        d["marca_modelo"] = texto
        sessao["etapa"] = "ano_fab_mod"
        enviar_texto(numero, "Informe o *ano fabricação / modelo*:")
        return

    if etapa == "ano_fab_mod":
        d["ano_fab_mod"] = texto
        sessao["etapa"] = "renavam"
        enviar_texto(numero, "Informe o *RENAVAM*:")
        return

    if etapa == "renavam":
        d["renavam"] = texto
        sessao["etapa"] = "chassi"
        enviar_texto(numero, "Informe o *número do chassi*:")
        return

    if etapa == "chassi":
        d["chassi"] = texto
        enviar_botoes(
            numero,
            resumo_veiculo(d) + "\n\nConfirma este bloco?",
            [
                {"id": "confirma_veiculo", "title": "Confirmar"},
                {"id": "editar_veiculo", "title": "Editar"}
            ]
        )
        sessao["etapa"] = "confirma_veiculo"
        return

    if etapa == "confirma_veiculo":
        if texto_lower.startswith("confirma"):
            enviar_botoes(
                numero,
                "Deseja *confirmar e finalizar* seu cadastro?",
                [
                    {"id": "final_confirmar", "title": "Confirmar cadastro"},
                    {"id": "final_editar", "title": "Editar algum bloco"}
                ]
            )
            sessao["etapa"] = "final"
            return
        if texto_lower.startswith("editar"):
            sessao["etapa"] = "placa"
            enviar_texto(numero, "Informe novamente a *placa*:")
            return

    # ========================================================
    # FINALIZAÇÃO
    # ========================================================

    if etapa == "final":
        if texto_lower == "final_confirmar":
            enviar_template(numero, "up_ligado_cadastro_concluido")
            resetar_sessao(numero)
            return
