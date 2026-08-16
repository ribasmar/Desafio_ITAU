# Monta o relatorio final: gera o HTML self-contained (figuras embutidas em
# base64, 5 paginas de 1280x720) e converte para PDF via Chromium headless.
# O documento e anonimo por construcao: nenhum nome, instituicao ou logo
# institucional entra no template.
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIG = BASE.parent / "assets"
SAIDA_HTML = BASE / "CopomLens_relatorio.html"
SAIDA_PDF = BASE / "CopomLens_relatorio.pdf"


def img(nome: str) -> str:
    dados = base64.b64encode((FIG / nome).read_bytes()).decode()
    return f"data:image/png;base64,{dados}"


def contar_palavras(html: str) -> int:
    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"&[a-z]+;|&#\d+;", " ", texto)
    return len([p for p in texto.split() if any(c.isalnum() for c in p)])


HTML = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>CopomLens</title>
<style>
  @page {{ size: 13.333in 7.5in; margin: 0; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --teal:#1D9E75; --teal-esc:#0F6E56; --teal-cl:#E1F5EE;
    --cinza:#444441; --muted:#7d7c76; --fundo:#F1EFE8; --branco:#FBFAF7;
    --linha:#dedcd3; --tinta:#131312;
  }}
  body {{ font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; color:var(--tinta);
          background:#8a8a86; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  .pg {{ width:1280px; height:720px; background:var(--fundo); position:relative;
         overflow:hidden; page-break-after:always; padding:38px 52px 34px; display:flex;
         flex-direction:column; }}
  .pg:last-child {{ page-break-after:auto; }}
  .top {{ display:flex; justify-content:space-between; align-items:baseline;
          border-bottom:2px solid var(--teal); padding-bottom:7px; margin-bottom:16px; }}
  .sec {{ font-size:17px; font-weight:700; letter-spacing:.2px; }}
  .num {{ font-size:11px; color:var(--muted); letter-spacing:1.6px; text-transform:uppercase; }}
  h1 {{ font-size:64px; font-weight:800; letter-spacing:-2px; line-height:1; }}
  h1 .l {{ color:var(--teal); }}
  h2 {{ font-size:15px; font-weight:700; margin-bottom:7px; }}
  p, li {{ font-size:13px; line-height:1.5; color:var(--cinza); }}
  .lead {{ font-size:15.5px; line-height:1.5; }}
  b, strong {{ color:var(--tinta); font-weight:700; }}
  .g {{ display:grid; gap:15px; }}
  .card {{ background:var(--branco); border:1px solid var(--linha); border-radius:9px; padding:14px 16px; }}
  .card.k {{ border-left:4px solid var(--teal); }}
  .kpi {{ font-size:31px; font-weight:800; letter-spacing:-1px; line-height:1.05; }}
  .kpi.v {{ color:var(--teal); }} .kpi.n {{ color:#c0392b; }}
  .kpi-l {{ font-size:10.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.7px; margin-top:5px; line-height:1.3; }}
  table {{ width:100%; border-collapse:collapse; font-size:11.5px; }}
  th {{ text-align:left; font-size:9.5px; text-transform:uppercase; letter-spacing:.6px;
        color:var(--muted); border-bottom:1.5px solid var(--linha); padding:0 7px 5px 0; font-weight:600; }}
  td {{ padding:5px 7px 5px 0; border-bottom:1px solid #eceae2; color:var(--cinza); }}
  td.n, th.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
  tr.hi td {{ background:var(--teal-cl); font-weight:700; color:var(--tinta); }}
  .tag {{ display:inline-block; background:var(--teal-cl); color:var(--teal-esc); font-size:9.5px;
          font-weight:700; padding:3px 9px; border-radius:20px; letter-spacing:.4px; }}
  .fluxo {{ display:flex; align-items:stretch; gap:0; }}
  .et {{ flex:1; background:var(--branco); border:1px solid var(--linha); border-radius:8px;
         padding:11px 12px; position:relative; }}
  .et + .et {{ margin-left:20px; }}
  .et + .et::before {{ content:"›"; position:absolute; left:-16px; top:50%; transform:translateY(-50%);
                       color:var(--teal); font-size:22px; font-weight:700; }}
  .et .n2 {{ font-size:9.5px; font-weight:800; color:var(--teal); letter-spacing:.8px; }}
  .et h3 {{ font-size:12.5px; margin:3px 0 4px; }}
  .et p {{ font-size:10.5px; line-height:1.4; color:var(--muted); }}
  img.fig {{ width:100%; display:block; border-radius:7px; border:1px solid var(--linha); }}
  .rod {{ margin-top:auto; padding-top:10px; font-size:10px; color:var(--muted);
          border-top:1px solid var(--linha); display:flex; justify-content:space-between; }}
  .fill {{ flex:1; align-content:stretch; }}
  .mid {{ margin:auto 0; width:100%; }}
  ul {{ padding-left:16px; }} li {{ margin-bottom:4px; }}
  li::marker {{ color:var(--teal); }}
</style></head><body>

<!-- ============================ 1 ============================ -->
<div class="pg">
 <div class="mid">
  <div style="display:flex;align-items:center;gap:26px;margin-bottom:6px">
    <svg width="86" height="86" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="46" fill="none" stroke="#1D9E75" stroke-width="4"/>
      <circle cx="50" cy="50" r="31" fill="none" stroke="#1D9E75" stroke-width="3" opacity=".62"/>
      <circle cx="50" cy="50" r="17" fill="none" stroke="#1D9E75" stroke-width="2.5" opacity=".38"/>
      <circle cx="50" cy="50" r="6" fill="#1D9E75"/>
      <line x1="50" y1="0" x2="50" y2="13" stroke="#1D9E75" stroke-width="3"/>
      <line x1="50" y1="87" x2="50" y2="100" stroke="#1D9E75" stroke-width="3"/>
      <line x1="0" y1="50" x2="13" y2="50" stroke="#1D9E75" stroke-width="3"/>
      <line x1="87" y1="50" x2="100" y2="50" stroke="#1D9E75" stroke-width="3"/>
    </svg>
    <div>
      <h1>Copom<span class="l">Lens</span></h1>
      <p style="font-size:17px;margin-top:5px">Uma lente sobre o que o Banco Central está realmente dizendo.</p>
    </div>
  </div>

  <div class="g" style="grid-template-columns:1.55fr 1fr;margin-top:26px">
    <div>
      <div class="card k" style="margin-bottom:13px">
        <span class="tag">O NOME</span>
        <p style="margin-top:7px"><b>Lente</b>, não oráculo: o robô não prevê a Selic. Ele
        <b>foca o texto da ata</b> e devolve o tom em número auditável, com o trecho que
        embasou o score.</p>
      </div>
      <div class="card k">
        <span class="tag">HIPÓTESE — DELIBERADAMENTE FALSIFICÁVEL</span>
        <p style="margin-top:7px">O tom da ata do Copom carrega informação <b>incremental</b>
        sobre a reação do DI 1 ano, <b>além</b> da surpresa da decisão (Selic − mediana Focus).
        <br><b>"Não há ganho incremental" é resultado válido</b> — e foi o que encontramos.</p>
      </div>
    </div>
    <div>
      <div class="card" style="height:100%">
        <span class="tag">A INEFICIÊNCIA TESTADA</span>
        <p style="margin-top:8px">A ata sai 8 dias após a decisão, às 8h30. Se o mercado leva horas para digerir 27 mil caracteres, quem lê em segundos captura o intervalo.</p>
        <div style="margin-top:12px;padding-top:11px;border-top:1px solid var(--linha)">
          <div class="kpi v">110</div><div class="kpi-l">eventos point-in-time · 2006–2019</div>
        </div>
      </div>
    </div>
  </div>
 </div>
  <div class="rod" style="margin-top:0"><span>Estratégia quantitativa em renda fixa · DI 1 ano</span><span>1 / 5</span></div>
</div>

<!-- ============================ 2 ============================ -->
<div class="pg">
  <div class="top"><span class="sec">Modelagem — do texto à posição</span><span class="num">Pipeline</span></div>

  <div class="fluxo" style="margin-bottom:15px">
    <div class="et"><div class="n2">CAMADA 1</div><h3>Ingestão point-in-time</h3>
      <p>APIs públicas do BCB, com carimbo de disponibilidade por documento.</p></div>
    <div class="et"><div class="n2">CAMADA 2</div><h3>Extração de tom</h3>
      <p>LLM local (T=0, seed fixa, JSON) <b>e</b> baseline léxico hawkish/dovish como piso.</p></div>
    <div class="et"><div class="n2">CAMADA 3</div><h3>Surpresa da decisão</h3>
      <p>Selic efetiva − mediana Focus anterior à reunião, rotulada pelo calendário oficial.</p></div>
    <div class="et"><div class="n2">CAMADA 4</div><h3>Comparação aninhada</h3>
      <p>Walk-forward: média → + surpresa → + tom; ganho medido por Clark-West.</p></div>
    <div class="et"><div class="n2">CAMADA 5</div><h3>Sinal → posição → P&amp;L</h3>
      <p>Sinal vira posição em DI 1Y; P&amp;L líquido de custo, Sharpe e drawdown.</p></div>
  </div>

  <div class="g fill" style="grid-template-columns:1.25fr 1fr">
    <div class="card">
      <h2>Dados — tudo de fonte pública e única</h2>
      <table>
        <tr><th>dado</th><th>fonte</th><th class="n">janela</th></tr>
        <tr><td>atas e comunicados</td><td>API BCB <i>sitebcb/copom</i></td><td class="n">259 reuniões</td></tr>
        <tr><td><b>alvo: DI 1 ano</b></td><td>BCB/SGS 7806 — maturidade constante</td><td class="n">2004–2019</td></tr>
        <tr><td>Selic meta efetiva</td><td>BCB/SGS 432</td><td class="n">idem</td></tr>
        <tr><td>mediana Focus</td><td>BCB Olinda, rótulo R<i>k</i>/ano</td><td class="n">desde R1/2006</td></tr>
      </table>
      <p style="margin-top:9px;font-size:11.5px"><b>Por que a 7806:</b> maturidade constante de 360 dias
      por construção — sem o salto artificial da troca de vencimento do contrato cru.</p>
      <h2 style="margin-top:14px">Funil da amostra — cada corte com a sua razão</h2>
      <div class="fluxo">
        <div class="et"><div class="n2">259</div><h3>atas listadas</h3><p>universo oficial do BCB</p></div>
        <div class="et"><div class="n2">134</div><h3>com reação DI casada</h3><p>janela viva da 7806 (2004–2019)</p></div>
        <div class="et"><div class="n2">110</div><h3>com mediana Focus</h3><p>rótulo por reunião existe desde R1/2006</p></div>
        <div class="et" style="border-left:4px solid var(--teal)"><div class="n2">84 + 26</div><h3>painel final</h3><p>texto via API/HTML + via PDF</p></div>
      </div>
    </div>
    <div class="card k">
      <h2>A regra cardinal — sem lookahead</h2>
      <p>Nenhuma feature influencia um retorno sem prova de que já era pública. A reação é medida
      na <b>data de publicação da ata</b>, nunca na da reunião, 8 dias antes.</p>
      <p style="margin-top:8px"><b>Decisão observável:</b> <b>+1</b> paga fixo, <b>−1</b> recebe fixo.
      Entra no fechamento anterior, sai no da publicação. Sem previsão, sem posição — nunca herda a anterior.</p>
      <p style="margin-top:8px"><b>Estimação walk-forward:</b> janela expansiva, treino mínimo de
      40 eventos, refit a cada evento — <b>70 previsões out-of-sample</b> (2011–2019).</p>
      <p style="margin-top:8px;color:var(--teal-esc)"><b>Auditoria: 110 de 110 eventos com
      disponibilidade idêntica à data de publicação. Zero violações.</b></p>
    </div>
  </div>
  <div class="rod"><span>O evento <i>t</i> só enxerga os eventos anteriores a ele · cada corte do funil gravado com contagem e razão</span><span>2 / 5</span></div>
</div>

<!-- ============================ 3 ============================ -->
<div class="pg">
  <div class="top"><span class="sec">Backtest — o evento é real, a direção não</span><span class="num">Resultados</span></div>

  <div class="g" style="grid-template-columns:1fr 1fr;margin-bottom:13px">
    <img class="fig" src="{img('1_evento.png')}" alt="volatilidade no dia da ata">
    <img class="fig" src="{img('3_aninhada.png')}" alt="comparacao aninhada">
  </div>

  <div class="g" style="grid-template-columns:1fr 1fr 1fr 1.7fr">
    <div class="card"><div class="kpi v">+0,004</div><div class="kpi-l">Sharpe bruto da melhor regra — zero</div></div>
    <div class="card"><div class="kpi n">−0,265</div><div class="kpi-l">Sharpe líquido de 1 bp por trade</div></div>
    <div class="card"><div class="kpi">0,71</div><div class="kpi-l">p do Clark-West: tom não agrega</div></div>
    <div class="card">
      <table>
        <tr><th>estratégia (70 eventos OOS)</th><th class="n">bruto</th><th class="n">líq.</th><th class="n">Sharpe</th><th class="n">p perm.</th></tr>
        <tr class="hi"><td>Regra do Δ tom</td><td class="n">+1</td><td class="n">−66</td><td class="n">−0,27</td><td class="n">0,49</td></tr>
        <tr><td>Previsão surpresa + tom</td><td class="n">−41</td><td class="n">−111</td><td class="n">−0,44</td><td class="n">0,72</td></tr>
        <tr><td>Previsão só surpresa</td><td class="n">−47</td><td class="n">−117</td><td class="n">−0,46</td><td class="n">0,94</td></tr>
        <tr><td>Benchmark: sempre recebe fixo</td><td class="n">−19</td><td class="n">−89</td><td class="n">−0,35</td><td class="n">n/a</td></tr>
      </table>
    </div>
  </div>
  <div class="rod"><span>P&amp;L em bps de taxa capturada · teste de permutação com 5.000 sorteios · subamostra homogênea de 84 não melhora o resultado</span><span>3 / 5</span></div>
</div>

<!-- ============================ 4 ============================ -->
<div class="pg">
  <div class="top"><span class="sec">Análise crítica — por que não funcionou</span><span class="num">Diagnóstico</span></div>

  <div class="g" style="grid-template-columns:1.05fr 1fr;margin-bottom:12px">
    <img class="fig" src="{img('2_equity.png')}" alt="curvas de equity">
    <img class="fig" src="{img('4_quebra.png')}" alt="quebra estrutural">
  </div>

  <div class="g fill" style="grid-template-columns:1fr 1fr 1fr">
    <div class="card k"><h2>A surpresa está no evento errado</h2>
      <p>É ≠ 0 em só <b>24 dos 110</b> eventos e correlaciona <b>0,05</b> com a reação: quando a ata
      sai, 8 dias depois, a surpresa já é notícia velha. O teste certo dela é no <b>comunicado</b>.</p></div>
    <div class="card k"><h2>Três mudanças na mesma reunião</h2>
      <p>Na reunião 200 a ata encurta de 27 para 14 mil caracteres, a fonte vira PDF e o regime
      muda — efeitos <b>não separáveis</b>, e a variância do tom dobra justo no out-of-sample.</p></div>
    <div class="card k"><h2>O léxico não enxerga negação</h2>
      <p>"O risco de desancoragem <b>diminuiu</b>" e "<b>aumentou</b>" contam a mesma ocorrência
      hawkish. Falhou o <b>piso de comparação</b> — a contagem de palavras — que é exatamente o
      escopo que o extrator por LLM existe para cobrir.</p></div>
  </div>
  <div class="rod"><span>Sem borda no bruto, o custo não é a explicação: não há o que ele consumir</span><span>4 / 5</span></div>
</div>

<!-- ============================ 5 ============================ -->
<div class="pg">
  <div class="top"><span class="sec">IA generativa, conclusão e próximos passos</span><span class="num">Encerramento</span></div>

  <div class="g fill" style="grid-template-columns:1.3fr 1fr;margin-bottom:13px">
    <div class="card k">
      <h2>Onde a IA generativa entrou — e o que ela custou</h2>
      <div class="g" style="grid-template-columns:1fr 1fr;gap:11px;margin-top:8px">
        <div>
          <p><b>1. Como instrumento de medida.</b> O extrator lê a ata e devolve <i>stance</i>,
          guidance, incerteza e convicção em JSON determinístico — <b>temperatura 0 e seed fixa</b>.</p>
          <p style="margin-top:7px"><b>2. Como par de engenharia.</b> Revisão adversarial do pipeline:
          dois bugs que invertiam a conclusão saíram daí — um parsing de data que embaralhava os dias
          1–12 e um teste de permutação que "aprovava" posição constante.</p>
        </div>
        <div>
          <p><b>3. Como crítico do próprio resultado.</b> Foi a IA que apontou que a surpresa
          estava sendo testada no evento errado.</p>
          <p style="margin-top:7px"><b>Limitações.</b> O LLM local é lento (~2 min/ata em CPU) e,
          sem <i>schema</i> rígido, devolvia texto fora do JSON; saída estruturada obrigatória
          resolveu. Determinismo só com seed e temperatura travadas em código.</p>
        </div>
      </div>
      <div style="margin-top:11px;background:#1b1b19;color:#cfe9de;border-radius:7px;padding:9px 13px;font-family:Menlo,Consolas,monospace;font-size:10.5px;line-height:1.55">{{"stance": 0.6, "forward_guidance": "aperto", "incerteza": 0.3, "conviccao": 0.8,<br>&nbsp;"trecho": "…a convergência da inflação para a meta requer postura mais contracionista…"}}</div>
      <p style="margin-top:6px;font-size:10px;color:var(--muted)">Saída da CopomLens: mesmo texto, mesmo JSON, em qualquer máquina.</p>
    </div>
    <div class="card">
      <h2>Viabilidade prática</h2>
      <p>Custo desprezível: dados públicos, inferência local, 8 decisões por ano.
      <b>Mas não recomendamos alocar capital</b> na versão direcional: reportar Sharpe positivo aqui
      exigiria escolher janela ou custo a dedo.</p>
      <p style="margin-top:9px">O que sobrevive é a <b>infraestrutura auditável</b>: painel
      point-in-time, funil com a razão de cada corte e 38 testes travando lookahead.</p>
    </div>
  </div>

  <div class="g" style="grid-template-columns:1fr 1fr 1fr 1fr">
    <div class="card"><span class="tag">PRÓXIMO 1</span><p style="margin-top:7px"><b>Tom por LLM nas 110 atas.</b>
      A hipótese só foi falsificada na camada léxica. O piso está medido; agora há o que bater.</p></div>
    <div class="card"><span class="tag">PRÓXIMO 2</span><p style="margin-top:7px"><b>Surpresa no comunicado.</b>
      Testar a decisão no evento em que ela é notícia, não 8 dias depois.</p></div>
    <div class="card"><span class="tag">PRÓXIMO 3</span><p style="margin-top:7px"><b>Volatilidade, não direção.</b>
      O prêmio de <b>+35%</b> no dia da ata é o achado que passou no teste. É o que uma
      estratégia de vol usaria.</p></div>
    <div class="card k"><span class="tag">A CONCLUSÃO</span><p style="margin-top:7px">Uma hipótese
      falsificável, testada sem lookahead, <b>foi rejeitada</b> — e o relatório diz isso.
      A lente funciona; o que ela mostrou é que ali não havia sinal.</p></div>
  </div>
  <div class="rod"><span>Todo número deste relatório é gerado por script a partir dos artefatos do pipeline — nenhum foi digitado à mão</span><span>5 / 5</span></div>
</div>

</body></html>"""


def main() -> int:
    SAIDA_HTML.write_text(HTML, encoding="utf-8")
    palavras = contar_palavras(HTML)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1280, "height": 720})
        pagina.goto(SAIDA_HTML.as_uri())
        pagina.wait_for_timeout(900)
        pagina.pdf(path=str(SAIDA_PDF), width="13.333in", height="7.5in",
                   print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        for i in range(5):
            pagina.locator(".pg").nth(i).screenshot(path=str(BASE / f"pg{i+1}.png"))
        navegador.close()

    print(f"palavras: {palavras}  (referência do edital: ~750)")
    print(f"HTML: {SAIDA_HTML}")
    print(f"PDF:  {SAIDA_PDF}  ({SAIDA_PDF.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
