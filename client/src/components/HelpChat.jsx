import React, { useState } from "react";
import { HelpIcon, XIcon, ArrowRightIcon } from "./Icons";

const HELP_RESPONSES = {
  hola: "¡Hola! Soy el asistente de NEXORA. Puedo ayudarte con: buscar precios en ChileCompra, validar RUT en SII, crear aprobaciones de compra, exportar a tu ERP, hacer backups y configurar tu marca blanca.",
  "hola!": "¡Hola! Soy el asistente de NEXORA. ¿En qué puedo ayudarte hoy?",
  "buenos dias": "¡Buenos días! ¿En qué puedo ayudarte? Puedo guiarte en el uso de NEXORA.",
  "buenas tardes": "¡Buenas tardes! ¿En qué puedo ayudarte?",
  precios: "Para buscar precios en ChileCompra, ve a la sección Integraciones y usa 'Buscar precios'. Puedes filtrar por producto o ver los mejores precios (más baratos).",
  rut: "Para validar un RUT chileno, ve a la sección Integraciones → SII y usa 'Validar RUT'. Ingresa el RUT y te diré si el formato es válido.",
  sii: "El SII te permite validar RUT de proveedores y obtener facturas electrónicas. Ve a Integraciones → SII para usarlo.",
  chilecompra: "ChileCompra te permite buscar precios de referencia del mercado público y proveedores registrados. Ve a Integraciones → ChileCompra.",
  aprobacion: "Para aprobar una compra, ve a la sección Aprobaciones. Allí puedes ver solicitudes pendientes y aprobarlas o rechazarlas.",
  aprobaciones: "Para aprobar una compra, ve a la sección Aprobaciones. Allí puedes ver solicitudes pendientes y aprobarlas o rechazarlas.",
  erp: "Para exportar a tu ERP, ve a Integraciones → ERP. Puedes exportar proveedores, enviar aprobaciones e importar facturas en archivos CSV listos para importar.",
  backup: "Para hacer un backup, ve a Integraciones → Backups. Nota: requiere que el servidor tenga pg_dump instalado. Si no está disponible, puedes exportar documentos individualmente desde Documentos.",
  drive: "Para guardar en Google Drive, ve a Integraciones → Google Workspace y usa 'Guardar en Drive'.",
  white: "Para configurar tu marca blanca (logo, colores, nombre), ve a Integraciones → Seguridad y marca (o Enterprise → White-label).",
  sso: "Para configurar SSO con Google Workspace, ve a Integraciones → Seguridad y marca. Allí puedes habilitar el inicio de sesión con Google y restringir el acceso por dominio.",
  ayuda: "Pregúntame sobre: precios, RUT, SII, ChileCompra, aprobaciones, ERP, backups, Drive, SSO o white-label. Prueba escribiendo una de esas palabras.",
  tutorial: "NEXORA tiene módulos de Documentos, Proveedores, Aprobaciones, Integraciones (ChileCompra, SII, ERP, Google Drive, Backups) y Configuración. Cada uno tiene acciones directas.",
  quienessomos: "NEXORA es una plataforma de auditoría de compras y precios para ferreterías y distribuidores industriales, ayudando a comparar precios, validar RUTs y gestionar documentos.",
};

function getHelpResponse(text) {
  const lower = text.toLowerCase().trim();
  for (const [key, response] of Object.entries(HELP_RESPONSES)) {
    if (lower.includes(key)) {
      return response;
    }
  }
  return "No entiendo tu consulta. Puedo ayudarte con: precios, RUT, SII, ChileCompra, aprobaciones, ERP, backups, Drive, SSO o white-label. Prueba escribiendo una de esas palabras.";
}

function HelpChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "¡Hola! Soy el asistente de NEXORA. ¿En qué puedo ayudarte hoy?",
      sender: "bot",
    },
  ]);

  const sendMessage = () => {
    if (!input.trim()) return;
    const userMsg = { id: Date.now(), text: input, sender: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    const botText = getHelpResponse(input);
    setMessages((prev) => [...prev, { id: Date.now() + 1, text: botText, sender: "bot" }]);
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
              <div
                key={m.id}
                className={`help-chat-message ${m.sender}`}
              >
                <div className="help-chat-bubble">{m.text}</div>
              </div>
            ))}
          </div>
          <div className="help-chat-input">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Escribe tu consulta…"
            />
            <button type="button" className="help-chat-send" onClick={sendMessage} disabled={!input.trim()}>
              <ArrowRightIcon />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default HelpChat;