from __future__ import annotations

import psycopg
from psycopg import pq

from src.core.config import PROJECT_ROOT, settings


def apply_schema() -> None:
    schema_path = PROJECT_ROOT / "database" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"No se encontró {schema_path}")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurada.")

    sql = schema_path.read_text(encoding="utf-8")
    with psycopg.connect(settings.database_url, autocommit=True, connect_timeout=20) as conn:
        # El protocolo simple permite ejecutar varias sentencias y bloques DO.
        result = conn.pgconn.exec_(sql.encode("utf-8"))
        if result.status == pq.ExecStatus.FATAL_ERROR:
            message = result.error_message.decode("utf-8", errors="replace")
            raise RuntimeError(f"Error aplicando schema.sql: {message}")

    print(f"Esquema aplicado correctamente: {schema_path}")


if __name__ == "__main__":
    apply_schema()
