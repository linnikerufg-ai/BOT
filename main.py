"""
Assistente pessoal unificado via WhatsApp — despesas + dieta
----------------------------------------------------------------
Um único webhook (um único número de WhatsApp) cuidando dos dois
assistentes: controle de despesas e controle de dieta/nutrição.

Como o bot decide o que fazer com uma mensagem:
  - Foto                        -> sempre registra REFEIÇÃO (a Claude analisa a imagem)
  - "gasto <descrição>"         -> registra DESPESA
  - "agua <ml>"                 -> registra ÁGUA
  - "peso <kg>"                 -> registra PESO
  - "resumo"                    -> resumo de despesas do mês + dieta do dia
  - "resumo despesas"           -> só despesas
  - "resumo dieta"              -> só dieta
  - "ajuda"                     -> lista de comandos
  - qualquer outro texto        -> registra REFEIÇÃO por padrão (descrição livre de comida)

Por que "gasto" é obrigatório para despesas: sem esse prefixo, não dá
pra saber com certeza se "45 no mercado" é uma compra (despesa) ou
uma refeição. Como fotos e descrições de comida tendem a ser mais
frequentes nesse bot combinado, o texto livre por padrão vira
refeição, e despesas passam a exigir o prefixo "gasto".
"""

import os
import re
from datetime import date, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

load_dotenv()

from expense_parser import interpretar_mensagem as interpretar_despesa
from food_parser import interpretar_refeicao_texto, interpretar_refeicao_imagem
from whatsapp_client import enviar_mensagem
from whatsapp_media import baixar_midia
import sheets

app = FastAPI(title="Assistente Unificado WhatsApp")


@app.get("/")
def healthcheck():
    return {"status": "ok"}


@app.get("/webhook")
def verificar_webhook(request: Request):
    params = request.query_params
    modo = params.get("hub.mode")
    token_recebido = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token_esperado = os.environ["META_VERIFY_TOKEN"]

    if modo == "subscribe" and token_recebido == verify_token_esperado:
        return PlainTextResponse(content=challenge)

    return PlainTextResponse(content="Token de verificação inválido", status_code=403)


@app.post("/webhook")
async def receber_mensagem(request: Request):
    body = await request.json()

    mensagem = extrair_mensagem(body)
    if mensagem is None:
        return {"status": "ignorado"}

    message_id = mensagem["message_id"]

    # Evita processar a mesma mensagem duas vezes (a Meta reenvia o
    # webhook se o servidor demorar pra responder, ex: acordando do
    # "sono" do plano gratuito do Render)
    if sheets.ja_processado(message_id):
        return {"status": "duplicado_ignorado"}

    remetente = mensagem["remetente"]
    resposta = processar_mensagem(mensagem)
    enviar_mensagem(remetente, resposta)
    sheets.marcar_processado(message_id)

    return {"status": "ok"}


def extrair_mensagem(body: dict) -> dict | None:
    try:
        value = body["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return None

        msg = value["messages"][0]
        remetente = msg["from"]
        message_id = msg["id"]
        tipo = msg.get("type")

        if tipo == "text":
            return {
                "remetente": remetente,
                "message_id": message_id,
                "tipo": "text",
                "texto": msg["text"]["body"],
            }

        if tipo == "image":
            return {
                "remetente": remetente,
                "message_id": message_id,
                "tipo": "image",
                "media_id": msg["image"]["id"],
                "legenda": msg["image"].get("caption", ""),
            }

        return None

    except (KeyError, IndexError):
        return None


def extrair_data_relativa(texto: str) -> str:
    """'ontem', 'anteontem', 'N dias atrás' -> data em YYYY-MM-DD. Sem match, devolve hoje."""
    texto_lower = texto.lower()
    hoje = date.today()

    if "anteontem" in texto_lower:
        return (hoje - timedelta(days=2)).isoformat()
    if "ontem" in texto_lower:
        return (hoje - timedelta(days=1)).isoformat()

    match = re.search(r"(\d+)\s*dias?\s*atr[aá]s", texto_lower)
    if match:
        return (hoje - timedelta(days=int(match.group(1)))).isoformat()

    return hoje.isoformat()


def processar_mensagem(mensagem: dict) -> str:
    remetente = mensagem["remetente"]

    if mensagem["tipo"] == "image":
        return processar_foto_refeicao(remetente, mensagem["media_id"], mensagem["legenda"])

    texto = mensagem["texto"].strip()
    texto_lower = texto.lower()

    # --- Comandos de consulta ---
    if texto_lower == "resumo":
        return sheets.resumo_despesas_do_mes(remetente) + "\n\n" + sheets.resumo_dieta_do_dia(remetente)

    if texto_lower in ("resumo despesas", "resumo do mes", "resumo do mês"):
        return sheets.resumo_despesas_do_mes(remetente)

    if texto_lower in ("resumo dieta", "resumo do dia"):
        return sheets.resumo_dieta_do_dia(remetente)

    if texto_lower in ("ajuda", "help", "menu"):
        return (
            "Oi! Aqui vai o que eu entendo:\n\n"
            "💰 *Despesas*\n"
            "'gasto 45 no mercado' -> registra a despesa\n\n"
            "🥗 *Dieta*\n"
            "Foto do prato, ou texto tipo '2 ovos e pão' -> registra refeição\n"
            "'agua 500' -> registra 500ml de água\n"
            "'peso 78.5' -> registra seu peso\n\n"
            "📊 *Resumos*\n"
            "'resumo' -> despesas do mês + dieta de hoje\n"
            "'resumo despesas' / 'resumo dieta' -> separado"
        )

    # --- Despesa (exige o prefixo "gasto") ---
    if texto_lower.startswith("gasto"):
        texto_despesa = texto[len("gasto"):].strip()
        dados = interpretar_despesa(texto_despesa)
        if dados is None:
            return "Não consegui entender esse gasto 🤔 Tenta algo como: 'gasto 45 no mercado hoje'."
        sheets.registrar_despesa(remetente, dados)
        return (
            f"✅ Despesa registrada!\n"
            f"Valor: R$ {dados['valor']:.2f}\n"
            f"Categoria: {dados['categoria']}\n"
            f"Descrição: {dados['descricao']}\n"
            f"Data: {dados['data']}"
        )

    # --- Água ---
    match_agua = re.match(r"agua\s+(\d+([.,]\d+)?)", texto_lower)
    if match_agua:
        quantidade = float(match_agua.group(1).replace(",", "."))
        data_str = extrair_data_relativa(texto)
        sheets.registrar_agua(remetente, data_str, quantidade)
        return f"💧 Registrado! {quantidade:.0f}ml de água em {data_str}"

    # --- Peso ---
    match_peso = re.match(r"peso\s+(\d+([.,]\d+)?)", texto_lower)
    if match_peso:
        peso = float(match_peso.group(1).replace(",", "."))
        data_str = extrair_data_relativa(texto)
        sheets.registrar_peso(remetente, data_str, peso)
        return f"⚖️ Registrado! {peso:.1f}kg em {data_str}"

    # --- Padrão: refeição por texto ---
    dados = interpretar_refeicao_texto(texto)
    if dados is None:
        return (
            "Não consegui entender 🤔\n"
            "Pra despesa: 'gasto 45 no mercado'\n"
            "Pra refeição: manda uma foto ou descreve a comida\n"
            "Manda 'ajuda' pra ver todos os comandos."
        )

    data_str = extrair_data_relativa(texto)
    sheets.registrar_refeicao(remetente, data_str, dados)
    return formatar_confirmacao_refeicao(dados, data_str)


def processar_foto_refeicao(remetente: str, media_id: str, legenda: str) -> str:
    try:
        imagem_bytes, mime_type = baixar_midia(media_id)
    except Exception as e:
        print(f"Erro ao baixar mídia: {e}")
        return "Não consegui baixar sua foto 😕 Tenta mandar de novo."

    dados = interpretar_refeicao_imagem(imagem_bytes, mime_type, legenda)
    if dados is None:
        return "Não consegui identificar a comida na foto 🤔 Tenta descrever em texto."

    data_str = extrair_data_relativa(legenda) if legenda else date.today().isoformat()
    sheets.registrar_refeicao(remetente, data_str, dados)
    return formatar_confirmacao_refeicao(dados, data_str)


def formatar_confirmacao_refeicao(dados: dict, data_str: str) -> str:
    return (
        f"✅ Refeição registrada!\n"
        f"{dados['descricao']}\n\n"
        f"🔥 {dados['calorias']:.0f} kcal\n"
        f"🥩 Proteína: {dados['proteina_g']:.0f}g\n"
        f"🍞 Carboidrato: {dados['carboidrato_g']:.0f}g\n"
        f"🥑 Gordura: {dados['gordura_g']:.0f}g\n"
        f"📅 {data_str}"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
