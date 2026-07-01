# CopomLens — Testes de INTEGRACAO: batem na API real do BCB (SGS + Olinda) para
# detectar mudanca de schema/quebra que os testes unitarios (mockados) nao pegam.
# Exigem rede e sao pulados por padrao; rode com RUN_INTEGRATION=1.
#   PowerShell:  $env:RUN_INTEGRATION=1; python -m pytest tests/test_integration_marketdata.py -q
import os

import pytest

import copom.ingest.marketdata as md

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION"),
    reason="teste de integracao (rede): defina RUN_INTEGRATION=1 para rodar.",
)


def test_selic_meta_api_real():
    df = md.fetch_selic_meta(data_inicial="01/01/2024")
    assert not df.empty
    assert list(df.columns) == ["data", "selic_meta"]
    assert df["selic_meta"].between(0, 40).all()  # sanidade: Selic plausivel
    assert df["data"].is_monotonic_increasing


def test_focus_selic_api_real():
    df = md.fetch_focus_selic(data_inicial="2024-01-01", base_calculo=0)
    assert not df.empty
    assert {"reuniao", "data", "mediana", "n_respondentes"} <= set(df.columns)
    assert (df["base_calculo"] == 0).all()
    assert df["mediana"].between(0, 40).all()
    assert (df["data"].min() >= __import__("pandas").Timestamp("2024-01-01"))
