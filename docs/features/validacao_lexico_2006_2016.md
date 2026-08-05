# Validação do léxico histórico — 2006-2016

> Issue: "Camada 2 + relatório" — Parte 1 (Dono: Elder · Timebox: 16-17/07)
> Revisão de gate: review do mentor no PR `fix/lexico-viés-historico`
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

## Passo 1 — Distribuição do score (léxico v1.2.0, estado final)

| Métrica | v1.0.0 (original) | v1.1.0 | v1.2.0 (final) |
|---|---|---|---|
| N (atas) | 84 | 84 | 84 |
| Média | +0.0162 | -0.1010 | -0.1171 |
| Mediana | -0.0118 | -0.0928 | -0.1155 |
| Desvio padrão | 0.1912 | 0.2286 | 0.2271 |
| Min / Max | -0.5111 / +0.4146 | -0.7297 / +0.3333 | -0.7600 / +0.3333 |

Distribuição segue concentrada perto de zero, com cauda mais longa do lado dovish —
plausível dado que o período 2006-2016 inclui vários ciclos de corte de juros.

## Passo 2 — Mode-share

**Resultado v1.2.0: 3.6%** (valor mais frequente: -0.3333, em 3/84 documentos).
Continua muito abaixo do critério original de 30%.

⚠️ **Nota de rigor metodológico (achado do review do mentor):** o mode-share **não
discriminou nada** ao longo de todo o processo — passou com folga em todas as versões
(v1.0.0: 3.6%, v1.1.0: 2.4%, v1.2.0: 3.6%). Um critério que passa igual antes e depois de
uma mudança substancial na lista de termos não está testando o que a mudança de fato
mudou. Ele foi mantido como registro de sanidade (garante que o léxico não travou em
poucos valores, como o bug do LLM), mas **deixou de ser o critério de aceite principal**
— substituído pelo gate de discriminação por termo (Passo 4).

## Passo 3 — Termos com zero ocorrências

**v1.1.0 → v1.2.0:** sem mudança nesse critério. `desancoragem` e `resiliente` seguem
zerados no período 2006-2016 e mantidos, pela mesma justificativa da v1.1.0: são
vocabulário mais recente do Copom, confirmado presente nas atas de 2025-2026 — não são
termos "quebrados", é deriva de vocabulário ao longo do tempo. Essa decisão foi
explicitamente confirmada como correta pelo mentor no review ("ler o critério pelo
espírito, não pela letra — desvio aceito"), com o pedido de deixá-la registrada aqui de
forma explícita para qualquer revisor externo.

## Passo 4 — Gate de discriminação por termo (substituindo o mode-share)

### Histórico: por que esse passo mudou de desenho duas vezes

**Tentativa 1 (issue original):** revisar só os 3 termos que a issue apontava como
suspeitos (`incerteza`, `riscos`, `cautela`), medindo em quantos documentos hawkish vs.
dovish cada um aparece. Os três ficaram perto de 50/50 e foram removidos na v1.1.0.

**Review do mentor identificou dois problemas nessa abordagem:**

1. O critério de aceite formal (mode-share) não testava a mudança de verdade (ver Passo 2).
2. **Circularidade:** o documento era classificado hawkish/dovish por um score que **já
   incluía o termo sendo testado** — o termo participava da régua que o julgava.

**Tentativa 2 — gate ingênuo (40%-60% fixo) + leave-one-out.** Corrigimos a
circularidade: para testar cada termo, o score do documento é recalculado **sem** aquele
termo antes de classificar hawkish/dovish. Aplicado a **todos os 33 termos** (não só os 3
suspeitos), com um gate fixo de 40%-60% proposto pelo mentor.

Resultado: **13 de 33 termos reprovaram** — incluindo os termos dovish mais frequentes de
todo o léxico (`redução`, 923 ocorrências; `queda`, 660; `desaceleração`, 472;
`moderação`, 234). Isso acendeu um alerta: não parecia plausível que os termos mais
centrais do léxico fossem, ao mesmo tempo, os menos informativos.

### Investigação da causa raiz (antes de remover qualquer coisa)

Testamos duas hipóteses para explicar por que termos tão frequentes reprovavam, **por
argumento estatístico e linguístico, sem consultar dado de mercado**:

**Hipótese A — diluição estatística.** Um termo muito frequente "dilui" no leave-one-out
porque o resto do documento (muitas outras palavras) domina o score residual,
independente de o termo ser um bom sinal. Testada calculando a correlação entre
frequência do termo (n de documentos) e distância de 50%: **r = -0.276** — fraca, e
refutada por contraexemplos diretos: `elevação` (a palavra mais frequente do léxico
inteiro) e `pressões` continuam extremas (10-23% hawkish) mesmo sendo tão ou mais
frequentes que os termos reprovados. Se fosse pura diluição por frequência, elas também
teriam diluído. **Não sustenta.**

**Hipótese B — concentração no parágrafo de balanço de riscos.** Mesmo mecanismo já
identificado para `incerteza`/`riscos`/`cautela`: será que os termos reprovados aparecem
desproporcionalmente dentro do parágrafo padrão de "balanço de riscos" (que descreve
simetricamente riscos de alta e de baixa)? Testado contando ocorrências dentro vs. fora
desse trecho para os 13 reprovados e 5 termos de controle (alta frequência, não
reprovados). Resultado: reprovados ficaram entre 0% e 9,2% de ocorrências dentro do
parágrafo; controles entre 0,8% e 6% — **sem separação entre os grupos**. **Refutada.**

**Causa raiz encontrada:** o corpus **não é 50/50** entre documentos hawkish e dovish — é
**~66% dovish / 34% hawkish** (medido diretamente: 55-56 de 83-84 documentos com score
negativo, dependendo da versão da lista). O gate de 40%-60% comparava o split de cada
termo contra um "neutro" de 50%, que não é o neutro real do corpus. Um termo sem sinal
algum deveria refletir a taxa base do corpus (~66/34), não 50/50 — cair perto de 50%
significa, na verdade, que o termo puxa o documento para **menos dovish que a média**, o
que é sinal (mais fraco que outros termos, mas sinal), não ausência de sinal.

### Gate corrigido e aplicado (v1.2.0)

**Gate final:** termo reprova se `|pct_hawkish do termo − taxa base do corpus| <= 10
pontos percentuais` (em vez de comparar contra 50% fixo). Recalculado com leave-one-out.

**Resultado, sobre a lista v1.1.0 (33 termos), taxa base = 33.7% hawkish:** 14 termos
reprovaram — um conjunto bem diferente do gate ingênuo. Note que `redução`, `queda` e
`desaceleração` — que reprovariam no gate de 40-60% — **sobrevivem** aqui, porque são mais
dovish que a média do corpus (carregam sinal real, mais forte que a média).

**Removidos (hawkish, 5):** `persistência`, `aperto`, `aceleração`, `pressão`,
`deterioração` — todos a ≤8pp da taxa base (sem sinal além da média do corpus).

**Removidos (dovish, 9):** `afrouxamento`, `convergência`, `estabilização`,
`normalização`, `ancoragem`, `acomodação`, `alívio`, `arrefecimento`, `moderação` — mesmo
motivo.

**Ressalva:** `vigilância` sobrevive (100% hawkish, muito longe da base), mas com apenas 1
ocorrência em 84 atas — amostra pequena demais para dar confiança real à aprovação;
mantido por ora, candidato a nova revisão se seguir tão raro no restante do corpus.

## Lista final (léxico v1.2.0)

**Hawkish (10 termos, era 20 na v1.0.0):**
`elevação`, `alta`, `pressões`, `vigilância`, `contracionista`, `restritiva`,
`desancoragem`, `persistente`, `resiliente`, `aquecimento`

**Dovish (9 termos, era 21 na v1.0.0):**
`redução`, `queda`, `desaceleração`, `flexibilização`, `recuo`, `melhora`, `benigno`,
`desinflação`, `recuando`

## Observação registrada, não aplicada: instabilidade do gate sob reaplicação

Reaplicamos o gate corrigido (Passo 4) sobre a lista já reduzida da v1.2.0, como checagem
de consistência. **Resultado: mais 5 termos reprovam** (`flexibilização`, `recuando`,
`persistente`, `melhora`, `desinflação`), porque a taxa base do corpus se deslocou entre
rodadas (33.7% → 31.3%) — remover termos hawkish fracos torna o corpus, como um todo, um
pouco mais dovish, o que desloca a régua e revela um novo conjunto de "reprovados" que
antes estavam confortavelmente aprovados.

**Essa segunda leva não foi removida.** Aplicar o gate repetidamente até ele parar de
reprovar termos, sem um critério de parada definido a priori, é uma forma de garimpo
metodológico — mesmo com cada remoção individualmente justificada por argumento
estatístico, o processo agregado (iterar até convergir) não tem uma regra de parada, e
esvaziaria progressivamente o léxico até sobrar um punhado de termos extremos,
enfraquecendo o baseline exatamente no papel que ele precisa cumprir (ser um adversário
justo contra o qual a LLM precisa provar valor, não um adversário artificialmente fraco).
A lista v1.2.0 (Passo 4, primeira aplicação do gate corrigido) fica congelada como está.

## `LEXICO_VERSAO`

Incrementado de `1.1.0` para **`1.2.0`**. Changelog completo documentado como comentário
no próprio `lexico.py`, acima das listas — inclui a cadeia de hipóteses testadas e
refutadas, não só a lista final.

⚠️ Scores calculados com versões diferentes **não são diretamente comparáveis**. Qualquer
análise que combine versões precisa filtrar por `versao_lexico` no output de
`calcular_lexico()`.

## Ordem de decisões (registro para o critério 4.4 — evitar viés oportunista)

Todas as remoções foram decididas por argumento linguístico e estatístico — distribuição
hawkish/dovish nos próprios documentos, taxa base do corpus, testes de hipótese sobre a
causa da reprovação — sem nenhuma consulta a dado de mercado em nenhum momento do
processo. A observação sobre a instabilidade do gate sob reaplicação (seção acima) é
reportada como achado metodológico, não usada para justificar remoção adicional sem
critério de parada definido.

## Pendências / próximos passos

- [x] ~~Revisar se `vigilância` deve ser removida~~ — mantida, com ressalva de amostra
      pequena (n=1) registrada acima.
- [x] Aplicar o patch em `src/copom/features/lexico.py` (v1.2.0).
- [x] Atualizar `tests/test_lexico.py` (exemplos que usavam termos removidos —
      `cautela`→`elevação`/`alta`; `aperto`→removido do exemplo hawkish; `arrefecimento`→
      `recuo` no exemplo dovish). `pytest tests/test_lexico.py -v`: 10/10 passando.
- [ ] Levar a observação da seção "instabilidade do gate sob reaplicação" para o mentor —
      não como pergunta em aberto, mas como constatação registrada: o processo de
      reaplicar o gate corrigido sobre a própria lista reduzida não converge sozinho, e a
      equipe optou por não iterar sem critério de parada definido.