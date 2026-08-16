# Gera os quatro graficos do relatorio a partir dos artefatos ja calculados.
# Paleta CopomLens validada pelo validador do metodo (teal da marca no slot 1,
# azul e laranja de referencia); contraste do teal fica em 2,94:1 sobre o
# off-white da marca, entao todo grafico traz rotulo direto visivel, que e o
# alivio exigido nesse caso. Sem eixo duplo, sem cor carregando identidade
# sozinha, texto sempre em tinta neutra.
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "analise"
FIG = Path(__file__).resolve().parents[2] / "docs" / "assets"
FIG.mkdir(parents=True, exist_ok=True)

TEAL, AZUL, LARANJA = "#1D9E75", "#2a78d6", "#eb6834"
SUPERFICIE = "#F1EFE8"
TINTA, TINTA2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRADE, BASE = "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "axes.edgecolor": BASE, "axes.labelcolor": TINTA2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TINTA, "axes.titlecolor": TINTA,
    "grid.color": GRADE, "grid.linewidth": 0.8,
    "savefig.facecolor": SUPERFICIE, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def limpar(ax, grade_y=True):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.spines["left"].set_color(BASE)
    ax.spines["bottom"].set_color(BASE)
    if grade_y:
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linewidth=0.8, color=GRADE)
        ax.xaxis.grid(False)


def barra_arredondada(ax, x, altura, largura, cor, raio=0.035):
    y0, y1 = (0, altura) if altura >= 0 else (altura, 0)
    p = FancyBboxPatch((x - largura / 2, y0), largura, abs(altura),
                       boxstyle=f"round,pad=0,rounding_size={raio}",
                       linewidth=0, facecolor=cor, mutation_aspect=abs(altura) / largura if largura else 1)
    ax.add_patch(p)
    return y1


# ---------------------------------------------------------------- 1. evento
rob = json.loads((OUT / "robustez.json").read_text(encoding="utf-8"))
ev = rob["evento_vs_dia_qualquer"]

fig, ax = plt.subplots(figsize=(6.4, 3.6))
vals = [ev["abs_var_media_dia_ata_bps"], ev["abs_var_media_dia_normal_bps"]]
rots = [f"Dia de publicação\nda ata  (n={ev['n_dias_ata']})", f"Dia qualquer\n(n={ev['n_dias_normais']:,})".replace(",", ".")]
for i, (v, c) in enumerate(zip(vals, [TEAL, MUTED])):
    ax.bar(i, v, width=0.5, color=c, zorder=3)
    ax.text(i, v + 0.25, f"{v:.2f} bps", ha="center", va="bottom", fontsize=13, fontweight="bold", color=TINTA)
ax.set_xticks(range(2), rots, fontsize=10, color=TINTA2)
ax.set_ylabel("variação absoluta média do DI 1Y (bps)", fontsize=9.5)
ax.set_ylim(0, max(vals) * 1.30)
ax.set_title("A ata move o DI 1Y — o evento existe", fontsize=13, fontweight="bold", loc="left", pad=34)
ax.text(0, 1.045, f"+{(vals[0]/vals[1]-1)*100:.0f}% de variação média · Mann-Whitney p = {ev['mannwhitney_p_ata_maior']:.4f}",
        transform=ax.transAxes, fontsize=9.5, color=TINTA2, va="bottom")
limpar(ax)
fig.savefig(FIG / "1_evento.png")
plt.close(fig)

# ------------------------------------------------------- 2. curvas de equity
cur = pd.read_csv(OUT / "curvas_equity.csv", parse_dates=["data"])
painel = pd.read_csv(OUT / "painel_com_tom.csv", parse_dates=["data_publicacao_ata"]).sort_values("data_publicacao_ata").reset_index(drop=True)
painel["lex_delta"] = painel["lex_score"].diff()
oos = painel[painel["data_publicacao_ata"].isin(cur["data"])].reset_index(drop=True)
pos = np.sign(oos["lex_delta"].fillna(0.0).to_numpy(float))
bruto = np.cumsum(pos * oos["reacao_bps"].to_numpy(float))

fig, ax = plt.subplots(figsize=(7.2, 3.8))
series = [(cur["data"], bruto, TEAL, "Regra de tom — bruto"),
          (cur["data"], cur["S3_regra_delta_tom"], LARANJA, "Regra de tom — líquido de custo"),
          (cur["data"], cur["B1_sempre_recebe_fixo"], AZUL, "Benchmark: sempre recebe fixo")]
for x, y, c, lab in series:
    ax.plot(x, y, color=c, linewidth=2.0, label=lab, zorder=3)
    ax.annotate(f"{y.iloc[-1] if hasattr(y,'iloc') else y[-1]:+.0f}", (x.iloc[-1], y.iloc[-1] if hasattr(y, "iloc") else y[-1]),
                xytext=(7, 0), textcoords="offset points", va="center", fontsize=10, fontweight="bold", color=TINTA)
ax.axhline(0, color=BASE, linewidth=1.2, zorder=2)
ax.set_ylabel("P&L acumulado (bps de taxa)", fontsize=9.5)
ax.set_title("No bruto o sinal termina em zero: é ruído, não borda", fontsize=13, fontweight="bold", loc="left", pad=34)
ax.text(0, 1.045, "70 eventos out-of-sample · +1 bp bruto acumulado, drawdown de 100 bps no caminho", transform=ax.transAxes, fontsize=9.5, color=TINTA2, va="bottom")
ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, labelcolor=TINTA2, handlelength=1.6, columnspacing=1.6)
ax.margins(x=0.08)
limpar(ax)
fig.savefig(FIG / "2_equity.png")
plt.close(fig)

# --------------------------------------------------- 3. comparacao aninhada
wf = json.loads((OUT / "walkforward.json").read_text(encoding="utf-8"))[0]
fig, ax = plt.subplots(figsize=(6.4, 3.5))
nomes = ["Média histórica\n(referência)", "+ surpresa\nda decisão", "+ tom léxico\nda ata"]
r2 = [wf["modelos"]["M0_media"]["r2_oos_vs_media"], wf["modelos"]["M1_surpresa"]["r2_oos_vs_media"], wf["modelos"]["M2_surpresa_tom"]["r2_oos_vs_media"]]
cores = [MUTED, AZUL, TEAL]
for i, (v, c) in enumerate(zip(r2, cores)):
    ax.bar(i, v, width=0.5, color=c, zorder=3)
    ax.text(i, v - 0.004, f"{v:+.3f}", ha="center", va="top", fontsize=12, fontweight="bold", color=TINTA)
ax.axhline(0, color=BASE, linewidth=1.4, zorder=4)
ax.set_xticks(range(3), nomes, fontsize=9.5, color=TINTA2)
ax.set_ylabel("R² out-of-sample", fontsize=9.5)
ax.set_ylim(min(r2) * 1.28, 0.018)
ax.set_title("Cada camada adicionada piora a previsão fora da amostra", fontsize=13, fontweight="bold", loc="left", pad=34)
cw = wf["clark_west"]["M2_sobre_M1"]
ax.text(0, 1.045, f"Clark-West do tom sobre a surpresa: {cw['cw_stat']:+.2f} (p = {cw['p_valor_unicaudal']:.2f}) — sem ganho incremental",
        transform=ax.transAxes, fontsize=9.5, color=TINTA2, va="bottom")
limpar(ax)
fig.savefig(FIG / "3_aninhada.png")
plt.close(fig)

# --------------------------------------------------- 4. quebra estrutural
fig, ax = plt.subplots(figsize=(7.2, 3.6))
for fonte, cor, lab in [("api_html", TEAL, "texto via API/HTML  (84)"), ("pdf", LARANJA, "texto via PDF  (26)")]:
    s = painel[painel["fonte_texto"] == fonte]
    ax.scatter(s["data_publicacao_ata"], s["lex_score"], s=26, color=cor, label=lab, zorder=3,
               edgecolors=SUPERFICIE, linewidths=1.2)
corte = painel.loc[painel["numero_reuniao"] == 200, "data_publicacao_ata"].iloc[0]
ax.axvline(corte, color=TINTA2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)
ax.text(corte, ax.get_ylim()[1], "  reunião 200 — ata encurta,\n  fonte vira PDF, regime muda",
        va="top", ha="left", fontsize=9, color=TINTA2)
ax.axhline(0, color=BASE, linewidth=1.0, zorder=1)
ax.set_ylabel("score léxico hawkish–dovish", fontsize=9.5)
ax.set_title("A quebra da reunião 200 confunde regime, formato e extração", fontsize=13, fontweight="bold", loc="left", pad=34)
ax.text(0, 1.045, "desvio-padrão do score dobra: 0,19 → 0,38 — justamente no out-of-sample",
        transform=ax.transAxes, fontsize=9.5, color=TINTA2, va="bottom")
ax.legend(frameon=False, fontsize=9, loc="lower left", labelcolor=TINTA2, handletextpad=0.4)
limpar(ax)
fig.savefig(FIG / "4_quebra.png")
plt.close(fig)

# ------------------------------------------- 5. evento do comunicado (se houver)
arq_com = OUT / "evento_comunicado.json"
if arq_com.exists():
    com = json.loads(arq_com.read_text(encoding="utf-8"))
    est = com["estudo_evento"]
    estr = com["resultados"][0]["estrategia_sinal_da_surpresa"]

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    nomes = [f"Dia do comunicado\n(n={est['comunicado']['n_dias']})",
             f"Dia da ata\n(n={est['ata']['n_dias']})",
             f"Dia qualquer\n(n={est['dia_comum']['n_dias']:,})".replace(",", ".")]
    vals = [est["comunicado"]["abs_var_media_bps"], est["ata"]["abs_var_media_bps"], est["dia_comum"]["abs_var_media_bps"]]
    for i, (v, c) in enumerate(zip(vals, [TEAL, AZUL, MUTED])):
        ax.bar(i, v, width=0.5, color=c, zorder=3)
        ax.text(i, v + 0.3, f"{v:.2f} bps", ha="center", va="bottom", fontsize=12.5, fontweight="bold", color=TINTA)
    ax.set_xticks(range(3), nomes, fontsize=10, color=TINTA2)
    ax.set_ylabel("variação absoluta média do DI 1Y (bps)", fontsize=9.5)
    ax.set_ylim(0, max(vals) * 1.30)
    ax.set_title("A decisão é notícia no comunicado — não na ata, 8 dias depois", fontsize=13, fontweight="bold", loc="left", pad=44)
    ax.text(0, 1.045,
            f"sinal da surpresa no comunicado: {estr['n_trades']} trades OOS, {estr['pnl_bruto_bps']:+.0f} bps brutos, "
            f"Sharpe {estr['sharpe_bruto']:.2f}, permutação p = {estr['permutacao']['p_valor_empirico']:.3f}\n"
            "janela fechamento-a-fechamento: limite superior otimista, não P&L executável",
            transform=ax.transAxes, fontsize=9, color=TINTA2, va="bottom", linespacing=1.5)
    limpar(ax)
    fig.savefig(FIG / "5_comunicado.png")
    plt.close(fig)

print("figuras geradas:")
for p in sorted(FIG.glob("*.png")):
    print(" ", p.name, f"{p.stat().st_size/1024:.0f} KB")
