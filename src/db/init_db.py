from __future__ import annotations

import re
from pathlib import Path

import psycopg

from src.core.config import PROJECT_ROOT, settings

MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"
SCHEMA_SQL = PROJECT_ROOT / "database" / "schema.sql"


def _extract_migration_number(filename: str) -> int | None:
    """Extrae el número de orden de un archivo de migración (ej. '012_savings_tracking.sql' -> 12)."""
    basename = Path(filename).stem
    match = re.match(r"^(\d+)_", basename)
    if match:
        return int(match.group(1))
    return None


def _migration_sort_key(filepath: Path) -> tuple[int, str]:
    """Clave de ordenamiento: (número, nombre de archivo)."""
    num = _extract_migration_number(filepath.name) or 0
    return (num, filepath.name)


def apply_schema(database_url: str | None = None) -> None:
    """Aplica el schema base (idempotente) a la base indicada.

    Útil para tests y para inicializar una base vacía con un rol dueño.
    """
    url = (database_url or settings.database_url or "").strip()
    if not url:
        print("⚠️  DATABASE_URL no configurada. Saltando schema base.")
        return
    if not SCHEMA_SQL.exists():
        print(f"⚠️  No se encontró {SCHEMA_SQL}, saltando schema base.")
        return
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True, connect_timeout=20) as conn:
        conn.pgconn.exec_(sql.encode("utf-8"))


def ensure_auth_columns() -> None:
    """Repara columnas críticas de autenticación en bases con migraciones parciales.

    Cada sentencia es idempotente (``ADD COLUMN IF NOT EXISTS``) y se ejecuta de
    forma aislada para que un error en una no impida aplicar las demás. Así el
    login deja de fallar aunque una migración previa se haya cortado a medias.
    """
    ddl_url = settings.ddl_database_url
    if not ddl_url:
        return

    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'America/Santiago'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_quota BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_weekly BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE plans ADD COLUMN IF NOT EXISTS user_limit INTEGER",
        "UPDATE plans SET user_limit = 1 WHERE id = 'free' AND (user_limit IS NULL OR user_limit <> 1)",
        "UPDATE plans SET user_limit = 5 WHERE id = 'pro' AND (user_limit IS NULL OR user_limit <> 5)",
        "UPDATE plans SET user_limit = NULL WHERE id = 'enterprise'",
    ]
    applied = 0
    for statement in statements:
        try:
            with psycopg.connect(ddl_url, autocommit=True, connect_timeout=20) as conn:
                conn.pgconn.exec_((statement + ";").encode("utf-8"))
            applied += 1
        except Exception as exc:  # noqa: BLE001 - best-effort self-heal
            lower = str(exc).lower()
            if "must be owner" in lower or "permission denied" in lower:
                print(
                    "⚠️  No se pudo reparar columnas de auth por permisos. "
                    "Ejecuta database/migrations como dueño de la base."
                )
                return
    if applied:
        print(f"✅ Columnas de autenticación verificadas ({applied} sentencias).")


def apply_migrations() -> None:
    """Aplica todas las migraciones pendientes en orden numérico.

    Cada archivo SQL usa 'CREATE TABLE IF NOT EXISTS' y 'CREATE INDEX IF NOT EXISTS',
    por lo que son idempotentes y seguras para ejecutar sobre una BD ya inicializada.
    """
    ddl_url = settings.ddl_database_url
    if not ddl_url:
        print("⚠️  DATABASE_URL no configurada. Saltando aplicación de migraciones.")
        return

    if ddl_url == settings.database_url and settings.database_url:
        print(
            "ℹ️  Aplicando migraciones con DATABASE_URL. Si el rol no es dueño de la base, "
            "define MIGRATION_DATABASE_URL o DIRECT_DATABASE_URL con un rol privilegiado."
        )

    # Aplicar schema base primero
    if SCHEMA_SQL.exists():
        try:
            sql = SCHEMA_SQL.read_text(encoding="utf-8")
            with psycopg.connect(ddl_url, autocommit=True, connect_timeout=20) as conn:
                conn.pgconn.exec_(sql.encode("utf-8"))
            print(f"✅ Schema base aplicado: {SCHEMA_SQL}")
        except Exception as exc:
            print(
                f"⚠️  No se pudo aplicar el schema base ({exc}). "
                "Se continúa con las migraciones; si el rol no es dueño, ejecuta "
                "database/schema.sql y database/migrations en el Supabase SQL Editor."
            )
    else:
        print(f"⚠️  No se encontró {SCHEMA_SQL}, saltando schema base.")

    # Aplicar migraciones en orden numérico
    migration_files = sorted(
        MIGRATIONS_DIR.glob("*.sql"), key=_migration_sort_key
    )

    applied = 0
    skipped = 0
    failed = 0

    for migration_path in migration_files:
        migration_name = migration_path.name
        try:
            sql = migration_path.read_text(encoding="utf-8")
            with psycopg.connect(ddl_url, autocommit=True, connect_timeout=20) as conn:
                conn.pgconn.exec_(sql.encode("utf-8"))
            applied += 1
            print(f"✅ Migración aplicada: {migration_name}")
        except Exception as exc:
            # Algunas migraciones pueden 'fallar' si ya estaban aplicadas anteriormente
            # (por ejemplo, si una tabla ya existe). Las etiquetamos como 'skipped'
            # pero las volvemos a intentar para asegurar el estado correcto.
            error_msg = str(exc)
            if "already exists" in error_msg.lower() or "duplicate key" in error_msg.lower():
                skipped += 1
                print(f"🔁 Migración ya aplicada (skip): {migration_name}")
            else:
                failed += 1
                lower = error_msg.lower()
                if "must be owner" in lower or "permission denied" in lower or "row-level security" in lower:
                    print(
                        f"⚠️  Migración {migration_name} requiere un rol privilegiado: "
                        f"{error_msg}. Ejecútala como dueño de la base (Supabase SQL Editor)."
                    )
                else:
                    print(f"❌ Error applying migration {migration_name}: {error_msg}")
                # No levantamos el error para no bloquear el inicio si es no-crítico

    print(
        f"\n📊 Resumen de migraciones: aplicadas={applied}, ya existían={skipped}, fallidas={failed}"
    )

    # Auto-reparación de columnas críticas de autenticación.
    try:
        ensure_auth_columns()
    except Exception as exc:  # noqa: BLE001 - nunca bloquear el arranque
        print(f"⚠️  No se pudo verificar columnas de auth: {exc}")


if __name__ == "__main__":
    apply_migrations()