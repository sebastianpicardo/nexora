from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = [
    ROOT / "src",
    ROOT / "tests",
    ROOT / "database",
    ROOT / "client" / "src",
]

SCAN_SUFFIXES = {".py", ".sql", ".js", ".jsx", ".css", ".json", ".html"}

MOJIBAKE_MARKERS = (
    "\u00c3\u00a1",
    "\u00c3\u00a9",
    "\u00c3\u00ad",
    "\u00c3\u00b3",
    "\u00c3\u00ba",
    "\u00c3\u00b1",
    "\u00c3\u0081",
    "\u00c2\u00bf",
    "\u00c2\u00a1",
    "\u00e2\u0080\u0099",
    "\u00e2\u0080\u009c",
    "\u00e2\u0080\u009d",
    "\ufffd",
)


def _iter_files():
    for directory in SCAN_DIRS:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
                if "node_modules" in path.parts:
                    continue
                yield path


def test_source_files_are_utf8_and_free_of_mojibake():
    offenders: list[str] = []
    for path in _iter_files():
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            offenders.append(f"{path.relative_to(ROOT)}: no es UTF-8 válido")
            continue
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                relative = path.relative_to(ROOT)
                offenders.append(f"{relative}: contiene texto corrupto ({marker!r})")
                break

    assert not offenders, "Archivos con codificación corrupta:\n" + "\n".join(offenders)
