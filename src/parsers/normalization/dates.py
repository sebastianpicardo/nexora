from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as date_parser


def parse_flexible_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass

    try:
        return date_parser.parse(text, dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None
