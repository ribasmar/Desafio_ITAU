# CopomLens — Camada 3: calcula a SURPRESA DA DECISAO do Copom para uma reuniao:
#   surpresa = Selic_efetiva - Selic_esperada
# Selic_efetiva = Meta Selic vigente apos a decisao (serie SGS 432).
# Selic_esperada = mediana do Focus para aquela reuniao, tomada no ULTIMO survey
# disponivel ANTES da data da reuniao (disciplina point-in-time: nada que so se
# soube depois pode entrar). Resultado em pontos percentuais (p.p.).
"""Surpresa da decisao do Copom (em p.p.) a partir de Selic efetiva e Focus."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from pandas.tseries.offsets import BDay

# Calendario do Copom (inicio da reuniao de 2 dias e data da decisao = 2o dia).
# A surpresa precisa do inicio (corte point-in-time do Focus) e da data da
# decisao (leitura da meta efetiva). Datas de 2025 e 2026 validadas contra o
# calendario oficial do BCB. Estender conforme o BCB publica novos anos.
COPOM_CALENDAR: dict[str, dict[str, date]] = {
    "R1/2025": {"inicio": date(2025, 1, 28), "decisao": date(2025, 1, 29)},
    "R2/2025": {"inicio": date(2025, 3, 18), "decisao": date(2025, 3, 19)},
    "R3/2025": {"inicio": date(2025, 5, 6), "decisao": date(2025, 5, 7)},
    "R4/2025": {"inicio": date(2025, 6, 17), "decisao": date(2025, 6, 18)},
    "R5/2025": {"inicio": date(2025, 7, 29), "decisao": date(2025, 7, 30)},
    "R6/2025": {"inicio": date(2025, 9, 16), "decisao": date(2025, 9, 17)},
    "R7/2025": {"inicio": date(2025, 11, 4), "decisao": date(2025, 11, 5)},
    "R8/2025": {"inicio": date(2025, 12, 9), "decisao": date(2025, 12, 10)},
    "R1/2026": {"inicio": date(2026, 1, 27), "decisao": date(2026, 1, 28)},
    "R2/2026": {"inicio": date(2026, 3, 17), "decisao": date(2026, 3, 18)},
    "R3/2026": {"inicio": date(2026, 4, 28), "decisao": date(2026, 4, 29)},
    "R4/2026": {"inicio": date(2026, 6, 16), "decisao": date(2026, 6, 17)},
    "R5/2026": {"inicio": date(2026, 8, 4), "decisao": date(2026, 8, 5)},
    "R6/2026": {"inicio": date(2026, 9, 15), "decisao": date(2026, 9, 16)},
    "R7/2026": {"inicio": date(2026, 11, 3), "decisao": date(2026, 11, 4)},
    "R8/2026": {"inicio": date(2026, 12, 8), "decisao": date(2026, 12, 9)},
}


@dataclass(frozen=True)
class SurpresaDecisao:
    """Resultado auditavel da surpresa de uma reuniao."""

    reuniao: str
    data_decisao: date
    selic_efetiva: float
    selic_esperada: float
    surpresa: float
    data_expectativa: date  # data do survey Focus usado (prova do point-in-time)
    n_respondentes: int | None


def selic_esperada(
    focus: pd.DataFrame,
    reuniao: str,
    data_reuniao: date,
    base_calculo: int = 0,
    defasagem_dias_uteis: int = 1,
) -> tuple[float, date, int | None]:
    """Mediana Focus da reuniao no ultimo survey publico ANTES de `data_reuniao`.

    Retorna (mediana, data_do_survey, n_respondentes). Levanta ValueError se nao
    houver survey valido (evita lookahead).

    `defasagem_dias_uteis` recua o corte para refletir que o survey de referencia
    do dia D so se torna publico ~1 dia util depois: com o default 1, exige
    `data_survey < inicio - 1 dia util`. Use 0 para cortar exatamente no inicio.
    Aproximacao: BDay considera apenas fins de semana, nao feriados nacionais.
    """
    sel = focus[focus["reuniao"] == reuniao].copy()
    if "base_calculo" in sel.columns and base_calculo is not None:
        sel = sel[sel["base_calculo"] == base_calculo]

    corte = pd.Timestamp(data_reuniao) - BDay(defasagem_dias_uteis)
    sel = sel[(pd.to_datetime(sel["data"]) < corte) & sel["mediana"].notna()]
    if sel.empty:
        raise ValueError(
            f"Sem expectativa Focus valida para {reuniao} antes de {data_reuniao} "
            "(point-in-time): nada a usar como Selic esperada."
        )

    linha = sel.sort_values("data").iloc[-1]
    n = linha.get("n_respondentes")
    n = int(n) if pd.notna(n) else None
    return float(linha["mediana"]), pd.to_datetime(linha["data"]).date(), n


def selic_efetiva(selic_meta: pd.DataFrame, data_decisao: date) -> float:
    """Meta Selic vigente imediatamente APOS a decisao.

    Retorna o primeiro valor da serie 432 com data ESTRITAMENTE posterior a data
    da decisao — a meta votada passa a valer no dia seguinte. Levanta ValueError
    se a serie ainda nao cobrir o pos-decisao (ex.: rodando no mesmo dia da
    reuniao, antes de o SGS publicar a nova meta), em vez de devolver
    silenciosamente a meta antiga.
    """
    df = selic_meta.copy()
    df["data"] = pd.to_datetime(df["data"])
    pos = df[df["data"] > pd.Timestamp(data_decisao)].sort_values("data")
    if pos.empty:
        raise ValueError(
            f"Serie de Meta Selic nao cobre o pos-decisao de {data_decisao}: meta "
            "efetiva ainda indisponivel (reuniao corrente ou serie desatualizada?)."
        )
    return float(pos.iloc[0]["selic_meta"])


def surpresa_decisao(
    reuniao: str,
    selic_meta: pd.DataFrame,
    focus: pd.DataFrame,
    base_calculo: int = 0,
    defasagem_dias_uteis: int = 1,
) -> SurpresaDecisao:
    """Calcula a surpresa (p.p.) de uma reuniao do Copom.

    surpresa > 0 -> decisao mais dura (hawkish) que o esperado;
    surpresa < 0 -> mais branda (dovish); ~0 -> em linha com o Focus.
    `defasagem_dias_uteis` e repassado a `selic_esperada` (point-in-time).
    """
    if reuniao not in COPOM_CALENDAR:
        raise KeyError(f"Reuniao {reuniao} fora do calendario; atualize COPOM_CALENDAR.")

    cal = COPOM_CALENDAR[reuniao]
    esperada, data_exp, n = selic_esperada(
        focus, reuniao, cal["inicio"], base_calculo, defasagem_dias_uteis
    )
    efetiva = selic_efetiva(selic_meta, cal["decisao"])

    return SurpresaDecisao(
        reuniao=reuniao,
        data_decisao=cal["decisao"],
        selic_efetiva=efetiva,
        selic_esperada=esperada,
        surpresa=round(efetiva - esperada, 4),
        data_expectativa=data_exp,
        n_respondentes=n,
    )


def _demo() -> None:
    """Demo de aceite: calcula a surpresa de UMA reuniao a partir de data/raw/."""
    from pathlib import Path

    raw = Path(__file__).resolve().parents[3] / "data" / "raw"
    selic = pd.read_csv(raw / "selic_meta.csv")
    focus = pd.read_csv(raw / "focus_selic.csv")

    reuniao = "R4/2026"
    res = surpresa_decisao(reuniao, selic, focus)
    print(
        f"{res.reuniao} | efetiva={res.selic_efetiva:.2f}% | "
        f"esperada={res.selic_esperada:.2f}% (Focus {res.data_expectativa}, "
        f"n={res.n_respondentes}) | surpresa={res.surpresa:+.2f} p.p."
    )


if __name__ == "__main__":
    _demo()
