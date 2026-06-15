# Da Narrativa ao Número — Arquitetura de Software e Roadmap de Implementação

**Projeto:** Estratégia quantitativa baseada em features qualitativas geradas por LLM sobre comunicação do Copom, integradas a modelos de previsão de volatilidade e retorno no mercado brasileiro (Itaú Asset Quant AI 2026).

**Versão do documento:** 1.0 — Junho/2026

---

## 1. Regra-mãe do projeto

> **Nenhum dado entra em feature, universo, preço ajustado, score ou fundamento se não puder provar `available_time <= as_of`.**

Esta frase é simultaneamente o critério de arquitetura, de teste e de auditoria. Toda decisão estrutural deste documento deriva dela. O projeto não é um sistema online: é um **pipeline científico auditável**, e sua propriedade arquitetural dominante não é performance, mas **correção temporal (point-in-time) e reprodutibilidade**.

## 2. Princípios arquiteturais

**Monolito modular em Python.** O sistema é um pipeline batch de pesquisa, sem requisito de latência ou de serviço multiusuário. Um monolito com fronteiras rígidas entre camadas elimina a complexidade operacional de microsserviços sem sacrificar a separação de responsabilidades.

**Modelagem bitemporal.** Todo registro carrega dois timestamps obrigatórios: `event_time` (a que período o dado se refere) e `available_time` (quando se tornou público — ata do Copom na terça às 8h BRT, comunicado às 18h30 do dia da decisão, fundamento na data de entrega à CVM). Datetimes sempre tz-aware via `zoneinfo`, conforme recomendação da documentação do Python, eliminando bugs de fuso na sincronização com Fed/ECB/BoE.

**Chokepoint único de leitura.** Existe exatamente um caminho de código entre a camada validada (`silver`) e os datasets de treino (`gold`): o `PointInTimeRepository`, cuja API obrigatória é `repo.as_of(timestamp)`. Nenhum módulo de `features/` lê Parquet diretamente. A regra-mãe deixa de ser convenção e vira barreira executável, reforçada por teste de arquitetura (import-linter) que proíbe I/O direto fora do repository.

**Imutabilidade como defesa.** `data/raw/` nunca é alterado após a escrita — é o que permite reconstruir todo o pipeline quando uma fonte muda de API. O cache de scoring LLM é igualmente imutável: scores nunca são recalculados silenciosamente.

**Config declarativa, experimento rastreável.** Cada experimento é um arquivo YAML validado por Pydantic. Uma ablação (`features.global_layer: false`) é literalmente um diff de config, auditável no Git. O hash da config canônica (serialização ordenada via `model_dump_json()`, nunca o YAML cru) chaveia os artefatos, garantindo que configs semanticamente idênticas mapeiem para o mesmo diretório.

**Notebooks consomem, não definem.** Notebooks vivem em `notebooks/exploratory/` e leem artefatos do pipeline. Nunca são fonte da verdade.

## 3. Stack tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Linguagem | Python 3.12+ | Ecossistema padrão de quant research, cobre todas as camadas |
| Manipulação | Polars (ou pandas) | Performance e API expressiva para joins temporais |
| Armazenamento | Parquet particionado + DuckDB | Append-only, versionável em disco, consultável sem servidor |
| Validação de registros | Pydantic v2 | Schemas de configs e registros individuais |
| Validação de DataFrames | pandera | Invariantes no nível da tabela (ex.: `available_time >= event_time` como check declarativo) |
| Modelos ML | LightGBM, XGBoost, scikit-learn | Gradient Boosting e Random Forest do protocolo |
| Benchmarks econométricos | arch (GARCH), statsmodels (HAR-RV, Diebold-Mariano) | Comparação justa exigida pela Fase 1 |
| Scoring LLM | SDK do provedor, model string fixado (snapshot datado) | Determinismo máximo possível; `model_id` retornado é gravado junto ao score |
| Clientes HTTP | httpx + tenacity | Ingestão idempotente e retomável (BCB SGS, Focus, CVM) |
| CLI | Typer | Help automático e validação de tipos via type hints |
| Configuração | Pydantic Settings (+ YAML) | Experimentos declarativos |
| Testes | pytest + hypothesis | Property-based testing para invariantes temporais |
| Calendário | exchange_calendars | Fonte única para pregões da B3 |
| Tracking | MLflow ou diretório `runs/` com JSON | Cada número do relatório aponta para uma run reproduzível |

## 4. Estrutura de diretórios

```
narrativa-numero/
├── pyproject.toml          # src-layout, entry point: narrativa = "narrativa.cli:app"
├── configs/                # experimentos declarativos (ablações = diffs de config)
├── prompts/                # versionados: copom_v1.md, fed_v1.md, ...
├── src/
│   └── narrativa/
│       ├── core/           # tipos bitemporais, calendário B3, config, logging
│       ├── contracts/      # schemas Pydantic + pandera (macro, documents, features, ...)
│       ├── ingestion/      # adapters: BCB SGS, Focus, CVM, Copom, Fed/ECB/BoE
│       ├── corpus/         # parsing e normalização textual (atas, comunicados)
│       ├── scoring/        # cliente LLM, embeddings, cache imutável
│       ├── marketdata/     # preços, proventos, amortizações, retorno total, universo PIT
│       ├── features/       # PointInTimeRepository e construção de datasets
│       ├── models/         # HAR-RV, GARCH, RF, LightGBM (Strategy + Factory)
│       ├── backtest/       # walk-forward, métricas, teste Diebold-Mariano
│       ├── experiments/    # runner, tracking, artefatos
│       └── cli.py          # Typer: ingest, score, build-features, run, validate
├── data/
│   ├── raw/                # resposta original das fontes — imutável
│   ├── bronze/             # opcional: só para fontes com parsing trabalhoso (atas, CVM)
│   ├── silver/             # tabelas limpas, validadas e bitemporais
│   └── gold/
│       └── {config_hash}/  # dataset.parquet + config.json resolvida (hash reversível)
├── runs/                   # resultados: hash da config + commit do Git
├── notebooks/
│   └── exploratory/        # consomem artefatos; nunca definem o pipeline
└── tests/
```

Notas sobre a árvore: o módulo `fundamentals/` só ganha pasta própria se derivar indicadores (ROE, DL/EBITDA calculados); enquanto for apenas ingestão CVM, vive em `ingestion/` + `contracts/`. A camada `bronze` é pulada para fontes de normalização trivial (JSON do SGS vai direto de `raw` para `silver`).

## 5. Camadas e responsabilidades

**core/** define os tipos bitemporais compartilhados, a regra de alinhamento de calendário em um único lugar (ata às 8h BRT → disponível no pregão do mesmo dia; comunicado às 18h30 → pregão seguinte; comunicados globais convertidos pelo horário real com fuso) e a config base.

**contracts/** materializa os campos obrigatórios — `event_time`, `available_time`, `source`, `revision_id`, `asset_id`, `as_of`, `calendar_date` — como schemas Pydantic (registros e configs) e pandera (DataFrames). Sobre `revision_id`: vintages históricos de séries macro revisadas (IPCA, séries do BCB) só são capturáveis daqui para frente; para o passado, usa-se a base em tempo real do próprio BCB quando disponível, ou documenta-se a limitação como ameaça à validade declarada — nunca se finge que o backtest de 2015 viu o vintage de 2015.

**ingestion/** implementa interfaces por tipo de fonte (`MacroProvider`, `DocumentProvider`, `FundamentalsProvider`) com adapters concretos. Ingestão idempotente e retomável via tenacity, escrevendo sempre em `raw/` antes de qualquer transformação.

**corpus/** transforma atas e comunicados (HTML/PDF) em texto normalizado com metadados de publicação. Corpus central: Copom desde 1998. Corpus auxiliar: Fed (primário), ECB, BoE.

**scoring/** produz os scores qualitativos (postura hawkish/dovish, incerteza, mudança semântica via embeddings, diferencial Copom−Fed, surpresa frente ao Focus). O score é função pura de `(hash_do_texto, prompt_version, model_id)` e é persistido em cache imutável. Prompts são arquivos versionados em `prompts/`, nunca strings inline. Duas defesas explícitas: temperatura 0 **não garante** determinismo total em LLMs via API, então o `model_id` efetivo retornado pela resposta é gravado junto ao score para detectar drift; e, se o provedor descontinuar o modelo, o cache imutável é o que preserva a auditabilidade dos scores históricos.

**marketdata/** trata o que mais contamina resultado depois de vazamento macro: retorno total de FIIs usa a **data ex** do provento (não a data de pagamento — o erro desloca o retorno em ~15 dias e cria vazamento sutil); amortizações de FIIs de papel não são dividendo e exigem ajuste de cota; o universo é point-in-time (dezenas de FIIs foram incorporados/deslistados desde 2010 — usar a lista atual da B3 introduz survivorship bias). Fonte preferencial de proventos: FNET/B3, não agregadores.

**features/** contém o `PointInTimeRepository` — único ponto de filtragem `available_time <= as_of` — e a materialização dos datasets `gold/`, alinhados ao pregão da B3.

**models/** segue o padrão Strategy: interfaces `VolatilityModel` e `ReturnModel`, com HAR-RV, GARCH, LightGBM e Random Forest como implementações intercambiáveis instanciadas por Factory a partir da config. Benchmark e candidato passam pelo mesmo pipeline de avaliação — comparação justa por construção.

**backtest/** implementa o walk-forward como Template Method: o esqueleto (janelas, refit, coleta de previsões out-of-sample) é fixo; modelo e conjunto de features são injetados. Inclui ablação (cada camada auxiliar só permanece se superar a versão sem ela) e teste de significância Diebold-Mariano contra os benchmarks.

**experiments/** orquestra runs: resolve config, calcula hash canônico, executa o pipeline, grava artefatos em `runs/` com o commit do Git.

## 6. Padrões de projeto

| Padrão | Onde | Por quê |
|---|---|---|
| Adapter | `ingestion/` | Fontes externas substituíveis atrás de contratos estáveis |
| Repository | `features/PointInTimeRepository` | Acesso a dados centralizado e auditável; encapsula a regra-mãe |
| Strategy | `models/` | Benchmarks e candidatos intercambiáveis sob a mesma interface |
| Factory | `models/` | Instanciação de modelos a partir da config declarativa |
| Template Method | `backtest/` | Esqueleto fixo do walk-forward, variação injetada |
| Memoização content-addressed | `scoring/` | Cache imutável chaveado por hash de conteúdo |

Padrões deliberadamente **evitados**: Observer/eventos — pipeline batch determinístico se beneficia de fluxo explícito e linear. Orquestração pesada (Airflow) é peso morto; Typer + Makefile (ou Prefect, se necessário) basta.

## 7. Estratégia de testes

Para este projeto, teste não é apenas qualidade de software — é **defesa contra autoengano estatístico**. Os testes de invariantes temporais usam hypothesis (property-based) para gerar combinações que não seriam imaginadas manualmente: documento publicado em feriado, ata caindo na transição de horário de verão americano, comunicado global fora do pregão brasileiro.

```
tests/
├── test_point_in_time_joins.py      # nenhum join viola available_time <= as_of
├── test_calendar_alignment.py       # regra de alinhamento codificada uma única vez
├── test_llm_cache_key.py            # score é função pura da chave de cache
├── test_walk_forward_no_leakage.py  # janelas de treino nunca veem o futuro
├── test_total_return.py             # data ex, amortização, ajuste de cota
└── test_architecture.py             # import-linter: features/ não faz I/O direto
```

Comando dedicado de validação: `narrativa validate --stage silver` roda os checks pandera isoladamente, fora do fluxo de experimento.

## 8. Roadmap de implementação

O roadmap segue a lógica de risco do projeto: primeiro a fundação anti-vazamento (que não pode ser retrofitada), depois dados, depois o diferencial (scoring), e só então modelos — alinhado às Fases 1 e 2 do protocolo da estratégia.

### Sprint 0 — Fundação (1–2 semanas)

Esqueleto do repositório com src-layout formal: `pyproject.toml`, instalação editável, entry point da CLI. Implementação de `core/` (tipos bitemporais, calendário B3 via exchange_calendars, regra de alinhamento de publicação), `contracts/` (schemas Pydantic + pandera com o invariante `available_time >= event_time`) e o `PointInTimeRepository` com a filtragem `as_of`. Primeiro teste hypothesis tentando violar o invariante e teste de arquitetura com import-linter. **Critério de saída:** a regra-mãe é executável e tem teste que falha quando violada. Nada de dados reais ainda.

### Sprint 1 — Ingestão e marketdata (2–3 semanas)

Adapters de macro (BCB SGS: Selic, IPCA, câmbio), expectativas (Focus/Expectativas) e corpus Copom (atas e comunicados desde 1998, com `available_time` correto). Módulo `marketdata/` com preços de FIIs por subtipo (tijolo, papel-CDI, papel-IPCA), ações de construção/varejo e PETR4 como controle; proventos via FNET/B3; retorno total com data ex e tratamento de amortização; universo point-in-time. Pipeline `raw → (bronze) → silver` com validação pandera. **Critério de saída:** `narrativa ingest` e `narrativa validate` funcionais; série de retorno total de um FII reconciliada manualmente contra fonte independente.

### Sprint 2 — Scoring LLM (2 semanas)

Cliente LLM com prompts versionados (`copom_v1.md`), execução com temperatura 0 e model string fixado, cache imutável chaveado por `(hash_texto, prompt_version, model_id)`, gravação do `model_id` efetivo. Scores de postura, incerteza e mudança semântica via embeddings para o corpus Copom completo. Primeira passada idempotente e retomável (tenacity) — o corpus desde 1998 tem custo de API relevante e a re-execução deve ser zero. **Critério de saída:** corpus Copom 100% escorado, cache validado por `test_llm_cache_key`, inspeção qualitativa de uma amostra de scores contra leitura humana.

### Sprint 3 — Feature store e benchmarks (2 semanas)

Materialização dos datasets `gold/{config_hash}/` alinhados ao pregão. Implementação dos benchmarks da Fase 1 (HAR-RV e GARCH via Strategy) e da métrica de volatilidade realizada. Walk-forward funcional como Template Method, ainda sem features LLM. **Critério de saída:** benchmark HAR-RV reproduz resultados plausíveis da literatura para o mercado brasileiro; pipeline completo roda de config a `runs/` com um comando.

### Sprint 4 — Fase 1 do protocolo: volatilidade (3 semanas)

LightGBM e Random Forest com as três camadas de features (macro, fundamentos, qualitativa). Ablação completa: cada camada auxiliar só permanece se superar a versão sem ela, fora da amostra, com Diebold-Mariano contra HAR-RV/GARCH. Validação priorizando janela posterior ao cutoff do LLM para neutralizar o retrovisor do conhecimento de treino. Conversão da previsão de volatilidade em dimensionamento de risco. **Critério de saída:** resposta clara e auditável à pergunta central — a feature qualitativa adiciona valor estatisticamente significativo sobre os benchmarks?

### Sprint 5 — Fase 2 do protocolo: retorno relativo (3 semanas)

Previsão de retorno relativo na janela pós-Copom sobre o gradiente de sensibilidade a juros (FIIs → construção/varejo → PETR4 como controle). Teste falsificável do mecanismo: o poder preditivo deve escalar com a sensibilidade a juros. Configuração do long/short orientado à Selic com o dimensionamento de risco da Fase 1. **Critério de saída:** o gradiente de poder preditivo é medido e reportado, confirme ou refute o mecanismo.

### Sprint 6 — Corpus global e medidas futuras (2+ semanas, condicional)

Corpus auxiliar Fed/ECB/BoE com alinhamento de fuso, diferencial de postura Copom−Fed, e — se as fases anteriores justificarem — a extração de temas citados pelo Copom cruzados com base point-in-time de notícias/indicadores (intensidade contextual de petróleo, Fed, China, risco fiscal, câmbio, commodities, guerra). Cada adição entra como variável auxiliar e só permanece se sobreviver à ablação. **Critério de saída:** relatório final com todas as runs rastreáveis por hash + commit.

### Dependências críticas entre sprints

A ordem não é negociável nos seguintes pontos: o `PointInTimeRepository` (Sprint 0) precede qualquer dado real, porque retrofitar point-in-time em dados já materializados é a fonte clássica de vazamento; o retorno total reconciliado (Sprint 1) precede qualquer backtest, porque erro de data ex contamina tudo a jusante; e os benchmarks (Sprint 3) precedem os modelos ML (Sprint 4), porque sem baseline não há afirmação defensável sobre o valor da feature qualitativa.

## 9. Riscos arquiteturais monitorados

| Risco | Mitigação |
|---|---|
| Vazamento temporal por join ad hoc | Chokepoint único (`PointInTimeRepository`) + import-linter + hypothesis |
| Revisões de séries macro | Campo `revision_id`; vintages capturados daqui para frente; limitação histórica documentada |
| Não-determinismo do LLM apesar de temperatura 0 | Model string fixado + `model_id` gravado + cache imutável |
| Descontinuação do modelo LLM pelo provedor | Cache imutável preserva scores históricos auditáveis |
| Survivorship bias no universo de FIIs | Universo point-in-time, não a lista atual da B3 |
| Erro de data ex / amortização em retorno total | Fonte FNET/B3 + `test_total_return` + reconciliação manual |
| Sobrescrita de datasets entre ablações | `gold/{config_hash}/` com hash canônico da config Pydantic |
| Divergência da regra de calendário | Regra codificada uma única vez em `core/` + `test_calendar_alignment` |
| Custo e rate limit do scoring (corpus desde 1998) | Cache imutável + ingestão idempotente e retomável |