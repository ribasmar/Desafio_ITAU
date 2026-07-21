# CopomLens — Testes negados e de borda da ingestao de mercado (marketdata),
# sem rede: bordas da paginacao $skip/$top do Focus (pagina cheia, parcial,
# parada por data_inicial e trava max_paginas) e negados do cliente HTTP
# (_get_json): status != 200 levanta, retries esgotados propagam o erro e
# resposta 200 sem JSON valido (corpo vazio/HTML transitorio do SGS) e
# retentada antes de levantar com o corpo na mensagem.
import httpx
import pytest

import copom.ingest.marketdata as md


def _payload(datas):
    return {
        "value": [
            {"Reuniao": "R1/2026", "Data": d, "Mediana": 14.0, "Media": 14.0,
             "numeroRespondentes": 50, "baseCalculo": 0}
            for d in datas
        ]
    }


def test_paginacao_pagina_cheia_busca_proxima(monkeypatch):
    chamadas = []

    def fake(url, params=None):
        chamadas.append(url)
        if len(chamadas) == 1:
            return _payload(["2026-06-02", "2026-06-01"])
        return _payload(["2026-05-30"])

    monkeypatch.setattr(md, "_get_json", fake)
    regs = md._coletar_focus_paginado(None, pagina=2, max_paginas=10)
    assert len(chamadas) == 2
    assert len(regs) == 3
    assert "%24skip=2" in chamadas[1] or "$skip=2" in chamadas[1]


def test_paginacao_pagina_parcial_encerra(monkeypatch):
    chamadas = []

    def fake(url, params=None):
        chamadas.append(url)
        return _payload(["2026-06-01"])

    monkeypatch.setattr(md, "_get_json", fake)
    regs = md._coletar_focus_paginado(None, pagina=2, max_paginas=10)
    assert len(chamadas) == 1
    assert len(regs) == 1


def test_paginacao_para_ao_alcancar_data_inicial(monkeypatch):
    chamadas = []

    def fake(url, params=None):
        chamadas.append(url)
        return _payload(["2026-06-01", "2023-12-31"])

    monkeypatch.setattr(md, "_get_json", fake)
    regs = md._coletar_focus_paginado("2024-01-01", pagina=2, max_paginas=10)
    assert len(chamadas) == 1
    assert len(regs) == 2


def test_paginacao_respeita_max_paginas(monkeypatch):
    chamadas = []

    def fake(url, params=None):
        chamadas.append(url)
        return _payload(["2026-06-02", "2026-06-01"])

    monkeypatch.setattr(md, "_get_json", fake)
    regs = md._coletar_focus_paginado(None, pagina=2, max_paginas=3)
    assert len(chamadas) == 3
    assert len(regs) == 6


class _FakeResp:
    def __init__(self, status_code, corpo_json=True):
        self.status_code = status_code
        self.text = "erro simulado"
        self.content = b"erro simulado"
        self.headers = {"content-type": "text/html"}
        self.url = "http://teste"
        self.request = httpx.Request("GET", "http://teste")
        self._corpo_json = corpo_json

    def json(self):
        if not self._corpo_json:
            raise ValueError("corpo nao e JSON")
        return {"value": []}


class _FakeClient:
    def __init__(self, comportamento):
        self._comportamento = comportamento

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        return self._comportamento()


def test_get_json_status_nao_200_levanta(monkeypatch):
    monkeypatch.setattr(
        md.httpx, "Client",
        lambda *a, **k: _FakeClient(lambda: _FakeResp(400)),
    )
    with pytest.raises(httpx.HTTPStatusError):
        md._get_json("http://teste")


def test_get_json_esgota_retries_e_levanta(monkeypatch):
    tentativas = []

    def estoura():
        tentativas.append(1)
        raise httpx.ConnectTimeout("timeout simulado")

    monkeypatch.setattr(md.httpx, "Client", lambda *a, **k: _FakeClient(estoura))
    monkeypatch.setattr(md.time, "sleep", lambda s: None)
    with pytest.raises(httpx.ConnectTimeout):
        md._get_json("http://teste")
    assert len(tentativas) == md._MAX_TENTATIVAS


def test_get_json_corpo_nao_json_retenta_e_depois_sucede(monkeypatch):
    respostas = [_FakeResp(200, corpo_json=False), _FakeResp(200, corpo_json=True)]
    monkeypatch.setattr(
        md.httpx, "Client", lambda *a, **k: _FakeClient(lambda: respostas.pop(0))
    )
    monkeypatch.setattr(md.time, "sleep", lambda s: None)
    assert md._get_json("http://teste") == {"value": []}
    assert not respostas  # consumiu a resposta ruim e a boa


def test_get_json_corpo_nao_json_persistente_levanta_com_corpo(monkeypatch):
    tentativas = []

    def sempre_ruim():
        tentativas.append(1)
        return _FakeResp(200, corpo_json=False)

    monkeypatch.setattr(md.httpx, "Client", lambda *a, **k: _FakeClient(sempre_ruim))
    monkeypatch.setattr(md.time, "sleep", lambda s: None)
    with pytest.raises(ValueError, match="erro simulado"):
        md._get_json("http://teste")
    assert len(tentativas) == md._MAX_TENTATIVAS
