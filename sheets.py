"""
Armazenamento no Google Sheets — despesas, refeições, água e peso,
tudo na mesma planilha, em abas separadas.

Abas criadas automaticamente:
"Despesas":  data | remetente | valor | categoria | descricao
"Refeicoes": data | remetente | descricao | calorias | proteina_g | carboidrato_g | gordura_g
"Agua":      data | remetente | quantidade_ml
"Peso":      data | remetente | peso_kg
"""

import os
import json
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client = None
_planilha = None


def _get_planilha():
    global _client, _planilha
    if _client is None:
        creds = _carregar_credenciais()
        _client = gspread.authorize(creds)
    if _planilha is None:
        _planilha = _client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    return _planilha


def _carregar_credenciais() -> Credentials:
    """
    Carrega as credenciais da service account de duas formas possíveis:
    - GOOGLE_CREDENTIALS_JSON: o conteúdo do JSON direto na variável de
      ambiente (usado em produção, ex: Railway, onde não dá pra subir
      um arquivo solto com segredo)
    - GOOGLE_CREDENTIALS_PATH: caminho pra um arquivo .json no disco
      (usado localmente)
    """
    json_direto = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if json_direto:
        info = json.loads(json_direto)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    caminho_arquivo = os.environ["GOOGLE_CREDENTIALS_PATH"]
    return Credentials.from_service_account_file(caminho_arquivo, scopes=SCOPES)


def _get_aba(nome: str, cabecalho: list[str]):
    """Retorna a aba pelo nome, criando (com cabeçalho) se não existir."""
    planilha = _get_planilha()
    try:
        return planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(title=nome, rows=2000, cols=len(cabecalho))
        aba.append_row(cabecalho)
        return aba


# --- Despesas ---

def registrar_despesa(remetente: str, dados: dict) -> None:
    aba = _get_aba("Despesas", ["data", "remetente", "valor", "categoria", "descricao"])
    aba.append_row([
        dados["data"], remetente, dados["valor"], dados["categoria"], dados["descricao"],
    ])


def resumo_despesas_do_mes(remetente: str) -> str:
    aba = _get_aba("Despesas", ["data", "remetente", "valor", "categoria", "descricao"])
    registros = aba.get_all_records()

    mes_atual = date.today().strftime("%Y-%m")
    gastos_mes = [
        r for r in registros
        if str(r["data"]).startswith(mes_atual) and str(r["remetente"]) == str(remetente)
    ]

    if not gastos_mes:
        return "💰 Nenhuma despesa registrada esse mês ainda."

    total = sum(float(r["valor"]) for r in gastos_mes)
    por_categoria: dict[str, float] = {}
    for r in gastos_mes:
        cat = r["categoria"]
        por_categoria[cat] = por_categoria.get(cat, 0) + float(r["valor"])

    linhas = [f"💰 Despesas de {mes_atual}", f"Total: R$ {total:.2f}", ""]
    for cat, valor in sorted(por_categoria.items(), key=lambda x: -x[1]):
        linhas.append(f"- {cat}: R$ {valor:.2f}")

    return "\n".join(linhas)


# --- Refeições / Água / Peso ---

def registrar_refeicao(remetente: str, data_str: str, dados: dict) -> None:
    aba = _get_aba("Refeicoes", ["data", "remetente", "descricao", "calorias", "proteina_g", "carboidrato_g", "gordura_g"])
    aba.append_row([
        data_str, remetente, dados["descricao"], dados["calorias"],
        dados["proteina_g"], dados["carboidrato_g"], dados["gordura_g"],
    ])


def registrar_agua(remetente: str, data_str: str, quantidade_ml: float) -> None:
    aba = _get_aba("Agua", ["data", "remetente", "quantidade_ml"])
    aba.append_row([data_str, remetente, quantidade_ml])


def registrar_peso(remetente: str, data_str: str, peso_kg: float) -> None:
    aba = _get_aba("Peso", ["data", "remetente", "peso_kg"])
    aba.append_row([data_str, remetente, peso_kg])


def resumo_dieta_do_dia(remetente: str) -> str:
    hoje = date.today().isoformat()

    aba_refeicoes = _get_aba("Refeicoes", ["data", "remetente", "descricao", "calorias", "proteina_g", "carboidrato_g", "gordura_g"])
    refeicoes = [
        r for r in aba_refeicoes.get_all_records()
        if str(r["data"]) == hoje and str(r["remetente"]) == str(remetente)
    ]

    aba_agua = _get_aba("Agua", ["data", "remetente", "quantidade_ml"])
    aguas = [
        r for r in aba_agua.get_all_records()
        if str(r["data"]) == hoje and str(r["remetente"]) == str(remetente)
    ]

    if not refeicoes and not aguas:
        return "🥗 Nenhum registro de dieta hoje ainda."

    total_cal = sum(float(r["calorias"]) for r in refeicoes)
    total_prot = sum(float(r["proteina_g"]) for r in refeicoes)
    total_carb = sum(float(r["carboidrato_g"]) for r in refeicoes)
    total_gord = sum(float(r["gordura_g"]) for r in refeicoes)
    total_agua = sum(float(a["quantidade_ml"]) for a in aguas)

    linhas = [f"🥗 Dieta de hoje ({hoje})", ""]

    if refeicoes:
        linhas.append(f"🔥 Calorias: {total_cal:.0f} kcal")
        linhas.append(f"🥩 Proteína: {total_prot:.0f} g")
        linhas.append(f"🍞 Carboidrato: {total_carb:.0f} g")
        linhas.append(f"🥑 Gordura: {total_gord:.0f} g")

    if aguas:
        linhas.append(f"💧 Água: {total_agua:.0f} ml")

    return "\n".join(linhas)
