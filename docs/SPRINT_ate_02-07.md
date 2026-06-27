# Sprint 0 — até a reunião de 02/07

**Janela:** 25/06 → 02/07 (~1 semana). **Objetivo:** sair de "ideia no papel" para uma **fatia vertical fina e demoável** — provar que o pipeline anda ponta a ponta em **um único evento**.

## Meta da reunião (definition of done do sprint)

> Repositório reorganizado + textos do Copom coletados com timestamp de publicação + **uma ata** rodada pelo extrator LLM local devolvendo o JSON + baseline léxico calculado na mesma ata + um notebook mostrando os dois lado a lado.

Nenhuma camada 4/5 (modelo/backtest) ainda — é cedo.

## Sequência e dependências

As tarefas são **encadeadas**: cada etapa só começa quando a anterior fecha. Dentro de uma etapa, o que está na mesma linha roda em **paralelo**.

```
ETAPA 0   #1 base do repo (merge da PR) ......................... todos
              │
              ▼
ETAPA 1   #2 ingest atas (Gustavo)   #6 marketdata (Rafael)   #7 identidade (Elder)
              │                            
              ▼                            
ETAPA 2   #3 dataset point-in-time (Gustavo + Rafael)  ◄── precisa de #2
              │
              ▼
ETAPA 3   #4 extract_tone LLM (Gustavo)     #5 baseline léxico (Elder)  ◄── ambos precisam de #3
              │__________________________________│
                               ▼
ETAPA 4   #8 notebook EDA: LLM vs léxico (Elder + Gustavo)  ◄── precisa de #4 e #5
```

| # | Tarefa | Dono | Depende de | Bloqueia |
|---|---|---|---|---|
| 1 | Base do repo (esta PR) | Elder + Gustavo | — | tudo |
| 2 | Ingest atas/comunicados (API BCB) | **Gustavo** | #1 | #3 |
| 3 | Dataset point-in-time (parse + timestamp) | **Gustavo + Rafael** | #2 | #4, #5 |
| 4 | `extract_tone()` em LLM local (1 ata) | **Gustavo** | #3 | #8 |
| 5 | Baseline léxico hawkish/dovish *(back do Elder)* | **Elder** (+ Rafael/validação estatística) | #3 | #8 |
| 6 | Selic + Focus → surpresa da decisão | **Rafael** | #1 | (Sprint 1) |
| 7 | Identidade/nome do robô (critério 5%) | **Elder** | #1 | — |
| 8 | Notebook EDA: LLM vs léxico | **Elder + Gustavo** | #4, #5 | — |

## Carga por pessoa (todos codam back)

- **Gustavo** — espinha do pipeline: #2 → #3 → #4 (e ajuda no #8). É o caminho crítico.
- **Rafael** — #6 (dados de mercado, paralelo) + co-dono do #3. Coordena a entrada da validação estatística.
- **Elder** — #7 (leve, na Etapa 1) **e #5 (back de verdade: módulo Python do léxico)** na Etapa 3, fechando com o #8. Começa o léxico contra uma ata de exemplo enquanto a espinha #2→#3 anda, e conecta ao `data/processed/` quando o #3 fica pronto.

## Caminho crítico e folga

- **Crítico:** #1 → #2 → #3 → #4 → #8. Se isso atrasar, a fatia vertical não fecha.
- **Folga (paralelo, começam já na Etapa 1):** #6 e #7 não dependem da espinha — destravar no dia 1 para ninguém ficar ocioso esperando.
- **Risco do #5:** o módulo do léxico (lógica de contagem + lista de termos) pode ser prototipado **antes** de #3 ficar pronto, usando uma ata colada à mão; só a ligação ao dataset processado espera o #3.

## O que NÃO fazer ainda

Modelo preditivo, walk-forward, backtest, P&L, estratégia. Isso é Sprint 1+, depois da fatia vertical validar a viabilidade e da validação estatística entrar no time.

## Para a reunião de 02/07, levar

1. Repo reorganizado e cada um com ≥ 1 PR mergeado.
2. A fatia vertical rodando (notebook #8).
3. Lista honesta de bloqueios (ex.: fonte de DI 1Y, custo/latência do modelo local).
