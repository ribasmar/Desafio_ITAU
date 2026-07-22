# CopomLens — Testes do bônus de ingestão das atas PDF, sem rede e sem
# pdfminer (download e extração são mockados): limpeza do texto extraído
# (des-hifenização e colapso de espaços), orquestração idempotente com
# manifesto (fonte="pdf"), guard de texto curto e de data de publicação
# ausente (falha nomeada, não silêncio), e o parser preservando '<'/'>'
# literais do texto de PDF em vez de tratá-los como tag HTML.
import json

import pytest

import copom.ingest.atas_pdf as atas_pdf
import copom.ingest.parser as parser_mod

# --- limpeza do texto extraído ------------------------------------------------


def test_limpar_texto_junta_hifenizacao_de_quebra_de_linha():
    assert atas_pdf.limpar_texto("a infla-\nção subiu") == "a inflação subiu"


def test_limpar_texto_colapsa_espacos_e_quebras():
    assert atas_pdf.limpar_texto("Copom\n\n  231 \t reunião") == "Copom 231 reunião"


def test_limpar_texto_preserva_hifen_no_meio_da_linha():
    assert atas_pdf.limpar_texto("ex-presidente do BC") == "ex-presidente do BC"


# --- orquestração -------------------------------------------------------------

TEXTO_LONGO = "ata do copom " * 1000  # ~13k chars, acima do mínimo


@pytest.fixture
def raw(tmp_path, monkeypatch):
    registros = [
        {
            "numero_reuniao": 200,
            "data_reuniao": "2016-07-20",
            "data_publicacao": "2016-07-26",
            "url_pdf": "https://bcb/COPOM200.PDF",
            "motivo": "textoAta nulo (ata publicada só em PDF)",
        },
        {
            "numero_reuniao": 201,
            "data_reuniao": "2016-08-31",
            "data_publicacao": "2016-09-06",
            "url_pdf": "https://bcb/COPOM201.PDF",
            "motivo": "textoAta nulo (ata publicada só em PDF)",
        },
        {
            "numero_reuniao": 202,
            "data_reuniao": "2016-10-19",
            "data_publicacao": None,
            "url_pdf": "https://bcb/COPOM202.PDF",
            "motivo": "textoAta nulo (ata publicada só em PDF)",
        },
    ]
    (tmp_path / atas_pdf.ATAS_SEM_TEXTO_FILENAME).write_text(
        json.dumps(registros), encoding="utf-8"
    )

    class _Resp:
        content = b"%PDF-fake"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(atas_pdf, "_get", lambda client, url: _Resp())
    # 200 extrai texto longo; 201 extrai lixo curto (PDF "escaneado")
    monkeypatch.setattr(
        atas_pdf,
        "extrair_texto",
        lambda caminho: TEXTO_LONGO if "_200_" in caminho.name else "curto",
    )
    return tmp_path


def test_ingesta_registra_no_manifesto_com_fonte_pdf(raw):
    stats = atas_pdf.ingerir_atas_pdf(raw)
    assert stats["candidatas"] == 3
    assert stats["ingeridas"] == 1
    assert (raw / "ata_200_2016-07-20.txt").exists()
    assert (raw / atas_pdf.PDF_SUBDIR / "ata_200_2016-07-20.pdf").exists()

    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1
    entrada = manifest[0]
    assert entrada["numero_reuniao"] == 200
    assert entrada["fonte"] == "pdf"
    assert entrada["data_publicacao"] == "2016-07-26"
    assert entrada["url"].endswith("COPOM200.PDF")


def test_falhas_sao_nomeadas_nao_silenciosas(raw):
    stats = atas_pdf.ingerir_atas_pdf(raw)
    motivos = {f["numero_reuniao"]: f["motivo"] for f in stats["falhas"]}
    assert 201 in motivos and "curto demais" in motivos[201]
    assert 202 in motivos and "point-in-time" in motivos[202]
    # nem arquivo nem manifesto para as falhas
    assert not (raw / "ata_201_2016-08-31.txt").exists()


def test_reexecucao_e_idempotente(raw):
    atas_pdf.ingerir_atas_pdf(raw)
    stats = atas_pdf.ingerir_atas_pdf(raw)
    assert stats["ingeridas"] == 0
    assert stats["ja_registradas"] == 1
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 1


def test_sem_arquivo_de_sem_texto_falha_alto(tmp_path):
    with pytest.raises(FileNotFoundError, match="coleta"):
        atas_pdf.ingerir_atas_pdf(tmp_path)


def test_excecao_de_extracao_nao_derruba_o_lote(raw, monkeypatch):
    # Ata 200 estoura na extração (PDF quebrado); 201 segue o fluxo normal e o
    # lote termina com a falha nomeada — nada de traceback matando a execução.
    def explode_ou_extrai(caminho):
        if "_200_" in caminho.name:
            raise RuntimeError("xref quebrado")
        return TEXTO_LONGO

    monkeypatch.setattr(atas_pdf, "extrair_texto", explode_ou_extrai)
    stats = atas_pdf.ingerir_atas_pdf(raw)
    assert stats["ingeridas"] == 1  # a 201 entra
    motivos = {f["numero_reuniao"]: f["motivo"] for f in stats["falhas"]}
    assert 200 in motivos and "xref quebrado" in motivos[200]


def test_extrair_texto_usa_fallback_pypdf(monkeypatch, tmp_path):
    caminho = tmp_path / "ata.pdf"
    caminho.write_bytes(b"%PDF-fake")

    def pdfminer_quebra(c):
        raise ValueError("Invalid PDF stream spec.")

    monkeypatch.setattr(atas_pdf, "_extrair_pdfminer", pdfminer_quebra)
    monkeypatch.setattr(atas_pdf, "_extrair_pypdf", lambda c: "texto recuperado")
    assert atas_pdf.extrair_texto(caminho) == "texto recuperado"


def test_extrair_texto_falha_dos_dois_extratores_nomeia_ambos(monkeypatch, tmp_path):
    caminho = tmp_path / "ata.pdf"
    caminho.write_bytes(b"%PDF-fake")
    monkeypatch.setattr(
        atas_pdf, "_extrair_pdfminer", lambda c: (_ for _ in ()).throw(ValueError("xref"))
    )
    monkeypatch.setattr(
        atas_pdf, "_extrair_pypdf", lambda c: (_ for _ in ()).throw(ValueError("eof"))
    )
    with pytest.raises(RuntimeError, match="pdfminer.*pypdf"):
        atas_pdf.extrair_texto(caminho)


# --- parser: fonte="pdf" não passa pelo strip de tags --------------------------


def test_parser_preserva_menor_maior_de_texto_pdf(tmp_path):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir()
    manifest = [
        {
            "url": "https://bcb/atas_detalhes?nro_reuniao=199",
            "data_publicacao": "2016-06-16",
            "data_reuniao": "2016-06-08",
            "tipo": "ata",
            "numero_reuniao": 199,
            "filename": "ata_199.txt",
        },
        {
            "url": "https://bcb/COPOM200.PDF",
            "data_publicacao": "2016-07-26",
            "data_reuniao": "2016-07-20",
            "tipo": "ata",
            "numero_reuniao": 200,
            "filename": "ata_200.txt",
            "fonte": "pdf",
        },
    ]
    (raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (raw / "ata_199.txt").write_text("<p>inflação <b>alta</b></p>", encoding="utf-8")
    (raw / "ata_200.txt").write_text(
        "projeção de inflação < 4,5% e > 3% no horizonte", encoding="utf-8"
    )

    parser_mod.main(["--raw-path", str(raw), "--processed-path", str(processed)])

    registros = [
        json.loads(l)
        for l in (processed / "copom_dataset.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    por_numero = {r["numero_reuniao"]: r for r in registros}
    assert por_numero[199]["fonte"] == "html"
    assert por_numero[199]["text"] == "inflação alta"  # tags removidas
    assert por_numero[200]["fonte"] == "pdf"
    assert "< 4,5% e > 3%" in por_numero[200]["text"]  # '<'/'>' preservados
