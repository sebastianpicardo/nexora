from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.parsers.normalization.currency import normalize_currency, parse_decimal


def _confidence(value: object) -> float:
    if value is None:
        return 0.5
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if 1 < number <= 100:
        number = number / 100
    return max(0.0, min(1.0, number))


def _number(value: object) -> float | None:
    parsed = parse_decimal(value)
    return float(parsed) if parsed is not None else None


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line_number: int | None = None
    sku: str | None = None
    description: str = ""
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    line_total: float | None = None
    currency: str | None = None
    package_size: float | None = None
    price_date: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence_text: str | None = None
    page: int | None = None

    @field_validator("quantity", "unit_price", "line_total", "package_size", mode="before")
    @classmethod
    def _parse_number(cls, value: object) -> float | None:
        return _number(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _parse_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("description", mode="before")
    @classmethod
    def _description(cls, value: object) -> str:
        text = " ".join(str(value or "").split())
        return text or "Ítem sin descripción"

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return normalize_currency(value, default="") or None


class ExtractedDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_type: str | None = None
    supplier_name: str | None = None
    supplier_tax_id: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    items: list[ExtractedItem] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None

    @field_validator("items", mode="before")
    @classmethod
    def _items(cls, value: object) -> list:
        return value if isinstance(value, list) else []

    @field_validator("doc_type", mode="before")
    @classmethod
    def _doc_type(cls, value: object) -> str | None:
        text = str(value or "").strip().lower()
        return text if text in {"quote", "invoice", "price_list"} else None

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return normalize_currency(value, default="") or None

    @field_validator("confidence", mode="before")
    @classmethod
    def _parse_confidence(cls, value: object) -> float | None:
        if value is None or str(value).strip() == "":
            return None
        return _confidence(value)

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def _parse_money(cls, value: object) -> float | None:
        return _number(value)


@dataclass
class AuditFlag:
    type: str
    severity: str
    reason: str
    evidence: dict = field(default_factory=dict)


@dataclass
class NormalizedItem:
    sku: str | None
    original_description: str
    normalized_description: str
    original_unit: str | None
    base_unit: str
    unit_factor: Decimal
    quantity: Decimal | None
    package_size: Decimal | None
    original_unit_price: Decimal | None
    normalized_unit_price: Decimal | None
    currency: str
    price_date: date
    confidence: float
    source_page: int | None
    source_text: str | None
    flags: list[AuditFlag]
    metadata: dict = field(default_factory=dict)


@dataclass
class NormalizationResult:
    extraction: ExtractedDocument
    items: list[NormalizedItem]
    raw_text: str = ""
    provider: str = ""
    model: str = ""
