import { useEffect } from "react";
import UploadCard from "./UploadCard";
import { UploadIcon, XIcon } from "./Icons";

export default function UploadModal({ onClose, onUploaded }) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", handleKey);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.classList.remove("modal-open");
    };
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Subir documento"
      onMouseDown={() => onClose?.()}
    >
      <div className="modal upload-modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div className="upload-modal-heading">
            <span className="upload-modal-icon"><UploadIcon /></span>
            <div>
              <div className="topbar-eyebrow">Ingesta documental</div>
              <h2>Subir documento</h2>
            </div>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            <XIcon />
          </button>
        </div>
        <div className="modal-body upload-modal-body">
          <UploadCard onUploaded={onUploaded} />
        </div>
      </div>
    </div>
  );
}
