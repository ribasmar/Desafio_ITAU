# CopomLens — relatório final vs. edital e manual de avaliação

Revisão de 13/08/2026 sobre `CopomLens_relatorio_1.pdf` (5 páginas, 470 KB).

---

## 1. Conformidade formal (risco de eliminação)

| Requisito | Status | Evidência |
|---|---|---|
| Formato PDF | OK | — |
| Máximo 5 páginas | OK | exatamente 5 |
| 16:9 widescreen | OK | 13,33 × 7,50 pol em todas as páginas (razão 1,7778) |
| Anonimato | OK | sem nomes, equipe, universidade ou logo institucional; metadados limpos (`/Title: CopomLens`, `/Creator: Chromium`, sem `/Author`) |
| Identidade do robô | OK | nome, logo (íris/alvo) e explicação "lente, não oráculo" na p1, retomada na conclusão da p5 |
| Sem links externos / QR | OK | — |
| Português | OK | — |
| Nome do arquivo = chave de envio | **PENDENTE** | renomear quando a chave chegar |
| Legibilidade sem zoom | **ATENÇÃO** | menores corpos (legendas do funil p2, tabela de estratégias p3, subtítulos de gráfico p3/p4) no limite |
| Referência de ~750 palavras | **EXCEDIDO** | 1.106 palavras extraídas (p1 132 · p2 328 · p3 95 · p4 163 · **p5 388**) |

---

## 2. Avaliação por critério

### 4.1 Apresentação do robô — 5%
**Forte.** O nome descreve o que o modelo faz (instrumento de medida, não previsor), a identidade visual é coerente com "lente", e a explicação está integrada ao conteúdo em vez de ocupar espaço decorativo. A conclusão da p5 fecha o arco ("a lente funciona; agora sabe para onde apontar"). Praticamente sem perda.

### 4.2 Conceito da estratégia — 20%
**Bom, com duas fissuras.**

*A favor:* hipótese explícita, falsificável e testada; "não há ganho incremental é resultado válido" é postura madura e o manual premia isso.

*Fissura 1 — a ineficiência declarada não é a ineficiência testada.* A p1 vende uma vantagem de **latência**: "o mercado leva horas para digerir 27 mil caracteres, quem lê em segundos captura o intervalo". O backtest é fechamento-a-fechamento diário, que por construção não captura nenhuma vantagem intradiária. A própria p4 reconhece que o salto do comunicado é overnight e que executar exige a abertura de D+1. Um avaliador quant lê a p1 e a p4 e vê incoerência entre o edge alegado e o objeto medido.

*Fissura 2 — não há estratégia investível proposta.* O critério pede "consistência da proposta como estratégia de investimento" e "justificativa para geração de retorno". A resposta honesta do relatório é "não recomendamos alocar capital". Isso pontua bem em análise crítica e conclusão, mas deixa 20% do peso parcialmente sem entrega.

### 4.3 Modelagem — 20%
**O ponto mais forte do relatório.** Pipeline de 5 camadas, tabela de fontes com janela, funil da amostra com razão para cada corte (259 → 134 → 110 = 84 + 26), decisão observável (+1 paga fixo / −1 recebe fixo), walk-forward especificado (janela expansiva, treino mínimo 40, refit por evento) e auditoria de lookahead "110 de 110, zero violações". É exatamente o "replicável e transparente" do manual.

*Única fissura, e é grande:* **o extrator por LLM não entrou no modelo testado.** A Camada 2 na p2 lista "LLM local (T=0, seed fixa, JSON) **e** baseline léxico como piso" — o leitor entende que ambos foram testados. Só na p4 ("rejeitada na camada léxica") e no Próximo 1 da p5 ("falta a escoragem entrar no painel") fica claro que a CopomLens não estava no painel. A reconciliação é deixada para o leitor montar.

### 4.4 Backtest — 15%
**Rigoroso.** Walk-forward com 70 previsões out-of-sample, permutação com 5.000 sorteios, custo com sensibilidade, subamostra homogênea de 84, benchmark passivo e limites de execução declarados.

*Lacuna:* **não há justificativa para o período terminar em 2019.** O manual lista "escolhas oportunistas de período" como ponto negativo explícito. A razão real é sólida — a SGS 7806 é descontinuada em 30/09/2019 — mas não aparece; a tabela da p2 só diz "2004–2019". Sem essa linha, um desafio de 2026 que ignora os ciclos de 2021–2022 e 2024–2025 fica exposto à pergunta mais óbvia da banca.

*Menor:* a sensibilidade a custo (0 / 0,5 / 1 / 2 bps) existe no pipeline mas só o cenário de 1 bp aparece.

### 4.5 Análise dos resultados — 15%
**Muito forte.** A p4 é diagnóstico de verdade, não descrição de métrica: por que falhou, o que confunde o sinal (três mudanças colineares na reunião 200), o limite conceitual do léxico (não enxerga negação) e onde a informação de fato está. O gráfico com os pontos separados por fonte de texto sustenta visualmente o argumento da quebra estrutural. Cobre "identificação de limitações" e "consistência da interpretação" com folga.

*Menor:* o manual pede identificar cenários favoráveis e desfavoráveis; a quebra de regime cobre parcialmente, mas falta uma linha do tipo "em que regime esse sinal funcionaria".

### 4.6 Conclusão e próximos passos — 10%
**Boa e proporcional.** Três próximos passos concretos, viabilidade prática com custo, e a recusa explícita de recomendar alocação — exatamente o "evitar conclusões desproporcionais às evidências" do manual.

*Fissura:* o achado que **sobreviveu** ao teste (prêmio de volatilidade de +41% na ata e +130% no comunicado) está como um dos três cartõezinhos, com o rótulo "Próximo 3". É o resultado positivo do trabalho e está subvendido.

### 4.7 Uso de IA generativa — 15%
**Conteúdo bom, espaço incompatível com o peso.** Os três usos são concretos e não declaratórios: instrumento de medida com determinismo travado, par de engenharia que achou dois bugs que invertiam a conclusão, e crítico do próprio resultado que apontou o evento errado. As limitações são específicas. O JSON de saída materializa a auditabilidade.

*Problemas:*
1. É o bloco de prosa mais denso do deck, dividindo a p5 com viabilidade, próximos passos e conclusão — um critério de 15% em ~1/6 de página. O edital recomenda explicitamente espaço compatível com o peso.
2. Zero elemento visual, num relatório que é visual em todo o resto.
3. A auditoria "dois modelos independentes concordam (r = 0,925)" se refere a escores que **não estão no painel testado**. Precisa de precisão cirúrgica na redação, ou vira a mesma incoerência da 4.3.

---

## 3. Coerência entre ideia, modelo e resultado (critério geral)

A leitura mais dura possível do relatório, e a banca vai fazê-la:

> O robô é uma lente de LLM sobre a ata. A lente nunca entrou no teste. O que foi testado e falhou foi um contador de palavras. O único resultado positivo vem da surpresa da decisão, que não usa texto nenhum.

Tudo o que desmonta essa leitura já está no relatório — só que espalhado entre p2, p4 e p5, e nunca dito em uma frase. **Falta a frase.** Algo como:

> O piso léxico é a barra que a CopomLens precisa superar. O piso falhou, então o valor do tom por LLM ainda não está demonstrado — e é por isso que a escoragem das 110 atas é o próximo passo, não uma ambição vaga.

---

## 4. Ações priorizadas

### P0 — antes do envio
1. Renomear o PDF para a chave de envio.
2. Subir o menor corpo de texto (legendas do funil p2, tabela p3, subtítulos de gráfico) e conferir em tela cheia a 100%.

### P1 — maior ganho de nota por palavra editada
3. **Uma linha na p2 sobre o fim da série em 2019** (SGS 7806 descontinuada em 30/09/2019) — fecha a pergunta mais provável da banca e elimina a suspeita de janela escolhida a dedo. ~15 palavras.
4. **Rótulo explícito na Camada 2 da p2**: testado nesta entrega = piso léxico; CopomLens = instrumento auditado, escoragem pendente. ~20 palavras.
5. **Reescrever a ineficiência da p1** de latência para conteúdo informacional, ou subordinar a latência explicitamente ("a janela diária mede o conteúdo, não a velocidade; medir velocidade exige intradiário — Próximo 2").
6. **Promover a volatilidade a estratégia proposta**, com regra declarada (ex.: comprar vol em D−1 do comunicado, zerar em D+1), ancorada no teste que passou. Converte um resultado negativo em proposta positiva e serve os 20% do critério 4.2.
7. **Dar peso visual à IA generativa** — um elemento gráfico da concordância entre modelos ou do espelho 67% → 3%, com a prosa cortada em troca.

### P2 — polimento
8. Cortar ~300 palavras entre p2 (regra cardinal) e p5 (coluna esquerda) para aproximar da referência de 750 e abrir espaço para os itens 6 e 7.
9. Dar ao caveat "limite superior, não executável" o mesmo peso visual do número +209 bps na p3.
10. Incluir a sensibilidade a custo (0 / 0,5 / 1 / 2 bps) como mini-tabela — o dado já existe.
11. Uma linha sobre em que regime o sinal direcional funcionaria (cenário favorável explícito).

---

## 5. O que não mexer

- O funil da amostra com razão por corte.
- "110 de 110 eventos, zero violações" — auditoria de lookahead é diferencial raro.
- A comparação aninhada com Clark-West e a escada de R² OOS negativo.
- O gráfico da quebra da reunião 200 separado por fonte de texto.
- A recusa explícita de recomendar alocação de capital.
- A identidade do robô.
