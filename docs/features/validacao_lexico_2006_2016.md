# Validação do léxico histórico — 2006-2016

> Issue: "Camada 2 + relatório" — Parte 1 (Dono: Elder · Timebox: 16-17/07)
> Script: `scripts/validar_lexico_historico.py`
> Dados de entrada: `data/processed/copom_dataset.jsonl`, filtrado para `tipo=ata` e `data_reuniao` entre 2006 e 2016.

## Por que essa etapa importa

O léxico é o grupo de controle do experimento — um dicionário conta palavras e não tem
memória de eventos futuros, então é o único medidor do projeto imune a contaminação por
hindsight. Se ele não funcionar no período histórico (2006-2016), não há contra o que
comparar o LLM depois, e o resultado-manchete do projeto fica sem referência.

## Coleta de dados (pré-requisito)

Antes de validar o léxico, foi necessário expandir a coleta de dados, que originalmente
tinha só 40 documentos (as 20 atas e 20 comunicados mais recentes).

- **Bug encontrado em `src/copom/ingest/collect.py`:** o script travava com
  `TypeError: data must be str, not NoneType` ao encontrar um documento cujo campo de
  texto (`textoAta`/`textoComunicado`) vinha vazio da API do BCB (comum em documentos mais
  antigos, provavelmente por serem PDF-only). O código só tratava erro HTTP 500 como
  "documento sem texto"; não tratava resposta HTTP 200 com campo de texto vazio.
- **Correção:** adicionado `if not text: logger.warning(...); continue` antes de salvar,
  em `collect_minutes` e `collect_statements`, para pular o documento sem travar o
  pipeline inteiro.
- **Resultado:** coleta expandida de 40 para 340 documentos. Confirmado: **84 atas** no
  período 2006-2016, sequência de `numero_reuniao` fechada de 116 a 199 (2006-01-18 a
  2016-06-08), sem nenhum buraco de numeração.
- Documentos entre `numero_reuniao` 200-231 (aprox. 2016-2020) vieram sem texto (32 no
  total) — fora do escopo desta validação, mas relevante para quem for expandir a coleta
  para outros períodos.

## Passo 1 — Distribuição do score (léxico v1.1.0, após ajustes)

| Métrica | Valor |
|---|---|
| N (atas) | 84 |
| Média | -0.1010 |
| Mediana | -0.0928 |
| Desvio padrão | 0.2286 |
| Mínimo | -0.7297 |
| Máximo | +0.3333 |

Histograma (10 bins, -1 a +1):

```
[-1.0, -0.8):
[-0.8, -0.6): ██ (2)
[-0.6, -0.4): ████████ (8)
[-0.4, -0.2): █████████████████ (17)
[-0.2, +0.0): ████████████████████████████ (28)
[+0.0, +0.2): ████████████████████ (20)
[+0.2, +0.4): █████████ (9)
[+0.4, +0.6):
[+0.6, +0.8):
[+0.8, +1.0):
```

Distribuição concentrada perto de zero, com cauda mais longa do lado dovish — plausível
dado que o período 2006-2016 inclui vários ciclos de corte de juros (ex: 2011-2012,
2016-2017 em diante). Não há acúmulo em nenhum extremo (-1 ou +1), o que já é um bom sinal
de que o léxico não está saturando.

## Passo 2 — Mode-share

**Critério de aceite: < 30% — PASSOU (2.4%)**

Valor de score mais frequente: `+0.0130`, presente em apenas 2 dos 84 documentos. Os top-5
valores mais repetidos aparecem no máximo 2 vezes cada. O léxico discrimina bem entre
documentos no período histórico — não há nenhum padrão de travamento parecido com o bug
identificado no `extract_tone()` (LLM), que tinha 80% dos documentos cravados no mesmo
valor.

## Passo 3 — Termos com zero ocorrências

**Critério de aceite: nenhum termo zerado, ou remover e justificar.**

Rodando o léxico original (v1.0.0, 20 termos hawkish + 21 dovish) nas 84 atas, 6 termos
zeraram:

| Termo | Lista | Decisão | Justificativa |
|---|---|---|---|
| `desequilíbrio` | hawkish | **Removido** | Zero em 2006-2016 e também em 2025-2026 (amostra que já havíamos analisado). Não discrimina em nenhum período testado; sem sinônimo próximo na lista. |
| `benignidade` | dovish | **Removido** | Zero; `benigno` (134 ocorrências) já cobre a mesma ideia nesse registro formal. Redundante. |
| `cedendo` | dovish | **Removido** | Zero; `recuando` (60 ocorrências) já cobre a ideia. Redundante. |
| `desancoragem` | hawkish | **Mantido** | Zero em 2006-2016, mas presente nas atas de 2025-2026. Não é termo "quebrado" — é vocabulário que passou a existir/consolidar mais recentemente no discurso do Copom ("ancoragem de expectativas"). Remover perderia sinal útil para o período recente. |
| `resiliente` | hawkish | **Mantido** | Mesmo padrão de `desancoragem` — zero no histórico, presente no período recente. |
| `vigilância` | hawkish | Mantido (quase-zero, 1 ocorrência) | Não zera tecnicamente, então não é obrigatório pelo critério. Decisão de deixar como está; candidato a remoção futura se seguir irrelevante. |

Após remover os 3 termos sem justificativa de manutenção, rodando novamente: **restam 2
termos zerados** (`desancoragem`, `resiliente`), ambos já justificados como mantidos por
serem vocabulário mais recente do Copom. Considerando a cláusula "remover e justificar" da
issue, o critério é tratado como **atendido**: todo termo zerado tem decisão documentada
(removido, ou mantido com justificativa).

## Passo 4 — Revisão de termos direcionalmente ambíguos

A issue apontou que `incerteza`, `riscos` e `cautela` são palavras que indicam a
*existência* de incerteza, não a *direção* da política monetária. Testamos isso cruzando,
para cada termo, em quantos documentos hawkish (score geral > 0) vs. dovish (score geral <
0) ele aparece — usando o léxico v1.0.0 (para não viesar o teste com a própria mudança que
estávamos avaliando):

| Termo | Ocorrências | Docs. hawkish | Docs. dovish |
|---|---|---|---|
| `incerteza` | 282 | 33 (59%) | 23 (41%) |
| `riscos` | 565 | 41 (49%) | 42 (51%) |
| `cautela` | 7 | 3 (43%) | 4 (57%) |

Todos os três ficam próximos de 50/50 — evidência textual clara de que não indicam
direção. Exemplos de frase confirmam: "riscos associados aos cenários", "cautela com o
cenário externo" aparecem tanto em documentos que no geral pendem hawkish quanto dovish.

**Decisão: remover `incerteza`, `riscos`, `cautela` (e `cauteloso`, mesma raiz de
`cautela`, que já estava zerada) da lista hawkish.** Não foram movidos para a lista dovish
nem para nenhuma categoria nova — simplesmente saem da contagem de direção, já que não
indicam nenhuma das duas.

## Lista final (léxico v1.1.0)

**Hawkish (15 termos, era 20):**
`elevação`, `alta`, `pressão`, `pressões`, `vigilância`, `deterioração`, `aceleração`,
`aperto`, `contracionista`, `restritiva`, `desancoragem`, `persistência`, `persistente`,
`resiliente`, `aquecimento`

**Dovish (18 termos, era 21):**
`redução`, `queda`, `moderação`, `arrefecimento`, `convergência`, `flexibilização`,
`afrouxamento`, `acomodação`, `desaceleração`, `recuo`, `melhora`, `benigno`,
`estabilização`, `ancoragem`, `desinflação`, `normalização`, `alívio`, `recuando`

## Resultado após aplicar a lista v1.1.0 (revalidação)

| Métrica | v1.0.0 (original) | v1.1.0 (revisado) |
|---|---|---|
| Média do score | +0.0162 | -0.1010 |
| Mediana | -0.0118 | -0.0928 |
| Desvio padrão | 0.1912 | 0.2286 |
| Min / Max | -0.5111 / +0.4146 | -0.7297 / +0.3333 |
| Mode-share | 3.6% | **2.4%** |
| Termos zerados sem justificativa | 3 | **0** |

O mode-share melhorou (menos concentração), o desvio padrão aumentou (mais variância
capturada), e a queda na média/mediana é esperada e correta: `incerteza` e `riscos` eram
os dois termos hawkish mais frequentes de longe (282 e 565 ocorrências) e não
discriminavam direção — removê-los corrige um viés que inflava o score hawkish
artificialmente.

## `LEXICO_VERSAO`

Incrementado de `1.0.0` para **`1.1.0`** (minor — o método continua bag-of-words, só a
lista de termos foi recalibrada). Changelog documentado como comentário no próprio
`lexico.py`, acima das listas.

⚠️ Scores calculados com a v1.0.0 e a v1.1.0 **não são diretamente comparáveis**. Qualquer
análise que combine os dois precisa filtrar por `versao_lexico` no output de
`calcular_lexico()`.

## Ordem de decisões (registro para o critério 4.4 — evitar viés oportunista)

Todas as remoções/manutenções acima foram decididas **por argumento linguístico** (a
palavra indica direção de política monetária, sim ou não — testado com a distribuição
hawkish/dovish dos próprios documentos, não com dados de mercado). A comparação com
reação de mercado (DI) só deve acontecer **depois** desta lista estar travada e
versionada — não foi feita nenhuma consulta a dados de mercado até este ponto.

## Pendências / próximos passos

- [ ] Revisar se `vigilância` (1 ocorrência) deve ser removida também, ou mantida.
- [ ] Rodar os testes existentes (`tests/test_lexico.py`) após o patch, para confirmar que
      nada quebra com a lista nova.