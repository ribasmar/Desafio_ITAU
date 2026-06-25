# Re-alinhamento da Equipe — Copom Quant AI (Itaú Asset 2026)

**Documento-âncora do pitch.** Funde as boas ideias das discussões da equipe dentro da moldura do pré-relatório v0.1. Onde houver dúvida, este documento vence.

---

## 1. Tese (uma frase)

Prever o *número* da Selic não tem valor — já está precificado (Focus + curva DI). O alfa está no **tom da ata do Copom relativo ao que já estava precificado**, e a hipótese é que esse tom, extraído por LLM, carrega informação **incremental** sobre a reação do **DI 1Y**, além da surpresa da decisão e além de um **baseline léxico**. "Não há ganho incremental" é resultado válido e será reportado como tal.

## 2. Decisões fechadas (não reabrir)

| Item | Decisão |
|---|---|
| **Alvo único de reação** | **DI 1Y** (vértice de 1 ano). Mais líquido, sem slippage de FII, resposta quase direta à semântica. |
| **Objeto textual primário** | **Ata** (rica em forward guidance). Comunicado = apoio, para medir a surpresa da decisão. |
| **Entregável** | **Estratégia quantitativa** (posições, P&L, Sharpe, drawdown). NÃO é produto/ferramenta. |
| **Baseline léxico** | **Obrigatório.** A LLM só se justifica se superá-lo out-of-sample. |
| **LLM** | Extrator **determinístico** (modelo open-source local, pesos fixados, greedy/seed fixo) → JSON auditável. **Sem fine-tuning** (amostra pequena demais). |
| **Disciplina temporal** | Point-in-time: cada texto/feature carimbado com **timestamp real de publicação**. |

## 3. O que ENTRA das discussões da equipe (boas ideias, reenquadradas)

- **Mecânica Comunicado→Ata** como residualização: o comunicado (quarta) já precificou parte; o ganho está no **resíduo da ata** (terça seguinte). Não é "segunda surpresa solta".
- **Calibração dinâmica por regime / mandato do BCB** (janelas expanding; marcação de gestões). Combate não-estacionariedade.
- **Camada de fricção no backtest**: custos de corretagem, emolumentos B3, entrada no *open* da janela do evento (anti look-ahead).
- **Estudo de eventos em janelas curtas** (24/48/72h pós-publicação), coerente com a baixa frequência (8 reuniões/ano).

## 4. O que SAI do centro (ou vira "próximos passos")

- **Interface conversacional** → apenas **demo de auditoria** no pitch (ver §6), nunca o entregável.
- **FIIs / cabaz de ações / volatilidade como fim** → fora; o alvo é DI 1Y.
- **Fine-tuning / bge-m3 como "backbone"** → fora do caminho crítico. Embeddings ≠ extração de tom; no máximo feature auxiliar futura.

## 5. Pipeline (5 camadas)

1. **Ingestão + timestamping** → dataset point-in-time (atas, comunicados, DI, Focus).
2. **Extração de tom (LLM como função, temp 0)** → `{stance, stance_delta, forward_guidance, incerteza, conviccao, justificativa}` + **baseline léxico** em paralelo.
3. **Surpresa precificada** → `surpresa_decisao = Selic_efetiva − Selic_esperada` (Focus/DI).
4. **Modelo preditivo aninhado (walk-forward)**: (1) só surpresa → (2) + tom léxico → (3) + tom-LLM. O **ganho incremental (1)→(2)→(3)** é o resultado-manchete.
5. **Estratégia + backtest**: previsão → posição em DI 1Y → P&L líquido de custos → Sharpe, drawdown vs. baseline ingênuo.

## 6. Papel da IA generativa (critério 15%) e da interface

- **Uso que pontua:** LLM como extrator determinístico, com saída JSON auditável e **trecho citado** (`justificativa`). Concreto, relevante, replicável.
- **Interface = instrumento de auditoria, não produto.** Frase para o deck: *"a estratégia é o entregável; a interface é o instrumento de auditoria do extrator."* Mostra: abrir uma ata → ver o score e o trecho que o embasou.

## 7. Ordem do pitch (não inverter)

1. Tese + hipótese falsificável.
2. **Manchete:** ganho incremental do tom-LLM sobre o baseline léxico (out-of-sample, DI 1Y).
3. Estratégia: Sharpe / drawdown líquidos de custo vs. baseline ingênuo.
4. **Só então** a demo da interface (prova de auditabilidade).
5. Limitações honestas + próximos passos.

> Se a interface abrir o pitch, a banca arquiva como "ferramenta, não estratégia". A demo entra no fim.

## 8. Limitações a reportar (sem esconder)

Amostra pequena (poucas centenas de eventos); não-estacionariedade de regime; **contaminação por hindsight** da LLM (mitigação: baseline léxico é livre de contaminação por construção; validar em atas pós-cutoff do modelo); janela tradeável estreita → realismo de custos.

## 9. Visão de deployment — do sinal ao wealth (roadmap, critério 10%)

> Seção de **próximos passos**, não de resultado. Tudo aqui é visão de produto: nada é backtestado nem usa dado de cliente real. Entra como slide de encerramento do pitch.

O sinal de tom no DI 1Y é uma **primitiva**. Em produção dentro do Itaú, ela se desdobra em três camadas de valor, da mais testada à mais visionária:

1. **Posicionamento tático** em fundos de renda fixa/multimercado — o uso direto, já backtestado neste trabalho.
2. **Gatilho risk-off para wealth/Private** — surpresa *hawkish* na ata → tilt defensivo / sinal de rebalanceamento. O **mesmo sinal mapeia diferente conforme o perfil de suitability** (conservador vs. agressivo): ponte de deployment, não novo backtest.
3. **Comentário/alerta personalizado** ao cliente Private, servido pela interface de auditoria ("a ata foi mais dura que o precificado; veja o trecho").

**Open Finance** aparece aqui apenas como *arquitetura futura* de personalização (consentimento do cliente → ajuste de carteira). **Não** é usado no projeto: não há dado de cliente consentido, e LGPD/consentimento são pré-requisitos. Apresentar como roadmap, nunca como algo testado.

## 10. Papéis e responsabilidades

Time de **Engenharia da Computação (UTFPR)** + validação estatística + mentoria. Cada camada do pipeline tem um dono explícito — sem dono, a camada vira ponto cego de nota.

| Pessoa | Papel | Camadas / critérios |
|---|---|---|
| **Rafael Ribas** | Lead de estratégia & produto. Conversão sinal→posição, visão de deployment/wealth (ancorada na sua experiência real de Open Finance/Lizard) e fio condutor do pitch. | Camada 5 · §9 · narrativa |
| **Gustavo More** | Lead de engenharia. Pipeline point-in-time, LLM open-source local determinístico e **reprodutibilidade** (nossa vantagem competitiva). | Camadas 1–2 · Modelagem (20%) · IA (15%) |
| **Elder Nunes** | Lead de identidade & comunicação. Apresentação do robô, deck e clareza narrativa. | Critério 1 (5%) · comunicação transversal |
| **Validação estatística** *(a confirmar — indicado pelo Rafael)* | Revisa o **rigor da camada 4**: comparação aninhada, walk-forward, validação out-of-sample e controle de overfitting na amostra pequena. | Camada 4 · Backtest (15%) |
| **Randerson (mentor)** | Não executa o pipeline. Blinda a **leitura macro/juros** (camada 3) e impõe a disciplina anti-overfitting; orienta método e honestidade científica. | Camada 3 · rigor transversal |

> **Status dos gaps de competência.** Rigor estatístico (camada 4): **coberto** pela nova validação estatística. Leitura macro/juros (camada 3): sob responsabilidade do **mentor + exposição de mercado da Liga** — é o ponto a vigiar para a tese não soar ingênua à banca de asset.

## 11. Ainda em aberto

- Granularidade de mercado: intradiário vs. fechamento (condiciona a janela do evento).
- Modelo do extrator open-source específico + verificação do cutoff de treino (para o teste de contaminação).
