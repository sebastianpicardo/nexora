from __future__ import annotations


class NexoraError(Exception):
    status_code = 400
    code = "nexora_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(NexoraError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(NexoraError):
    status_code = 403
    code = "permission_denied"


class ConflictError(NexoraError):
    status_code = 409
    code = "conflict"


class ValidationError(NexoraError):
    status_code = 422
    code = "validation_error"


class StorageError(NexoraError):
    status_code = 502
    code = "storage_error"


class LLMNotConfiguredError(NexoraError):
    status_code = 503
    code = "llm_not_configured"


class LLMError(NexoraError):
    status_code = 502
    code = "llm_error"


AI_TEMPORARY_MESSAGE = (
    "El motor de IA está experimentando alta demanda. "
    "Tu documento se procesará en breve; vuelve a intentarlo en unos segundos."
)


class LLMTemporaryError(LLMError):
    status_code = 503
    code = "ai_temporarily_unavailable"

    def __init__(self, message: str = AI_TEMPORARY_MESSAGE) -> None:
        super().__init__(message, details={"retry_after_seconds": 30})


class ExtractionError(NexoraError):
    status_code = 422
    code = "extraction_error"
