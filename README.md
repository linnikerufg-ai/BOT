# Assistente Unificado via WhatsApp — Despesas + Dieta

Combina os dois bots (despesas e dieta) num único webhook, já que o
número de teste da Meta é compartilhado entre os apps do mesmo
portfólio de negócios.

## Comandos

| Você manda | O bot faz |
|---|---|
| `gasto 45 no mercado` | Registra a **despesa** |
| Foto do prato | Registra a **refeição** (a Claude analisa a imagem) |
| `2 ovos e uma fatia de pão` (texto livre) | Registra a **refeição** |
| `agua 500` | Registra 500ml de água |
| `peso 78.5` | Registra seu peso do dia |
| `resumo` | Despesas do mês **+** dieta de hoje |
| `resumo despesas` | Só despesas do mês |
| `resumo dieta` | Só dieta de hoje |
| `ajuda` | Lista de comandos |

Todos entendem referências de tempo: "ontem", "anteontem", "N dias
atrás".

## ⚠️ Por que "gasto" é obrigatório

Sem um prefixo, o bot não teria como saber se "45 no mercado" é uma
**compra** (despesa) ou uma **refeição** que custou 45 reais de
alguma forma estranha. Como fotos e descrições livres de comida
tendem a ser o uso mais comum nesse bot combinado, decidi que:
- **Texto livre, sem prefixo** → vira refeição por padrão
- **Despesas exigem o prefixo `gasto`** → deixa a intenção explícita

## Planilha

Uma única planilha, com 4 abas criadas automaticamente:
- **Despesas**: data, remetente, valor, categoria, descrição
- **Refeicoes**: data, remetente, descrição, calorias, proteína, carboidrato, gordura
- **Agua**: data, remetente, quantidade em ml
- **Peso**: data, remetente, peso em kg

Pode usar a mesma planilha que você já tinha no projeto de despesas —
as abas novas (Refeicoes, Agua, Peso) são criadas sozinhas, sem mexer
na aba Despesas existente.

## Migração — o que fazer com os projetos antigos

1. **Para os dois servidores antigos** (`assistente-despesas-whatsapp`
   e `dieta-ai-whatsapp`) — se estiverem rodando, dá Ctrl+C nos dois
2. Só esse projeto (`assistente-unificado-whatsapp`) deve ficar
   rodando daqui pra frente
3. No painel da Meta, você só precisa manter o **webhook de um dos
   dois apps** configurado (apontando pra esse servidor unificado) —
   pode até desativar/ignorar o segundo app, já que o número de teste
   é o mesmo mesmo

## Configuração

### 1. Variáveis de ambiente

```bash
cp .env.example .env
```

Preenche com:
- `ANTHROPIC_API_KEY`: a mesma chave que você já usa
- `GOOGLE_CREDENTIALS_PATH` e `GOOGLE_SHEET_ID`: pode reaproveitar os
  mesmos do projeto de despesas
- `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`: use as credenciais de
  **qualquer um** dos dois apps (recomendo o token permanente que
  você já gerou, pra não expirar em 24h)
- `META_VERIFY_TOKEN`: pode reaproveitar o que já usava

### 2. Instalar e rodar

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. ngrok + webhook

```bash
ngrok http 8000
```

Configura o Callback URL (URL do ngrok + `/webhook`) em **um dos dois
apps** da Meta — só precisa estar configurado em um, já que ambos
compartilham o mesmo número.

### 4. Testar

- `gasto 30 uber`
- Foto do almoço
- `agua 500`
- `resumo`
