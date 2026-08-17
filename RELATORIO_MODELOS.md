# Relatório — Comparativo de modelos e o instrumento de tom (divergência ata × comunicado)

> CopomLens · Desafio Quant AI · Itaú Asset Management 2026
> Status: validação v0.1 — instrumento de tom da camada 4 fechado e determinístico.

---

## 1. Sumário executivo

O objetivo era medir o **tom da comunicação do Copom relativo ao que já está precificado**, para testar se esse tom carrega informação **incremental** sobre a reação do DI 1Y, *além* da surpresa da decisão de juros.

O ponto de partida (prompt `copom_v2`) tinha um defeito estrutural: o *stance* extraído era dominado pela **decisão de juros**, não pela comunicação. A correção levou a três descobertas encadeadas e a um desfecho:

1. **A divergência é o instrumento certo** — `divergencia = tom(ata) − tom(comunicado)` da mesma reunião, medida por prompt de dois documentos (a ata *acrescenta* ao que o comunicado já revelava).
2. **A divergência contínua (float) não funciona em modelo pequeno** — o 14B local colapsa em passos grossos; os modelos fortes (32B/70B) extraem resolução fina, provando que a informação existe.
3. **Determinismo (`std=0`) só existe no backend local** — nenhum provedor remoto do OpenRouter garante saída bit-exata.

A solução que fecha as duas exigências — **determinismo + resolução** — foi pedir ao modelo a classificação **discreta** da divergência (`direcao` × `magnitude` × `eixo`) e derivar o número em código por um mapa determinístico (o mesmo desenho do `STANCE_MAP`).

**Resultado-manchete (produção, 14B local):**

| Métrica | Alvo (gates) | Medido | |
|---|---|---|---|
| Divergência não-nula | > 60% | **96,4%** (81/84) | ✅ passa |
| Determinismo (`std=0`) | 100% | **100%** (0/84 docs com std>0) | ✅ passa |

---

## 2. Contexto — por que o instrumento mudou

### 2.1 O problema do prompt v2

No `prompts/copom_v2.md`, os 15 rótulos de postura eram definidos **pelo tamanho do corte/alta** ("corte grande", "alta moderada"), a primeira das cinco dimensões era literalmente "Direção + magnitude da ação sobre a taxa de juros", e os 10 exemplos começavam todos pela decisão ("Aumentou a Selic em 1,00 p.p. …").

Medido contra a decisão (delta da Selic por reunião), quanto da variância do *stance* a decisão sozinha explica:

| Modelo | eta² (ANOVA, grupos de decisão) |
|---|---|
| Qwen3-32B (v2, arquivo) | **0,886** |
| Qwen2.5-14B (v3) | **0,455** |
| Qwen3-32B (v3) | **0,422** |

A descontaminação do prompt (v3, rótulos pela *comunicação*, sem decisão) derrubou o eta² de ~0,89 para ~0,45 — mas não zerou, porque o **tom da ata acompanha a decisão de verdade** (quando o Copom corta, a ata é dovish; quando sobe, hawkish). Esse residual é co-movimento real, não rótulo contaminado.

### 2.2 Por que o pareado-subtração não bastou

A hipótese original era `stance(ata) − stance(comunicado)`: os dois descrevem a mesma decisão, ela se cancela, sobra o tom.

Isso só vale quando **os dois lados espelham a decisão** — o que acontecia no v2 (comunicado ancorado na decisão). No v3, com a decisão fora dos critérios, **67 dos 84 comunicados colapsaram para `neutro`** (a "Nota à Imprensa" de 2006–2012 contém quase só a decisão). Sem tom no comunicado para cancelar, o pareado degenera em `stance_ata`:

| Instrumento | eta² vs decisão |
|---|---|
| stance bruto v2 (pooled) | 0,886 |
| stance bruto v3 (pooled) | 0,455 |
| pareado v3 (subtracção) | 0,621 |

Ou seja: a subtração de dois rótulos grossos (15 degraus) **não** era o caminho — a divergência precisava ser medida **diretamente**, como a issue original já antecipava.

### 2.3 A janela de dados

- **84 reuniões pareadas** (ata + comunicado com texto) entre as reuniões 116 e 199 (2006-01-18 a 2016-06-08), casadas com a janela viva do DI 1Y (SGS 7806) e com Focus por reunião (R1/2006+).
- Durante o trabalho, a reingestão recuperou **120 comunicados (46–165)** que estavam listados pelo BCB mas ausentes do manifesto (bug de auto-cura no `collect.py`).
- Foi corrigido um problema de qualidade: atas 200–227 eram **bytes de PDF parseados como texto** (lixo); o `parser.py` passou a pular arquivos não-`.txt` e o dataset foi reconstruído (463 linhas). O tone v2 tinha 28 pares contaminados por esse lixo.

---

## 3. Método e critérios de aceite

### 3.1 Gates (todos mensuráveis sem olhar o alvo DI 1Y)

| Gate | Alvo |
|---|---|
| eta²(stance ~ decisão) | < 30% |
| justificativa cita nível/magnitude/votação | < 20% |
| divergência não-nula | > 60% |
| determinismo: `std=0` em 100% (modelo de produção) | 100% |
| mode-share do `stance_label` | < 30% |

### 3.2 Métricas

- **eta²**: ANOVA de 1 via — variância entre grupos da decisão (delta da Selic) sobre variância total.
- **não-nulas**: fração de reuniões com `divergencia ≠ 0`.
- **`std`**: desvio-padrão entre `n_runs=3` execuções **com a mesma seed** (temperatura 0). `std=0` ⇔ mesma saída (determinismo bit-exato).

### 3.3 Modelos testados

| Modelo | Backend | Precisão | Observação |
|---|---|---|---|
| Qwen2.5-14B-Instruct-1M Q4_K_M | llama.cpp local (GPU ROCm) | quantizado Q4 | **produção** |
| Qwen3-32B | OpenRouter → Groq | plena (sem quantização) | reasoning |
| Llama-3.3-70B-Instruct | OpenRouter → Groq | plena (sem quantização) | não-reasoning |

---

## 4. Comparativo de divergência

### 4.1 Abordagem contínua (float `-1..1` pedido ao modelo)

| Modelo | Não-nula | Resolução | `std>0` | Veredito |
|---|---|---|---|---|
| 14B local | 46,4% (39/84) | colapso em ±0,25 | 0/84 (0%) | determinístico, sem resolução |
| 32B Groq | 94,1% (79/84) | fina (0,083–0,667) | 30/84 (36%) | resolvido, não-determinístico |
| 70B Groq | 98,2% (54/55) | fina (0,083–0,5) | 11/55 (20%) | resolvido, não-determinístico |

**Leitura:** os modelos fortes provam que a **informação existe** (94–98% de reuniões têm divergência não-nula, com resolução fina). O 14B tem a disciplina determinística, mas **não consegue** produzir o float contínuo — colapsa no degrau mínimo.

### 4.2 Abordagem discreta (produção)

O prompt de divergência passou a pedir classificação **discreta**:

```json
{
  "direcao": "<ata_mais_hawkish|igual|ata_mais_dovish>",
  "magnitude": "<leve|clara|forte|nenhuma>",
  "eixo_divergencia": "<riscos|conviccao|horizonte|condicionalidade|nenhum>",
  "justificativa_ata": "...",
  "justificativa_comunicado": "..."
}
```

E o número é derivado em código por `DIVERGENCIA_MAP` (como o `STANCE_MAP`):

```
divergencia = sinal(direcao) × {leve: 0.25, clara: 0.5, forte: 0.75}
```

**Resultado (14B local, produção):**

| Métrica | Valor |
|---|---|
| Não-nula | **96,4%** (81/84) |
| `std=0` | **100%** (0/84) |
| Distribuição | `{−0.5: 4, −0.25: 4, 0.0: 3, +0.25: 25, +0.5: 48}` |
| `direcao` | `ata_mais_hawkish` 73 · `ata_mais_dovish` 8 · `igual` 3 |
| `eixo` | `riscos` 78 · `condicionalidade` 3 · `nenhum` 3 |

A classificação discreta é o que o 14B faz bem (é o mesmo princípio que tornou o `stance` de 15 rótulos estável); o float contínuo é onde ele colapsa. O par de `justificativa_ata`/`justificativa_comunicado` torna cada linha auditável: dá para abrir qualquer reunião e ler *por que* aquele número é aquele.

### 4.3 Viés observado

A produção concentra em `ata_mais_hawkish` (73/84) e magnitude `clara` (52/84). É um viés direcional plausível — atas tipicamente acrescentam nuance de risco — mas merece menção no relatório como característica do instrumento (não é colapso: 5 dos 7 valores da grade são usados).

### 4.4 Controle negativo — Qwen2.5-7B (por que não dá certo)

Teste adicional com o **Qwen2.5-7B-Instruct-Q8_0** local (mesmo prompt discreto, mesma receita) para delimitar o piso de capacidade. Resultado:

| Métrica | Valor |
|---|---|
| Não-nula | **100%** (84/84) |
| `std=0` | **100%** (0/84) — determinístico |
| Distribuição | `{−0.5: 71, −0.25: 10, +0.25: 2, +0.5: 1}` |
| `direcao` | `ata_mais_dovish` 81 · `ata_mais_hawkish` 3 · `igual` 0 |
| `eixo` | `riscos` 84/84 (100%) |
| mode-share (divergência) | 84% em `−0.5` |

**O 7B "passa" o gate de não-nulas (100%) e o de determinismo (std=0) — e ainda assim está inútil.** Ele não discrimina: colapsa numa resposta única (`ata_mais_dovish` + `clara` + `riscos` = `−0.5`) em 71 de 84 reuniões. É o oposto do 14B discreto, que usa 5 valores com direção equilibrada.

**Conclusão metodológica:** o gate "divergência não-nula > 60%" é **necessário mas não suficiente** — precisa ser acompanhado de uma checagem de **discriminação** (mode-share / entropia da distribuição). O 14B discreto discrimina (mode-share 57%, 5 valores); o 7B degenera (mode-share 84%, 1 resposta dominante). O tone do 7B confirma a mesma degeneração: mode-share do `stance_label` de **73,2%** em `neutro` (o 14B tem 53,6%).

---

## 5. A questão do determinismo (`std = 0`)

**Determinismo não é flag de modelo — é propriedade do backend de inferência.**

Inferência remota (GPU/LPU) tem não-determinismo de ponto flutuante: a ordem de redução varia entre chamadas, e `seed` + `temperature=0` são *best-effort* através do roteamento do OpenRouter. Medido nesta validação:

| Backend | docs com `std>0` |
|---|---|
| Groq (qwen3-32B) | 44% (tone) · 36% (divergência) |
| Groq (llama-3.3-70B) | 20% (divergência) |

Um *probe* de 1 documento engana (o documento 116 saiu determinístico em 5 runs); só o corpus inteiro revela a não-determinidade. O único backend **bit-exato** é o llama.cpp local (greedy, pesos e seed fixos) — que é o modelo de produção, com `std=0` em 100% dos 168 documentos de tone e 84 de divergência.

---

## 6. Gates finais (produção — 14B local)

| Gate | Alvo | 14B | 32B Groq | 7B local | |
|---|---|---|---|---|---|
| eta²(stance ~ decisão) | < 30% | 45,5% | 42,2% | 35,1% | desvio documentado |
| justificativa cita decisão | < 20% | 92,9% | 76,2% | 79,8% | desvio documentado |
| determinismo `std=0` | 100% | **100%** | 44,4% | **100%** | 14B/7B ✅ |
| mode-share `stance_label` | < 30% | 53,6% | 58,9% | 73,2% | desvio (7B degenera) |
| **divergência não-nula** | > 60% | **96,4%** | 94,1% | **100%** ⚠️ | 7B degenera |

⚠️ O 7B "passa" o gate de divergência não-nula por acidente — 100% é colapso numa resposta única, não discriminação (ver §4.4).

Os três gates que seguem em desvio dizem respeito ao **stance absoluto** — que é **variável de controle** (o regressor da camada 4 é a divergência). Decisão registrada: **aceitar desvio documentado** (não calibrar contra o alvo). Os dois gates que importam para o instrumento de tom — **divergência não-nula** e **determinismo** — passam na produção, com a ressalva de que não-nula exige, junto, a checagem de discriminação (§4.4).

---

## 7. Detalhes técnicos encontrados (documentados)

1. **Groq rejeita `json_schema` strict no roteamento** (HTTP 404 "No endpoints found"). Solução: `response_format: {"type": "json_object"}` (garante JSON válido) + validação do schema em código (`promptExec._validate` / `divergencia._validate`), que já existia.
2. **Qwen3-32B é modelo reasoning**: sem desligar o *thinking*, os tokens vão para `reasoning` e o `content` sai `null` (estouro de `max_tokens`). Solução: `reasoning: {"enabled": false}` **condicional** (só para modelos reasoning), `max_tokens` 800 (tone) / 1600 (divergência), e `content=null` tratado como falha transiente (retry).
3. **Llama-3.3-70B não suporta o campo `reasoning`** — enviá-lo causaria erro; por isso o envio é condicional.
4. **PDFs parseados como texto**: atas 200–227 tinham bytes de PDF no dataset (lixo que contaminou o tone v2). `parser.py` agora pula não-`.txt`; dataset reconstruído.
5. **Auto-cura do manifesto**: o coletor pulava arquivos já existentes sem registrá-los no manifesto, perdendo 120 comunicados. Corrigido (registra mesmo sem reescrever).

---

## 8. Artefatos e custo

**Código/prompts novos ou alterados:**

- `prompts/copom_v3.md` — tone descontaminado (15 rótulos pela comunicação).
- `prompts/copom_v3_divergencia.md` — divergência em dois documentos, campos discretos.
- `src/copom/features/divergencia.py` — extração da divergência + `DIVERGENCIA_MAP` + CLI.
- `src/copom/features/pareamento.py` — pareado-subtração (controle) + diagnóstico eta².
- `src/copom/features/gates.py` — medição dos gates (sem tocar no alvo).
- `src/copom/models/llm_client.py` — `json_object`, reasoning condicional, `content=null`→retry, `max_tokens` 800.
- `src/copom/features/extract_tone.py` — `STANCE_MAP.get(..., NaN)` (rótulo desconhecido nunca vira neutro).
- `src/copom/ingest/collect.py`, `parser.py`, `surprise/surpresa.py` — auto-cura do manifesto, skip de PDF, dedup por reunião.

**Artefatos de dados (`data/processed/`):**

- `tone_results_v3.jsonl` (produção tone, 168 docs) · `tone_results_v3_32b.jsonl` · `tone_results_v3_7b.jsonl`
- `divergencia_tone.jsonl` (**produção**, discreto) · `divergencia_tone_32b.jsonl` · `divergencia_tone_70b.jsonl` · `divergencia_tone_7b.jsonl`
- `pares_tone.jsonl` · `gates_v3.json` · `gates_v3_32b.json` · `gates_v3_7b.json` · `painel_di1y.csv` · `funil_amostra.json`

**Custo OpenRouter:** US$ 4,29 dos US$ 5,00 da chave (restante US$ 0,71). Todo o restante foi inferência local gratuita.

---

## 9. Conclusões e próximos passos

1. **O instrumento de tom está fechado e determinístico**: divergência ata×comunicado por classificação discreta, 96,4% não-nulas, `std=0` em 100%, auditável linha a linha.
2. **A informação existe e foi provada por dois modelos fortes** (32B: 94%, 70B: 98% não-nulas) — a lacuna do 14B era de *formato* (float contínuo), resolvida pela decomposição discreta.
3. **Remoto não é determinístico**: a promessa de reprodutibilidade do README ("a banca obtém o mesmo JSON") só é verdadeira no 14B local — e é esse o modelo de produção.
4. **Há piso e teto de capacidade**: o 7B (determinístico) degenera numa resposta única — 100% não-nula é colapso, não discriminação; o gate de não-nulas precisa de uma checagem de discriminação junto. O 14B é o menor modelo que discrimina; 32B/70B discriminam mais ainda, mas não são determinísticos.

**Próximos passos (fora do escopo desta validação):**

- Fechar a camada 4 (comparação aninhada walk-forward: (1) surpresa → (2) + controles → (3) + divergência).
- Reavaliar os gates de desvio do stance (eta², justificativa, mode-share) se houver interesse em re-extrair com modelo mais forte — sem tocar no alvo.
- Documentar o viés hawkish da divergência e testar se é regime-dependente (Meirelles vs. Tombini).
- Se a amostra crescer (PDFs de 2016–2019 via OCR, proxy mensal do Focus), re-rodar o instrumento.

---

## 10. Reprodução

```bash
# dados (já gerados)
python -m copom.ingest.collect --last 300
python -m copom.ingest.marketdata
python -m copom.ingest.parser
python -m copom.surprise            # painel_di1y.csv + funil_amostra.json

# tone (produção local, determinístico)
python -m copom.models --ata-range 116:199 --output data/processed/tone_results_v3.jsonl

# divergência (produção local, discreta)
python -m copom.features.divergencia --range 116:199

# controles e gates
python -m copom.features.pareamento --tone data/processed/tone_results_v3.jsonl
python -m copom.features.gates

# testes
python -m pytest tests/ -q          # 128 passed, 2 skipped
```
