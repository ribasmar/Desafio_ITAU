# CopomLens · Bloqueio — fonte da série de DI 1 ano

**Status:** aberto · **Dono:** Rafael · **Bloqueia:** reação do DI 1Y (Sprint 1) ·
**Relacionado:** #6 (Selic + Focus → surpresa da decisão)

## Por que isso bloqueia

A variável-resposta do projeto é a **reação do DI de 1 ano** à comunicação do
Copom (a surpresa da decisão e o tom da ata/comunicado). A surpresa da decisão
(`Selic_efetiva − Selic_esperada`) já está calculável com fontes públicas e
gratuitas (SGS 432 + Focus/Olinda). **O que ainda não está resolvido é a fonte
da série de DI 1Y** point-in-time necessária para medir a reação. Sem ela, a
Camada 4 (modelo) e a Camada 5 (backtest) não fecham.

## O que precisamos exatamente

- Uma série de **taxa do DI de ~252 dias úteis (1 ano)**, ponto a ponto no tempo.
- Granularidade **diária** (fechamento) é o mínimo; idealmente **intradiária**
  em torno da decisão, para isolar a janela tradeável (a decisão sai ~18h30).
- Carimbo temporal confiável para respeitar a regra **point-in-time**.

A janela de evento curta (a reação se concentra em minutos/horas após a decisão)
torna a granularidade um fator de qualidade, não só de conveniência.

## Opções avaliadas

| Fonte | Cobre DI 1Y? | Granularidade | Custo/acesso | Observação |
|---|---|---|---|---|
| **B3 (mercado de DI Futuro)** | Sim (vértices DI1) | Diária; intradiária via market data pago | Diária é pública (ajustes); intradiária é paga | Fonte primária; exige interpolar para 252 du e mapear código de contrato |
| **ANBIMA (curva DI/ETTJ)** | Sim (curva pré) | Diária | Pública (arquivos diários) | Curva já interpolada; bom candidato para o vértice de 1 ano |
| **SGS/BCB** | Não diretamente | Diária | Pública | Tem Selic/CDI, **não** o DI futuro 1Y |
| **Provedores (Bloomberg/Refinitiv/B3 UP2DATA)** | Sim | Intradiária | Pago/licença | Melhor qualidade; depende de acesso institucional |

## Decisão pendente (precisa do mentor / validação)

1. **MVP (Sprint 1):** usar **fechamento diário** do DI 1Y — ANBIMA (curva pré,
   vértice 252 du) ou B3 (ajuste do DI1 + interpolação). Mede a reação como
   variação D0→D+1, suficiente para a fatia vertical.
2. **Evolução:** buscar **intradiário** (B3 market data / provedor) para isolar a
   janela de evento e ganhar realismo de custos no backtest.

## Riscos / erros adjacentes a vigiar

- **Interpolação para 252 du:** o vértice exato de 1 ano raramente existe;
  interpolar entre contratos introduz ruído — documentar o método.
- **Rolagem de contrato:** ao usar DI1 da B3, trocas de vencimento criam saltos
  artificiais; usar série de taxa interpolada, não o contrato cru.
- **Fuso/horário do carimbo:** alinhar o fechamento do DI ao horário da decisão
  (~18h30) para não medir reação com dado anterior à decisão (lookahead).

## Próximo passo

Confirmar com o mentor se o MVP pode rodar com **fechamento diário (ANBIMA)** e,
em paralelo, sondar acesso a intradiário da B3. Atualizar este documento ao fechar.
