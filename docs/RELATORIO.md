# CopomLens — Relatório

> O esqueleto completo por critério do manual vem do #30. Esta seção já está
> fechada: todo número abaixo é gerado por `python scripts/numeros_amostra.py`
> a partir dos artefatos do pipeline e conferido por identidade de
> reconciliação — nenhum foi digitado à mão nem herdado de default.

## Dados e premissas

### Fontes

| dado | fonte | identificador | janela efetivamente usada |
| --- | --- | --- | --- |
| atas e comunicados do Copom | API pública do BCB (`sitebcb/copom/atas`, `atas_detalhes`) | lista oficial de reuniões | 259 reuniões listadas (1998–2026) |
| atas publicadas só em PDF | `urlPdfAta` do próprio JSON do BCB | 32 PDFs (reuniões 200–231) | 26 entram no painel (200–225) |
| alvo: DI 1 ano | BCB/SGS série 7806 (pré-fixado 360 dias, maturidade constante) | 7806 | 02/01/2004 a 30/09/2019 (fim da série) |
| Selic meta efetiva | BCB/SGS série 432 | 432 | acompanha a janela do painel |
| mediana Focus por reunião | BCB Olinda `ExpectativasMercadoSelic` | rótulo `R{k}/{ano}` | rótulos existem a partir de R1/2006 |

A série 7806 é de maturidade constante — sempre 360 dias, por construção. Isso
elimina o contrato cru (DI1F**xx**), que envelhece e produz salto artificial na
troca de vencimento, e elimina também qualquer emenda de metodologias: o alvo
inteiro vem de uma fonte só.

### Funil da amostra

| etapa | restantes | removidas | razão do corte |
| --- | --- | --- | --- |
| atas listadas pelo BCB | 259 | — | lista oficial (`atas_listadas.json`): universo de partida |
| com texto extraído | 259 | 0 | guard-rail para `textoAta = None` + fallback de PDF: nenhuma ata listada fica sem texto |
| com reação DI 1Y casada | 134 | 125 | publicação da ata fora da janela viva da 7806 (02/01/2004–30/09/2019): sem D0/D+1 |
| com mediana Focus da reunião | 110 | 24 | `ExpectativasMercadoSelic` só rotula reuniões a partir de R1/2006 (remove 2004–2005) |

**Painel final: 110 eventos, de 2006-01-18 a 2019-09-18 (reuniões 116 a 225).**
Regimes: Meirelles 40, Tombini 44, Goldfajn 21, Campos Neto 5 — presidente do BC
por tabela de fato público, nunca inferido do texto.

### Os quatro números da amostra, cada um com o seu limite

| número | o que é | limite que o define |
| --- | --- | --- |
| **259** | atas listadas pelo BCB | universo de partida: a lista oficial de reuniões |
| **112** | atas escoradas pelo LLM (2006–2019, reuniões 116–227) | decisão de escoragem: cobrir a janela em que o alvo poderia existir (7806 morre em 30/09/2019) |
| **110** | linhas do painel = eventos do estudo | interseção de alvo casado **e** mediana Focus: as duas atas restantes (226 e 227) foram publicadas em 05/11/2019 e 17/12/2019, depois do fim da 7806, e não têm D0→D+1 |
| **84** | subamostra de formato homogêneo (2006-01-18 a 2016-06-08, reuniões 116–199) | fim do texto servido pela API em HTML: a partir da reunião 200 o BCB publica a ata em PDF **e** em formato editorial novo (ver quebra abaixo) |

Reconciliação (verificada pelo script, que sai com código 1 se não fechar):

```
84 (texto via API/HTML) + 26 (texto via PDF) = 110 linhas do painel
110 + 2 escoradas sem alvo                    = 112 atas escoradas pelo LLM
```

O 84 do escopo original **não** foi substituído nem furado: ele é exatamente a
fatia do painel cujo texto veio da API em HTML. Deixou de ser o tamanho do
painel quando o fallback de PDF passou a ingerir as reuniões 200–225, que antes
não tinham texto. Ele continua no relatório como subamostra de robustez, pelo
motivo da seção seguinte.

Sobre reuniões com **ata e comunicado pareados** (amostra da feature de
divergência ata↔comunicado): a disponibilidade medida é de **110 no painel** e
234 no corpus inteiro — todo evento do painel tem comunicado com texto. Qualquer
recorte menor é decisão da issue que implementa a feature, não limite dos dados,
e precisa ser declarado lá com a sua própria razão.

### Quebra estrutural na reunião 200 (2016-07-20)

Três mudanças caem exatamente na mesma reunião e são perfeitamente colineares
nesta amostra:

1. **formato do documento** — a ata encurta de 27,2 mil caracteres (reunião 199)
   para 13,9 mil (reunião 200) e perde a estrutura antiga (a marca `Sumário`
   desaparece). É degrau, não tendência: reuniões 193–199 ficam entre 26,2 e
   27,8 mil; reuniões 200–225, entre 13,3 e 17,9 mil.
2. **fonte do texto** — API/HTML até a 199, PDF da 200 em diante, registrada por
   documento no campo `fonte` do `manifest.json`.
3. **regime** — o conjunto das 26 reuniões de fonte PDF é *idêntico* ao conjunto
   das 21 de Goldfajn mais as 5 de Campos Neto (reuniões 200 a 225).

Consequência para a leitura dos resultados: um efeito de regime, um efeito de
método de extração e um efeito de redesenho editorial da ata **não são
separáveis** neste painel. O degrau de tamanho não invalida o tom — o score
léxico é uma razão em [−1, +1], insensível ao comprimento — mas reduz a
contagem de termos por documento e, com isso, aumenta a variância da feature
justamente no trecho final da amostra, que é o out-of-sample da comparação
walk-forward. Daí as duas providências:

- todo resultado é reportado no painel de 110 e repetido na subamostra
  homogênea de 84 (só API/HTML, formato antigo);
- features contadas por ocorrência entram normalizadas por tamanho do texto,
  nunca em contagem bruta.

### Premissas

- **Point-in-time, sem exceção.** Nenhum texto ou feature influencia um retorno
  sem prova de que já era público naquele instante. A reação é medida em torno da
  **data de publicação da ata**, nunca da data da reunião: a ata sai 8 dias
  depois na mediana da amostra (mínimo 6, máximo 9), e usar a data da reunião
  importaria informação que o mercado ainda não tinha.
- **Janela da reação**: `reacao_bps` = 7806 no dia da publicação − 7806 na última
  observação anterior a ela (D0 fica 1 ou 2 dias úteis antes, conforme o
  calendário). A ata sai pré-abertura (8h30), então o fechamento do próprio dia
  da publicação já reflete a ata e o anterior não — a janela é a mais curta que
  capta o evento sem olhar para frente. Medir publicação → dia seguinte pegaria
  o dia posterior à absorção, que é ruído.
- **Surpresa da decisão** = Selic meta efetiva − mediana Focus da última pesquisa
  anterior à decisão, com o rótulo `R{k}/{ano}` conferido contra a data da
  reunião: uma pesquisa posterior à decisão, ou anterior a ela por mais de 10
  dias, derruba a linha em vez de virar número silencioso.
- **Rótulo Focus rankeado contra o calendário oficial**, carregado de
  `atas_listadas.json` (todas as reuniões listadas pelo BCB, inclusive as sem
  texto), nunca contra as reuniões presentes no dataset carregado — com dataset
  parcial, a k-ésima reunião do ano baixada receberia o rótulo errado.
- **Regime = presidente do BC** por tabela de fato público, com data de posse.
  Fora da cobertura da tabela o código levanta erro: incluir regime novo é
  decisão explícita, não default.
- **Uma reunião = uma linha**, deduplicada por número de reunião, preferindo a
  data da ata. Há caso real de o BCB divergir de si próprio na data de
  referência entre ata e comunicado da mesma reunião (reunião 94).
- **Nenhum default silencioso na amostra.** A ingestão histórica é explícita
  (`--last 300`) e cada corte do funil é gravado com contagem e razão em
  `data/processed/funil_amostra.json`.

### Fora de escopo, com o motivo

| não entrou | motivo | onde fica |
| --- | --- | --- |
| 24 atas de 2004–2005 | Focus por reunião não existe antes de R1/2006; só há a série mensal, que serviria de proxy | próximos passos |
| atas de 2019-10 em diante | a 7806 termina em 30/09/2019: sem alvo comparável na mesma metodologia | próximos passos (pipeline B3/XML) |
| pipeline B3 (BVBG.187, Flat Forward 252 du) | a 7806 já entrega, pronta, a curva de maturidade constante que esse pipeline existiria para fabricar | próximos passos: caminho de aprimoramento com arquitetura já desenhada |

### Reprodutibilidade

```bash
python -m copom.ingest.collect --last 300     # atas + comunicados + manifesto
python -m copom.ingest.atas_pdf               # bônus: atas publicadas só em PDF
python -m copom.ingest.parser                 # corpus point-in-time
python -m copom.ingest.marketdata             # SGS 432, SGS 7806, Focus por reunião
python -m copom.surprise                      # painel_di1y.csv + funil_amostra.json
python scripts/numeros_amostra.py             # números desta seção + reconciliação
```
