import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { UploadIcon } from "./Icons";

const DOC_TYPES = [
  { value: "quote", label: "Cotización" },
  { value: "invoice", label: "Factura" },
  { value: "price_list", label: "Lista de precios" },
];

export default function UploadCard({ onUploaded }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [supplierName, setSupplierName] = useState("");
  const [docType, setDocType] = useState("quote");
  const [documentDate, setDocumentDate] = useState("");
  const [suppliers, setSuppliers] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api("/api/suppliers")
      .then((data) => setSuppliers(data.items || []))
      .catch(() => setSuppliers([]));
  }, []);

  function selectFile(nextFile) {
    setError("");
    setSuccess("");
    setFile(nextFile || null);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) selectFile(dropped);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      setError("Selecciona un archivo para continuar.");
      return;
    }

    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("doc_type", docType);
      if (supplierName.trim()) body.append("supplier_name", supplierName.trim());
      if (documentDate) body.append("document_date", documentDate);

      const data = await api("/api/documents/ingest", { method: "POST", body });
      setSuccess(
        data.duplicate
          ? "Este documento ya estaba cargado. Te mostramos el registro existente."
          : "Documento recibido. El procesamiento se ejecutará en segundo plano.",
      );
      setFile(null);
      setDocumentDate("");
      if (inputRef.current) inputRef.current.value = "";
      onUploaded?.(data.document);
    } catch (err) {
      setError(err.message || "No se pudo subir el documento.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card upload-card" onSubmit={handleSubmit}>
      <div className="card-head">
        <div>
          <h2>Subir documento</h2>
          <p>Cotizaciones, facturas o listas de precios en PDF, Excel, CSV o imagen.</p>
        </div>
      </div>

      <label
        className={`dropzone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.xlsx,.xls,.csv,.txt,.png,.jpg,.jpeg,.webp,.tif,.tiff"
          onChange={(event) => selectFile(event.target.files?.[0])}
        />
        <span className="dropzone-icon">
          <UploadIcon />
        </span>
        <span className="dropzone-title">
          {file ? file.name : "Arrastra el archivo o haz clic para seleccionar"}
        </span>
        <span className="dropzone-hint">
          {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "Máximo 25 MB"}
        </span>
      </label>

      <div className="form-grid">
        <label className="field">
          <span>Proveedor</span>
          <input
            list="supplier-options"
            value={supplierName}
            onChange={(event) => setSupplierName(event.target.value)}
            placeholder="Nombre del proveedor (opcional)"
          />
          <datalist id="supplier-options">
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.name} />
            ))}
          </datalist>
        </label>

        <label className="field">
          <span>Tipo de documento</span>
          <select value={docType} onChange={(event) => setDocType(event.target.value)}>
            {DOC_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Fecha del documento</span>
          <input
            type="date"
            value={documentDate}
            onChange={(event) => setDocumentDate(event.target.value)}
          />
        </label>
      </div>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="card-actions">
        <span className="muted-note">El archivo queda privado en tu organización.</span>
        <button type="submit" className="button primary" disabled={submitting || !file}>
          {submitting ? "Subiendo…" : "Procesar documento"}
        </button>
      </div>
    </form>
  );
}
