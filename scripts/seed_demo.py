from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from src.db.seeding import PLANS_SEED_SQL  # noqa: E402

SEED_NAMESPACE = UUID("a69879ff-6a3a-4f34-bc54-5f0fd6a2d6c7")
DEMO_STORAGE_PREFIX = "demo/"

SUPPLIERS = [
    {
        "key": "aceros-pacifico",
        "name": "Aceros del Pacífico SpA",
        "normalized_name": "aceros del pacifico spa",
        "tax_id": "76.542.310-8",
        "email": "ventas@acerospacifico.cl",
    },
    {
        "key": "insumos-andes",
        "name": "Insumos Industriales Andes Ltda.",
        "normalized_name": "insumos industriales andes ltda",
        "tax_id": "77.218.640-2",
        "email": "cotizaciones@insumosandes.cl",
    },
    {
        "key": "ferreteria-central",
        "name": "Ferretería Central Mayorista",
        "normalized_name": "ferreteria central mayorista",
        "tax_id": "78.903.145-6",
        "email": "compras@ferreteriacentral.cl",
    },
]

DOCUMENTS = [
    {
        "key": "cotizacion-acero",
        "filename": "cotizacion-acero-octubre.pdf",
        "mime_type": "application/pdf",
        "doc_type": "quote",
        "status": "processed",
        "month_offset": 0,
        "supplier": 0,
        "file_size_bytes": 248_320,
        "document_number": "COT-1042",
    },
    {
        "key": "factura-andes",
        "filename": "factura-insumos-andes.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "doc_type": "invoice",
        "status": "processing",
        "month_offset": 0,
        "supplier": 1,
        "file_size_bytes": 96_512,
        "document_number": "FAC-8821",
    },
    {
        "key": "cotizacion-pernos",
        "filename": "cotizacion-pernos-agosto.pdf",
        "mime_type": "application/pdf",
        "doc_type": "quote",
        "status": "processed",
        "month_offset": -2,
        "supplier": 2,
        "file_size_bytes": 184_640,
        "document_number": "COT-0874",
    },
    {
        "key": "factura-ferreteria",
        "filename": "factura-ferreteria-julio.pdf",
        "mime_type": "application/pdf",
        "doc_type": "invoice",
        "status": "processed",
        "month_offset": -3,
        "supplier": 0,
        "file_size_bytes": 312_800,
        "document_number": "FAC-7615",
    },
    {
        "key": "lista-precios",
        "filename": "lista-precios-junio.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "doc_type": "price_list",
        "status": "processed",
        "month_offset": -4,
        "supplier": 1,
        "file_size_bytes": 74_240,
        "document_number": "LP-2026-06",
    },
]

ITEMS = [
    {
        "sku": "TOR-M8X40",
        "description": "Tornillo hexagonal M8 x 40 mm",
        "unit": "unidad",
        "quantity": 500,
        "price": 180,
    },
    {
        "sku": "DIS-45",
        "description": 'Disco de corte 4.5" para metal',
        "unit": "unidad",
        "quantity": 80,
        "price": 1250,
    },
    {
        "sku": "PLA-A36-3",
        "description": "Plancha de acero A36 3 mm",
        "unit": "kg",
        "quantity": 1200,
        "price": 1180,
    },
    {
        "sku": "ELE-6013",
        "description": "Electrodo de soldadura 6013",
        "unit": "kg",
        "quantity": 60,
        "price": 2890,
    },
    {
        "sku": "TUE-M8",
        "description": "Tuerca hexagonal M8",
        "unit": "unidad",
        "quantity": 800,
        "price": 65,
    },
    {
        "sku": "ROD-6204",
        "description": "Rodamiento 6204 2RS",
        "unit": "unidad",
        "quantity": 60,
        "price": 4200,
    },
    {
        "sku": "PER-4040",
        "description": "Perfil cuadrado 40x40x2 mm",
        "unit": "barra",
        "quantity": 150,
        "price": 8950,
    },
    {
        "sku": "PIN-ANT",
        "description": "Pintura anticorrosiva",
        "unit": "galón",
        "quantity": 24,
        "price": 32900,
    },
    {
        "sku": "ROD-6204",
        "description": "Rodamiento 6204 2RS",
        "unit": "unidad",
        "quantity": 60,
        "price": 5100,
    },
    {
        "sku": "ACE-ISO68",
        "description": "Aceite hidráulico ISO 68",
        "unit": "litro",
        "quantity": 200,
        "price": 2790,
    },
    {
        "sku": "TOR-M8X40",
        "description": "Tornillo hexagonal M8 x 40 mm",
        "unit": "unidad",
        "quantity": 500,
        "price": 235,
    },
    {
        "sku": "DIS-45",
        "description": 'Disco de corte 4.5" para metal',
        "unit": "unidad",
        "quantity": 80,
        "price": 1750,
    },
]

EXCEPTION_ITEMS = {
    8: {
        "severity": "medium",
        "previous_price": 4200,
        "reason": "Aumento de precio de 21.4% frente a la compra anterior del mismo rodamiento.",
    },
    10: {
        "severity": "high",
        "previous_price": 180,
        "reason": "Aumento de precio de 30.6% frente a la última compra registrada del mismo tornillo.",
    },
    11: {
        "severity": "critical",
        "previous_price": 1250,
        "reason": 'Aumento de precio de 40.0% frente a la última compra registrada del disco de corte 4.5".',
    },
}


def month_start(offset: int) -> date:
    today = date.today().replace(day=1)
    month_index = today.year * 12 + today.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def at_month(month: date, day: int, hour: int = 12) -> datetime:
    candidate = month + timedelta(days=day - 1)
    today = date.today()
    if candidate > today:
        candidate = today
    return datetime.combine(candidate, time(hour=hour), tzinfo=UTC)


def load_env(path: str) -> None:
    values = dotenv_values(path)
    for key, value in values.items():
        if value is not None:
            os.environ[key] = value


def demo_uuid(org_id: UUID, kind: str, key: str) -> UUID:
    return uuid5(SEED_NAMESPACE, f"{org_id}:{kind}:{key}")


def choose_user(conn, email: str) -> dict:
    if email:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.org_id, u.role, u.name, o.name AS org_name
            FROM users u
            JOIN organizations o ON o.id = u.org_id
            WHERE lower(u.email) = lower(%s) AND u.active = TRUE
            """,
            (email,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.org_id, u.role, u.name, o.name AS org_name
            FROM users u
            JOIN organizations o ON o.id = u.org_id
            WHERE u.active = TRUE
            ORDER BY CASE WHEN u.role IN ('owner', 'super_admin') THEN 0 ELSE 1 END, u.created_at
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise RuntimeError("No se encontró un usuario activo para sembrar los datos demo.")
    return row


def reset_demo_rows(conn, org_id: UUID) -> None:
    conn.execute(
        "DELETE FROM documents_log WHERE org_id = %s AND storage_path LIKE %s",
        (org_id, f"{DEMO_STORAGE_PREFIX}%"),
    )
    supplier_ids = [demo_uuid(org_id, "supplier", supplier["key"]) for supplier in SUPPLIERS]
    conn.execute(
        "DELETE FROM suppliers WHERE org_id = %s AND id = ANY(%s)",
        (org_id, supplier_ids),
    )


def seed_plans(conn) -> None:
    conn.execute(PLANS_SEED_SQL)


def seed_subscription(conn, org_id: UUID) -> None:
    conn.execute(
        """
        INSERT INTO subscriptions (org_id, plan_id, status)
        VALUES (%s, 'free', 'active')
        ON CONFLICT (org_id) DO NOTHING
        """,
        (org_id,),
    )


def seed_suppliers(conn, org_id: UUID) -> dict[int, UUID]:
    supplier_ids: dict[int, UUID] = {}
    for index, supplier in enumerate(SUPPLIERS):
        supplier_id = demo_uuid(org_id, "supplier", supplier["key"])
        row = conn.execute(
            """
            INSERT INTO suppliers (id, org_id, name, normalized_name, tax_id, email)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, normalized_name) DO UPDATE SET
                name = EXCLUDED.name,
                tax_id = EXCLUDED.tax_id,
                email = EXCLUDED.email
            RETURNING id
            """,
            (
                supplier_id,
                org_id,
                supplier["name"],
                supplier["normalized_name"],
                supplier["tax_id"],
                supplier["email"],
            ),
        ).fetchone()
        supplier_ids[index] = row["id"] if row else supplier_id
    return supplier_ids


def seed_documents(conn, org_id: UUID, user_id: UUID, supplier_ids: dict[int, UUID]) -> list[dict]:
    documents = []
    for document in DOCUMENTS:
        month = month_start(document["month_offset"])
        created_at = at_month(month, 5, 10)
        document_id = demo_uuid(org_id, "document", document["key"])
        file_hash = hashlib.sha256(f"nexora-demo:{org_id}:{document['key']}".encode()).hexdigest()
        processed_at = created_at + timedelta(minutes=4) if document["status"] == "processed" else None
        processing_started_at = created_at + timedelta(seconds=30) if document["status"] == "processing" else None
        row = conn.execute(
            """
            INSERT INTO documents_log (
                id, org_id, supplier_id, uploaded_by, original_filename, storage_path,
                file_hash, mime_type, file_size_bytes, doc_type, status,
                extraction_provider, extraction_model, metadata, created_at,
                processing_started_at, processed_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                'demo', 'seed-script', %s, %s,
                %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                supplier_id = EXCLUDED.supplier_id,
                uploaded_by = EXCLUDED.uploaded_by,
                original_filename = EXCLUDED.original_filename,
                metadata = EXCLUDED.metadata,
                status = EXCLUDED.status,
                created_at = EXCLUDED.created_at,
                processing_started_at = EXCLUDED.processing_started_at,
                processed_at = EXCLUDED.processed_at
            RETURNING id
            """,
            (
                document_id,
                org_id,
                supplier_ids[document["supplier"]],
                user_id,
                document["filename"],
                f"{DEMO_STORAGE_PREFIX}{org_id}/{document['filename']}",
                file_hash,
                document["mime_type"],
                document["file_size_bytes"],
                document["doc_type"],
                document["status"],
                Jsonb(
                    {
                        "demo": True,
                        "document_number": document["document_number"],
                        "supplier": SUPPLIERS[document["supplier"]]["name"],
                    }
                ),
                created_at,
                processing_started_at,
                processed_at,
            ),
        ).fetchone()
        documents.append(
            {
                **document,
                "id": row["id"] if row else document_id,
                "created_at": created_at,
            }
        )
    return documents


def seed_items(conn, org_id: UUID, documents: list[dict], supplier_ids: dict[int, UUID]) -> list[dict]:
    items = []
    for index, item in enumerate(ITEMS):
        month_index, position = divmod(index, 2)
        month = month_start(month_index - 5)
        price_date = month + timedelta(days=13)
        if price_date > date.today():
            price_date = date.today()
        document = documents[4 - min(month_index, 4)]
        supplier_index = month_index % len(SUPPLIERS)
        supplier_id = supplier_ids[supplier_index]
        review_status = "pending" if index in EXCEPTION_ITEMS else "auto_approved"
        item_id = demo_uuid(org_id, "item", str(index))
        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["price"]))
        row = conn.execute(
            """
            INSERT INTO items_history (
                id, org_id, document_id, supplier_id, sku, original_description,
                normalized_description, original_unit, base_unit, unit_factor,
                quantity, original_unit_price, normalized_unit_price, currency,
                price_date, confidence, review_status, source_page, source_text,
                metadata, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, 1,
                %s, %s, %s, 'CLP',
                %s, %s, %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                supplier_id = EXCLUDED.supplier_id,
                quantity = EXCLUDED.quantity,
                original_unit_price = EXCLUDED.original_unit_price,
                normalized_unit_price = EXCLUDED.normalized_unit_price,
                price_date = EXCLUDED.price_date,
                confidence = EXCLUDED.confidence,
                review_status = EXCLUDED.review_status,
                metadata = EXCLUDED.metadata,
                created_at = EXCLUDED.created_at
            RETURNING id
            """,
            (
                item_id,
                org_id,
                document["id"],
                supplier_id,
                item["sku"],
                item["description"],
                item["description"],
                item["unit"],
                item["unit"],
                quantity,
                unit_price,
                unit_price,
                price_date,
                Decimal("0.96") if index not in EXCEPTION_ITEMS else Decimal("0.88"),
                review_status,
                position + 1,
                f"{item['description']} | {item['quantity']} {item['unit']} | CLP {item['price']}",
                Jsonb(
                    {
                        "demo": True,
                        "line_total": float(quantity * unit_price),
                        "period": price_date.strftime("%Y-%m"),
                    }
                ),
                at_month(month, 15, 11),
            ),
        ).fetchone()
        items.append(
            {
                **item,
                "id": row["id"] if row else item_id,
                "document_id": document["id"],
                "supplier_id": supplier_id,
                "supplier_name": SUPPLIERS[supplier_index]["name"],
                "price_date": price_date,
                "month": month,
            }
        )
    return items


def seed_exceptions(conn, org_id: UUID, items: list[dict]) -> int:
    created = 0
    for index, config in EXCEPTION_ITEMS.items():
        item = items[index]
        item_id = item["id"]
        document_id = item["document_id"]
        exception_id = demo_uuid(org_id, "exception", str(index))
        variation = round(((item["price"] - config["previous_price"]) / config["previous_price"]) * 100, 1)
        row = conn.execute(
            """
            INSERT INTO exceptions_log (
                id, org_id, document_id, item_id, type, severity, reason,
                evidence, status, created_at
            )
            VALUES (%s, %s, %s, %s, 'price_spike', %s, %s, %s, 'pending', %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            (
                exception_id,
                org_id,
                document_id,
                item_id,
                config["severity"],
                config["reason"],
                Jsonb(
                    {
                        "demo": True,
                        "previous_price": config["previous_price"],
                        "current_price": item["price"],
                        "variation_pct": variation,
                        "threshold_pct": 10,
                        "supplier": item["supplier_name"],
                    }
                ),
                at_month(item["month"], 20, 16),
            ),
        ).fetchone()
        if row:
            created += 1
    return created


def print_summary(conn, org_id: UUID) -> None:
    row = conn.execute(
        """
        SELECT
            (SELECT count(*) FROM documents_log WHERE org_id = %(org_id)s) AS documents,
            (SELECT count(*) FROM items_history WHERE org_id = %(org_id)s) AS items,
            (SELECT count(*) FROM exceptions_log WHERE org_id = %(org_id)s AND status = 'pending') AS exceptions,
            (SELECT plan_id FROM subscriptions WHERE org_id = %(org_id)s) AS plan_id
        """,
        {"org_id": org_id},
    ).fetchone()
    print(
        "Datos demo listos: "
        f"{row['documents']} documentos, {row['items']} ítems, "
        f"{row['exceptions']} excepciones pendientes, plan {row['plan_id']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Siembra datos demo idempotentes en una organización de NEXORA.")
    parser.add_argument("--email", default="", help="Email del usuario cuya organización se poblará.")
    parser.add_argument("--env-file", default="", help="Archivo .env alternativo, por ejemplo .env.render.local.")
    parser.add_argument("--reset", action="store_true", help="Elimina los documentos demo previos antes de sembrar.")
    args = parser.parse_args()

    if args.env_file:
        load_env(args.env_file)

    from src.core.config import settings

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no configurada. Usa --env-file o define la variable de entorno.")

    with psycopg.connect(settings.database_url, connect_timeout=20, row_factory=dict_row, autocommit=True) as conn:
        # Desactivamos RLS temporalmente para poder insertar datos de prueba;
        # si el usuario conectado no tiene privilegios para cambiar de rol, capturamos la excepción y continuamos.
        try:
            conn.execute("SET ROLE postgres")
        except Exception as e:
            print(f"Información: no se pudo cambiar a rol postgres ({e}); se continuará sin desactivar RLS explícitamente.")
        # Intentamos desactivar RLS en las tablas clave; si falla (por ejemplo, por falta de permisos), registramos y proseguimos.
        try:
            conn.execute("ALTER TABLE plans DISABLE ROW LEVEL SECURITY")
        except Exception as e:
            print(f"Información: no se pudo desactivar RLS en plans ({e}); proseguimos confiando que ya está desactivado.")
        try:
            conn.execute("ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY")
        except Exception as e:
            print(f"Información: no se pudo desactivar RLS en subscriptions ({e}); proseguimos.")
        try:
            conn.execute("ALTER TABLE team_invitations DISABLE ROW LEVEL SECURITY")
        except Exception as e:
            print(f"Información: no se pudo desactivar RLS en team_invitations ({e}); proseguimos.")
        conn.execute("SET ROLE nexora_app")
        user = choose_user(conn, args.email)
        org_id = user["org_id"]
        if args.reset:
            reset_demo_rows(conn, org_id)
        seed_plans(conn)
        seed_subscription(conn, org_id)
        supplier_ids = seed_suppliers(conn, org_id)
        documents = seed_documents(conn, org_id, user["id"], supplier_ids)
        items = seed_items(conn, org_id, documents, supplier_ids)
        seed_exceptions(conn, org_id, items)
        print(f"Organización: {user['org_name']} ({org_id})")
        print(f"Usuario: {user['email']} ({user['role']})")
        print_summary(conn, org_id)


if __name__ == "__main__":
    main()
