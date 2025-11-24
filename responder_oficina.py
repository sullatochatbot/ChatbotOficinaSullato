import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{os.getenv('WA_PHONE_NUMBER_ID')}"
WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")

GOOGLE_SHEETS_URL = os.getenv("OFICINA_SHEET_WEBHOOK_URL")
SECRET_KEY = os.getenv("OFICINA_SHEETS_SECRET")

TIMEOUT_SESSAO = 30
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
        "Vamos começar seu atendimento.\n"
        "Por favor, digite *seu nome completo:*"
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
        print("Erro ao enviar dados para WebApp:", e)

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
        f"Origem: {d.get('origem','')}\n"
        f"Descrição: {d.get('descricao','')}\n"
        f"Sugestão: {d.get('sugestao','')}\n"
    )

# ============================================================
# PROCESSAR CONFIRMAÇÃO
# ============================================================

def processar_confirmacao(numero, sessao, escolha):
    if escolha == "confirmar":
        salvar_via_webapp(sessao)
        enviar_texto(
            numero,
            "👍 *Perfeito!* Seus dados foram enviados para nossa equipe.\n"
            "Um técnico da Sullato irá te chamar em breve."
        )
        reset_sessao(numero)
        return

    if escolha == "editar":
        enviar_texto(numero, "Vamos começar novamente!\nDigite seu *nome completo*:")
        nome_wpp = sessao["dados"]["nome_whatsapp"]
        sessao["etapa"] = "pergunta_nome"
        sessao["dados"] = {"fone": numero, "nome_whatsapp": nome_wpp}
        return
# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def responder_oficina(numero, texto_digitado, nome_whatsapp):

    texto = texto_digitado.strip()
    agora = time.time()

    # ========================================================
    # INICIA SESSÃO
    # ========================================================
    if numero not in SESSOES:
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao = SESSOES[numero]

    # ========================================================
    # TIMEOUT
    # ========================================================
    if agora - sessao.get("inicio", 0) > TIMEOUT_SESSAO:
        enviar_texto(numero, "Sessão expirada por inatividade. Vamos começar novamente!")
        iniciar_sessao(numero, nome_whatsapp)
        return

    sessao["inicio"] = agora
    etapa = sessao["etapa"]
    d = sessao["dados"]

    # ========================================================
    # ETAPA 1 — NOME
    # ========================================================
    if etapa == "pergunta_nome":
        d["nome"] = texto
        sessao["etapa"] = "pergunta_cpf"
        enviar_texto(numero, "Ótimo! Agora digite *seu CPF* (formato: 123.456.789-00):")
        return

    # ========================================================
    # ETAPA 2 — CPF
    # ========================================================
    if etapa == "pergunta_cpf":
        d["cpf"] = texto
        sessao["etapa"] = "pergunta_nascimento"
        enviar_texto(numero, "Agora digite *sua data de nascimento* (00/00/0000):")
        return

    # ========================================================
    # ETAPA 3 — NASCIMENTO
    # ========================================================
    if etapa == "pergunta_nascimento":
        d["nascimento"] = texto
        sessao["etapa"] = "pergunta_tipo_veiculo"
        enviar_botoes(
            numero,
            "Qual o *tipo de veículo*?",
            [
                {"id": "tv_passeio", "title": "Passeio"},
                {"id": "tv_utilitario", "title": "Utilitário"},
            ]
        )
        return

    # ========================================================
    # ETAPA 4 — RECEBER TIPO DE VEÍCULO
    # ========================================================
    if etapa == "pergunta_tipo_veiculo":

        if texto in ["tv_passeio", "Passeio"]:
            d["tipo_veiculo"] = "Passeio"

        elif texto in ["tv_utilitario", "Utilitário"]:
            d["tipo_veiculo"] = "Utilitário"

        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

        sessao["etapa"] = "pergunta_marca_modelo"
        enviar_texto(numero, "Informe *marca / modelo* do veículo:")
        return

    # ========================================================
    # ETAPA 5 — MARCA / MODELO
    # ========================================================
    if etapa == "pergunta_marca_modelo":
        d["marca_modelo"] = texto
        sessao["etapa"] = "pergunta_ano_modelo"
        enviar_texto(numero, "Digite o *ano fab/mod* (Ex: 20/21):")
        return

    # ========================================================
    # ETAPA 6 — ANO MODELO
    # ========================================================
    if etapa == "pergunta_ano_modelo":
        d["ano_modelo"] = texto
        sessao["etapa"] = "pergunta_km"
        enviar_texto(numero, "Digite a *quilometragem atual*:")
        return

    # ========================================================
    # ETAPA 7 — KM
    # ========================================================
    if etapa == "pergunta_km":
        d["km"] = texto
        sessao["etapa"] = "pergunta_combustivel"
        enviar_texto(
            numero,
            "Qual o combustível? (Gasolina, Etanol, Flex, Diesel, GNV)"
        )
        return

    # ========================================================
    # ETAPA 8 — COMBUSTÍVEL
    # ========================================================
    if etapa == "pergunta_combustivel":
        d["combustivel"] = texto
        sessao["etapa"] = "pergunta_placa"
        enviar_texto(numero, "Digite a placa do veículo (Ex: ABC1D23):")
        return

    # ========================================================
    # ETAPA 9 — PLACA
    # ========================================================
    if etapa == "pergunta_placa":
        d["placa"] = texto
        sessao["etapa"] = "pergunta_cep"
        enviar_texto(numero, "Digite o *CEP* (12345-678):")
        return

    # ========================================================
    # ETAPA 10 — CEP
    # ========================================================
    if etapa == "pergunta_cep":
        d["cep"] = texto
        sessao["etapa"] = "pergunta_numero_endereco"
        enviar_texto(numero, "Digite o *número* do endereço:")
        return

    # ========================================================
    # ETAPA 11 — NÚMERO ENDEREÇO
    # ========================================================
    if etapa == "pergunta_numero_endereco":
        d["numero"] = texto
        sessao["etapa"] = "pergunta_complemento"
        enviar_botoes(
            numero,
            "Deseja adicionar *complemento*?",
            [
                {"id": "comp_sim", "title": "Sim"},
                {"id": "comp_nao", "title": "Não"},
            ]
        )
        return

    # ========================================================
    # ETAPA 12 — COMPLEMENTO (SIM/NÃO)
    # ========================================================
    if etapa == "pergunta_complemento":

        if texto in ["comp_sim", "Sim"]:
            sessao["etapa"] = "complemento_digitacao"
            enviar_texto(numero, "Digite o complemento:")
            return

        if texto in ["comp_nao", "Não"]:
            d["complemento"] = ""
            sessao["etapa"] = "pergunta_tipo_atendimento"
            enviar_botoes(
                numero,
                "Qual atendimento você procura?",
                [
                    {"id": "servico", "title": "Serviços"},
                    {"id": "peca", "title": "Peças"},
                ]
            )
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ========================================================
    # ETAPA 12B — COMPLEMENTO DIGITADO
    # ========================================================
    if etapa == "complemento_digitacao":
        d["complemento"] = texto
        sessao["etapa"] = "pergunta_tipo_atendimento"
        enviar_botoes(
            numero,
            "Qual atendimento você procura?",
            [
                {"id": "servico", "title": "Serviços"},
                {"id": "peca", "title": "Peças"},
            ]
        )
        return
    # ========================================================
    # ETAPA 13 — TIPO DE ATENDIMENTO
    # ========================================================
    if etapa == "pergunta_tipo_atendimento":

        # -----------------------------
        # SERVIÇOS
        # -----------------------------
        if texto in ["servico", "Serviços"]:
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "descricao_servico"
            enviar_texto(
                numero,
                "Descreva em poucas palavras o *serviço desejado*:"
            )
            return

        # -----------------------------
        # PEÇAS
        # -----------------------------
        if texto in ["peca", "Peças"]:
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "descricao_peca"
            enviar_texto(
                numero,
                "Descreva em poucas palavras a *peça desejada*:"
            )
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ========================================================
    # ETAPA 14 — SERVIÇO → DESCRIÇÃO
    # ========================================================
    if etapa == "descricao_servico":
        d["descricao"] = texto
        sessao["etapa"] = "origem_servico"

        enviar_botoes(
            numero,
            "Onde você nos conheceu?",
            [
                {"id": "org_google", "title": "Google"},
                {"id": "org_instagram", "title": "Instagram"},
                {"id": "org_facebook", "title": "Facebook"},
                {"id": "org_outros", "title": "Outros"},
            ]
        )
        return

    # ========================================================
    # ETAPA 15 — ORIGEM (SERVIÇO)
    # ========================================================
    if etapa == "origem_servico":

        origens = {
            "org_google": "Google",
            "org_instagram": "Instagram",
            "org_facebook": "Facebook",
            "org_outros": "Outros"
        }

        if texto in origens:
            d["origem"] = origens[texto]
        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

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

    # ========================================================
    # ETAPA 16 — PEÇA → DESCRIÇÃO
    # ========================================================
    if etapa == "descricao_peca":
        d["descricao"] = texto
        sessao["etapa"] = "origem_peca"

        enviar_botoes(
            numero,
            "Onde você nos conheceu?",
            [
                {"id": "org_google", "title": "Google"},
                {"id": "org_instagram", "title": "Instagram"},
                {"id": "org_facebook", "title": "Facebook"},
                {"id": "org_outros", "title": "Outros"},
            ]
        )
        return

    # ========================================================
    # ETAPA 17 — ORIGEM (PEÇA)
    # ========================================================
    if etapa == "origem_peca":

        origens = {
            "org_google": "Google",
            "org_instagram": "Instagram",
            "org_facebook": "Facebook",
            "org_outros": "Outros"
        }

        if texto in origens:
            d["origem"] = origens[texto]
        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

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

    # ========================================================
    # ETAPA 18 — PÓS-VENDA → DATA COMPRA
    # ========================================================
    if etapa == "posvenda_data_compra":
        d["data_compra_veiculo"] = texto
        sessao["etapa"] = "posvenda_descricao"

        enviar_texto(
            numero,
            "Descreva em poucas palavras o *problema ocorrido*:"
        )
        return

    # ========================================================
    # ETAPA 19 — PÓS-VENDA → DESCRIÇÃO
    # ========================================================
    if etapa == "posvenda_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "posvenda_sugestao"

        enviar_texto(
            numero,
            "Nos deixe uma *sugestão* para melhorarmos:"
        )
        return

    # ========================================================
    # ETAPA 20 — PÓS-VENDA → SUGESTÃO
    # ========================================================
    if etapa == "posvenda_sugestao":
        d["sugestao"] = texto
        sessao["etapa"] = "confirmacao"

        resumo = construir_resumo(d)

        enviar_botoes(
            numero,
            resumo + "\n\nConfirma o pós-venda?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ========================================================
    # ETAPA 21 — RETORNO → DATA SERVIÇO
    # ========================================================
    if etapa == "retorno_data_servico":
        d["data_servico"] = texto
        sessao["etapa"] = "retorno_os"

        enviar_texto(
            numero,
            "Digite o *número da Ordem de Serviço*:"
        )
        return

    # ========================================================
    # ETAPA 22 — RETORNO → OS
    # ========================================================
    if etapa == "retorno_os":
        d["ordem_servico"] = texto
        sessao["etapa"] = "retorno_descricao"

        enviar_texto(
            numero,
            "Descreva o *problema apresentado após o serviço*:"
        )
        return

    # ========================================================
    # ETAPA 23 — RETORNO → DESCRIÇÃO
    # ========================================================
    if etapa == "retorno_descricao":
        d["descricao"] = texto
        sessao["etapa"] = "retorno_sugestao"

        enviar_texto(
            numero,
            "Nos deixe uma *sugestão* para melhorarmos:"
        )
        return

    # ========================================================
    # ETAPA 24 — RETORNO → SUGESTÃO
    # ========================================================
    if etapa == "retorno_sugestao":
        d["sugestao"] = texto
        sessao["etapa"] = "confirmacao"

        resumo = construir_resumo(d)

        enviar_botoes(
            numero,
            resumo + "\n\nConfirma o retorno?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return
    # ========================================================
    # ETAPA 25 — CONFIRMAÇÃO FINAL
    # ========================================================
    if etapa == "confirmacao":

        # CONFIRMAR
        if texto in ["confirmar", "Confirmar"]:
            salvar_via_webapp(sessao)
            enviar_texto(
                numero,
                "👍 *Perfeito!* Seus dados foram enviados.\n"
                "Um técnico da Sullato irá te chamar em breve!"
            )
            reset_sessao(numero)
            return

        # EDITAR
        if texto in ["editar", "Editar"]:
            enviar_texto(numero, "Vamos começar novamente!\nDigite seu *nome completo*:")
            nome_wpp = d.get("nome_whatsapp", "")
            sessao["etapa"] = "pergunta_nome"
            sessao["dados"] = {"fone": numero, "nome_whatsapp": nome_wpp}
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ========================================================
    # FALLBACK — QUALQUER OUTRA SITUAÇÃO
    # ========================================================
    enviar_texto(
        numero,
        "Não entendi sua resposta. Vamos reiniciar!\n\n"
        "Por favor digite *seu nome completo*:"
    )
    nome_wpp = d.get("nome_whatsapp", "")
    sessao["etapa"] = "pergunta_nome"
    sessao["dados"] = {"fone": numero, "nome_whatsapp": nome_wpp}
    return
