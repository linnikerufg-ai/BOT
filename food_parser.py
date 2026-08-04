"""
Interpretação de refeições usando a API da Claude — aceita tanto texto
("comi 2 ovos e uma fatia de pão") quanto foto do prato.
"""

import os
import json
import base64
from datetime import date
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = f"""Você é um nutricionista que estima calorias e macros de refeições
a partir de uma descrição em texto OU de uma foto do prato, em português do Brasil.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato:
{{"descricao": "<string curta descrevendo a refeição>", "calorias": <number>, "proteina_g": <number>, "carboidrato_g": <number>, "gordura_g": <number>}}

Regras:
- Dê sua MELHOR estimativa mesmo com informação incompleta — nunca diga que não é possível
- Os valores devem ser números (não strings), arredondados para inteiros
- descricao deve resumir os itens da refeição em poucas palavras
- Se a mensagem também citar quando a refeição foi feita (ex: "ontem", "3 dias atrás"),
  isso será tratado separadamente — ignore isso na sua resposta, foque só na comida
- Se não for possível identificar nenhuma comida na mensagem/imagem, responda exatamente:
  {{"erro": "sem_comida"}}
"""


def interpretar_refeicao_texto(texto: str) -> dict | None:
    """Interpreta uma refeição descrita em texto."""
    return _chamar_claude([{"type": "text", "text": texto}])


def interpretar_refeicao_imagem(imagem_bytes: bytes, mime_type: str, legenda: str = "") -> dict | None:
    """
    Interpreta uma refeição a partir de uma foto (mais legenda opcional,
    caso a pessoa tenha mandado a foto com um texto junto).
    """
    imagem_base64 = base64.b64encode(imagem_bytes).decode("utf-8")

    conteudo = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": imagem_base64,
            },
        },
        {"type": "text", "text": legenda or "Analise esta refeição."},
    ]
    return _chamar_claude(conteudo)


def _chamar_claude(conteudo_usuario: list) -> dict | None:
    """Faz a chamada à API e valida o JSON retornado."""
    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": conteudo_usuario}],
        )

        bloco_texto = next(
            (bloco for bloco in response.content if bloco.type == "text"), None
        )
        if bloco_texto is None:
            print("Erro ao interpretar refeição: resposta sem bloco de texto")
            return None

        texto_resposta = bloco_texto.text.strip()
        texto_resposta = texto_resposta.replace("```json", "").replace("```", "").strip()

        dados = json.loads(texto_resposta)

        if "erro" in dados:
            return None

        campos_esperados = ("descricao", "calorias", "proteina_g", "carboidrato_g", "gordura_g")
        if not all(k in dados for k in campos_esperados):
            return None

        for campo in ("calorias", "proteina_g", "carboidrato_g", "gordura_g"):
            dados[campo] = float(dados[campo])

        return dados

    except Exception as e:
        print(f"Erro ao interpretar refeição: {e}")
        return None
