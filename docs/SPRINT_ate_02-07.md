# Sprint 0 — até a reunião de 02/07

**Janela:** 25/06 → 02/07 (~1 semana). **Objetivo:** sair de "ideia no papel" para uma **fatia vertical fina e demoável** — provar que o pipeline anda ponta a ponta em **um único evento**.

## Meta da reunião (definition of done do sprint)

> Repositório reorganizado + textos do Copom coletados com timestamp de publicação + **uma ata** rodada pelo extrator LLM local devolvendo o JSON + baseline léxico calculado na mesma ata + um notebook mostrando os dois lado a lado.

Isso valida a hipótese tecnicamente **antes** de investir em modelagem. Nenhuma camada 4/5 ainda — é cedo.

## Tarefas → PRs

Cada item é **uma branch + uma PR pequena e revisável**. Dono sugerido entre parênteses.

| # | PR (branch) | Entrega | Dono | Aceite |
|---|---|---|---|---|
| 1 | `chore/reorg-estrutura` | Estrutura, README, CONTRIBUTING, templates (esta base) | Elder + Gustavo | `pip install -e .` funciona; árvore de pastas no lugar |
| 2 | `feat/ingest-copom` | Coletor de atas + comunicados via [API/dataset do BCB](https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom); salva em `data/raw/` com manifesto (`url`, `data_publicacao`, `data_reuniao`, `tipo`) | Gustavo | ≥ 20 atas baixadas; manifesto com data de **publicação** real |
| 3 | `feat/pit-dataset` | Parse do HTML/PDF → texto limpo; carimba `available_time` (publicação) → `data/processed/` | Gustavo + Rafael | 1 documento parseado e inspecionado manualmente |
| 4 | `feat/extract-tone-poc` | `prompts/copom_v1.md` + `extract_tone()` rodando **1 ata** num LLM local (Ollama, ex. `llama3.1`/`qwen2.5`); roda 3× e mostra estabilidade do score | Gustavo + Rafael | JSON válido conforme schema; scores estáveis entre execuções |
| 5 | `feat/lexico-baseline` | Lista PT hawkish/dovish + índice por contagem; score na mesma ata da #4 | Rafael (+ validação estatística quando entrar) | número de tom léxico para a ata, comparável ao LLM |
| 6 | `feat/marketdata-selic-focus` | Selic e mediana do Focus via [BCB SGS / Expectativas](https://dadosabertos.bcb.gov.br/dataset); estrutura para DI 1Y (fonte a definir) | Rafael | série puxada e salva; surpresa da decisão calculável para 1 reunião |
| 7 | `docs/identidade-robo` | Brainstorm de nome + identidade do robô (critério 5%) — coerente com a tese (tom/DI) | Elder | 3 propostas de nome + 1 parágrafo de identidade |
| 8 | `docs/eda-notebook` | Notebook lendo a 1ª ata: texto + score LLM + score léxico lado a lado | Elder + Gustavo | notebook roda do zero e renderiza a comparação |

## Ordem e dependências

- #1 primeiro (todos dependem da estrutura).
- #2 → #3 → #4/#5 em sequência (precisam do texto coletado e carimbado).
- #6 e #7 são **paralelos** (não dependem das outras) — bons para destravar trabalho desde o dia 1.
- #8 fecha o sprint juntando #4 e #5.

## O que NÃO fazer ainda

Modelo preditivo, walk-forward, backtest, P&L, estratégia. Isso é Sprint 1+, depois da fatia vertical validar a viabilidade e da validação estatística entrar no time.

## Para a reunião de 02/07, levar

1. Repo reorganizado e cada um com ≥ 1 PR mergeado.
2. A fatia vertical rodando (notebook #8).
3. Lista honesta de bloqueios encontrados (ex.: achar fonte boa de DI 1Y, custo/latência do modelo local).
