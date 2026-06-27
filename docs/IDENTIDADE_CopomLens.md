# Identidade do Projeto — CopomLens

> Documento de identidade visual e narrativa do projeto.
> Usar como referência para deck, README, interface de auditoria e pitch.

---

## Nome

**CopomLens**

O "Lens" em destaque (verde na identidade visual) representa a metáfora central: uma lente que foca o que já está escrito na ata e torna visível o que o olho humano demora horas pra ver.

---

## Tagline

> "Uma lente sobre o que o Banco Central realmente está dizendo."

Versão em inglês (para slides internacionais):
> "A lens on what the Central Bank is really saying."

---

## Logo

Ícone de lente de mira — círculos concêntricos com ponto central.
Representa precisão, foco e leitura sistemática.

```
    ◎
  CopomLens
```

Arquivo vetorial: a ser criado em SVG (círculos concêntricos, cor primária teal #1D9E75).

---

## Paleta de cores

| Papel | Nome | Hex |
|---|---|---|
| Primária | Teal escuro | `#1D9E75` |
| Primária hover | Teal profundo | `#0F6E56` |
| Primária fundo | Teal claro | `#E1F5EE` |
| Secundária | Cinza médio | `#444441` |
| Secundária muted | Cinza claro | `#888780` |
| Fundo neutro | Off-white | `#F1EFE8` |

**Teal** → precisão, clareza, confiança. É a cor da lente.
**Cinza** → rigor, neutralidade, auditabilidade. O projeto não inventa: lê e reporta.

---

## Linha do pitch (frase de abertura)

> "Enquanto analistas levam 4 horas pra ler a ata, a CopomLens já devolveu o score — em segundos, com o trecho que o embasou."

---

## Como usar em cada entregável

### No deck (slides)
- Logo + tagline na capa
- Linha do pitch no slide de abertura do problema
- Cor primária teal nos destaques e gráficos

### No repositório
- README começa com o nome `CopomLens` e a tagline
- Função principal de extração: `copom_lens()` ou `extract_tone()`
- Pasta `src/copom/` mantida — o módulo se chama internamente CopomLens

### Na interface de auditoria
- Header: "CopomLens — Score da ata [número] · [data]"
- Output JSON com score e trecho citado
- Cores teal para scores hawkish positivos, neutro para zero, cinza para dovish

### No pitch oral
Frase de encerramento da demo:
> "A estratégia é o entregável. A CopomLens é o instrumento de auditoria — qualquer um na banca pode rodar o mesmo texto e obter o mesmo JSON."

---

## Output padrão da CopomLens

```json
{
  "stance": 0.6,
  "stance_delta": +0.2,
  "forward_guidance": "aperto",
  "incerteza": 0.3,
  "conviccao": 0.8,
  "justificativa": "O Comitê avalia que a convergência da inflação para a meta requer postura mais contracionista..."
}
```

---

## Badges para deck e documentação

`CopomLens` · `extrator LLM` · `score auditável` · `DI 1Y` · `backtest` · `walk-forward` · `baseline léxico` · `point-in-time`

---

## O que NÃO fazer com a identidade

- Não usar "Copom Quant AI" como nome principal — CopomLens é o nome do projeto
- Não apresentar a interface antes da estratégia no pitch (a demo entra no fim como auditoria)
- Não dizer "a IA substitui o analista" — a CopomLens libera o analista do trabalho mecânico

---

*Documento criado em 27/06/2026 · Dono: Elder Nunes · Task #7 do Sprint 0*