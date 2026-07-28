# Central Bank Lens — Extração de Tom v2

Analise o documento de política monetária abaixo e extraia os indicadores de tom.
Baseie cada valor exclusivamente em evidência textual do documento.
Não use conhecimento sobre eventos posteriores à data deste documento.

---

**CLASSIFICAÇÃO DE POSTURA — escolha exatamente UM rótulo desta lista:**

emergencial_dovish     = cortes de crise + linguagem fortemente acomodatícia
agressivo_dovish       = corte grande + sinal decisivo de flexibilização
claramente_dovish      = corte significativo + forward guidance dovish
moderadamente_dovish   = corte moderado com viés claramente dovish
levemente_dovish       = corte modesto, tom cauteloso
marginalmente_dovish   = corte pequeno OU manutenção com viés dovish
neutro_dovish          = manutenção, inclinando para flexibilização
neutro                 = genuinamente equilibrado — raro
neutro_hawkish         = manutenção, inclinando para aperto
marginalmente_hawkish  = alta pequena OU manutenção com viés hawkish
levemente_hawkish      = alta modesta, tom cauteloso
moderadamente_hawkish  = alta moderada com viés claramente hawkish
claramente_hawkish     = alta significativa + forward guidance hawkish
agressivo_hawkish      = alta grande + sinal decisivo de aperto
emergencial_hawkish    = altas de crise + linguagem fortemente restritiva

**SELEÇÃO DA POSTURA — pese estas 5 dimensões:**
1. Direção + magnitude da ação sobre a taxa de juros
2. Surpresa em relação às expectativas de mercado
3. Grau de certeza da linguagem (tentativa ↔ decisiva)
4. Sinal de forward guidance (indica próximos passos)
5. Balanço de riscos (inflação ↔ atividade/crescimento)

**ORIENTAÇÃO FUTURA (forward_guidance):**
- aperto       = sinalização de alta de juros no futuro
- manutencao   = manutenção da taxa atual
- afrouxamento = sinalização de corte de juros no futuro
- neutro       = sem sinalização clara / data-dependent

---

**EXEMPLOS DE CLASSIFICAÇÃO — estude a relação entre o texto e o rótulo:**

"Aumentou a Selic em 1,00 p.p., em reunião extraordinária, citando crise cambial e fuga de capitais."
→ agressivo_hawkish

"Aumentou a Selic em 0,50 p.p., com viés de alta, citando deterioração do cenário inflacionário."
→ moderadamente_hawkish

"Aumentou a Selic em 0,25 p.p., de forma unânime, citando pressões generalizadas e urgência de ação."
→ levemente_hawkish

"Aumentou a Selic em 0,25 p.p., por maioria, citando pressões localizadas."
→ marginalmente_hawkish

"Manteve a Selic, mas destacou que pressões inflacionárias exigem vigilância contínua."
→ neutro_hawkish

"Manteve a Selic, sem viés, citando equilíbrio entre os riscos inflacionários e de atividade."
→ neutro

"Manteve a Selic, citando desaceleração da atividade e arrefecimento da inflação."
→ neutro_dovish

"Reduziu a Selic em 0,25 p.p., citando cautela e necessidade de avaliar os próximos passos."
→ marginalmente_dovish

"Reduziu a Selic em 0,50 p.p., com viés de baixa, citando convergência da inflação para a meta."
→ moderadamente_dovish

"Reduziu a Selic em 0,75 p.p., citando recessão técnica e colapso da demanda agregada."
→ claramente_dovish

---

**REGRA DE PRECISÃO:**
Todos os valores numéricos devem ter exatamente 4 casas decimais.

**FORMATO DE SAÍDA:**
Responda APENAS com o objeto JSON abaixo — sem texto antes ou depois.

{
  "stance_label": "<rótulo exato da lista de classificação acima>",
  "forward_guidance": "<aperto|manutencao|afrouxamento|neutro>",
  "incerteza": <float 0.0000 a 1.0000, 4 casas>,
  "conviccao": <float 0.0000 a 1.0000, 4 casas>,
  "justificativa": "<trecho citado do documento que sustenta sua avaliação>"
}

Documento ({tipo}, publicado em {data_publicacao}):

"""
{texto}
"""
