# Central Bank Lens — Extração de Tom v3

Analise o documento de política monetária abaixo e extraia os indicadores de tom.
Baseie cada valor exclusivamente em evidência textual do documento.
Não use conhecimento sobre eventos posteriores à data deste documento.

---

**REGRA CENTRAL — O QUE ESTÁ SENDO MEDIDO:**

Este prompt classifica a **COMUNICAÇÃO** do Copom: o tom da linguagem — viés
declarado, balanço de riscos, forward guidance, grau de certeza e ênfase temática.

A decisão de juros (direção e magnitude do corte/alta/manutenção) é **contexto**,
não critério. Dois documentos com a mesma decisão podem — e devem, quando a
linguagem diferir — receber rótulos diferentes. Se a única diferença entre dois
documentos for a magnitude da decisão, isso NÃO deve mover o rótulo.

**CLASSIFICAÇÃO DE POSTURA — escolha exatamente UM rótulo desta lista:**

emergencial_dovish     = linguagem de crise com fortíssima acomodação, tom de urgência máxima
agressivo_dovish       = sinal decisivo e intenso de flexibilização, linguagem de urgência
claramente_dovish      = acomodação forte e inequívoca, sem ambiguidade
moderadamente_dovish   = viés dovish claro, sem urgência
levemente_dovish       = inclinação dovish suave, tom cauteloso
marginalmente_dovish   = inclinação dovish tênue
neutro_dovish          = equilíbrio, inclinando levemente para flexibilização
neutro                 = genuinamente equilibrado — raro
neutro_hawkish         = equilíbrio, inclinando levemente para aperto
marginalmente_hawkish  = inclinação hawkish tênue
levemente_hawkish      = inclinação hawkish suave, tom cauteloso
moderadamente_hawkish  = viés hawkish claro, sem urgência
claramente_hawkish     = restrição forte e inequívoca
agressivo_hawkish      = sinal decisivo e intenso de aperto, linguagem de urgência
emergencial_hawkish    = linguagem de crise com fortíssima restrição, tom de urgência máxima

**SELEÇÃO DA POSTURA — pese estas 5 dimensões da comunicação:**
1. Viés declarado (dovish ↔ hawkish) e sua intensidade
2. Balanço de riscos (inflação ↔ atividade/crescimento)
3. Forward guidance (indica próximos passos)
4. Grau de certeza da linguagem (tentativa ↔ decisiva)
5. Ênfase temática (inflação, atividade, cenário externo)

**ORIENTAÇÃO FUTURA (forward_guidance):**
- aperto       = sinalização de alta de juros no futuro
- manutencao   = manutenção da taxa atual
- afrouxamento = sinalização de corte de juros no futuro
- neutro       = sem sinalização clara / data-dependent

---

**EXEMPLOS DE CLASSIFICAÇÃO — estude a relação entre o texto e o rótulo:**

Os exemplos citam apenas a linguagem; a decisão de juros não aparece porque
não é critério de classificação.

"Linguagem de crise, citando deterioração abrupta, fuga de capitais e risco imediato, com tom de urgência máxima."
→ agressivo_hawkish

"Viés de alta firme, citando deterioração do cenário inflacionário, sem tom de urgência."
→ moderadamente_hawkish

"Preocupação com pressões generalizadas e prontidão para agir, com linguagem cautelosa."
→ levemente_hawkish

"Preocupação limitada, citando pressões localizadas, sem sinal de prontidão imediata."
→ marginalmente_hawkish

"Equilíbrio entre os riscos, com leve ênfase na vigilância inflacionária."
→ neutro_hawkish

"Equilíbrio genuíno entre riscos inflacionários e de atividade, sem inclinação."
→ neutro

"Equilíbrio entre os riscos, com leve ênfase na desaceleração da atividade."
→ neutro_dovish

"Alívio modesto e cauteloso, citando necessidade de avaliar os próximos passos."
→ marginalmente_dovish

"Viés de baixa firme, citando convergência da inflação para a meta."
→ moderadamente_dovish

"Comunicação de forte acomodação, citando recessão técnica e colapso da demanda agregada."
→ claramente_dovish

---

**REGRAS DE EVIDÊNCIA:**
A justificativa deve citar trecho do documento com avaliação prospectiva.
NÃO cite como evidência o nível da Selic, a magnitude em p.p., nem a votação —
a decisão de juros não é critério de classificação.

**FORMATO DE SAÍDA:**
Responda APENAS com o objeto JSON abaixo — sem texto antes ou depois.

{
  "stance_label": "<rótulo exato da lista de classificação acima>",
  "forward_guidance": "<aperto|manutencao|afrouxamento|neutro>",
  "incerteza": <float 0.0 a 1.0>,
  "conviccao": <float 0.0 a 1.0>,
  "justificativa": "<trecho citado do documento que sustenta sua avaliação>"
}

Documento ({tipo}, publicado em {data_publicacao}):

"""
{texto}
"""
