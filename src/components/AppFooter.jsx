import { useEffect, useState } from "react";

import { api } from "../lib/api";

export default function AppFooter() {
  const [version, setVersion] = useState("cargando...");

  useEffect(() => {
    let active = true;
    api("/version")
      .then((data) => {
        if (!active) return;
        const commit = data?.commit ? ` · ${String(data.commit).slice(0, 7)}` : "";
        setVersion(`${data?.version || "0.1.0"}${commit}`);
      })
      .catch(() => {
        if (active) setVersion("0.1.0");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <footer className="app-footer">
      <div className="footer-brand">
        <span className="footer-mark">N</span>
        <div>
          <strong>NEXORA</strong>
          <small>Compras auditadas con trazabilidad</small>
        </div>
      </div>
      <nav className="footer-links" aria-label="Ayuda y recursos">
        <a href="#documentos">Documentos</a>
        <a href="#excepciones">Excepciones</a>
        <a href="#facturacion">Facturación</a>
        <a href="#perfil">Perfil</a>
      </nav>
      <div className="footer-meta">
        <span>v{version}</span>
        <span>© {new Date().getFullYear()} NEXORA</span>
      </div>
    </footer>
  );
}
