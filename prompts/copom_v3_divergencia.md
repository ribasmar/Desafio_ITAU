# Central Bank Lens — Divergência Ata × Comunicado v3

Você recebe DOIS documentos da MESMA reunião do Copom: o Comunicado
(publicado no dia da decisão) e a Ata (publicada ~6 dias depois).

Compare o TOM da Ata com o TOM do Comunicado.
Baseie cada valor exclusivamente nos dois textos fornecidos.
Não use conhecimento sobre eventos posteriores à data da Ata.

---

**COMO COMPARAR — TRÊS PASSOS:**

1. TOM DO COMUNICADO: resuma o tom de política monetária do comunicado
   (viés, balanço de riscos, sinalização). O comunicado é curto — em geral
   traz quase só a decisão, com pouco ou nenhum tom.

2. TOM DA ATA: resuma o tom da ata (viés, balanço de riscos, forward
   guidance, convicção).

3. COMPARE: a ata SEMPRE acrescenta conteúdo que o comunicado não tinha
   (riscos, projeções, justificativas, sinalizações). Classifique a DIREÇÃO
   e a MAGNITUDE desse acréscimo em relação ao tom do comunicado.

A decisão de juros (nível/magnitude da Selic) NÃO conta: os dois documentos
tratam da mesma decisão. Confirmar a decisão não é divergência; revelar tom
novo é.

`direcao = igual` NÃO é default: só use quando a ata tiver o MESMO tom do
comunicado (mesma direção e mesma intensidade) — raro. Se a ata acrescentar
qualquer inclinação hawkish ou dovish, `direcao` deve ser `ata_mais_hawkish`
ou `ata_mais_dovish`.

**CAMPOS:**

- `direcao` — em que direção a ata move o leitor em relação ao comunicado:
  - `ata_mais_hawkish` = a ata revela riscos/aperto que o comunicado não sinalizava
  - `igual` = mesmo tom (raro)
  - `ata_mais_dovish` = a ata revela alívio/afrouxamento que o comunicado não sinalizava

- `magnitude` — intensidade da divergência (`nenhuma` apenas se `direcao = igual`):
  - `leve` = deslocamento pequeno
  - `clara` = deslocamento nítido
  - `forte` = a ata muda substancialmente o tom (contradiz ou inverte)

- `eixo_divergencia` — onde está a divergência:
  - `riscos` = balanço de riscos (inflação ↔ atividade)
  - `conviccao` = grau de certeza/convicção
  - `horizonte` = horizonte de projeção relevante
  - `condicionalidade` = condições para os próximos passos
  - `nenhum` = sem divergência relevante

- `justificativa_ata` / `justificativa_comunicado` — trechos citados que
  sustentam direção e magnitude. NÃO cite nível da Selic, magnitude em p.p.,
  nem votação como evidência.

**EXEMPLOS — estude a relação entre o par e a classificação:**

Exemplo 1
Comunicado: "O Copom decidiu elevar a taxa Selic. A inflação segue acima da meta."
Ata: "A desaceleração da atividade e a dissipação dos choques de oferta indicam que o ciclo de aperto pode estar próximo do fim; o balanço de riscos tornou-se assimétrico para baixo."
→ direcao: ata_mais_dovish · magnitude: clara · eixo: condicionalidade

Exemplo 2
Comunicado: "O Copom decidiu elevar a taxa Selic. O ambiente segue desafiador."
Ata: "Os indicadores de atividade vieram abaixo do esperado e os efeitos defasados do aperto ainda não se materializaram; o Comitê avalia pausar o ciclo."
→ direcao: ata_mais_dovish · magnitude: forte · eixo: riscos

Exemplo 3
Comunicado: "O Copom decidiu manter a taxa Selic. A conjuntura econômica permanece sob monitoramento."
Ata: "A ata confirma a decisão sem acrescentar avaliação de riscos ou sinalização de próximos passos."
→ direcao: igual · magnitude: nenhuma · eixo: nenhum

Exemplo 4
Comunicado: "O Copom decidiu reduzir a taxa Selic. As condições de atividade seguem fracas."
Ata: "Os indicadores de atividade surpreenderam para cima; a ociosidade é menor do que o previsto e o ritmo de cortes será reavaliado."
→ direcao: ata_mais_hawkish · magnitude: leve · eixo: riscos

Exemplo 5
Comunicado: "O Copom decidiu manter a taxa Selic. Não há sinalização sobre os próximos passos."
Ata: "O balanço de riscos piorou: a inflação mostra persistência, as expectativas desancoraram e há incerteza fiscal. O Comitê avalia que um novo ciclo de aperto pode ser necessário."
→ direcao: ata_mais_hawkish · magnitude: forte · eixo: riscos

**FORMATO DE SAÍDA (APENAS JSON):**

{
  "direcao": "<ata_mais_hawkish|igual|ata_mais_dovish>",
  "magnitude": "<leve|clara|forte|nenhuma>",
  "eixo_divergencia": "<riscos|conviccao|horizonte|condicionalidade|nenhum>",
  "justificativa_ata": "<trecho citado da Ata>",
  "justificativa_comunicado": "<trecho citado do Comunicado>"
}

Comunicado (publicado em {data_publicacao_comunicado}):

"""
{texto_comunicado}
"""

Ata (publicada em {data_publicacao_ata}):

"""
{texto_ata}
"""
