# Testes do fechamento dos números da amostra: garantem que as identidades de
# reconciliação (fontes do texto = linhas do painel; painel + sem-alvo = corpus
# escorado) falham alto quando não fecham, que a fonte do texto vem do manifesto
# e não do número da reunião, e que a razão de cada corte chega ao JSON final.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from numeros_amostra import _janela, montar_numeros  # noqa: E402

LISTADAS = {116: "2006-01-18", 199: "2016-06-08", 200: "2016-07-20", 226: "2019-10-30"}

CORPUS = {
    116: {
        "ata": {"data_reuniao": "2006-01-18", "chars": 900},
        "comunicado": {"data_reuniao": "2006-01-18", "chars": 300},
    },
    199: {"ata": {"data_reuniao": "2016-06-08", "chars": 900}},
    200: {
        "ata": {"data_reuniao": "2016-07-20", "chars": 900},
        "comunicado": {"data_reuniao": "2016-07-20", "chars": 300},
    },
    226: {"ata": {"data_reuniao": "2019-10-30", "chars": 900}},
}

FONTES = {
    (116, "ata"): "api_html",
    (199, "ata"): "api_html",
    (200, "ata"): "pdf",
    (226, "ata"): "pdf",
}

PAINEL = [
    {"numero_reuniao": "116", "data_reuniao": "2006-01-18", "regime": "Meirelles"},
    {"numero_reuniao": "199", "data_reuniao": "2016-06-08", "regime": "Tombini"},
    {"numero_reuniao": "200", "data_reuniao": "2016-07-20", "regime": "Goldfajn"},
]

DESCARTES = {226: "publicação em 2019-11-05 fora da janela viva da SGS 7806"}


def _montar(**troca):
    argumentos = {
        "listadas": LISTADAS,
        "corpus": CORPUS,
        "fontes": FONTES,
        "painel": PAINEL,
        "descartes": DESCARTES,
        "janela": (2006, 2019),
    }
    argumentos.update(troca)
    return montar_numeros(**argumentos)


def test_reconciliacao_fecha_e_separa_por_fonte():
    numeros, falhas = _montar()
    assert falhas == []
    painel = numeros["painel_alvo_di1y"]
    assert painel["n"] == 3
    assert painel["por_fonte_do_texto"]["api_html"]["n"] == 2
    assert painel["por_fonte_do_texto"]["pdf"]["n"] == 1
    assert numeros["corpus_escorado_llm"]["n"] == painel["n"] + numeros["escoradas_sem_alvo"]["n"]


def test_razao_do_descarte_vem_do_funil():
    numeros, _ = _montar()
    sem_alvo = numeros["escoradas_sem_alvo"]
    assert [r["numero_reuniao"] for r in sem_alvo["reunioes"]] == [226]
    assert "fora da janela viva da SGS 7806" in sem_alvo["reunioes"][0]["motivo"]


def test_reuniao_sem_motivo_gravado_nao_fica_com_razao_vazia():
    numeros, _ = _montar(descartes={})
    assert numeros["escoradas_sem_alvo"]["reunioes"][0]["motivo"] == (
        "motivo não gravado no funil"
    )


def test_painel_mais_largo_que_a_escoragem_derruba_a_reconciliacao():
    numeros, falhas = _montar(janela=(2006, 2015))
    assert numeros["corpus_escorado_llm"]["n"] == 1
    assert any("corpus escorado" in f for f in falhas)


def test_janela_que_exclui_reuniao_fora_do_painel_continua_fechando():
    numeros, falhas = _montar(janela=(2006, 2016))
    assert falhas == []
    assert numeros["corpus_escorado_llm"]["n"] == 3
    assert numeros["escoradas_sem_alvo"]["n"] == 0


def test_reuniao_do_painel_fora_da_lista_oficial_e_falha():
    _, falhas = _montar(listadas={k: v for k, v in LISTADAS.items() if k != 200})
    assert any("ausentes da lista oficial" in f for f in falhas)


def test_ata_com_texto_vazio_e_falha():
    corpus = {n: {t: dict(d) for t, d in tipos.items()} for n, tipos in CORPUS.items()}
    corpus[199]["ata"]["chars"] = 0
    _, falhas = _montar(corpus=corpus)
    assert any("texto vazio" in f for f in falhas)


def test_fonte_ausente_no_manifesto_cai_no_padrao_e_nao_no_numero_da_reuniao():
    numeros, falhas = _montar(fontes={})
    assert falhas == []
    assert numeros["painel_alvo_di1y"]["por_fonte_do_texto"]["api_html"]["n"] == 3


def test_pareadas_contam_apenas_reunioes_com_comunicado_com_texto():
    numeros, _ = _montar()
    assert numeros["pareadas_ata_comunicado"]["n_no_painel"] == 2
    assert numeros["pareadas_ata_comunicado"]["n_no_corpus"] == 2


def test_saida_e_serializavel_em_json():
    numeros, _ = _montar()
    assert json.loads(json.dumps(numeros, ensure_ascii=False))["atas_listadas_bcb"]["n"] == 4


@pytest.mark.parametrize("texto", ["2006", "2006-2019", "2019:2006", "a:b", ""])
def test_janela_invalida_levanta(texto):
    with pytest.raises(ValueError):
        _janela(texto)


def test_janela_valida():
    assert _janela("2006:2019") == (2006, 2019)
