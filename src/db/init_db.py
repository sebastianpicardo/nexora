from __future__ import annotations

import re
from pathlib import Path

import psycopg

from src.core.config import PROJECT_ROOT, settings

MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"
SCHEMA_SQL = PROJECT_ROOT / "database" / "schema.sql"

# Tablas/columnas mínimas para autenticación, sesiones, suscripción y planes.
REQUIRED_SCHEMA: dict[str, list[str]] = {
    "organizations": [
        "id",
        "name",
        "slug",
        "price_spike_threshold_pct",
        "min_confidence",
        "default_currency",
    ],
    "users": [
        "id",
        "org_id",
        "email",
        "name",
        "avatar_url",
        "role",
        "active",
        "created_at",
        "updated_at",
        "google_id",
        "password_hash",
        "last_login_at",
        "job_title",
        "phone",
        "timezone",
        "notify_quota",
        "notify_weekly",
        "email_verified",
    ],
    "user_sessions": ["id", "org_id", "user_id"],
    "plans": [
        "id",
        "name",
        "price_monthly",
        "currency",
        "document_limit",
        "user_limit",
        "features",
        "sort_order",
        "active",
    ],
    "subscriptions": [
        "id",
        "org_id",
        "plan_id",
        "status",
        "current_period_start",
        "current_period_end",
    ],
}


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


def _split_sql(sql: str) -> list[str]:
    """Divide un script SQL en sentencias respetando ``'`` y bloques ``$$ ... $$``."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            end = sql.find("\n", i)
            if end == -1:
                buf.append(sql[i:])
                break
            buf.append(sql[i : end + 1])
            i = end + 1
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                buf.append(sql[i:])
                break
            buf.append(sql[i : end + 2])
            i = end + 2
            continue
        if ch == "'":
            buf.append(ch)
            i += 1
            while i < n:
                c = sql[i]
                buf.append(c)
                if c == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append(sql[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    buf.append(sql[i:])
                    break
                buf.append(sql[i : end + len(tag)])
                i = end + len(tag)
                continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _apply_sql_script(ddl_url: str, sql: str) -> tuple[int, int, list[str]]:
    """Ejecuta un script sentencia por sentencia tolerando errores idempotentes.

    Devuelve ``(aplicadas, omitidas, errores)``. Con autocommit, un fallo en una
    sentencia no aborta las siguientes: así un esquema parcial se completa aunque
    alguna migración haya quedado a medias.
    """
    applied = 0
    skipped = 0
    errors: list[str] = []
    statements = _split_sql(sql)
    with psycopg.connect(ddl_url, autocommit=True, connect_timeout=20) as conn:
        for statement in statements:
            try:
                conn.pgconn.exec_((statement + ";").encode("utf-8"))
                applied += 1
            except Exception as exc:  # noqa: BLE001 - tolerante por diseño
                message = str(exc)
                low = message.lower()
                if (
                    "already exists" in low
                    or "duplicate key" in low
                    or "must be owner" in low
                    or "permission denied" in low
                    or "row-level security" in low
                ):
                    skipped += 1
                else:
                    errors.append(message.splitlines()[0][:200])
    return applied, skipped, errors


def apply_migrations() -> None:
    """Aplica schema y migraciones pendientes de forma tolerante.

    Se ejecuta sentencia por sentencia para tolerar esquemas parciales: una
    sentencia que falla no impide que el resto (incluidas las columnas que
    faltaban) se aplique.
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

    if SCHEMA_SQL.exists():
        try:
            sql = SCHEMA_SQL.read_text(encoding="utf-8")
            ok, skipped, errors = _apply_sql_script(ddl_url, sql)
            print(
                f"✅ Schema base: aplicadas={ok}, omitidas={skipped}, errores={len(errors)}"
            )
            for err in errors[:5]:
                print(f"❌ Schema: {err}")
        except Exception as exc:  # noqa: BLE001
            print(
                f"⚠️  No se pudo aplicar el schema base ({exc}). "
                "Si el rol no es dueño, ejecuta database/schema.sql como dueño de la base."
            )
    else:
        print(f"⚠️  No se encontró {SCHEMA_SQL}, saltando schema base.")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=_migration_sort_key)

    total_applied = 0
    total_skipped = 0
    total_failed = 0
    for migration_path in migration_files:
        try:
            sql = migration_path.read_text(encoding="utf-8")
            ok, skipped, errors = _apply_sql_script(ddl_url, sql)
            total_applied += ok
            total_skipped += skipped
            total_failed += len(errors)
            status = "✅" if not errors else "⚠️"
            print(
                f"{status} {migration_path.name}: aplicadas={ok}, omitidas={skipped}, "
                f"errores={len(errors)}"
            )
            for err in errors[:3]:
                print(f"   ❌ {err}")
        except Exception as exc:  # noqa: BLE001
            total_failed += 1
            print(f"❌ No se pudo aplicar {migration_path.name}: {exc}")

    print(
        f"\n📊 Resumen: sentencias aplicadas={total_applied}, omitidas={total_skipped}, "
        f"fallidas={total_failed}"
    )

    # Auto-reparación de columnas críticas de autenticación/planes.
    try:
        ensure_auth_columns()
    except Exception as exc:  # noqa: BLE001 - nunca bloquear el arranque
        print(f"⚠️  No se pudo verificar columnas de auth: {exc}")


def diagnose_schema(database_url: str | None = None) -> dict[str, list[str]]:
    """Devuelve las tablas/columnas requeridas que faltan en la base.

    Se usa al arrancar y desde ``/health/schema`` para diagnosticar en vivo un
    esquema parcial. Solo aplica a PostgreSQL (en SQLite devuelve ``{}``).
    """
    url = (database_url or settings.ddl_database_url or "").strip()
    if not url or url.startswith("sqlite"):
        return {}

    existing: dict[str, set[str]] = {}
    with psycopg.connect(url, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = ANY(%s)
                """,
                (list(REQUIRED_SCHEMA.keys()),),
            )
            for table_name, column_name in cur.fetchall():
                existing.setdefault(table_name, set()).add(column_name)

    missing: dict[str, list[str]] = {}
    for table, columns in REQUIRED_SCHEMA.items():
        present = existing.get(table)
        if not present:
            missing[table] = ["<tabla ausente>"]
            continue
        absent = [column for column in columns if column not in present]
        if absent:
            missing[table] = absent
    return missing


if __name__ == "__main__":
    apply_migrations()