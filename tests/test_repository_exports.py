from __future__ import annotations

from src.db import repositories

EXPECTED = {
    "claim_document_by_id",
    "claim_next_queued",
    "count_open",
    "create_document",
    "create_exception",
    "create_user_with_org",
    "get_document",
    "get_document_by_hash",
    "get_exception",
    "get_item",
    "get_or_create_supplier",
    "get_organization",
    "get_price_history",
    "get_supplier",
    "get_user_by_email",
    "get_user_by_google_id",
    "get_user_with_org",
    "insert_item",
    "list_documents",
    "list_exceptions",
    "list_items",
    "list_suppliers",
    "list_users",
    "mark_failed",
    "mark_processed",
    "mark_processing",
    "reset_document_children",
    "reset_document_for_reprocess",
    "resolve_exception",
    "touch_last_login",
    "update_document_status",
    "update_google_profile",
    "update_item_fields",
    "update_organization",
}


def test_repository_package_exports_all_used_functions():
    missing = EXPECTED - set(repositories.__all__)
    assert not missing, f"Faltan exports: {sorted(missing)}"
    for name in EXPECTED:
        assert callable(getattr(repositories, name, None)), name
