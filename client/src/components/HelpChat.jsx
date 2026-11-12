import { useState } from "react";
import { HelpIcon, XIcon, ArrowRightIcon } from "./Icons";
import { api } from "../lib/api";

const HELP_RESPONSES = {
  hola: "¡Hola! Soy el asistente de NEXORA. Puedo guiarte por cualquier módulo: documentos, precios, oportunidades, pronóstico, aprobaciones, integraciones o configuración.",
  precios: "Los precios auditados están en Compras → Precios auditados. Puedes filtrar por proveedor, SKU o fecha y ver el precio normalizado para comparar unidades distintas.",
  rut: "Para validar un RUT chileno ve a Integraciones → SII y usa 'Validar RUT'. También puedes hacerlo desde la ficha de un proveedor.",
  sii: "El SII valida RUT y permite obtener facturas electrónicas. Lo encuentras en Integraciones → SII.",
  chilecompra: "ChileCompra entrega precios de referencia y proveedores del mercado público. Ve a Integraciones → ChileCompra → Buscar precios.",
  aprobacion: "Las solicitudes de compra se gestionan en Compras → Aprobaciones. Los administradores pueden aprobar o rechazar, y la decisión queda auditada.",
  aprobaciones: "Las solicitudes de compra se gestionan en Compras → Aprobaciones. Los administradores pueden aprobar o rechazar, y la decisión queda auditada.",
  "auto-aprob": "La Aprobación inteligente está en Inteligencia. Define una confianza mínima y NEXORA aprueba automáticamente los ítems sin alertas críticas.",
  excepciones: "La bandeja de Excepciones (Compras) reúne alzas de precio, baja confianza y totales inconsistentes para revisión humana.",
  documentos: "Sube cotizaciones, facturas o listas de precios en Compras → Documentos. La IA extrae productos, cantidades y precios, y el estado cambia a Procesado.",
  oportunidad: "Oportunidades de ahorro (Inteligencia) compara el precio actual contra la mediana histórica y el mejor precio registrado para estimar tu ahorro.",
  pronostico: "El Pronóstico de compras (Inteligencia) proyecta consumo y gasto futuro usando tu historial y la tendencia reciente.",
  analitica: "La Analítica ejecutiva (Inteligencia) muestra índice de precios, gasto mensual, mayores alzas, ahorro y estado de aprobaciones.",
  proveedor: "Gestiona proveedores en Compras → Proveedores: crea, edita, valida RUT y revisa su scorecard.",
  catalogo: "El Catálogo de precios (Compras) guarda tu costo, precio de venta y margen calculado por SKU.",
  erp: "La exportación a ERP está en Integraciones → ERP. Puedes exportar proveedores, aprobaciones e importar facturas en CSV.",
  backup: "Los backups están en Integraciones → Backups. Si el servidor no tiene pg_dump, exporta documentos individualmente.",
  drive: "Para guardar en Google Drive ve a Integraciones → Google Workspace y usa 'Guardar en Drive'.",
  white: "La marca blanca (logo, colores, nombre) se configura en Integraciones → Seguridad y marca.",
  sso: "SSO con Google Workspace se configura en Integraciones → Seguridad y marca; puedes restringir el acceso por dominio.",
  equipo: "Invita usuarios y asigna roles en Administración → Equipo. Solo owner/admin pueden gestionarlo.",
  plan: "Los planes Free, Pro y Enterprise están en Administración → Planes y precios, junto al consumo de documentos del período.",
  configuracion: "En Administración → Configuración ajustas moneda, umbral de alza de precio y confianza mínima de extracción.",
  ayuda: "Pregúntame por: documentos, precios, oportunidades, pronóstico, aprobaciones, excepciones, proveedores, integraciones, planes o configuración.",
  tutorial: "Cada módulo tiene un botón ? en la barra superior con una guía de 4 pasos y buenas prácticas. También puedes preguntarme aquí.",
  quienessomos: "NEXORA audita compras y precios B2B: extrae datos con IA, detecta sobreprecios y excepciones, y entrega analítica y ahorro medible.",
};

const SUGGESTIONS = [
  "¿Cómo subo un documento?",
  "¿Dónde veo oportunidades de ahorro?",
  "¿Cómo funciona la aprobación inteligente?",
  "¿Cómo invito a mi equipo?",
];

function getHelpResponse(text) {
  const lower = text.toLowerCase().trim();
  for (const [key, response] of Object.entries(HELP_RESPONSES)) {
    if (lower.includes(key)) {
      return response;
    }
  }
  return "Puedo ayudarte con documentos, precios, oportunidades, pronóstico, aprobaciones, excepciones, proveedores, integraciones, planes y configuración. Prueba con una de esas palabras o abre la guía ? del módulo que estás viendo.";
}

let messageId = 0;
function nextId() {
  messageId += 1;
  return `${Date.now()}-${messageId}`;
}

function HelpChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      text: "¡Hola! Soy el asistente de NEXORA. Pregúntame cómo usar cualquier módulo o escribe una palabra clave (precios, aprobaciones, pronóstico…).",
      sender: "bot",
      source: "guía",
    },
  ]);

  const sendMessage = async (rawText) => {
    const text = (rawText ?? input).trim();
    if (!text || sending) return;
    const history = messages
      .filter((message) => message.id !== "welcome")
      .slice(-6)
      .map((message) => ({ role: message.sender === "user" ? "user" : "assistant", content: message.text }));
    setMessages((prev) => [...prev, { id: nextId(), text, sender: "user" }]);
    setInput("");
    setSending(true);
    try {
      const data = await api("/api/assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message: text, history }),
      });
      const answer = (data?.answer || "").trim();
      if (data?.ai_available && answer) {
        setMessages((prev) => [...prev, { id: nextId(), text: answer, sender: "bot", source: "IA" }]);
      } else {
        setMessages((prev) => [...prev, { id: nextId(), text: getHelpResponse(text), sender: "bot", source: "guía" }]);
      }
    } catch {
      setMessages((prev) => [...prev, { id: nextId(), text: getHelpResponse(text), sender: "bot", source: "guía" }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="help-chat-container">
      {!open && (
        <button
          type="button"
          className="help-chat-fab fixed bottom-0 right-0 z-50"
          onClick={() => setOpen(true)}
          title="Asistente de ayuda"
          aria-label="Abrir asistente de ayuda"
        >
          <HelpIcon />
          <span className="help-badge">1</span>
        </button>
      )}
      {open && (
        <div className="help-chat-panel">
          <div className="help-chat-header">
            <div className="help-chat-title">
              <HelpIcon /> Asistencia NEXORA
            </div>
            <button type="button" className="help-chat-close" onClick={() => setOpen(false)}>
              <XIcon />
            </button>
          </div>
          <div className="help-chat-messages">
            {messages.map((m) => (
              <div key={m.id} className={`help-chat-message ${m.sender}`}>
                <div className="help-chat-bubble">
                  {m.text}
                  {m.sender === "bot" && m.source ? (
                    <span className={`help-chat-source ${m.source === "IA" ? "ai" : ""}`}>{m.source}</span>
                  ) : null}
                </div>
              </div>
            ))}
            {sending ? (
              <div className="help-chat-message bot">
                <div className="help-chat-bubble help-chat-typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            ) : null}
            {messages.length <= 1 ? (
              <div className="help-chat-suggestions">
                {SUGGESTIONS.map((suggestion) => (
                  <button key={suggestion} type="button" className="help-chip" onClick={() => sendMessage(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="help-chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Escribe tu consulta…"
              disabled={sending}
            />
            <button
              type="button"
              className="help-chat-send"
              onClick={() => sendMessage()}
              disabled={!input.trim() || sending}
            >
              <ArrowRightIcon />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default HelpChat;
