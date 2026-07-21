# CopomLens · Bloqueios — dados da variável-alvo (DI 1Y) e expectativas Copom

**Status:** resolvido — reescopo final validado pelo mentor (fonte única SGS 7806) · **Dono:** Rafael ·
**Desbloqueia:** reação do DI 1Y (Sprint 1) ·
**Relacionado:** #6 (Selic + Focus → surpresa da decisão)

## Bloqueante 1 — Ausência de fonte pública, diária e contínua do DI 1Y (variável-alvo)

**Status:** encerrado (jul/2026) — decisão do mentor, não reabrir. Fonte única:
SGS 7806. Pipeline B3/XML congelado e promovido a "próximos passos" do
relatório (critério 4.6).

### O desafio original

Não existe API RESTful pronta que entregue a série histórica de 1 ano já
interpolada, o que travava a definição precisa da variável-alvo do modelo
econométrico. Sem ela, a Camada 4 (modelo) e a Camada 5 (backtest) não fecham.

### Reescopo (verificação de 02/07/2026)

Verificação empírica das fontes alternativas alterou o escopo da solução:

- **BCB/SGS série 7806** (swap DI×pré 360 dias) está ativa via API REST
  (`api.bcb.gov.br/dados/serie/bcdata.sgs.7806/dados`) e cobre **02/01/2004 a
  30/09/2019** com dados diários, sem parser e sem crawler.
- O endpoint legado de Taxas Referenciais da B3 (www2.bmf.com.br) está
  inoperante ("Unspecified error"), confirmando a descontinuação de 31/03/2026.
- **Consequência:** a carga histórica via arquivos TXT posicionais (2004–2016)
  torna-se **desnecessária e está descartada**. O pipeline XML BVBG.187 fica
  restrito a **out/2019–presente**.

### Reescopo final (decisão do mentor, jul/2026 — não reabrir)

O diagnóstico acima está correto e verificado. O que muda é a conclusão: a
**7806 é uma série de maturidade constante** — sempre 360 dias corridos, todo
dia, por construção. Ou seja, ela **já é a "série de taxa interpolada"** que
este documento manda usar em vez do contrato cru. Para o período do estudo, o
BCB entrega pronto, de graça, numa URL, o produto final que o pipeline B3/XML
existia para fabricar.

1. **Fonte única do alvo:** SGS 7806 via API REST do BCB, janela viva completa
   (02/01/2004 a 30/09/2019), carga única + guarda estática (série
   descontinuada não sofre revisão). Implementado em
   `src/copom/ingest/marketdata.py` (`fetch_di1y`), com fatiamento automático
   de janelas de 10 anos (o SGS responde HTTP 406 acima disso).
2. **Alvo por ata:** `reacao_bps = 7806(D1) − 7806(D0)`, medida em torno da
   **data de publicação da ata** (nunca da reunião — look-ahead). Como a ata
   sai às 8h30, antes da abertura, D0 = último pregão anterior à publicação e
   D1 = pregão do próprio dia da publicação (a janela atravessa o evento).
   Implementado em `src/copom/surprise/surpresa.py` (`reacao_di1y`,
   `montar_painel_di1y`).
3. **Pipeline B3/XML (crawler, BVBG.187, Flat Forward 252 du): congelado.**
   Vai para "próximos passos" do relatório — critério 4.6 (10% da nota), que
   premia realismo das propostas e caminhos claros de aprimoramento. Não é
   descarte, é promoção: sai de onde custava semanas e vai para onde paga
   pontos. A arquitetura está certa; só não estava no lugar certo.
4. **Validação de emenda: deixa de existir.** Com fonte única não há emenda de
   metodologias — o item que este documento marcava como obrigatório se
   dissolve por construção.

### Funil da amostra (medido ao vivo, não estimado)

| requisito                                  | sobram |
|--------------------------------------------|--------|
| atas listadas pelo BCB (1998–2026)         | 259    |
| ... com texto HTML                         | 227    |
| ... com alvo DI 1Y (7806 viva)             | 108    |
| ... com Focus por reunião (começa R1/2006) | 84     |

**Janela final: 2006-01-18 a 2016-06-08 · 84 atas.** Cada corte tem contagem e
razão gravadas em `data/processed/funil_amostra.json` (gerado por
`python -m copom.surprise`); regime por presidente do BC (40 Meirelles /
44 Tombini) vem de tabela de fato público (`REGIMES_BC`), nunca do LLM.

Validação da reação medida ao vivo (108/108 casadas, zero falhas):
dp = 12.3 bps · min = −31 · max = +33 · |reação| mediana = 7.0 bps ·
reações > 1 bp: 95/108. A série tem sinal; o alvo fecha.

**Fora de escopo (bônus, só se sobrar tempo):**

- 24 atas de 2004–2005: Focus por reunião não existe; a série mensal do Olinda
  (`ExpectativaMercadoMensais`, já verificada em `scripts/check_olinda.py`)
  serviria de proxy.
- 26 atas de jul/2016–set/2019: existem só em PDF; a `urlPdfAta` fica
  registrada em `data/raw/atas_sem_texto.json` pela ingestão.

### Riscos / erros adjacentes a vigiar

- **Rolagem de contrato:** NÃO usar gráfico/série de contrato (ex.: DI1F28).
  O contrato envelhece — hoje 1,5 ano, em 2027 vira 6 meses — e a troca de
  vencimento cria salto artificial que entraria na planilha como "reação à
  ata". A 7806 elimina isso por construção (maturidade constante).
- **Janela de medição da reação:** medir na data de PUBLICAÇÃO da ata, nunca
  na data da reunião (look-ahead). `reacao_di1y` recebe `available_time`.
  Como a publicação é pré-abertura (8h30), o fechamento do próprio dia já
  reflete a ata: a janela correta é véspera → dia da publicação; medir
  publicação → dia seguinte capturaria o dia após a absorção (só ruído).
- **Calendário parcial:** `COPOM_CALENDAR` estático cobre só 2025–2026 e é
  inútil para o histórico; o rótulo R{k}/{ano} usa a lista oficial completa de
  reuniões (`atas_listadas.json`), nunca um dataset parcial — com dataset
  parcial, a última reunião baixada de um ano viraria R1 daquele ano.
- **Nenhum número herdado de default:** quantidade de ingestão, janelas de
  série e cortes do painel são explícitos e logados; se o painel der diferente
  de 84 linhas, explicar a diferença (via `funil_amostra.json`) no PR — não
  ajustar até bater.

## Bloqueante 2 — Limitação do histórico de expectativas por reunião do Copom

**Status:** superado.

### O desafio original

Dificuldade em obter profundidade histórica suficiente de expectativas do
mercado atreladas ao calendário de reuniões, o que inicialmente reduzia o
escopo da análise.

### A solução estabelecida

Validação de que os registros desde 2004 podem ser acessados sistematicamente
via **API Olinda (Banco Central do Brasil)**.

### Por que isso resolve

- A API entrega o dado com chancela institucional, de forma gratuita e contínua.
- Ao cruzar o histórico de expectativas da API Olinda com a curva limpa do DI
  (via engenharia dos dados da B3), o pipeline ganha a robustez necessária para
  treinar o modelo sem furos na linha do tempo.

## Como reproduzir o painel do alvo

```bash
python -m copom.ingest --last 300        # atas + comunicados + lista oficial
python -m copom.ingest.marketdata        # SGS 432 + SGS 7806 + Focus completo
python -m copom.surprise                 # painel_di1y.csv + funil_amostra.json
```

O último comando imprime o funil (cada corte com razão) e as estatísticas da
reação no mesmo formato dos números medidos ao vivo, para conferência 1:1.

## Próximos passos (relatório, critério 4.6)

1. Pipeline XML BVBG.187 (out/2019–presente): crawler → parser streaming →
   filtro de liquidez por `OpnIntrst` → prazo em du (calendário ANBIMA) →
   Flat Forward 252 du — estende o alvo para além de set/2019 e, aí sim,
   exigiria validação de emenda na sobreposição com a 7806.
2. Proxy mensal do Focus (`ExpectativaMercadoMensais`) para recuperar as 24
   atas de 2004–2005.
3. OCR/parse das 26 atas PDF de jul/2016–set/2019 (`urlPdfAta` já registrada
   em `atas_sem_texto.json`).
