import { useEffect, useState } from "react";

const STORAGE_KEY = "nexora.banner.dismissed";

export default function AppBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(localStorage.getItem(STORAGE_KEY) !== "1");
  }, []);

  if (!visible) return null;

  return (
    <div className="app-banner" role="status">
      <div>
        <strong>NEXORA listo:</strong> sube documentos, revisa excepciones y controla tu cuota desde un solo lugar.
      </div>
      <button
        type="button"
        className="banner-close"
        onClick={() => {
          localStorage.setItem(STORAGE_KEY, "1");
          setVisible(false);
        }}
        aria-label="Cerrar aviso"
      >
        ×
      </button>
    </div>
  );
}
