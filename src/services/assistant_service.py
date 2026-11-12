from __future__ import annotations

import logging

from src.core.config import settings
from src.db.pool import get_pool
from src.services import ai_usage_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Eres el asistente de NEXORA, una plataforma SaaS que audita compras y precios B2B.
Respondes siempre en español, de forma breve, clara y accionable (máximo 6 frases o una lista corta).

Contexto del producto:
- NEXORA recibe cotizaciones, facturas y listas de precios (PDF, Excel, CSV, imágenes), extrae
  automáticamente proveedor, productos, cantidades, unidades y precios con IA.
- Normaliza unidades y precios para comparar peras con peras y detecta anomalías: alzas de precio,
  baja confianza de extracción, unidades inconsistentes y totales que no cuadran.
- Módulos principales del menú:
  * Inicio (Resumen del día): KPIs de compra, ahorro, excepciones y documentos recientes.
  * Inteligencia: Analítica ejecutiva (índice de precios y gasto), Oportunidades de ahorro
    (sobreprecio vs mediana histórica y mejor precio), Pronóstico de compras (consumo futuro),
    Aprobación inteligente (auto-aprobación por confianza y ausencia de alertas críticas).
  * Compras: Documentos (subir y re-procesar), Precios auditados (histórico normalizado),
    Excepciones (bandeja HITL), Aprobaciones (solicitudes de compra), Proveedores, Catálogo de precios.
  * Integraciones: ChileCompra/SII/ERP, seguridad y marca, backups.
  * Administración: Equipo, Planes y precios, Configuración, Mi perfil.
  * Plataforma: Usuarios y auditoría (solo super admin).
- Roles: owner/admin gestionan equipo, planes, configuración e integraciones; analyst/user operan
  documentos y aprobaciones; viewer/auditor solo consulta.
- Flujo típico: subir documento -> extracción automática -> auditoría -> revisar excepciones ->
  aprobar compras -> analizar oportunidades y pronóstico.
- Cómo se vende: ahorro medible (sobreprecios detectados), menos horas manuales, control y trazabilidad
  de compras, alertas proactivas y reportes ejecutivos. Segmentos: distribuidores industriales,
  constructoras, retail B2B y áreas de compras de pymes/medianas empresas.

Reglas:
- Si te preguntan cómo hacer algo, indica el módulo exacto del menú y los pasos.
- Si te piden datos de la organización que no tienes, explica que deben revisar el módulo
  correspondiente; nunca inventes cifras.
- Si preguntan por precios del plan, indica que revisen "Administración > Planes y precios".
- Si el usuario necesita soporte técnico, sugiere revisar Documentos > estado de procesamiento
  o contactar al administrador de la organización.
""".strip()


def _history_block(history: list[dict] | None) -> str:
    if not history:
        return ""
    lines = []
    for entry in history[-6:]:
        role = "Usuario" if entry.get("role") == "user" else "Asistente"
        content = str(entry.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "\n\nConversación previa:\n" + "\n".join(lines)


async def _ask_gemini(question: str, history: list[dict] | None) -> tuple[str | None, dict[str, int] | None]:
    if not settings.gemini_api_key:
        return None, None
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = f"{question}{_history_block(history)}"
    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1200,
        ),
    )
    text = (response.text or "").strip()
    usage = None
    if getattr(response, "usage_metadata", None):
        usage = {
            "input_tokens": int(getattr(response.usage_metadata, "prompt_token_count", 0) or 0),
            "output_tokens": int(getattr(response.usage_metadata, "candidates_token_count", 0) or 0),
        }
    return (text or None, usage)


async def _ask_openai(question: str, history: list[dict] | None) -> tuple[str | None, dict[str, int] | None]:
    if not settings.openai_api_key:
        return None, None
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for entry in (history or [])[-6:]:
        content = str(entry.get("content") or "").strip()
        if content:
            messages.append(
                {
                    "role": "assistant" if entry.get("role") == "assistant" else "user",
                    "content": content,
                }
            )
    messages.append({"role": "user", "content": question})
    completion = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.3,
        max_tokens=900,
    )
    text = (completion.choices[0].message.content or "").strip()
    usage = None
    if completion.usage:
        usage = {
            "input_tokens": int(completion.usage.prompt_tokens or 0),
            "output_tokens": int(completion.usage.completion_tokens or 0),
        }
    return (text or None, usage)


async def _ask_anthropic(question: str, history: list[dict] | None) -> tuple[str | None, dict[str, int] | None]:
    if not settings.anthropic_api_key:
        return None, None
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout_seconds)
    messages = []
    for entry in (history or [])[-6:]:
        content = str(entry.get("content") or "").strip()
        if content:
            messages.append(
                {
                    "role": "assistant" if entry.get("role") == "assistant" else "user",
                    "content": content,
                }
            )
    messages.append({"role": "user", "content": question})
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=messages,
        temperature=0.3,
    )
    text = "\n".join(
        getattr(block, "text", "") for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
    usage = None
    if getattr(response, "usage", None):
        usage = {
            "input_tokens": int(getattr(response.usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(response.usage, "output_tokens", 0) or 0),
        }
    return (text or None, usage)


async def answer_question(
    question: str,
    *,
    history: list[dict] | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> tuple[str | None, str | None]:
    order = [
        name.strip().lower()
        for name in (settings.llm_provider_order or "openai,anthropic,gemini").split(",")
        if name.strip()
    ]
    handlers = {
        "openai": _ask_openai,
        "anthropic": _ask_anthropic,
        "gemini": _ask_gemini,
    }
    models = {
        "openai": settings.llm_model,
        "anthropic": settings.anthropic_model,
        "gemini": settings.gemini_model,
    }
    for name in order:
        handler = handlers.get(name)
        if handler is None:
            continue
        try:
            answer, usage = await handler(question, history)
        except Exception as exc:
            logger.warning("Asistente IA: proveedor %s falló: %s", name, str(exc)[:300])
            continue
        if answer:
            if org_id:
                try:
                    async with get_pool().connection() as conn:
                        await ai_usage_service.record_usage(
                            conn,
                            org_id=org_id,
                            kind="assistant",
                            provider=name,
                            model=models.get(name, ""),
                            input_tokens=(usage or {}).get("input_tokens", 0),
                            output_tokens=(usage or {}).get("output_tokens", 0),
                            user_id=user_id,
                            status="success",
                        )
                except Exception as exc:
                    logger.warning("No se pudo registrar uso de IA del asistente: %s", str(exc)[:300])
            return answer, name
    return None, None
