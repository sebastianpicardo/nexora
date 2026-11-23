from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from src.core.errors import ExtractionError

T = TypeVar("T")

RESOLUTION_INTERNAL = "internal_process"
RESOLUTION_AI_FALLBACK = "ai_fallback"
RESOLUTION_UNRESOLVED = "unresolved"


@dataclass
class ExtractionResult:
    """Resultado de una extracción con trazabilidad de origen.

    Attributes:
        result: Objeto extraído (puede ser None si no se pudo resolver).
        source: "internal_process" si se resolvió sin IA,
                "ai_fallback" si se usó un modelo de IA como respaldo,
                "unresolved" si no se pudo extraer nada.
        fallback_reason: Razón por la que se activó el fallback a IA
            ("parse_error", "low_confidence", "missing_required_fields",
             "unsupported_format", "no_items", "ai_consent_denied", None).
        ai_used: True si se consumieron tokens de IA.
        attempts: Lista de intentos realizados con su resultado.
    """

    result: Any
    source: str
    fallback_reason: str | None = None
    ai_used: bool = False
    attempts: list[dict] = field(default_factory=list)


class ExtractionPolicy:
    """Ejecuta un extractor determinístico primero y, solo si falla o no
    produce un resultado usable, recurre a un proveedor de IA como fallback.

    El objetivo es evitar gastar tokens de IA cuando el documento puede
    parsearse con reglas, regex, diccionarios o consultas a la base de datos.
    """

    def __init__(self) -> None:
        self.internal_calls = 0
        self.ai_calls = 0
        self.fallback_reasons: dict[str, int] = {}

    def _record_attempt(
        self,
        attempts: list[dict],
        stage: str,
        success: bool,
        reason: str | None = None,
        detail: str | None = None,
    ) -> None:
        attempts.append(
            {
                "stage": stage,
                "success": success,
                "reason": reason,
                "detail": detail,
            }
        )

    async def run(
        self,
        *,
        internal: Callable[[], Any],
        ai: Callable[[], Any],
        min_confidence: float = 0.0,
        required_fields: tuple[str, ...] | None = None,
        validate: Callable[[Any], bool] | None = None,
    ) -> ExtractionResult:
        """Ejecuta el pipeline determinista -> IA.

        Args:
            internal: Función async que ejecuta la extracción determinística.
            ai: Función async que ejecuta el fallback de IA.
            min_confidence: Umbral mínimo de confianza (0.0-1.0).
            required_fields: Campos obligatorios que deben estar presentes
                y no nulos en el resultado para considerarlo completo.
            validate: Función opcional de validación personalizada.

        Returns:
            Un ExtractionResult con el resultado, origen, razón de fallback
            y si se usó IA.
        """
        attempts: list[dict] = []

        # ── 1. Intento determinístico (sin IA) ──────────────────────────
        internal_meta = None
        try:
            raw_internal = await internal()
        except Exception as exc:
            self._record_attempt(
                attempts, "internal", False, "exception", str(exc)[:200]
            )
            raw_internal = None
        else:
            raw_internal, internal_meta = self._unwrap(raw_internal)
            if internal_meta is not None:
                attempts.extend(internal_meta.attempts)

        internal_ok = self._is_valid(raw_internal, min_confidence, required_fields, validate)
        if internal_ok:
            self.internal_calls += 1
            self._record_attempt(
                attempts, "internal", True, None, "resuelto internamente"
            )
            return ExtractionResult(
                result=raw_internal,
                source=internal_meta.source if internal_meta else RESOLUTION_INTERNAL,
                fallback_reason=None,
                ai_used=bool(internal_meta.ai_used) if internal_meta else False,
                attempts=attempts,
            )

        # Razón del fallback
        fallback_reason = self._diagnose_failure(raw_internal)
        self._record_attempt(
            attempts, "internal", False, fallback_reason, "fallback a IA"
        )

        # ── 2. Fallback a IA ───────────────────────────────────────────
        ai_meta = None
        try:
            raw_ai = await ai()
        except ExtractionError:
            # Errores de dominio (p. ej. consentimiento de IA denegado) deben
            # propagarse para que el llamador reciba el motivo real.
            raise
        except Exception as exc:
            self.ai_calls += 1
            self._record_attempt(
                attempts, "ai", False, "exception", str(exc)[:200]
            )
            return ExtractionResult(
                result=None,
                source=RESOLUTION_UNRESOLVED,
                fallback_reason=fallback_reason,
                ai_used=False,
                attempts=attempts,
            )
        else:
            raw_ai, ai_meta = self._unwrap(raw_ai)
            if ai_meta is not None:
                attempts.extend(ai_meta.attempts)

        self.ai_calls += 1
        self._record_attempt(attempts, "ai", True, None, "resuelto por IA")

        ai_ok = self._is_valid(raw_ai, min_confidence, required_fields, validate)
        if not ai_ok:
            self._record_attempt(
                attempts,
                "ai",
                False,
                "low_confidence_or_incomplete",
                "IA no resolvió completamente",
            )
            return ExtractionResult(
                result=raw_ai,
                source=RESOLUTION_UNRESOLVED,
                fallback_reason="low_confidence_or_incomplete",
                ai_used=True,
                attempts=attempts,
            )

        return ExtractionResult(
            result=raw_ai,
            source=ai_meta.source if ai_meta else RESOLUTION_AI_FALLBACK,
            fallback_reason=fallback_reason,
            ai_used=True,
            attempts=attempts,
        )

    @staticmethod
    def _unwrap(value: Any) -> tuple[Any, ExtractionResult | None]:
        """Desenvuelve un ExtractionResult anidado devuelto por un extractor.

        Los extractores determinísticos y de IA devuelven un ``ExtractionResult``
        que envuelve el ``ExtractedDocument``. El orquestador debe validar el
        documento interno, no el envoltorio.
        """
        if (
            value is not None
            and hasattr(value, "result")
            and hasattr(value, "source")
            and hasattr(value, "attempts")
        ):
            return value.result, value
        return value, None

    def _is_valid(
        self,
        result: Any,
        min_confidence: float,
        required_fields: tuple[str, ...] | None,
        validate: Callable[[Any], bool] | None,
    ) -> bool:
        if result is None:
            return False

        # Validar confianza si el objeto tiene el atributo
        if hasattr(result, "confidence") and result.confidence is not None:
            if result.confidence < min_confidence:
                return False

        # Validar campos requeridos
        if required_fields:
            for field in required_fields:
                if getattr(result, field, None) is None:
                    return False

        # Validación personalizada
        if validate is not None:
            try:
                if not validate(result):
                    return False
            except Exception:
                return False

        return True

    def _diagnose_failure(self, result: Any) -> str:
        """Diagnostica por qué el proceso interno falló."""
        if result is None:
            return "no_items"
        if hasattr(result, "confidence") and result.confidence is not None:
            if result.confidence < 0.75:
                return "low_confidence"
        if hasattr(result, "items") and not result.items:
            return "no_items"
        return "missing_required_fields"


def extraction_policy() -> ExtractionPolicy:
    """Devuelve una instancia compartida del orquestador."""
    return _policy


_policy = ExtractionPolicy()
