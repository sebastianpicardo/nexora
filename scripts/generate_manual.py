"""Genera el manual completo de NEXORA en PDF en la raíz del proyecto."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "NEXORA_Manual_Sistema.pdf"

BRAND = colors.HexColor("#059669")
BRAND_DARK = colors.HexColor("#047857")
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
SURFACE = colors.HexColor("#f8fafc")
AMBER = colors.HexColor("#b45309")
RED = colors.HexColor("#b91c1c")

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=34,
        leading=40,
        textColor=INK,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub",
        fontName="Helvetica",
        fontSize=14,
        leading=20,
        textColor=MUTED,
        spaceAfter=24,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverMeta",
        fontName="Helvetica",
        fontSize=10,
        leading=16,
        textColor=MUTED,
    )
)
styles.add(
    ParagraphStyle(
        name="H1",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=26,
        textColor=INK,
        spaceBefore=6,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="H2",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=BRAND_DARK,
        spaceBefore=14,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="H3",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=15,
        textColor=INK,
        spaceBefore=10,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Body2",
        fontName="Helvetica",
        fontSize=9.6,
        leading=14.5,
        textColor=INK,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Bullet2",
        fontName="Helvetica",
        fontSize=9.6,
        leading=14,
        textColor=INK,
        leftIndent=14,
        bulletIndent=4,
        spaceAfter=3,
    )
)
styles.add(
    ParagraphStyle(
        name="Note2",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=MUTED,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Cell",
        fontName="Helvetica",
        fontSize=8.4,
        leading=11.5,
        textColor=INK,
    )
)
styles.add(
    ParagraphStyle(
        name="CellHead",
        fontName="Helvetica-Bold",
        fontSize=8.4,
        leading=11.5,
        textColor=colors.white,
    )
)
styles.add(
    ParagraphStyle(
        name="TOC",
        fontName="Helvetica",
        fontSize=10,
        leading=17,
        textColor=INK,
    )
)
styles.add(
    ParagraphStyle(
        name="Center",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
)


def p(text: str, style: str = "Body2") -> Paragraph:
    return Paragraph(text, styles[style])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"&bull; {item}", styles["Bullet2"]) for item in items]


def table(headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> Table:
    data = [[Paragraph(cell, styles["CellHead"]) for cell in headers]]
    data += [[Paragraph(str(cell), styles["Cell"]) for cell in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def callout(title: str, body: str, tone: str = "brand") -> Table:
    color = BRAND if tone == "brand" else AMBER if tone == "warn" else RED
    box = Table(
        [[Paragraph(f"<b>{title}</b><br/>{body}", styles["Cell"])]],
        colWidths=[170 * mm],
        hAlign="LEFT",
    )
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 16 * mm, 190 * mm, 16 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(20 * mm, 11 * mm, "NEXORA - Manual del sistema")
    canvas.drawRightString(190 * mm, 11 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BRAND)
    canvas.rect(0, A4[1] - 46 * mm, A4[0], 46 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(20 * mm, A4[1] - 26 * mm, "NEXORA")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(20 * mm, A4[1] - 33 * mm, "Auditoria inteligente de compras y precios B2B")
    canvas.restoreState()
    footer(canvas, doc)


story: list = []

# ── Portada ──────────────────────────────────────────────────────────────────
story += [
    Spacer(1, 60 * mm),
    p("Manual completo del sistema", "CoverSub"),
    p("NEXORA", "CoverTitle"),
    p(
        "Plataforma SaaS para auditar compras, controlar precios de proveedores y "
        "convertir datos dispersos en ahorro medible.",
        "CoverSub",
    ),
    Spacer(1, 8 * mm),
    callout(
        "Que encontraras en este manual",
        "Vision de negocio, arquitectura tecnica, puesta en marcha, guia de cada modulo, "
        "roles y permisos, IA y resiliencia, integraciones, planes, guion de venta, "
        "operacion y checklist de QA para llevar el sistema a produccion.",
    ),
    Spacer(1, 10 * mm),
    p(f"Version del documento: {date.today().isoformat()}", "CoverMeta"),
    p("Destinatarios: fundadores, equipo comercial, soporte, implementadores y administradores.", "CoverMeta"),
    p("Clasificacion: interno / uso comercial.", "CoverMeta"),
    PageBreak(),
]

# ── Indice ───────────────────────────────────────────────────────────────────
story += [p("Contenido", "H1")]
toc = [
    "1. Resumen ejecutivo",
    "2. Propuesta de valor y segmentos",
    "3. Arquitectura y stack tecnologico",
    "4. Puesta en marcha y despliegue",
    "5. Variables de entorno",
    "6. Roles y permisos",
    "7. Mapa de modulos",
    "8. Modulo Inicio (Resumen del dia)",
    "9. Modulo Inteligencia (Analitica, Oportunidades, Pronostico, Aprobacion)",
    "10. Modulo Compras (Documentos, Precios, Excepciones, Aprobaciones, Proveedores, Catalogo)",
    "11. Modulo Integraciones (ChileCompra, SII, ERP, Google, Backups)",
    "12. Modulo Administracion y Plataforma",
    "13. Flujos operativos clave",
    "14. Inteligencia artificial y manejo de errores",
    "15. Seguridad, auditoria y multi-tenant",
    "16. Planes y precios",
    "17. Guion de venta y objeciones",
    "18. Operacion, monitoreo y soporte",
    "19. QA y checklist de operatividad",
    "20. Brechas conocidas y proximos pasos",
    "21. Glosario",
]
for item in toc:
    story.append(p(item, "TOC"))
story.append(PageBreak())

# ── 1. Resumen ejecutivo ─────────────────────────────────────────────────────
story += [p("1. Resumen ejecutivo", "H1")]
story += [
    p(
        "NEXORA es una plataforma SaaS que recibe cotizaciones, facturas y listas de precios en "
        "PDF, Excel, CSV o imagenes, extrae la informacion con inteligencia artificial y la "
        "convierte en una base de precios normalizada y comparable. Sobre esa base detecta "
        "sobreprecios, alzas anomalas, unidades inconsistentes y totales que no cuadran, y "
        "entrega analitica ejecutiva, oportunidades de ahorro, pronostico de compras y "
        "aprobacion inteligente.",
    ),
    p(
        "El problema que resuelve es concreto: las areas de compras trabajan con documentos "
        "heterogeneos, comparan precios a mano y descubren los sobreprecios meses despues. "
        "NEXORA automatiza la captura, normaliza unidades y precios, y pone la evidencia frente "
        "al decisor en el momento de comprar.",
    ),
    p("Resultados que persigue el cliente:", "H3"),
]
story += bullets(
    [
        "Ahorro medible: detecta productos pagados por sobre su mediana historica y estima el ahorro potencial.",
        "Menos trabajo manual: extraccion automatica y normalizacion de unidades por documento.",
        "Control y trazabilidad: bandeja de excepciones, aprobaciones y auditoria de cada accion.",
        "Decisiones con datos: indice de precios, gasto mensual, tendencias y pronostico.",
        "Gobierno: roles, SSO, white-label, backups y retencion de auditoria.",
    ]
)
story += [
    Spacer(1, 4 * mm),
    callout(
        "Estado actual del producto",
        "Modulos de valor agregado implementados (Analitica, Oportunidades, Pronostico y "
        "Aprobacion inteligente), asistente con IA y guias por modulo, correccion de cache del "
        "service worker y resiliencia ante errores transitorios del proveedor de IA. "
        "Pendiente: redeploy en Render y validacion de las consultas nuevas contra la base de datos.",
        "warn",
    ),
    PageBreak(),
]

# ── 2. Propuesta de valor ────────────────────────────────────────────────────
story += [p("2. Propuesta de valor y segmentos", "H1")]
story += [
    p(
        "NEXORA se posiciona como el control de precios de compra que se instala en semanas, no "
        "en meses, y que demuestra ahorro con datos. No reemplaza al ERP: se conecta y lo alimenta "
        "con informacion limpia y auditada.",
    ),
    p("Pilares de valor", "H2"),
]
story += bullets(
    [
        "<b>Captura sin friccion:</b> el usuario sube el documento tal como lo recibe; la IA hace el resto.",
        "<b>Comparabilidad real:</b> normalizacion de unidades (litros, kilos, cajas) y precios unitarios.",
        "<b>Deteccion proactiva:</b> alzas sobre umbral, baja confianza de extraccion y totales inconsistentes.",
        "<b>Ahorro demostrable:</b> diferencia contra mediana historica y mejor precio registrado.",
        "<b>Operacion gobernada:</b> aprobaciones con roles, auditoria y reportes ejecutivos.",
    ]
)
story += [
    p("Segmentos objetivo", "H2"),
    table(
        ["Segmento", "Dolor principal", "Como ayuda NEXORA"],
        [
            ["Distribuidores industriales", "Multiples proveedores, unidades y listas de precios cambiantes.",
             "Historico normalizado y oportunidades de ahorro por producto."],
            ["Constructoras y ferreterias", "Compras dispersas y sobreprecios no detectados.",
             "Alertas de alza y aprobacion con evidencia."],
            ["Retail B2B", "Margen presionado por costo de mercaderia.",
             "Catalogo con margen y comparacion contra mediana."],
            ["Pymes y areas de compras", "Procesos manuales en planillas.",
             "Extraccion automatica, excepciones y reportes ejecutivos."],
        ],
        [42 * mm, 62 * mm, 66 * mm],
    ),
    Spacer(1, 4 * mm),
    p(
        "Diferenciadores frente a alternativas: enfoque en documentos reales latinoamericanos, "
        "auditoria con intervencion humana (HITL), IA multi-proveedor y posibilidad de white-label "
        "para revender el servicio.",
    ),
    PageBreak(),
]

# ── 3. Arquitectura ──────────────────────────────────────────────────────────
story += [p("3. Arquitectura y stack tecnologico", "H1")]
story += [
    p(
        "La aplicacion es un monolito modular: backend FastAPI que sirve la API y el frontend "
        "compilado, base de datos PostgreSQL (Supabase) y almacenamiento de documentos. Se "
        "despliega como contenedor Docker en Render.",
    ),
    table(
        ["Capa", "Tecnologia", "Responsabilidad"],
        [
            ["Frontend", "React + Vite", "SPA con navegacion por modulos, graficos, tablas y asistente."],
            ["Backend", "FastAPI + Pydantic", "API REST, autenticacion, validacion, trabajos en segundo plano."],
            ["Base de datos", "PostgreSQL / Supabase", "Multi-tenant, documentos, items, excepciones, auditoria."],
            ["IA", "Gemini / OpenAI / Anthropic", "Extraccion estructurada con salida validada por esquema."],
            ["Archivos", "Supabase Storage o disco local", "Almacenamiento de documentos originales."],
            ["Despliegue", "Docker + Render", "Contenedor unico con healthcheck y auto-deploy."],
            ["PWA", "Service worker", "Cache de assets y soporte offline basico."],
        ],
        [28 * mm, 48 * mm, 94 * mm],
    ),
    p("Estructura de carpetas relevante", "H2"),
    table(
        ["Ruta", "Contenido"],
        [
            ["src/main.py", "Aplicacion FastAPI, SPAStaticFiles, cache headers y healthcheck."],
            ["src/api/routes/", "Endpoints por dominio: auth, documents, items, insights, assistant, enterprise."],
            ["src/services/", "Logica de negocio: documentos, auditoria, excepciones, asistente, billing."],
            ["src/db/repositories/", "Consultas SQL y acceso a datos por entidad."],
            ["src/parsers/", "Extractores, normalizacion de precios/unidades y proveedores LLM."],
            ["client/src/pages/", "Paginas de cada modulo."],
            ["client/src/components/", "Layout, tablas, graficos, guias y asistente."],
            ["database/migrations/", "Migraciones SQL versionadas (002 a 008 aplicadas)."],
            ["tests/ y e2e/", "Pruebas de backend y Playwright (requieren entorno)."],
        ],
        [55 * mm, 115 * mm],
    ),
    p("Modelo multi-tenant", "H2"),
    p(
        "Cada usuario pertenece a una organizacion. Todas las consultas relevantes filtran por "
        "organization_id, y los roles determinan que acciones puede ejecutar. El super "
        "administrador accede a una vista de plataforma para gestionar organizaciones y auditar.",
    ),
    PageBreak(),
]

# ── 4. Puesta en marcha ──────────────────────────────────────────────────────
story += [p("4. Puesta en marcha y despliegue", "H1")]
story += [p("Requisitos", "H2")]
story += bullets(
    [
        "Python 3.12 y Node.js 20 o superior.",
        "PostgreSQL 15 o superior (o proyecto Supabase).",
        "Clave de al menos un proveedor de IA (Gemini, OpenAI o Anthropic).",
        "Docker para despliegue en Render o cualquier plataforma de contenedores.",
    ]
)
story += [p("Ejecucion local", "H2")]
story += [
    p("1. Crear y activar el entorno virtual, e instalar dependencias:"),
    p("py -3 -m venv .venv / .venv\\Scripts\\activate / pip install -r requirements.txt", "Note2"),
    p("2. Copiar .env.example a .env y completar las variables."),
    p("3. Aplicar migraciones en la base de datos (002 a 008)."),
    p("4. Compilar el frontend: npm install y npm run build dentro de client."),
    p("5. Iniciar el backend: uvicorn src.main:app --reload --port 8000."),
    p("6. Verificar salud en http://localhost:8000/health."),
    p("Despliegue en Render", "H2"),
]
story += bullets(
    [
        "Servicio web tipo Docker, healthcheck en /health y auto-deploy desde la rama main.",
        "Cargar las variables de entorno del servicio (base de datos, JWT, IA, storage, Stripe).",
        "Aplicar migraciones antes del primer arranque o desde el job de release.",
        "Tras desplegar, verificar healthcheck, login, carga de un documento y modulos de Inteligencia.",
        "Si hay usuarios con service worker antiguo, el nuevo SW fuerza recarga y purga caches.",
    ]
)
story += [
    Spacer(1, 3 * mm),
    callout(
        "Checklist minimo de arranque",
        "Base de datos accesible, migraciones aplicadas, frontend compilado, proveedor de IA con "
        "cuota disponible, variables completas y healthcheck en verde.",
    ),
    PageBreak(),
]

# ── 5. Variables de entorno ──────────────────────────────────────────────────
story += [p("5. Variables de entorno", "H1")]
story += [
    p(
        "Las variables se definen en .env para desarrollo y en el panel de Render para produccion. "
        "Nunca se versionan claves reales.",
    ),
    table(
        ["Variable", "Proposito", "Ejemplo / nota"],
        [
            ["DATABASE_URL", "Conexion PostgreSQL.", "postgresql://usuario:clave@host:5432/nexora"],
            ["JWT_SECRET", "Firma de tokens de sesion.", "Cadena larga y aleatoria."],
            ["APP_ENV", "Entorno de ejecucion.", "development / production"],
            ["CORS_ORIGINS", "Origenes permitidos.", "https://tu-dominio.com"],
            ["LLM_PROVIDER", "Proveedor principal de IA.", "gemini / openai / anthropic"],
            ["LLM_PROVIDER_ORDER", "Orden de intento y fallback.", "gemini,openai,anthropic"],
            ["GEMINI_API_KEY", "Credencial Gemini.", "Obligatoria si se usa Gemini."],
            ["OPENAI_API_KEY", "Credencial OpenAI.", "Obligatoria si se usa OpenAI."],
            ["ANTHROPIC_API_KEY", "Credencial Anthropic.", "Obligatoria si se usa Anthropic."],
            ["SUPABASE_URL", "Endpoint del proyecto Supabase.", "https://xxx.supabase.co"],
            ["SUPABASE_SERVICE_KEY", "Clave de servicio para storage.", "Mantener en secreto."],
            ["STRIPE_SECRET_KEY", "Cobros y suscripciones.", "Modo test en desarrollo."],
            ["DEFAULT_PRICE_SPIKE_THRESHOLD_PCT", "Umbral de alerta por alza.", "10"],
        ],
        [56 * mm, 62 * mm, 52 * mm],
    ),
    PageBreak(),
]

# ── 6. Roles ─────────────────────────────────────────────────────────────────
story += [p("6. Roles y permisos", "H1")]
story += [
    p(
        "Los roles separan operacion, aprobacion y administracion. El backend valida permisos en "
        "cada endpoint; el frontend oculta acciones no permitidas.",
    ),
    table(
        ["Rol", "Puede hacer", "Restricciones"],
        [
            ["owner", "Todo, incluido equipo, planes, integraciones y white-label.",
             "Puede transferir o eliminar la organizacion."],
            ["admin", "Gestionar equipo, configuracion, integraciones y aprobaciones.",
             "No elimina la organizacion."],
            ["analyst", "Subir documentos, revisar excepciones, analizar y aprobar segun politica.",
             "No gestiona equipo ni facturacion."],
            ["user", "Subir documentos y operar sus propios registros.",
             "No administra ni aprueba compras globales."],
            ["viewer / auditor", "Consultar dashboards, precios y reportes.",
             "No modifica datos."],
            ["super_admin", "Vista de plataforma, organizaciones y auditoria global.",
             "Fuera del tenant; uso interno."],
        ],
        [32 * mm, 84 * mm, 54 * mm],
    ),
    PageBreak(),
]

# ── 7. Mapa de modulos ───────────────────────────────────────────────────────
story += [p("7. Mapa de modulos", "H1")]
story += [
    table(
        ["Seccion del menu", "Modulos", "Uso principal"],
        [
            ["Inicio", "Resumen del dia", "KPIs, carga rapida, alertas y documentos recientes."],
            ["Inteligencia", "Analitica, Oportunidades, Pronostico, Aprobacion inteligente",
             "Decisiones ejecutivas, ahorro y automatizacion."],
            ["Compras", "Documentos, Precios auditados, Excepciones, Aprobaciones, Proveedores, Catalogo",
             "Operacion diaria de compras y control."],
            ["Integraciones", "ChileCompra / SII / ERP, Seguridad y marca, Backups",
             "Conectividad, gobierno y continuidad."],
            ["Administracion", "Equipo, Planes y precios, Configuracion, Mi perfil",
             "Gestion de la organizacion y la cuenta."],
            ["Plataforma", "Usuarios y auditoria", "Solo super administrador."],
        ],
        [32 * mm, 72 * mm, 66 * mm],
    ),
    Spacer(1, 3 * mm),
    p(
        "Cada modulo incluye un boton de ayuda (?) en la barra superior con una guia de cuatro "
        "pasos, buenas practicas y enlaces a modulos relacionados.",
    ),
    PageBreak(),
]

# ── 8. Inicio ────────────────────────────────────────────────────────────────
story += [p("8. Modulo Inicio (Resumen del dia)", "H1")]
story += [
    p(
        "Punto de partida del usuario. Concentra indicadores de compra, ahorro estimado, "
        "documentos pendientes y excepciones que requieren atencion.",
    ),
    p("Como operarlo", "H2"),
]
story += bullets(
    [
        "Revisa los indicadores del mes: gasto, ahorro, documentos y excepciones.",
        "Sube un documento nuevo desde la tarjeta de carga si tienes permisos.",
        "Haz clic en una alerta para ir directo a la bandeja correspondiente.",
        "Usa los accesos rapidos para abrir precios, excepciones o aprobaciones.",
    ]
)
story += [
    p("Buenas practicas", "H2"),
    p(
        "Si no hay datos, carga la primera cotizacion para activar el analisis. El ahorro se "
        "calcula contra la mediana historica, por lo que requiere al menos dos registros "
        "comparables del mismo producto.",
    ),
    PageBreak(),
]

# ── 9. Inteligencia ──────────────────────────────────────────────────────────
story += [p("9. Modulo Inteligencia", "H1")]
story += [
    p(
        "Es el diferenciador de NEXORA: transforma el historico auditado en decisiones de "
        "compra. Se compone de cuatro vistas complementarias.",
    )
]
story += [p("9.1 Analitica ejecutiva", "H2")]
story += [
    p(
        "Vista de direccion con indice de precios, gasto mensual, mayores alzas, ahorro estimado "
        "y estado de aprobaciones. Permite comparar periodos de 6 y 12 meses.",
    )
]
story += bullets(
    [
        "Indice sobre 100 implica que los precios subieron respecto al inicio del periodo.",
        "Si el indice sube pero el gasto baja, probablemente cayo el volumen comprado.",
        "Usa las mayores alzas para priorizar negociaciones con proveedores.",
    ]
)
story += [p("9.2 Oportunidades de ahorro", "H2")]
story += [
    p(
        "Compara el precio actual contra la mediana historica y el mejor precio registrado. "
        "Muestra ranking de proveedores y ahorro potencial por producto.",
    )
]
story += bullets(
    [
        "Ajusta la ventana de analisis (30 a 365 dias) y el sobreprecio minimo.",
        "Un sobreprecio superior al 30% justifica revision inmediata.",
        "Necesita al menos dos registros del producto en documentos distintos.",
    ]
)
story += [p("9.3 Pronostico de compras", "H2")]
story += [
    p(
        "Proyecta consumo y gasto del proximo periodo usando historial y tendencia reciente. "
        "Sirve para presupuestar y adelantar compras de productos al alza.",
    )
]
story += bullets(
    [
        "Requiere al menos dos meses con datos.",
        "La tendencia compara los ultimos tres meses contra los tres anteriores.",
        "Usa la cantidad proyectada como referencia para ordenes de compra.",
    ]
)
story += [p("9.4 Aprobacion inteligente", "H2")]
story += [
    p(
        "Auto-aprueba items con confianza de extraccion alta y sin excepciones criticas; el resto "
        "permanece en revision manual. Cada decision queda auditada.",
    )
]
story += bullets(
    [
        "Define la confianza minima (recomendado 90% al inicio).",
        "Selecciona items puntuales o aprueba todos los elegibles.",
        "Los items con alertas de severidad alta nunca se auto-aprueban.",
    ]
)
story += [PageBreak()]

# ── 10. Compras ──────────────────────────────────────────────────────────────
story += [p("10. Modulo Compras", "H1")]
modules = [
    (
        "10.1 Documentos",
        "Corazon operativo. Recibe cotizaciones, facturas y listas de precios; la IA extrae "
        "proveedor, productos, cantidades, unidades y precios. Detecta duplicados por hash y "
        "permite re-procesar.",
        [
            "Subir PDF, Excel, CSV o imagen desde la tarjeta de carga.",
            "Esperar el cambio de estado de En cola a Procesado.",
            "Abrir el detalle para revisar items, confianza y excepciones.",
            "Re-procesar si hubo un error transitorio del proveedor de IA.",
        ],
    ),
    (
        "10.2 Precios auditados",
        "Historico normalizado de precios y unidades para comparar entre documentos y proveedores.",
        [
            "Filtrar por proveedor, SKU, descripcion, estado o fechas.",
            "Revisar precio original, unidad base y precio normalizado.",
            "Identificar items auto-aprobados y pendientes.",
            "Exportar el listado para contabilidad o compras.",
        ],
    ),
    (
        "10.3 Excepciones",
        "Bandeja de revision humana (HITL) con alzas de precio, baja confianza, unidades "
        "inconsistentes y totales que no cuadran.",
        [
            "Revisar por severidad y antiguedad.",
            "Abrir la excepcion y analizar la evidencia.",
            "Resolver si el dato es correcto o requiere correccion.",
            "Convertir alzas aprobadas en ahorro capturado.",
        ],
    ),
    (
        "10.4 Aprobaciones",
        "Gobierno de solicitudes de compra con monto, proveedor, prioridad y decisiones trazables.",
        [
            "Crear solicitud con titulo, monto, moneda y prioridad.",
            "Asociar proveedor y notas o centro de costo.",
            "Aprobar o rechazar segun rol.",
            "Enviar al ERP o notificar por Slack.",
        ],
    ),
    (
        "10.5 Proveedores",
        "Base de proveedores para asociar documentos, normalizar nombres y validar datos "
        "tributarios.",
        [
            "Crear proveedor con nombre, RUT y email.",
            "Editar datos de contacto.",
            "Validar RUT en SII o buscar en ChileCompra.",
            "Relacionar documentos y precios para scorecards.",
        ],
    ),
    (
        "10.6 Catalogo de precios",
        "Catalogo propio con costo, precio de venta y margen calculado.",
        [
            "Crear item con SKU, nombre, unidad y precios.",
            "Verificar el margen calculado automaticamente.",
            "Buscar y activar o desactivar productos.",
            "Actualizar precios cuando cambien las condiciones.",
        ],
    ),
]
for title, purpose, steps in modules:
    story += [p(title, "H2"), p(purpose)]
    story += bullets(steps)
story += [PageBreak()]

# ── 11. Integraciones ────────────────────────────────────────────────────────
story += [p("11. Modulo Integraciones", "H1")]
story += [
    table(
        ["Integracion", "Funcion", "Nota operativa"],
        [
            ["ChileCompra", "Busqueda de precios de referencia y proveedores publicos.",
             "Requiere nombre de producto o proveedor."],
            ["SII", "Validacion de RUT y obtencion de facturas electronicas.",
             "Validar formato antes de guardar proveedor."],
            ["ERP", "Exportacion de proveedores y aprobaciones; importacion de facturas CSV.",
             "Revisar mapeo de columnas del ERP."],
            ["Google Workspace", "Guardar documentos en Drive e inicio de sesion con Google.",
             "Requiere cuenta corporativa y permisos."],
            ["Backups", "Respaldo de informacion de la organizacion.",
             "El respaldo completo requiere pg_dump en el servidor."],
            ["Seguridad y marca", "SSO, retencion de auditoria, white-label y alertas.",
             "Requiere rol owner o admin."],
        ],
        [38 * mm, 74 * mm, 58 * mm],
    ),
    Spacer(1, 3 * mm),
    p(
        "Las integraciones se prueban con Sincronizar. Si un endpoint falla, revisar credenciales, "
        "URL y conectividad antes de escalar a soporte.",
    ),
    PageBreak(),
]

# ── 12. Administracion ───────────────────────────────────────────────────────
story += [p("12. Modulo Administracion y Plataforma", "H1")]
story += [
    p("12.1 Equipo", "H2"),
    p(
        "Invita usuarios por email y asigna roles. Revisa invitaciones pendientes y desactiva "
        "accesos cuando corresponda. Manten al menos dos administradores activos.",
    ),
    p("12.2 Planes y precios", "H2"),
    p(
        "Muestra el plan actual, consumo de documentos del periodo y comparativa de planes. "
        "Actualiza el plan cuando te acerques al limite mensual.",
    ),
    p("12.3 Configuracion", "H2"),
    p(
        "Define moneda por defecto, umbral de alza de precio y confianza minima de extraccion. "
        "Un umbral muy bajo genera demasiadas excepciones; la confianza recomendada es 0,75.",
    ),
    p("12.4 Mi perfil", "H2"),
    p("Actualiza datos personales, contrasena y preferencias de la cuenta."),
    p("12.5 Usuarios y auditoria (Plataforma)", "H2"),
    p(
        "Vista de super administrador para buscar organizaciones y usuarios, revisar metricas "
        "globales y auditar acciones sensibles por organizacion.",
    ),
    PageBreak(),
]

# ── 13. Flujos ───────────────────────────────────────────────────────────────
story += [p("13. Flujos operativos clave", "H1")]
story += [
    p("Flujo de carga y extraccion", "H2"),
    p(
        "Usuario sube documento -> validacion de formato y cuota -> almacenamiento -> trabajo en "
        "segundo plano -> extraccion con IA -> normalizacion de unidades y precios -> deteccion "
        "de excepciones -> actualizacion de dashboard y precios auditados.",
    ),
    p("Flujo de auditoria y excepciones", "H2"),
    p(
        "Item extraido -> comparacion con historico -> si el alza supera el umbral o la confianza "
        "es baja se crea excepcion -> analista revisa evidencia -> resuelve o corrige -> el "
        "historico se actualiza y el ahorro se registra.",
    ),
    p("Flujo de aprobacion", "H2"),
    p(
        "Solicitud de compra -> seleccion de proveedor y monto -> aprobacion o rechazo segun rol -> "
        "registro de auditoria -> notificacion y, si corresponde, envio al ERP.",
    ),
    p("Flujo de inteligencia", "H2"),
    p(
        "Historico normalizado -> analitica, oportunidades y pronostico -> revision ejecutiva -> "
        "decision de negociacion o auto-aprobacion -> seguimiento del ahorro.",
    ),
    PageBreak(),
]

# ── 14. IA ───────────────────────────────────────────────────────────────────
story += [p("14. Inteligencia artificial y manejo de errores", "H1")]
story += [
    p(
        "La extraccion usa modelos con salida estructurada validada por Pydantic. El sistema "
        "soporta Gemini, OpenAI y Anthropic, con orden de intento configurable y fallback.",
    ),
    p("Resiliencia implementada", "H2"),
]
story += bullets(
    [
        "Reintentos con backoff exponencial ante errores transitorios (503, 429, timeouts, saturacion).",
        "Deteccion de marcadores como UNAVAILABLE o high demand para reintentar sin intervencion.",
        "Mensaje accionable cuando el proveedor esta saturado, en lugar de un error tecnico crudo.",
        "Fallback entre proveedores segun LLM_PROVIDER_ORDER.",
        "Asistente con IA y respaldo en base de conocimiento local si no hay cuota o proveedor.",
    ]
)
story += [
    callout(
        "Error 503 del proveedor de IA",
        "Significa saturacion temporal del proveedor, no un fallo de los datos del cliente. "
        "El sistema reintenta automaticamente y luego informa que se puede reintentar en unos "
        "minutos o cambiar de proveedor. No es necesario volver a subir el documento.",
        "warn",
    ),
    PageBreak(),
]

# ── 15. Seguridad ────────────────────────────────────────────────────────────
story += [p("15. Seguridad, auditoria y multi-tenant", "H1")]
story += bullets(
    [
        "Autenticacion con tokens de sesion y cookies; validacion de permisos por rol en backend.",
        "Aislamiento por organization_id en consultas y almacenamiento.",
        "Auditoria de acciones sensibles: aprobaciones, auto-aprobaciones, cambios de configuracion.",
        "SSO opcional con restriccion por dominio corporativo.",
        "Retencion de auditoria configurable y backups periodicos.",
        "Cifrado en transito (HTTPS) y cuidado de claves en variables de entorno, nunca en el repositorio.",
    ]
)
story += [
    Spacer(1, 3 * mm),
    p(
        "Recomendacion: revisar permisos de base de datos, rotar claves periodicamente y limitar "
        "el acceso al panel de plataforma a personal interno.",
    ),
    PageBreak(),
]

# ── 16. Planes ───────────────────────────────────────────────────────────────
story += [p("16. Planes y precios", "H1")]
story += [
    table(
        ["Plan", "Precio mensual", "Documentos", "Incluye"],
        [
            ["Free", "USD 0", "25", "Auditoria de precios, dashboard mensual, exportaciones basicas."],
            ["Pro", "USD 49", "500", "Equipo con roles, alertas de cuota, PDF y Excel, historial 6 meses."],
            ["Enterprise", "USD 199", "Ilimitados", "Multi-tenant, auditoria avanzada, exportaciones masivas, gestion centralizada."],
        ],
        [30 * mm, 34 * mm, 30 * mm, 76 * mm],
    ),
    Spacer(1, 3 * mm),
    p(
        "Los precios y limites se cargan desde la tabla plans y pueden ajustarse por contrato. "
        "La facturacion se integra con Stripe cuando esta configurado.",
    ),
    callout(
        "Estrategia comercial sugerida",
        "Entrar con Free o piloto pagado de 30 dias, demostrar ahorro con dos o tres documentos "
        "reales y escalar a Pro. Enterprise para multi-sucursal, white-label y SSO.",
    ),
    PageBreak(),
]

# ── 17. Guion de venta ───────────────────────────────────────────────────────
story += [p("17. Guion de venta y objeciones", "H1")]
story += [p("Estructura de una demo (20 minutos)", "H2")]
story += bullets(
    [
        "Problema: documentos dispersos y sobreprecios detectados tarde.",
        "Carga en vivo de una cotizacion real y extraccion automatica.",
        "Revision de precios normalizados y una excepcion de alza.",
        "Analitica ejecutiva y oportunidades de ahorro con monto estimado.",
        "Aprobacion inteligente y trazabilidad.",
        "Cierre: piloto con documentos del cliente y medicion de ahorro.",
    ]
)
story += [p("Objeciones frecuentes", "H2")]
story += [
    table(
        ["Objecion", "Respuesta"],
        [
            ["Ya tenemos ERP.", "NEXORA no reemplaza el ERP: limpia y audita la informacion de compras antes de cargarla."],
            ["Es mucho trabajo implementar.", "La carga es la misma que ya hacen; la extraccion y normalizacion son automaticas."],
            ["No confio en la IA.", "Hay revision humana, confianza por item y auditoria; la IA propone, el equipo decide."],
            ["Es caro.", "El plan se paga con un solo sobreprecio evitado; el ROI se mide con el ahorro detectado."],
            ["Nuestros documentos son distintos.", "Soportamos PDF, Excel, CSV e imagenes, con normalizacion de unidades."],
        ],
        [52 * mm, 118 * mm],
    ),
    PageBreak(),
]

# ── 18. Operacion ────────────────────────────────────────────────────────────
story += [p("18. Operacion, monitoreo y soporte", "H1")]
story += bullets(
    [
        "Healthcheck: GET /health debe responder correctamente tras cada despliegue.",
        "Logs del contenedor: revisar errores de extraccion, base de datos y proveedores de IA.",
        "Documentos atascados: usar re-procesar; si persiste, revisar cola y cuota.",
        "Errores 503 de IA: esperar reintentos automaticos y luego reintentar mas tarde.",
        "Service worker: si un usuario ve una version antigua, el nuevo SW purga caches y recarga.",
        "Backups: verificar que pg_dump exista en el servidor o usar exportaciones alternativas.",
        "Facturacion: revisar consumo de documentos y estado de suscripcion en Administracion.",
    ]
)
story += [
    p("Runbook rapido", "H2"),
    table(
        ["Sintoma", "Revision", "Accion"],
        [
            ["Pantalla en blanco o error MIME", "Service worker y /index.html", "Confirmar SW v3 y recargar; purgar cache."],
            ["500 en Inteligencia", "Logs SQL y percentile_cont", "Verificar cast a double precision y datos."],
            ["503 al procesar", "Proveedor de IA", "Esperar reintentos o cambiar LLM_PROVIDER_ORDER."],
            ["Documento en cola", "Worker y cuota", "Re-procesar o revisar limite del plan."],
            ["No aparecen oportunidades", "Historial insuficiente", "Cargar mas documentos comparables."],
        ],
        [42 * mm, 56 * mm, 72 * mm],
    ),
    PageBreak(),
]

# ── 19. QA ───────────────────────────────────────────────────────────────────
story += [p("19. QA y checklist de operatividad", "H1")]
story += [
    p(
        "Estado verificado durante esta iteracion. La compilacion de backend, el lint y las 92 "
        "pruebas unitarias pasaron; las consultas nuevas no se pudieron ejecutar contra PostgreSQL "
        "real porque el entorno local no tiene DATABASE_URL, por lo que su validacion es estatica.",
    ),
    table(
        ["Area", "Verificacion", "Estado"],
        [
            ["Backend", "Compilacion py_compile de modulos tocados", "OK"],
            ["Lint", "ruff en archivos modificados", "OK"],
            ["Pruebas", "pytest: 92 pruebas unitarias", "OK"],
            ["Frontend", "npm run build (476 modulos)", "OK"],
            ["Service worker", "Network-first, sin cache de index, fallback Response", "OK"],
            ["Insights", "Cast de percentile_cont y endpoints registrados", "OK estatico"],
            ["LLM", "Reintentos y mensajes ante 503", "OK"],
            ["Asistente", "Endpoint y fallback a base de conocimiento", "OK"],
            ["Guias", "Ayuda contextual en todos los modulos", "OK"],
            ["PDF", "Manual generado en la raiz", "OK"],
            ["Base de datos", "Consultas nuevas contra PostgreSQL real", "Pendiente"],
            ["E2E", "Suite Playwright en entorno desplegado", "Pendiente"],
        ],
        [34 * mm, 88 * mm, 48 * mm],
    ),
    PageBreak(),
]

# ── 20. Brechas ──────────────────────────────────────────────────────────────
story += [p("20. Brechas conocidas y proximos pasos", "H1")]
story += bullets(
    [
        "<b>Validacion en base real:</b> ejecutar /api/insights/overview, opportunities, forecast, analytics y approvals contra Supabase para confirmar resultados.",
        "<b>Redeploy:</b> publicar el service worker v3 y los modulos nuevos en Render.",
        "<b>Pruebas automatizadas:</b> los 92 tests actuales pasan; ampliar la suite con pruebas de insights y assistant.",
        "<b>E2E:</b> correr Playwright contra el entorno desplegado para login, carga y navegacion.",
        "<b>Cuota de IA:</b> monitorear errores 503 y evaluar un segundo proveedor configurado.",
        "<b>Rate limiting:</b> proteger /api/assistant/chat si se expone a muchos usuarios.",
        "<b>Backups:</b> confirmar pg_dump en el contenedor o definir exportacion administrada.",
        "<b>Observabilidad:</b> alertas sobre healthcheck, errores 5xx y latencia de extraccion.",
    ]
)
story += [
    Spacer(1, 3 * mm),
    callout(
        "Definicion de 100% operativo",
        "Todos los modulos responden sin errores 5xx, la extraccion funciona con al menos un "
        "proveedor de IA, la carga y aprobacion son trazables, el manual y las guias estan "
        "disponibles, y existe monitoreo y respaldo verificados.",
    ),
    PageBreak(),
]

# ── 21. Glosario ─────────────────────────────────────────────────────────────
story += [p("21. Glosario", "H1")]
glossary = [
    ["HITL", "Human in the loop: revision humana de casos dudosos."],
    ["Item", "Producto extraido de un documento con cantidad, unidad y precio."],
    ["Precio normalizado", "Precio unitario llevado a una unidad base comparable."],
    ["Mediana historica", "Valor central del historico de precios de un producto."],
    ["Oportunidad", "Producto cuyo precio actual supera su referencia historica."],
    ["Excepcion", "Hallazgo que requiere revision: alza, baja confianza o inconsistencia."],
    ["Auto-aprobacion", "Aprobacion automatica de items elegibles por confianza y ausencia de alertas."],
    ["Scorecard", "Ficha comparativa del desempeno de un proveedor."],
    ["White-label", "Personalizacion de marca para revender la plataforma."],
    ["Service worker", "Componente del navegador que gestiona cache y modo offline."],
]
story += [table(["Termino", "Definicion"], glossary, [40 * mm, 130 * mm])]
story += [
    Spacer(1, 12 * mm),
    p("NEXORA - Auditoria inteligente de compras y precios B2B", "Center"),
    p("Documento generado para uso interno y comercial.", "Center"),
]


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=24 * mm,
        bottomMargin=22 * mm,
        title="NEXORA - Manual del sistema",
        author="NEXORA",
        subject="Manual completo del sistema",
    )
    doc.build(story, onFirstPage=cover, onLaterPages=footer)
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    build()
