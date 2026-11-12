export const MODULE_HELP = {
  dashboard: {
    eyebrow: "Inicio",
    title: "Resumen del día",
    purpose:
      "Es el punto de partida: muestra cuánto compraste, cuánto ahorro se detectó, qué documentos y excepciones requieren tu atención.",
    steps: [
      "Revisa los indicadores de compra del mes, ahorro estimado y excepciones pendientes.",
      "Sube un documento nuevo desde la tarjeta de carga si tienes permisos de operación.",
      "Haz clic en una alerta para ir directo a la bandeja de excepciones o aprobaciones.",
      "Usa los accesos rápidos para abrir precios auditados, excepciones o aprobaciones.",
    ],
    tips: [
      "Si no ves datos, carga tu primera cotización o factura para activar el análisis.",
      "El ahorro se calcula comparando precios contra la mediana histórica.",
    ],
    related: [
      { id: "documents", label: "Subir documento" },
      { id: "exceptions", label: "Ver excepciones" },
      { id: "analytics", label: "Analítica ejecutiva" },
    ],
  },
  analytics: {
    eyebrow: "Inteligencia",
    title: "Analítica ejecutiva",
    purpose:
      "Entrega una vista de dirección: índice de precios, gasto mensual, mayores alzas y un resumen de ahorro y aprobaciones.",
    steps: [
      "Selecciona el período y la moneda que quieres analizar.",
      "Interpreta el índice de precios: sobre 100 significa que los precios subieron respecto al inicio del período.",
      "Revisa el gasto mensual y las mayores alzas para detectar productos críticos.",
      "Abre Oportunidades o Aprobación inteligente desde los accesos de cada tarjeta.",
    ],
    tips: [
      "Si el índice sube pero el gasto baja, probablemente compraste menos volumen.",
      "Compara períodos de 6 y 12 meses para distinguir estacionalidad de una tendencia real.",
    ],
    related: [
      { id: "opportunities", label: "Oportunidades de ahorro" },
      { id: "forecast", label: "Pronóstico de compras" },
      { id: "auto-approvals", label: "Aprobación inteligente" },
    ],
  },
  opportunities: {
    eyebrow: "Inteligencia",
    title: "Oportunidades de ahorro",
    purpose:
      "Detecta automáticamente productos pagados por sobre su mediana histórica y muestra cuánto podrías ahorrar comprando al mejor precio registrado.",
    steps: [
      "Ajusta la ventana de análisis (30 a 365 días) y el sobreprecio mínimo.",
      "Revisa el ranking de proveedores con mayor ahorro potencial.",
      "Analiza la tabla: precio actual, mediana histórica, mejor precio y diferencia porcentual.",
      "Usa el nombre del mejor proveedor para negociar o cambiar de fuente de compra.",
    ],
    tips: [
      "Necesitas al menos dos registros del mismo producto en documentos distintos para comparar.",
      "Un sobreprecio sobre 30% suele justificar una revisión inmediata.",
    ],
    related: [
      { id: "items", label: "Precios auditados" },
      { id: "suppliers", label: "Proveedores" },
      { id: "analytics", label: "Analítica ejecutiva" },
    ],
  },
  forecast: {
    eyebrow: "Inteligencia",
    title: "Pronóstico de compras",
    purpose:
      "Proyecta cuánto consumirás y gastarás el próximo período según tu historial y la tendencia reciente de cada producto.",
    steps: [
      "Elige cuántos meses de historial usar y el horizonte de proyección (1 a 3 meses).",
      "Revisa el gasto proyectado total para planificar presupuesto.",
      "Identifica productos al alza para adelantar compras o renegociar precios.",
      "Usa la cantidad proyectada como referencia para tus próximas órdenes de compra.",
    ],
    tips: [
      "Necesitas al menos dos meses con datos para generar un pronóstico confiable.",
      "La tendencia compara los últimos 3 meses contra los 3 anteriores.",
    ],
    related: [
      { id: "documents", label: "Documentos" },
      { id: "approvals", label: "Aprobaciones" },
      { id: "analytics", label: "Analítica ejecutiva" },
    ],
  },
  "auto-approvals": {
    eyebrow: "Inteligencia",
    title: "Aprobación inteligente",
    purpose:
      "Reduce trabajo manual: auto-aprueba ítems extraídos con alta confianza y sin alertas críticas, y deja el resto para revisión humana.",
    steps: [
      "Define la confianza mínima (por ejemplo 90%).",
      "Revisa cuántos ítems son auto-aprobables y cuánto monto representan.",
      "Selecciona ítems puntuales o usa el botón para aprobar todos los elegibles.",
      "Los ítems con baja confianza o excepciones críticas permanecen para revisión.",
    ],
    tips: [
      "Empieza con 90% o más para mantener control; baja el umbral cuando tengas más historial.",
      "Cada auto-aprobación queda registrada en la auditoría de la organización.",
    ],
    related: [
      { id: "exceptions", label: "Excepciones" },
      { id: "documents", label: "Documentos" },
      { id: "approvals", label: "Aprobaciones" },
    ],
  },
  documents: {
    eyebrow: "Compras",
    title: "Documentos",
    purpose:
      "Es el corazón de NEXORA: subes cotizaciones, facturas o listas de precios y la IA extrae productos, cantidades, unidades y precios.",
    steps: [
      "Usa la tarjeta de carga para subir PDF, Excel, CSV o imágenes.",
      "Espera el procesamiento; el estado cambia de En cola a Procesado.",
      "Abre el detalle para revisar ítems extraídos, confianza y excepciones.",
      "Si hubo un error, usa Re-procesar cuando el proveedor de IA esté disponible.",
    ],
    tips: [
      "Si aparece un error 503 del proveedor de IA, es saturación temporal: reintenta más tarde.",
      "Documentos duplicados se detectan por hash y no se procesan dos veces.",
    ],
    related: [
      { id: "exceptions", label: "Revisar excepciones" },
      { id: "items", label: "Precios auditados" },
      { id: "auto-approvals", label: "Aprobación inteligente" },
    ],
  },
  items: {
    eyebrow: "Compras",
    title: "Precios auditados",
    purpose:
      "Muestra el histórico normalizado de precios y unidades para comparar compras entre documentos y proveedores.",
    steps: [
      "Filtra por proveedor, SKU, descripción, estado o rango de fechas.",
      "Revisa el precio original, la unidad base y el precio normalizado.",
      "Identifica ítems auto-aprobados y pendientes de revisión.",
      "Exporta el listado si necesitas compartirlo con contabilidad o compras.",
    ],
    tips: [
      "El precio normalizado permite comparar litros, kilos o cajas en una misma base.",
      "Una confianza baja indica que conviene revisar el documento de origen.",
    ],
    related: [
      { id: "documents", label: "Documentos" },
      { id: "opportunities", label: "Oportunidades" },
      { id: "price-catalog", label: "Catálogo de precios" },
    ],
  },
  exceptions: {
    eyebrow: "Compras",
    title: "Excepciones",
    purpose:
      "Es la bandeja de revisión humana (HITL): concentra alzas de precio, baja confianza, unidades inconsistentes y totales que no cuadran.",
    steps: [
      "Revisa la lista ordenada por severidad y antigüedad.",
      "Abre cada excepción para ver la evidencia y el ítem afectado.",
      "Resuelve indicando si el dato es correcto o si requiere corrección.",
      "Convierte las alzas aprobadas en ahorro capturado para el reporte de ROI.",
    ],
    tips: [
      "Prioriza severidad alta o crítica antes de aprobar un documento.",
      "Resolver excepciones mejora la calidad del histórico y de los pronósticos.",
    ],
    related: [
      { id: "documents", label: "Documentos" },
      { id: "items", label: "Precios auditados" },
      { id: "auto-approvals", label: "Aprobación inteligente" },
    ],
  },
  approvals: {
    eyebrow: "Compras",
    title: "Aprobaciones",
    purpose:
      "Gobierna solicitudes de compra: registra monto, proveedor y prioridad, y controla quién aprueba o rechaza antes de emitir la orden.",
    steps: [
      "Crea una nueva solicitud con título, monto, moneda y prioridad.",
      "Asocia un proveedor y agrega notas o centro de costo.",
      "Los administradores aprueban o rechazan las solicitudes pendientes.",
      "Puedes enviar la aprobación al ERP o notificarla por Slack.",
    ],
    tips: [
      "Usa prioridad urgente solo para compras que no pueden esperar.",
      "Cada decisión queda registrada con usuario y fecha para auditoría.",
    ],
    related: [
      { id: "auto-approvals", label: "Aprobación inteligente" },
      { id: "suppliers", label: "Proveedores" },
      { id: "documents", label: "Documentos" },
    ],
  },
  suppliers: {
    eyebrow: "Compras",
    title: "Proveedores",
    purpose:
      "Administra la base de proveedores para asociar documentos, normalizar nombres y validar datos tributarios.",
    steps: [
      "Crea un proveedor con nombre, RUT y email.",
      "Edita los datos cuando cambie la información de contacto.",
      "Valida el RUT en el SII o búscalo en ChileCompra desde las acciones.",
      "Relaciona documentos y precios para mejorar los scorecards.",
    ],
    tips: [
      "Un RUT bien registrado evita duplicados entre documentos.",
      "Los proveedores con buen score aparecen mejor rankeados en Inteligencia.",
    ],
    related: [
      { id: "analytics", label: "Analítica" },
      { id: "opportunities", label: "Oportunidades" },
      { id: "integrations", label: "Integraciones" },
    ],
  },
  "price-catalog": {
    eyebrow: "Compras",
    title: "Catálogo de precios",
    purpose:
      "Mantén tu propio catálogo con precio de costo, precio de venta y margen calculado para controlar rentabilidad.",
    steps: [
      "Crea un ítem con SKU, nombre, unidad y precios.",
      "El margen se calcula automáticamente al guardar.",
      "Busca por SKU o nombre y activa o desactiva productos.",
      "Actualiza precios cuando cambien las condiciones con tus proveedores.",
    ],
    tips: [
      "Un margen negativo indica que el precio de venta está bajo el costo.",
      "Mantén SKUs consistentes con los documentos para cruzar información.",
    ],
    related: [
      { id: "items", label: "Precios auditados" },
      { id: "opportunities", label: "Oportunidades" },
      { id: "suppliers", label: "Proveedores" },
    ],
  },
  integrations: {
    eyebrow: "Integraciones",
    title: "ChileCompra / SII / ERP",
    purpose:
      "Conecta NEXORA con el ecosistema de compras: valida RUT en el SII, busca precios de referencia en ChileCompra y exporta a tu ERP.",
    steps: [
      "Elige el conector y ejecuta la acción disponible (validar RUT, buscar precios o exportar).",
      "Configura una integración con nombre y endpoint de prueba.",
      "Usa Sincronizar para verificar la conexión.",
      "Revisa los últimos estados y errores de conexión.",
    ],
    tips: [
      "Las acciones de SII y ChileCompra requieren RUT o nombre del proveedor.",
      "Si el endpoint de prueba falla, revisa credenciales y URL.",
    ],
    related: [
      { id: "suppliers", label: "Proveedores" },
      { id: "approvals", label: "Aprobaciones" },
      { id: "enterprise", label: "Seguridad y marca" },
    ],
  },
  enterprise: {
    eyebrow: "Integraciones",
    title: "Seguridad y marca",
    purpose:
      "Configura SSO, retención de auditoría, white-label, notificaciones push y la suite de ROI ejecutivo.",
    steps: [
      "Revisa la pestaña ROI ejecutivo para exportar reportes en PDF o Excel.",
      "Activa SSO por dominio y define la retención de auditoría.",
      "Personaliza logo, colores y dominio para white-label.",
      "Configura canales de alertas y notificaciones push.",
    ],
    tips: [
      "Requiere rol owner o admin.",
      "El white-label es un diferenciador clave para revender el sistema.",
    ],
    related: [
      { id: "analytics", label: "Analítica" },
      { id: "settings", label: "Configuración" },
      { id: "billing", label: "Planes y precios" },
    ],
  },
  backups: {
    eyebrow: "Integraciones",
    title: "Backups",
    purpose:
      "Respalda la información de la organización para recuperación ante incidentes.",
    steps: [
      "Genera un backup cuando necesites una copia de seguridad.",
      "Verifica el estado del respaldo generado.",
      "Exporta documentos individuales desde Documentos si el backup no está disponible.",
    ],
    tips: [
      "Programa respaldos periódicos según la política de tu empresa.",
      "El backup completo requiere que el servidor tenga pg_dump disponible.",
    ],
    related: [
      { id: "documents", label: "Documentos" },
      { id: "enterprise", label: "Seguridad y marca" },
    ],
  },
  team: {
    eyebrow: "Administración",
    title: "Equipo",
    purpose:
      "Invita usuarios y define roles para separar quién opera, aprueba y administra la organización.",
    steps: [
      "Invita por email y asigna un rol (owner, admin, analyst, user, viewer).",
      "Revisa invitaciones pendientes y reenvíalas si es necesario.",
      "Cambia roles cuando cambien las responsabilidades.",
      "Desactiva accesos de personas que ya no trabajan en compras.",
    ],
    tips: [
      "Solo owner/admin pueden gestionar el equipo.",
      "Mantén al menos dos administradores activos para continuidad.",
    ],
    related: [
      { id: "settings", label: "Configuración" },
      { id: "admin", label: "Usuarios y auditoría" },
    ],
  },
  billing: {
    eyebrow: "Administración",
    title: "Planes y precios",
    purpose:
      "Muestra los planes Free, Pro y Enterprise, el consumo de documentos y las opciones de actualización.",
    steps: [
      "Revisa tu plan actual y el porcentaje de documentos usados.",
      "Compara límites y funcionalidades de cada plan.",
      "Actualiza el plan cuando te acerques al límite mensual.",
      "Gestiona el período actual y la renovación.",
    ],
    tips: [
      "El plan Free sirve para probar con pocos documentos.",
      "Enterprise incluye white-label, SSO y soporte dedicado.",
    ],
    related: [
      { id: "settings", label: "Configuración" },
      { id: "enterprise", label: "Seguridad y marca" },
    ],
  },
  settings: {
    eyebrow: "Administración",
    title: "Configuración",
    purpose:
      "Ajusta parámetros de la organización: moneda, umbral de alza de precio y confianza mínima de extracción.",
    steps: [
      "Define la moneda por defecto para tus reportes.",
      "Ajusta el umbral de alza de precio que genera alertas.",
      "Configura la confianza mínima de extracción.",
      "Guarda los cambios y verifica su impacto en los próximos documentos.",
    ],
    tips: [
      "Un umbral muy bajo genera demasiadas excepciones.",
      "La confianza mínima por defecto recomendada es 0,75.",
    ],
    related: [
      { id: "exceptions", label: "Excepciones" },
      { id: "billing", label: "Planes" },
    ],
  },
  profile: {
    eyebrow: "Administración",
    title: "Mi perfil",
    purpose:
      "Actualiza tus datos personales, contraseña y preferencias de la cuenta.",
    steps: [
      "Revisa tu nombre, email y rol.",
      "Cambia tu contraseña cuando sea necesario.",
      "Verifica el estado de tu email.",
    ],
    tips: [
      "Usa una contraseña larga y única para tu cuenta.",
    ],
    related: [{ id: "team", label: "Equipo" }],
  },
  admin: {
    eyebrow: "Plataforma",
    title: "Usuarios y auditoría",
    purpose:
      "Vista de super administrador para gestionar organizaciones, usuarios globales y revisar la auditoría de la plataforma.",
    steps: [
      "Busca organizaciones o usuarios.",
      "Revisa métricas globales de uso y planes.",
      "Audita acciones sensibles por organización.",
    ],
    tips: ["Solo accesible para super administradores."],
    related: [{ id: "team", label: "Equipo" }],
  },
};

export function getModuleHelp(view) {
  return MODULE_HELP[view] || null;
}
