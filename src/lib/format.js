export function formatMoney(value, currency = "CLP") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  try {
    return new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: currency || "CLP",
      maximumFractionDigits: currency === "CLP" ? 0 : 2,
    }).format(Number(value));
  } catch {
    return `${currency} ${Number(value).toLocaleString("es-CL")}`;
  }
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("es-CL", {
    maximumFractionDigits: digits,
  }).format(Number(value));
}

export function formatDate(value) {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatMonth(value) {
  if (!value) return "—";
  const match = /^(\d{4})-(\d{2})$/.exec(String(value));
  if (!match) return String(value);
  const date = new Date(Number(match[1]), Number(match[2]) - 1, 1);
  return new Intl.DateTimeFormat("es-CL", { month: "short" }).format(date).replace(".", "");
}

export function percent(value, digits = 0) {
  return `${formatNumber(value, digits)}%`;
}

const LABELS = {
  quote: "Cotización",
  invoice: "Factura",
  price_list: "Lista de precios",
  queued: "En cola",
  processing: "Procesando",
  processed: "Procesado",
  failed: "Fallido",
  pending: "Pendiente",
  approved: "Aprobado",
  rejected: "Rechazado",
  resolved: "Resuelto",
  auto_approved: "Auto-aprobado",
  low_confidence: "Baja confianza",
  price_spike: "Alza de precio",
  unit_mismatch: "Unidad inconsistente",
  price_mismatch: "Total inconsistente",
  missing_price: "Precio faltante",
  extraction_failed: "Extracción fallida",
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica",
  owner: "Administrador",
  admin: "Administrador",
  analyst: "Usuario",
  user: "Usuario",
  viewer: "Auditor",
  auditor: "Auditor",
  super_admin: "Super admin",
  active: "Activo",
  trialing: "Prueba",
  past_due: "Pago pendiente",
  canceled: "Cancelado",
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function labelize(value) {
  if (!value) return "—";
  return LABELS[value] || String(value).replaceAll("_", " ");
}

export function roleLabel(value) {
  return labelize(value);
}

export function initials(name) {
  return (name || "N")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
