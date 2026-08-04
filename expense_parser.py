"""
Interpretação de mensagens de despesa usando a API da Claude.

Recebe um texto livre (ex: "gastei 45 no mercado hoje") e devolve um
dicionário estruturado com valor, categoria, descrição e data.
"""

import os
import json
from datetime import date
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

CATEGORIAS = [
    "alimentação", "mercado", "transporte", "moradia", "lazer",
    "saúde", "educação", "assinaturas", "contas", "outros",
]

SYSTEM_PROMPT = f"""Você extrai dados de despesas pessoais a partir de mensagens em português do Brasil.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato:
{{"valor": <number>, "categoria": "<uma das categorias>", "descricao": "<string curta>", "data": "<YYYY-MM-DD>"}}

Categorias possíveis: {", ".join(CATEGORIAS)}

Regras:
- Se a mensagem não mencionar uma data, use a data de hoje: {date.today().isoformat()}
- Se a mensagem citar "ontem", "anteontem", "há X dias", "X dias atrás",
  "semana passada" ou qualquer outra referência relativa de tempo, calcule
  a data real a partir de hoje ({date.today().isoformat()}). Ex: se hoje é
  {date.today().isoformat()} e a mensagem diz "3 dias atrás", subtraia 3
  dias dessa data
- Se não for possível identificar um valor numérico claro, responda exatamente: {{"erro": "sem_valor"}}
- Escolha a categoria mais próxima da lista acima, mesmo que não seja perfeita
- descricao deve ser curta (poucas palavras), resumindo o que foi comprado/pago
"""


def interpretar_mensagem(texto: str) -> dict | None:
    """
    Chama a Claude para interpretar o texto da despesa.
    Retorna um dict com valor/categoria/descricao/data, ou None se
    não for possível identificar uma despesa válida.
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": texto}],
        )
        # Procura o bloco de texto na resposta — a Claude pode devolver
        # outros tipos de bloco antes do texto (ex: bloco de "pensamento"),
        # então não podemos assumir que é sempre o primeiro item da lista.
        bloco_texto = next(
            (bloco for bloco in response.content if bloco.type == "text"), None
        )

        if bloco_texto is None:
            print("Erro ao interpretar mensagem: resposta sem bloco de texto")
            return None

        conteudo = bloco_texto.text.strip()

        # remove possíveis blocos de código markdown, se vierem
        conteudo = conteudo.replace("```json", "").replace("```", "").strip()

        dados = json.loads(conteudo)

        if "erro" in dados:
            return None

        # validação básica dos campos esperados
        if not all(k in dados for k in ("valor", "categoria", "descricao", "data")):
            return None

        dados["valor"] = float(dados["valor"])
        return dados

    except Exception as e:
        print(f"Erro ao interpretar mensagem: {e}")
        return None
