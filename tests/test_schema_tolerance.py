from __future__ import annotations

from src.api.routes.billing import _plan_out
from src.db.init_db import _split_sql, diagnose_schema


def test_split_sql_keeps_dollar_blocks_whole():
    sql = (
        "CREATE TABLE a (id int);\n"
        "DO $$ BEGIN PERFORM 1; PERFORM 2; END $$;\n"
        "SELECT 1;"
    )
    statements = _split_sql(sql)
    assert len(statements) == 3
    assert statements[1].startswith("DO $$")
    assert statements[1].rstrip().endswith("END $$")
    # El ';' interno del bloque no debe dividir la sentencia.
    assert "PERFORM 1; PERFORM 2" in statements[1]


def test_split_sql_respects_strings_and_comments():
    sql = "INSERT INTO t VALUES ('a;b'); -- x; y\nSELECT 2;"
    statements = _split_sql(sql)
    assert len(statements) == 2
    assert "'a;b'" in statements[0]


def test_diagnose_schema_skips_sqlite():
    assert diagnose_schema("sqlite:///tmp/test.db") == {}


def test_plan_out_tolerates_missing_user_limit():
    row = {
        "id": "free",
        "name": "Free",
        "description": "Plan base",
        "price_monthly": 0,
        "currency": "CLP",
        "document_limit": 25,
        "features": ["25 documentos al mes"],
        "sort_order": 10,
    }
    plan = _plan_out(row)
    assert plan.user_limit is None
    assert plan.id == "free"
