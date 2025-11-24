import time
from enviar_mensagem import enviar_texto, enviar_botoes
from salvar_em_mala_direta import salvar_em_mala_direta
from registrar_historico import registrar_interacao
from responder_ia import responder_com_ia

# Dicionário de sessões (por número)
sessoes = {}

def reset_sessao(numero):
    sessoes[numero] = {
        "etapa": "inicio",
        "dados": {},
        "inicio": time.time()
    }

# ========================================================
# FUNÇÃO PRINCIPAL: responder_oficina
# ========================================================
def responder_oficina(numero, texto_digitado, nome_whatsapp):

    texto = texto_digitado.strip().lower()

    # Criar sessão se não existir
    if numero not in sessoes:
        reset_sessao(numero)

    sessao = sessoes[numero]
    etapa = sessao["etapa"]
    d = sessao["dados"]

    # Registrar histórico
    registrar_interacao(numero, texto_digitado, etapa)

    # Timeout de 25 minutos
    if time.time() - sessao["inicio"] > 1500:
        reset_sessao(numero)
        enviar_texto(numero, "Sessão reiniciada por inatividade. Vamos começar novamente.")
        return

    # ========================================================
    # ETAPA "INICIO"
    # ========================================================
    if etapa == "inicio":
        sessao["etapa"] = "coletar_nome"
        enviar_texto(numero, "Para começarmos, qual é o seu nome?")
        return

    # ========================================================
    # NOME
    # ========================================================
    if etapa == "coletar_nome":
        d["nome"] = texto_digitado
        salvar_em_mala_direta(numero, d["nome"])

        sessao["etapa"] = "coletar_cpf"
        enviar_texto(numero, "Digite o CPF:")
        return

    # ========================================================
    # CPF
    # ========================================================
    if etapa == "coletar_cpf":
        d["cpf"] = texto_digitado
        sessao["etapa"] = "coletar_nascimento"
        enviar_texto(numero, "Digite sua data de nascimento (DD/MM/AAAA):")
        return

    # ========================================================
    # NASCIMENTO
    # ========================================================
    if etapa == "coletar_nascimento":
        d["nascimento"] = texto_digitado
        sessao["etapa"] = "coletar_telefone"
        enviar_texto(numero, "Digite seu telefone com DDD:")
        return

    # ========================================================
    # TELEFONE
    # ========================================================
    if etapa == "coletar_telefone":
        d["telefone"] = texto_digitado
        sessao["etapa"] = "tipo_veiculo"
        enviar_botoes(
            numero,
            "Qual o tipo de veículo?",
            [
                {"id": "Passeio", "title": "Passeio"},
                {"id": "Utilitário", "title": "Utilitário"}
            ]
        )
        return

    # ========================================================
    # TIPO VEÍCULO
    # ========================================================
    if etapa == "tipo_veiculo":
        d["tipo"] = texto_digitado
        sessao["etapa"] = "marca_modelo"
        enviar_texto(numero, "Informe marca / modelo do veículo.")
        return

    # ========================================================
    # MARCA / MODELO
    # ========================================================
    if etapa == "marca_modelo":
        d["marca_modelo"] = texto_digitado
        sessao["etapa"] = "ano_modelo"
        enviar_texto(numero, "Digite o ano fab/mod (Ex: 20/21):")
        return

    # ========================================================
    # ANO / MODELO
    # ========================================================
    if etapa == "ano_modelo":
        d["ano_modelo"] = texto_digitado
        sessao["etapa"] = "pergunta_km"
        enviar_texto(numero, "Digite a quilometragem atual:")
        return

    # ========================================================
    # ETAPA 7 — KM
    # ========================================================
    if etapa == "pergunta_km":
        d["km"] = texto_digitado
        sessao["etapa"] = "pergunta_combustivel"
        sessao["inicio"] = time.time()
        enviar_texto(
            numero,
            "Qual o combustível do veículo? (Ex: Gasolina, Etanol, Flex, Diesel, GNV)"
        )
        return

    # ========================================================
    # ETAPA 8 — COMBUSTÍVEL
    # ========================================================
    if etapa == "pergunta_combustivel":
        d["combustivel"] = texto_digitado
        sessao["etapa"] = "pergunta_placa"
        enviar_texto(numero, "Digite a placa do veículo (Ex: ABC1D23):")
        return

    # ========================================================
    # PLACA
    # ========================================================
    if etapa == "pergunta_placa":
        d["placa"] = texto_digitado
        sessao["etapa"] = "pergunta_cep"
        enviar_texto(numero, "Agora digite o CEP (formato: 12345-678):")
        return
    # ========================================================
    # ETAPA 10 — CEP
    # ========================================================
    if etapa == "pergunta_cep":
        d["cep"] = texto_digitado
        sessao["etapa"] = "pergunta_numero_endereco"
        enviar_texto(numero, "Digite o número do endereço:")
        return

    # ========================================================
    # ETAPA 11 — NÚMERO DO ENDEREÇO
    # ========================================================
    if etapa == "pergunta_numero_endereco":
        d["numero"] = texto_digitado
        sessao["etapa"] = "pergunta_complemento"
        enviar_botoes(
            numero,
            "Deseja adicionar complemento?",
            [
                {"id": "comp_sim", "title": "Sim"},
                {"id": "comp_nao", "title": "Não"},
            ]
        )
        return

    # ========================================================
    # ETAPA 12 — COMPLEMENTO (SIM / NÃO)
    # ========================================================
    if etapa == "pergunta_complemento":

        if texto_digitado in ["sim", "comp_sim"]:
            sessao["etapa"] = "complemento_digitacao"
            enviar_texto(numero, "Digite o complemento:")
            return

        elif texto_digitado in ["não", "nao", "comp_nao"]:
            d["complemento"] = ""
            sessao["etapa"] = "pergunta_tipo_atendimento"
            enviar_botoes(
                numero,
                "Qual atendimento você procura?",
                [
                    {"id": "servico", "title": "Serviços"},
                    {"id": "peca", "title": "Peças"},
                    {"id": "mais", "title": "Mais opções"}
                ]
            )
            return

        else:
            enviar_texto(numero, "Escolha uma opção válida.")
            return

    # ========================================================
    # ETAPA 12B — DIGITAÇÃO DO COMPLEMENTO
    # ========================================================
    if etapa == "complemento_digitacao":
        d["complemento"] = texto_digitado
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

    # ========================================================
    # ETAPA 13 — TIPO DE ATENDIMENTO (SERVIÇO / PEÇA / MAIS)
    # ========================================================
    if etapa == "pergunta_tipo_atendimento":

        # -----------------------------
        # SERVIÇOS
        # -----------------------------
        if texto_digitado in ["servico", "serviços", "servico", "Serviços"]:
            d["tipo_registro"] = "Serviço"
            sessao["etapa"] = "origem_servico"
            enviar_botoes(
                numero,
                "Para melhorarmos nosso atendimento, como nos conheceu?",
                [
                    {"id": "orig_google", "title": "Google"},
                    {"id": "orig_insta", "title": "Instagram"},
                    {"id": "orig_face", "title": "Facebook"},
                    {"id": "orig_outros", "title": "Outros"},
                ]
            )
            return

        # -----------------------------
        # PEÇAS
        # -----------------------------
        if texto_digitado in ["peca", "peças", "Peças"]:
            d["tipo_registro"] = "Peça"
            sessao["etapa"] = "origem_peca"
            enviar_botoes(
                numero,
                "Para melhorarmos nosso atendimento, como nos conheceu?",
                [
                    {"id": "orig_google", "title": "Google"},
                    {"id": "orig_insta", "title": "Instagram"},
                    {"id": "orig_face", "title": "Facebook"},
                    {"id": "orig_outros", "title": "Outros"},
                ]
            )
            return

        # -----------------------------
        # MAIS OPÇÕES
        # -----------------------------
        if texto_digitado in ["mais", "mais opções", "Mais opções"]:
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

    # ========================================================
    # ETAPA — ORIGEM SERVIÇO
    # ========================================================
    if etapa == "origem_servico":
        d["origem"] = texto_digitado
        sessao["etapa"] = "descricao_servico"
        enviar_texto(numero, "Descreva em poucas palavras o serviço desejado:")
        return

    # ========================================================
    # ETAPA — ORIGEM PEÇA
    # ========================================================
    if etapa == "origem_peca":
        d["origem"] = texto_digitado
        sessao["etapa"] = "descricao_peca"
        enviar_texto(numero, "Descreva em poucas palavras a peça desejada:")
        return

    # ========================================================
    # ETAPA 14 — SUBMENU “MAIS OPÇÕES”
    # ========================================================
    if etapa == "submenu_mais":

        # -------- PÓS-VENDA --------
        if texto_digitado in ["posvenda", "Pós-venda"]:
            d["tipo_registro"] = "Pós-venda"
            sessao["etapa"] = "posvenda_data_compra"
            enviar_texto(numero, "Informe a data da compra (Ex: 10/08/2024):")
            return

        # -------- RETORNO OFICINA --------
        if texto_digitado in ["retorno", "Retorno Oficina"]:
            d["tipo_registro"] = "Retorno Oficina"
            sessao["etapa"] = "retorno_data_servico"
            enviar_texto(numero, "Digite a data em que o serviço foi feito:")
            return

        # -------- ENDEREÇO --------
        if texto_digitado in ["end", "endereço", "Endereço"]:
            enviar_texto(
                numero,
                "📍 *Endereços Sullato*\n\n"

                "📍 *Sullato Micros e Vans*\n"
                "Av. São Miguel, 7900 – CEP 08070-001\n"
                "☎️ (11) 2030-5081 / (11) 2031-5081\n"
                "👉 https://wa.me/551120305081\n"
                "👉 https://wa.me/5511940545704\n"
                "📸 Instagram: https://www.instagram.com/sullatomicrosevans\n\n"

                "📍 *Sullato Veículos*\n"
                "Av. São Miguel, 4049/4084 – CEP 03871-000\n"
                "☎️ (11) 2542-3332 / (11) 2542-3333\n"
                "👉 https://wa.me/551125423332\n"
                "👉 https://wa.me/5511940545704\n"
                "📸 Instagram: https://www.instagram.com/sullato.veiculos\n\n"

                "📍 *Sullato Oficina e Peças*\n"
                "Av. Amador Bueno da Veiga, 4222 – CEP 03652-000\n"
                "☎️ (11) 2542-3333\n"
                "👉 https://wa.me/551125423333\n\n"

                "🌐 Site: https://www.sullato.com.br"
            )
            reset_sessao(numero)
            return
    # ========================================================
    # ETAPA 15 — PÓS-VENDA → DATA DA COMPRA
    # ========================================================
    if etapa == "posvenda_data_compra":
        d["data_compra"] = texto_digitado
        sessao["etapa"] = "posvenda_descricao"
        enviar_texto(
            numero,
            "Descreva em poucas palavras o problema ocorrido:"
        )
        return

    # ========================================================
    # ETAPA 16 — PÓS-VENDA → DESCRIÇÃO DO PROBLEMA
    # ========================================================
    if etapa == "posvenda_descricao":
        d["descricao"] = texto_digitado
        sessao["etapa"] = "posvenda_avaliacao"
        enviar_texto(
            numero,
            "Para nós melhorarmos cada dia mais: o que achou dos nossos serviços?"
        )
        return

    # ========================================================
    # ETAPA 16B — PÓS-VENDA → AVALIAÇÃO
    # ========================================================
    if etapa == "posvenda_avaliacao":
        d["avaliacao"] = texto_digitado
        sessao["etapa"] = "posvenda_sugestao"
        enviar_texto(
            numero,
            "Nos deixe uma sugestão para melhorarmos ainda mais:"
        )
        return

    # ========================================================
    # ETAPA 16C — PÓS-VENDA → SUGESTÃO FINAL
    # ========================================================
    if etapa == "posvenda_sugestao":
        d["sugestao"] = texto_digitado
        sessao["etapa"] = "confirmacao"

        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma o envio?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ========================================================
    # ETAPA 17 — RETORNO → DATA DO SERVIÇO ANTERIOR
    # ========================================================
    if etapa == "retorno_data_servico":
        d["data_servico"] = texto_digitado
        sessao["etapa"] = "retorno_os"
        enviar_texto(
            numero,
            "Informe o número da Ordem de Serviço:"
        )
        return

    # ========================================================
    # ETAPA 18 — RETORNO → NÚMERO DA OS
    # ========================================================
    if etapa == "retorno_os":
        d["os"] = texto_digitado
        sessao["etapa"] = "retorno_descricao"
        enviar_texto(
            numero,
            "Descreva o problema apresentado após o serviço:"
        )
        return

    # ========================================================
    # ETAPA 19 — RETORNO → DESCRIÇÃO
    # ========================================================
    if etapa == "retorno_descricao":
        d["descricao"] = texto_digitado
        sessao["etapa"] = "retorno_avaliacao"
        enviar_texto(
            numero,
            "Para nós melhorarmos cada dia mais: o que achou dos nossos serviços?"
        )
        return

    # ========================================================
    # ETAPA 19B — RETORNO → AVALIAÇÃO
    # ========================================================
    if etapa == "retorno_avaliacao":
        d["avaliacao"] = texto_digitado
        sessao["etapa"] = "retorno_sugestao"
        enviar_texto(
            numero,
            "Nos deixe uma sugestão para melhorarmos ainda mais:"
        )
        return

    # ========================================================
    # ETAPA 19C — RETORNO → SUGESTÃO FINAL
    # ========================================================
    if etapa == "retorno_sugestao":
        d["sugestao"] = texto_digitado
        sessao["etapa"] = "confirmacao"

        resumo = construir_resumo(d)
        enviar_botoes(
            numero,
            resumo + "\n\nConfirma o envio?",
            [
                {"id": "confirmar", "title": "Confirmar"},
                {"id": "editar", "title": "Editar"},
            ]
        )
        return

    # ========================================================
    # ETAPA 20 — SERVIÇO → DESCRIÇÃO
    # ========================================================
    if etapa == "descricao_servico":
        d["descricao"] = texto_digitado
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
    # ETAPA 21 — PEÇA → DESCRIÇÃO
    # ========================================================
    if etapa == "descricao_peca":
        d["descricao"] = texto_digitado
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
    # ETAPA 22 — CONFIRMAÇÃO FINAL
    # ========================================================
    if etapa == "confirmacao":

        # ------------------------------
        # CONFIRMAR
        # ------------------------------
        if texto_digitado in ["confirmar", "Confirmar"]:
            from salvar_google import salvar_via_webapp
            salvar_via_webapp(sessao)

            enviar_texto(
                numero,
                "👍 *Perfeito!* Seus dados foram enviados.\n"
                "Um técnico da Sullato irá te chamar em breve!"
            )
            reset_sessao(numero)
            return

        # ------------------------------
        # EDITAR (volta ao início)
        # ------------------------------
        if texto_digitado in ["editar", "Editar"]:
            enviar_texto(
                numero,
                "Sem problemas! Vamos começar novamente.\n"
                "Digite seu *nome completo*:"
            )
            sessao["etapa"] = "coletar_nome"
            sessao["dados"] = {"telefone": numero, "nome": d["nome"]}
            return

        enviar_texto(numero, "Escolha uma opção válida.")
        return

    # ========================================================
    # FALLBACK — RESPOSTAS NÃO RECONHECIDAS
    # ========================================================
    # Se chegou até aqui, significa que a resposta não encaixa em nenhuma etapa.
    # Então usamos a IA para tentar ajudar o cliente sem travar o fluxo.
    try:
        resposta_ia = responder_com_ia(numero, texto_digitado, etapa)
        if resposta_ia:
            enviar_texto(numero, resposta_ia)
            return
    except:
        pass

    # Se nada resolver, reinicia o fluxo
    enviar_texto(
        numero,
        "Desculpe, não consegui entender. Vamos começar novamente!\n\n"
        "Digite seu *nome completo*:"
    )
    sessao["etapa"] = "coletar_nome"
    sessao["dados"] = {"telefone": numero, "nome": d.get("nome", "")}
    return
