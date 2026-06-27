# CopomLens — Uma lente sobre o que o Banco Central realmente está dizendo

> Estratégia quantitativa que mede o **tom da comunicação do Copom relativo ao que já está precificado**, e testa se esse tom — extraído por LLM — carrega informação **incremental** sobre a reação do **DI de 1 ano**.
>
> Desafio Quant AI · Itaú Asset Management 2026 · **Status: validação (v0.1)**

---

## A ideia em um parágrafo

Prever o *número* da Selic não tem valor: o mercado já o antecipa via Focus e curva de DI. O alfa potencial está no **conteúdo qualitativo** da comunicação do Copom — tom, *forward guidance*, convicção, incerteza — sobretudo na **ata**. Nossa hipótese, deliberadamente **falsificável**, é que esse tom carrega informação incremental sobre a reação do DI 1Y, **além** da surpresa da decisão de juros e **além** de um baseline léxico (dicionário hawkish/dovish). *"Não há ganho incremental"* é um resultado válido e será reportado como tal.

O entregável é uma **estratégia backtestada** (sinal → posição em DI 1Y → P&L líquido de custos), **não** um produto ou ferramenta.

---

## Regra cardinal — point-in-time

> **Nenhum texto ou feature influencia um retorno se não puder provar que já era público naquele instante.**

Cada artefato é carimbado com o **timestamp real de publicação** (a ata sai na semana seguinte à reunião, não na data da reunião), nunca com a data do evento. Ignorar isso (viés de *lookahead*) é a falha mais comum e mais fatal em estratégias baseadas em texto — e é o primeiro critério de auditoria deste projeto.

---

## Pipeline (5 camadas)

| # | Camada | Pasta | O que faz |
|---|---|---|---|
| 1 | Ingestão + timestamping | `src/copom/ingest/` | Coleta atas/comunicados (API BCB) e séries; carimba a data de publicação |
| 2 | Extração de tom (CopomLens) | `src/copom/features/` | LLM local determinístico → JSON auditável **+** baseline léxico |
| 3 | Surpresa precificada | `src/copom/surprise/` | `surpresa = Selic_efetiva − Selic_esperada` (Focus / DI) |
| 4 | Modelo preditivo | `src/copom/models/` | Comparação aninhada walk-forward: (1) só surpresa → (2) + léxico → (3) + tom-LLM |
| 5 | Estratégia + backtest | `src/copom/strategy/`, `src/copom/backtest/` | Sinal → posição DI 1Y → P&L líquido de custos → Sharpe, drawdown |

**Resultado-manchete:** o ganho incremental out-of-sample entre (1) → (2) → (3).

---

## CopomLens — extrator de tom como função determinística

A CopomLens **não é o produto**; é uma função determinística (temperatura 0) que recebe texto e devolve números auditáveis. Saída estruturada:

```json
{
  "stance": 0.0,
  "stance_delta": 0.0,
  "forward_guidance": "neutro",
  "incerteza": 0.0,
  "conviccao": 0.0,
  "justificativa": "..."
}
```

Usamos um **modelo open-source local** (pesos fixados, *greedy decoding*): a banca pode rodar o código e obter **exatamente o mesmo JSON** — reprodutibilidade que uma API fechada não garante. **Sem fine-tuning** (amostra pequena demais). O prompt é versionado em `prompts/` e instrui o modelo a pontuar **apenas pelo texto fornecido**, sem inferir o desfecho.

---

## Estrutura do repositório

```
Desafio_ITAU/
├── data/
│   ├── raw/          # textos do Copom + séries — imutável (não versionado)
│   └── processed/    # dataset point-in-time, features
├── src/copom/
│   ├── ingest/       # camada 1: coleta + timestamping (API BCB)
│   ├── features/     # camada 2: CopomLens (LLM local) + baseline léxico
│   ├── surprise/     # camada 3: surpresa da decisão
│   ├── models/       # camada 4: walk-forward, comparação aninhada
│   ├── strategy/     # camada 5: sinal → posição
│   └── backtest/     # P&L, custos, Sharpe, drawdown
├── prompts/          # copom_v1.md — prompt versionado da CopomLens
├── notebooks/        # EDA e resultados (consomem o pipeline, não o definem)
├── docs/             # identidade, realinhamento, decisões, sprint
└── tests/
```

---

## Stack

Python 3.11+ · `pandas` · `scikit-learn` · `statsmodels` · `httpx` (ingestão API BCB) · LLM local via [Ollama](https://ollama.com) (ou `transformers`) · `jupyter`. Deliberadamente enxuta: a prioridade é **correção e reprodutibilidade**, não sofisticação de stack.

---

## Reprodutibilidade

- Modelo LLM local com pesos e versão fixados; `model_id` e *seed* gravados junto ao score.
- `data/raw/` é **imutável**: permite reconstruir todo o pipeline.
- Notebooks **consomem** artefatos; nunca são fonte da verdade.

---

## Limitações (reportadas, não escondidas)

Amostra pequena (poucas centenas de reuniões; ~8/ano) → risco de overfitting, mitigado por modelos simples e walk-forward · não-estacionariedade de regime · contaminação por *hindsight* da LLM (baseline léxico é livre dela por construção) · janela tradeável estreita → realismo de custos.

---

## Documentação

- [`docs/IDENTIDADE_CopomLens.md`](docs/IDENTIDADE_CopomLens.md) — nome, logo, paleta, tagline e como usar no pitch
- [`docs/Realinhamento_Equipe.md`](docs/Realinhamento_Equipe.md) — decisões travadas, papéis e visão de deployment
- [`docs/SPRINT_ate_02-07.md`](docs/SPRINT_ate_02-07.md) — plano de atividades até a reunião de 02/07
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — convenções de branch, commit e PR

---

## Equipe

Rafael Ribas · Gustavo More · Elder Nunes — Engenharia da Computação, UTFPR-Apucarana.
Mentoria: Randerson Melville. Validação estatística: a confirmar.