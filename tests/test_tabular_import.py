from __future__ import annotations

from src.parsers.extractors import tabular


def _csv(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_deterministic_csv_import_maps_spanish_headers():
    content = _csv(
        [
            "Proveedor;RUT;Folio;Descripción;Unidad;Cantidad;Precio Unitario;Total",
            "Ferretería Los Andes;76.111.222-3;F-100;Tornillo acero;unidad;10;500;5000",
            "Ferretería Los Andes;76.111.222-3;F-100;Plancha acero;kg;2;3000;6000",
        ]
    )

    result = tabular.extract_tabular_document(content, "compras.csv")

    assert result is not None
    document, metadata = result
    assert len(document.items) == 2
    assert document.supplier_name == "Ferretería Los Andes"
    assert document.supplier_tax_id == "76.111.222-3"
    assert document.document_number == "F-100"
    assert document.items[0].description == "Tornillo acero"
    assert metadata["truncated"] is False
    assert metadata["processed_rows"] == 2


def test_deterministic_csv_import_returns_none_without_recognizable_header():
    content = _csv(["hola,mundo", "uno,dos"])

    assert tabular.extract_tabular_document(content, "notas.csv") is None


def test_tabular_import_truncates_and_warns(monkeypatch):
    monkeypatch.setattr(tabular, "MAX_IMPORT_ROWS", 2)
    content = _csv(
        [
            "descripcion,unidad,cantidad,precio,total",
            "Item 1,unidad,1,100,100",
            "Item 2,unidad,1,100,100",
            "Item 3,unidad,1,100,100",
            "Item 4,unidad,1,100,100",
        ]
    )

    result = tabular.extract_tabular_document(content, "compras.csv")

    assert result is not None
    document, metadata = result
    assert len(document.items) == 2
    assert metadata["truncated"] is True
    assert metadata["warnings"]
