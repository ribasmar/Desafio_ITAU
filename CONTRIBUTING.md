# Como contribuir

Fluxo leve para o time praticar PRs com qualidade. Nada de commit direto na `main`.

## Branches

Uma branch por tarefa, nomeada por tipo:

```
feat/ingest-copom        # nova funcionalidade
fix/timestamp-fuso       # correção
docs/identidade-robo     # documentação
chore/reorg-estrutura    # infra/manutenção
```

## Commits (Conventional Commits)

```
<tipo>(escopo opcional): descrição no imperativo

feat(ingest): coletor de atas do Copom via API do BCB
fix(features): corrige fuso do timestamp de publicação
docs(readme): adiciona seção de reprodutibilidade
```

Tipos: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`. Commits pequenos e frequentes > um commit gigante.

## Pull Requests

1. Abra a PR contra `main` com título no padrão de commit.
2. Preencha o template (o que muda, por quê, como testou).
3. Marque **um revisor** (outro membro ou o mentor).
4. Toda PR deve responder: **isso respeita a regra point-in-time?**
5. Merge só após 1 aprovação.

## Disciplina point-in-time (inegociável)

Antes de abrir qualquer PR que toque em dados ou features, confirme:
- nenhum dado entra em feature usando a **data da reunião** em vez da **data de publicação**;
- `data/raw/` não foi alterado após a escrita (é imutável).

## Setup local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```
