import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{os.getenv('WA_PHONE_NUMBER_ID')}"
WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

TIMEOUT_SESSAO = 600
SESSOES = {}

# ============================================================
# ENVIAR TEXTO
# ============================================================

def enviar_texto(numero, texto):
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "text": {"body": texto}
        }
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)
    except Exception as e:
        print("Erro ao enviar texto:", e)

# ============================================================
# ENVIAR BOTÕES
# ============================================================

def enviar_botoes(numero, texto, botoes):
    try:
        botoes_formatados = [{"type": "reply", "reply": {"id": i["id"], "title": i["title"]}}
                             for i in botoes]

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

        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        requests.post(f"{WHATSAPP_API_URL}/messages", json=payload, headers=headers)

    except Exception as e:
        print("Erro ao enviar botões:", e)

# ============================================================
# RESETAR SESSÃO
# ============================================================

def reset_sessao(numero):
    if numero in SESSOES:
        del SESSOES[numero]

# ============================================================
# INICIAR SESSÃO
# ============================================================

def iniciar_sessao(numero, nome_whatsapp):
    SESSOES[numero] = {
        "etapa": "pergunta_nome",
        "inicio": time.time(),
        "dados": {
            "fone": numero,
            "nome_whatsapp": nome_whatsapp
        }
    }

    enviar_texto(
        numero,
        f"Olá {nome_whatsapp}! 👋\n\n"
        "Vamos iniciar seu atendimento.\n"
        "Digite *seu nome completo:*"
    )

# ============================================================
# SALVAR VIA GOOGLE SHEETS
# ============================================================

def salvar_via_webapp(sessao):
    try:
        payload = {
            "secret": SECRET_KEY,
            "route": "chatbot",
            "dados": sessao["dados"],
            "fone": sessao["dados"].get("fone", "")
        }
        headers = {"Content-Type": "application/json"}
        requests.post(GOOGLE_SHEETS_URL, json=payload, headers=headers)
    except Exception as e:
        print("Erro ao enviar dados ao WebApp:", e)

# ============================================================
# RESUMO FINAL
# ============================================================

def construir_resumo(d):
    return (
        "✅ *Resumo do seu atendimento:*\n\n"
        f"*Nome:* {d.get('nome','')}\n"
        f"*CPF:* {d.get('cpf','')}\n"
        f"*Nascimento:* {d.get('nascimento','')}\n"
        f"*Telefone:* {d.get('fone','')}\n\n"

        "🚗 *Veículo*\n"
        f"Tipo: {d.get('tipo_veiculo','')}\n"
        f"Marca/Modelo: {d.get('marca_modelo','')}\n"
        f"Ano Fab/Mod: {d.get('ano_modelo','')}\n"
        f"KM: {d.get('km','')}\n"
        f"Combustível: {d.get('combustivel','')}\n"
        f"Placa: {d.get('placa','')}\n\n"

        "📍 *Endereço*\n"
        f"CEP: {d.get('cep','')}\n"
        f"Número: {d.get('numero','')}\n"
        f"Complemento: {d.get('complemento','')}\n\n"

        "📝 *Atendimento*\n"
        f"Tipo: {d.get('tipo_registro','')}\n"
        f"Descrição: {d.get('descricao','')}\n"
        f"Origem: {d.get('origem','')}\n"
        f"Feedback: {d.get('feedback','')}\n"
    )

# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp):

    texto = texto_digitado.strip()
    agora = time.time()

    # Criar sessão se não existir
    if numero not in SESSOES:
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao = SESSOES[numero]

    # Verificar timeout
    if agora - sessao.get("inicio", 0) > TIMEOUT_SESSAO:
        enviar_texto(numero, "Sessão expirada. Vamos recomeçar!")
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao["inicio"] = agora
    etapa = sessao["etapa"]
    d = sessao["dados"]

    # ================================
    # ETAPAS BÁSICAS — CADASTRO
    # ================================

    if etapa == "pergunta_nome":
        d["nome"] = texto
        sessao["etapa"] = "pergunta_cpf"
        enviar_texto(numero, "Digite *seu CPF*:")
        return

    if etapa == "pergunta_cpf":
        d["cpf"] = texto
        sessao["etapa"] = "pergunta_nascimento"
        enviar_texto(numero, "Digite *sua data de nascimento* (00/00/0000):")
        return

    if etapa == "pergunta_nascimento":
        d["nascimento"] = texto
        sessao["etapa"] = "pergunta_tipo_veiculo"
        enviar_botoes(
            numero, "Qual o tipo de veículo?",
            [
                {"id": "tv_passeio", "title": "Passeio"},
                {"id": "tv_utilitario", "title": "Utilitário"},
            ]
        )
        return

    if etapa == "pergunta_tipo_veiculo":
        if texto in ["Passeio", "tv_passeio"]:
            d["tipo_veiculo"] = "Passeio"
        elif texto in ["Utilitário", "tv_utilitario"]:
            d["tipo_veiculo"] = "Utilitário"
        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

        sessao["etapa"] = "pergunta_marca_modelo"
        enviar_texto(numero, "Digite a *marca/modelo*:")
        return

    if etapa == "pergunta_marca_modelo":
        d["marca_modelo"] = texto
        sessao["etapa"] = "pergunta_ano_modelo"
        enviar_texto(numero, "Digite o *ano fab/mod* (ex: 21/21):")
        return

    if etapa == "pergunta_ano_modelo":
        d["ano_modelo"] = texto
        sessao["etapa"] = "pergunta_km"
        enviar_texto(numero, "Digite o KM atual:")
        return

    if etapa == "pergunta_km":
        d["km"] = texto
        sessao["etapa"] = "pergunta_combustivel"
        enviar_texto(numero, "Combustível (Gasolina / Etanol / Diesel / Flex / GNV):")
        return

    if etapa == "pergunta_combustivel":
        d["combustivel"] = texto
        sessao["etapa"] = "pergunta_placa"
        enviar_texto(numero, "Digite a *placa*:")
        return

    if etapa == "pergunta_placa":
        d["placa"] = texto
        sessao["etapa"] = "pergunta_cep"
        enviar_texto(numero, "Digite o *CEP*:")
        return

    if etapa == "pergunta_cep":
        d["cep"] = texto
        sessao["etapa"] = "pergunta_numero_endereco"
        enviar_texto(numero, "Digite o *número*:")
        return

    if etapa == "pergunta_numero_endereco":
        d["numero"] = texto
        sessao["etapa"] = "pergunta_complemento"
        enviar_botoes(
            numero,
            "Deseja informar complemento?",
            [
                {"id": "comp_sim", "title": "Sim"},
                {"id": "comp_nao", "title": "Não"},
            ]
        )
        return

    if etapa == "pergunta_complemento":
        if texto in ["comp_sim", "Sim"]:
            sessao["etapa"] = "complemento_digitacao"
            enviar_texto(numero, "Digite o complemento:")
            return
        d["complemento"] = ""
        sessao["etapa"] = "pergunta_tipo_atendimento"
        enviar_botoes(
            numero,
            "Qual atendimento você procura?",
            [
                {"id": "servico", "title": "Serviços"},
                {"id": "peca", "title": "Peças"},
                {"id": "mais", "title": "Mais opções"},
            ]
        )
        return

    if etapa == "complemento_digitacao":
        d["complemento"] = texto
        sessao["etapa"] = "pergunta_tipo_atendimento"
        enviar_botoes(
            numero,
            "Qual atendimento você procura?",
            [
                {"id": "servico", "title": "Serviços"},
                {"id": "peca", "title": "Peças"},
                {"id": "mais", "title": "Mais opções"},
            ]
        )
        return

    # ================================
    # ATENDIMENTO PRINCIPAL
    # ================================

    if etapa == "pergunta_tipo_atendimento":

        # Serviços
        if texto in ["servico", "Serviços"]:
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(numero, "Descreva o serviço desejado:")
            return

        # Peças
        if texto in ["peca", "Peças"]:
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(numero, "Descreva a peça desejada:")
            return

        # Submenu extra
        if texto in ["mais", "Mais opções"]:
            sessao["etapa"] = "submenu_mais"
            enviar_botoes(
                numero,
                "Mais opções:",
                [
                    {"id": "posvenda", "title": "Pós-venda"},
                    {"id": "retorno", "title": "Retorno Oficina"},
                    {"id": "end", "title": "Endereço"}
                ]
            )
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ================================
    # SERVIÇOS E PEÇAS → ORIGEM
    # ================================

    if etapa == "descricao_servico":
        d["descricao"] = texto
        sessao["etapa"] = "servico_origem"
        enviar_botoes(
            numero,
            "Como nos conheceu?",
            [
                {"id": "Google", "title": "Google"},
                {"id": "Instagram", "title": "Instagram"},
                {"id": "Facebook", "title": "Facebook"},
                {"id": "Indicacao", "title": "Indicação"},
                {"id": "Outros", "title": "Outros"},
            ]
        )
        return

    if etapa == "servico_origem":
        d["origem"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma o serviço?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    if etapa == "descricao_peca":
        d["descricao"] = texto
        sessao["etapa"] = "peca_origem"
        enviar_botoes(
            numero,
            "Como nos conheceu?",
            [
                {"id": "Google", "title": "Google"},
                {"id": "Instagram", "title": "Instagram"},
                {"id": "Facebook", "title": "Facebook"},
                {"id": "Indicacao", "title": "Indicação"},
                {"id": "Outros", "title": "Outros"},
            ]
        )
        return

    if etapa == "peca_origem":
        d["origem"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma a peça?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ================================
    # PÓS-VENDA
    # ================================

    if etapa == "submenu_mais":
        if texto in ["posvenda", "Pós-venda"]:
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data_compra"
            enviar_texto(numero, "Digite a *data da compra*:")
            return

        if texto in ["retorno", "Retorno Oficina"]:
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data_servico"
            enviar_texto(numero, "Digite a *data do serviço*:")
            return

        if texto in ["end", "Endereço"]:
            enviar_texto(
                numero,
                "📍 *Endereços Sullato*\n\n"
                "📍 *Sullato Micros e Vans*\n"
                "Av. São Miguel, 7900 – CEP 08070-001\n\n"
                "📍 *Sullato Veículos*\n"
                "Av. São Miguel, 4049/4084 – CEP 03871-000\n\n"
                "📍 *Oficina & Peças*\n"
                "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000"
            )
            reset_sessao(numero)
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ================================
    # PÓS-VENDA FLUXO
    # ================================

    if etapa == "posvenda_data_compra":
        d["data_compra_veiculo"] = texto
        sessao["etapa"] = "posvenda_descricao"
        enviar_texto(numero, "Descreva o problema ocorrido:")
        return

    if etapa == "posvenda_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "posvenda_feedback"
        enviar_texto(numero, "Nos deixe uma sugestão ou avaliação:")
        return

    if etapa == "posvenda_feedback":
        d["feedback"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ================================
    # RETORNO OFICINA
    # ================================

    if etapa == "retorno_data_servico":
        d["data_servico"] = texto
        sessao["etapa"] = "retorno_os"
        enviar_texto(numero, "Digite o número da OS:")
        return

    if etapa == "retorno_os":
        d["ordem_servico"] = texto
        sessao["etapa"] = "retorno_descricao"
        enviar_texto(numero, "Descreva o problema encontrado após o serviço:")
        return

    if etapa == "retorno_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "retorno_feedback"
        enviar_texto(numero, "Nos deixe uma sugestão ou avaliação:")
        return

    if etapa == "retorno_feedback":
        d["feedback"] = texto
        sessao["etapa"] = "confirmacao"
        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ================================
    # CONFIRMAÇÃO FINAL
    # ================================

    if etapa == "confirmacao":

        if texto in ["confirmar", "Confirmar"]:
            salvar_via_webapp(sessao)
            enviar_texto(
                numero,
                "👍 *Perfeito!* Seus dados foram enviados.\n"
                "Um técnico da Sullato irá te chamar em breve!"
            )
            reset_sessao(numero)
            return

        if texto in ["editar", "Editar"]:
            enviar_texto(numero, "Ok! Vamos reiniciar.\nDigite seu nome completo:")
            sessao["etapa"] = "pergunta_nome"
            sessao["dados"] = {"fone": numero, "nome_whatsapp": d["nome_whatsapp"]}
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ================================
    # FORA DO FLUXO
    # ================================

    enviar_texto(
        numero,
        "Não entendi sua resposta. Vamos reiniciar!\n\n"
        "Digite *seu nome completo*:"
    )
    sessao["etapa"] = "pergunta_nome"
    sessao["dados"] = {"fone": numero, "nome_whatsapp": d["nome_whatsapp"]}
    return
