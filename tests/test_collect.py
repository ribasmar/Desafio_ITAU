# CopomLens — Testes da coleta de documentos (collect), sem rede: guard-rail de
# textoAta nulo (ata publicada só em PDF não derruba a coleta e fica registrada
# com a urlPdfAta em atas_sem_texto.json), gravação da lista oficial completa
# de reuniões (atas_listadas.json), ausência de piso silencioso em --last e
# default documentado cobrindo o histórico inteiro listado pelo BCB.
import json

import copom.ingest.collect as collect

LISTA = [
    {"nroReuniao": 210, "dataReferencia": "2017-01-11"},
    {"nroReuniao": 116, "dataReferencia": "2006-01-18"},
]

DETALHES = {
    210: {
        "dataReferencia": "2017-01-11",
        "dataPublicacao": "2017-01-19",
        "textoAta": None,
        "urlPdfAta": "https://www.bcb.gov.br/ata210.pdf",
    },
    116: {
        "dataReferencia": "2006-01-18",
        "dataPublicacao": "2006-01-26",
        "textoAta": "<p>Ata 116</p>",
    },
}


def _patch_api(monkeypatch):
    monkeypatch.setattr(collect, "fetch_minutes_list", lambda count, client=None: LISTA)
    monkeypatch.setattr(
        collect, "fetch_minute_detail", lambda num, client=None: DETALHES[num]
    )


def test_texto_nulo_nao_quebra_e_fica_registrado(tmp_path, monkeypatch):
    _patch_api(monkeypatch)
    stats = collect.collect_minutes(count=300, base_path=tmp_path)
    assert stats == {"listadas": 2, "novas": 1, "sem_texto": 1, "ja_registradas": 0}
    # a ata com texto vira arquivo + manifesto; a sem texto não vira nenhum dos dois
    assert (tmp_path / "ata_116_2006-01-18.txt").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert [e["numero_reuniao"] for e in manifest] == [116]
    sem_texto = json.loads(
        (tmp_path / collect.ATAS_SEM_TEXTO_FILENAME).read_text(encoding="utf-8")
    )
    assert sem_texto[0]["numero_reuniao"] == 210
    assert sem_texto[0]["url_pdf"].endswith("ata210.pdf")
    assert sem_texto[0]["motivo"]


def test_lista_oficial_completa_e_gravada(tmp_path, monkeypatch):
    _patch_api(monkeypatch)
    collect.collect_minutes(count=300, base_path=tmp_path)
    listadas = json.loads(
        (tmp_path / collect.ATAS_LISTADAS_FILENAME).read_text(encoding="utf-8")
    )
    assert {a["nroReuniao"] for a in listadas} == {116, 210}


def test_reexecucao_nao_duplica_sem_texto(tmp_path, monkeypatch):
    _patch_api(monkeypatch)
    collect.collect_minutes(count=300, base_path=tmp_path)
    stats = collect.collect_minutes(count=300, base_path=tmp_path)
    assert stats["ja_registradas"] == 1 and stats["novas"] == 0
    sem_texto = json.loads(
        (tmp_path / collect.ATAS_SEM_TEXTO_FILENAME).read_text(encoding="utf-8")
    )
    assert len(sem_texto) == 1


def test_detalhe_500_vira_sem_texto(tmp_path, monkeypatch):
    monkeypatch.setattr(
        collect, "fetch_minutes_list", lambda count, client=None: [LISTA[0]]
    )
    monkeypatch.setattr(collect, "fetch_minute_detail", lambda num, client=None: None)
    stats = collect.collect_minutes(count=300, base_path=tmp_path)
    assert stats["sem_texto"] == 1
    sem_texto = json.loads(
        (tmp_path / collect.ATAS_SEM_TEXTO_FILENAME).read_text(encoding="utf-8")
    )
    assert sem_texto[0]["data_reuniao"] == "2017-01-11"  # cai para o item da lista


def test_last_sem_piso_e_default_documentado(tmp_path, monkeypatch):
    assert collect._parse_args([]).last == collect.DEFAULT_LAST == 300
    assert collect._parse_args(["--last", "3"]).last == 3

    capturado = {}
    fake_result = {
        "minutes": {"listadas": 3, "novas": 0, "sem_texto": 0, "ja_registradas": 3},
        "statements": {"listados": 3, "novos": 0, "sem_texto": 0, "ja_registrados": 3},
    }

    def fake_collect_all(count, base_path):
        capturado["count"] = count
        return fake_result

    monkeypatch.setattr(collect, "collect_all", fake_collect_all)
    collect.executar(3, tmp_path)
    assert capturado["count"] == 3  # o valor pedido é o valor usado, sem max(x, 5)
