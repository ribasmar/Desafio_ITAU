# CopomLens · Bloqueios — dados da variável-alvo (DI 1Y) e expectativas Copom

**Status:** resolvido (soluções arquiteturais definidas) · **Dono:** Rafael ·
**Desbloqueia:** reação do DI 1Y (Sprint 1) ·
**Relacionado:** #6 (Selic + Focus → surpresa da decisão)

## Bloqueante 1 — Ausência de fonte pública, diária e contínua do DI 1Y (variável-alvo)

**Status:** reescopado (02/07/2026) — solução arquitetural simplificada e sob controle.

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

### A solução estabelecida (revisada)

1. **2004–set/2019:** série SGS 7806 via API REST do BCB (carga única + guarda
   estática; série descontinuada, não sofre revisão).
2. **out/2019–presente:** ingestão dos arquivos XML **BVBG.187.01** da
   Pesquisa por Pregão da B3 (crawler + `iterparse` com `elem.clear()` para
   memória constante), extraindo `TckrSymb`, `AdjstdQt` e `OpnIntrst` dos nós
   `<PricRpt>`, seguida de prazo em du (calendário ANBIMA) e interpolação
   **Flat Forward 252 du** no backend.
3. **Validação de emenda:** calcular ambas as metodologias no período de
   sobreposição (~2016–set/2019, arquivos XML disponíveis) e medir o spread
   nas janelas de reunião do Copom antes de unir as séries. Emenda só é
   aprovada se a aderência for comprovada; caso contrário, aplicar ajuste
   documentado de basis.

### Por que isso resolve

- **Profundidade histórica com custo mínimo:** 2004–2019 resolvido com uma
  chamada REST institucional (BCB), eliminando parser posicional, riscos de
  encoding (latin-1) e conversão PU→taxa da janela antiga.
- **Rigor quantitativo:** no trecho recente, o PU/Taxa de Ajuste oficial da B3
  garante a variável-alvo limpa de ruídos intradiários.
- **Critério de liquidez auditável:** `OpnIntrst` e volume permitem filtro
  automatizado de vértices líquidos no trecho XML.
- **Superfície de manutenção reduzida:** apenas um parser (XML) e um crawler
  para monitorar, em vez de dois formatos e duas fontes.

### Riscos / erros adjacentes a vigiar

- **Emenda metodológica (novo, crítico):** a 7806 é taxa de swap em 360 dias
  corridos reportada pela BM&F; a série própria é interpolação Flat Forward
  252 du sobre ajustes de DI1. Não unir sem a validação de sobreposição do
  item 3.
- **Rolagem de contrato:** trocas de vencimento do DI1 criam saltos artificiais;
  usar sempre a série de taxa interpolada, não o contrato cru.
- **Janela de medição da reação:** a decisão do Copom sai após o fechamento
  (~18h30); a reação deve ser medida como ajuste D0 → ajuste D+1, e não pelo
  timestamp da ingestão (lookahead).
- **Idempotência por chave natural:** a B3 republica arquivos retificados;
  usar upsert por (data-pregão + ticker) e hash do arquivo, não apenas a
  existência do nome do arquivo.
- **Mudança de layout XML:** validar contra o XSD publicado do BVBG.187 para
  detecção automática de quebra, com retry/backoff e alerta de falha no crawler.
- **Documentar o método de interpolação** (Flat Forward, 252 du, calendário
  ANBIMA) e a regra de emenda para reprodutibilidade e defesa metodológica.

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

## Próximo passo

1. Carga única da SGS 7806 (2004–set/2019) via API BCB.
2. Pipeline XML BVBG.187 (out/2019–presente): crawler → parser streaming →
   filtro de liquidez → prazo em du → Flat Forward 252 du.
3. Validação de emenda no período de sobreposição (~2016–2019) nas janelas
   de Copom.
4. Integração Olinda e validação da série final contra o calendário de
   reuniões do Copom.
