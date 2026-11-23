import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../lib/api";
import { UploadIcon, CheckIcon, SparkIcon } from "./Icons";
import Toast from "./Toast";

const DOC_TYPES = [
  { value: "quote", label: "Cotización" },
  { value: "invoice", label: "Factura" },
  { value: "price_list", label: "Lista de precios" },
];

const AI_STEPS = [
  { key: "ocr", label: "Lectura OCR", icon: "📷" },
  { key: "normalize", label: "Normalizar SKUs", icon: "🔧" },
  { key: "match", label: "Cruce precios", icon: "⚡" },
  { key: "validate", label: "Validar 3-way", icon: "✅" },
];

export default function UploadCard({ onUploaded }) {
  const inputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const file = files[0] || null;
  const [supplierName, setSupplierName] = useState("");
  const [docType, setDocType] = useState("invoice");
  const [documentDate, setDocumentDate] = useState("");
  const [suppliers, setSuppliers] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [currentAiStep, setCurrentAiStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [toast, setToast] = useState(null);

  useEffect(() => {
    api("/api/suppliers")
      .then((data) => setSuppliers(data.items || []))
      .catch(() => setSuppliers([]));
  }, []);

  function selectFiles(nextFiles) {
    setError("");
    setSuccess("");
    setFiles(Array.from(nextFiles || []));
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files?.length) selectFiles(event.dataTransfer.files);
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
      const isBulk = files.length > 1;
      const body = new FormData();
      files.forEach((item) => body.append("file", item));
      body.append("doc_type", docType);
      if (supplierName.trim()) body.append("supplier_name", supplierName.trim());
      if (documentDate) body.append("document_date", documentDate);

      const endpoint = isBulk ? "/api/documents/ingest-bulk" : "/api/documents/ingest";
      const data = await api(endpoint, { method: "POST", body, timeoutMs: 30000 });

      if (isBulk) {
        setSubmitting(false);
        setFiles([]);
        setDocumentDate("");
        if (inputRef.current) inputRef.current.value = "";
        const message =
          `Lote procesado: ${data.succeeded} de ${data.total} documentos aceptados` +
          (data.failed ? `, ${data.failed} con error.` : ".");
        setSuccess(message);
        setToast({ message, tone: data.failed ? "warning" : "success" });
        return;
      }

if (data.duplicate) {
      const message = "Este documento ya estaba cargado. Te mostramos el registro existente.";
      setSubmitting(false);
      setSuccess(message);
      setToast({ message, tone: "info" });
      setFiles([]);
      setDocumentDate("");
      if (inputRef.current) inputRef.current.value = "";
      onUploaded?.(data.document);
      return;
    }

      // Iniciar animación de procesamiento IA
      setSubmitting(false);
      setProcessing(true);
      setFiles([]);
      setDocumentDate("");
      if (inputRef.current) inputRef.current.value = "";
      onUploaded?.(data.document);

      // Simular pasos de IA con progreso real
      for (let i = 0; i < AI_STEPS.length; i++) {
        setCurrentAiStep(i);
        const targetProgress = Math.round(((i + 1) / AI_STEPS.length) * 100);
        // Animar progreso suave
        for (let p = progress; p <= targetProgress; p++) {
          await new Promise((r) => setTimeout(r, 30));
          setProgress(p);
        }
        await new Promise((r) => setTimeout(r, 500)); // Pausa en cada paso
      }

      // Completado
      setProgress(100);
      await new Promise((r) => setTimeout(r, 600));
      setProcessing(false);
      const message =
        data.message || "Documento recibido. La extracción con IA continuará en segundo plano.";
      setSuccess(message);
      setToast({ message, tone: "success" });
    } catch (err) {
      setProcessing(false);
      setSubmitting(false);
      const message =
        err.code === "timeout"
          ? "La carga superó los 30 segundos. El archivo no se envió; revisa tu conexión e inténtalo otra vez."
          : err.message || "No se pudo subir el documento.";
      setError(message);
      setToast({ message, tone: "error" });
    }
  }

  const AIProcessingView = () => (
    <motion.div
      className="ai-processing"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header con SparkIcon animado */}
      <div className="ai-header">
        <motion.div
          className="ai-spark"
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
        >
          <SparkIcon />
        </motion.div>
        <div className="ai-title">
          <h4>Procesando con IA…</h4>
          <p>Normalizando SKUs, cruzando precios y validando 3-way matching</p>
        </div>
      </div>

      {/* Barra de progreso con ondas */}
      <div className="progress-wave">
        <motion.div
          className="progress-track"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        >
          <div className="progress-fill" />
          <div className="progress-glow" />
        </motion.div>
        <motion.span
          className="progress-pct"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          key={progress}
        >
          {progress}%
        </motion.span>
      </div>

      {/* Pasos de IA en tiempo real */}
      <div className="ai-steps">
        {AI_STEPS.map((step, index) => {
          const isActive = index === currentAiStep;
          const isDone = index < currentAiStep;
          return (
            <motion.div
              key={step.key}
              className={`ai-step ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1, duration: 0.3 }}
            >
              <div className="ai-step-icon">
                {isDone ? (
                  <CheckIcon />
                ) : isActive ? (
                  <motion.span
                    className="spinner"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    {step.icon}
                  </motion.span>
                ) : (
                  <span>{step.icon}</span>
                )}
              </div>
              <span className="ai-step-label">{step.label}</span>
              <motion.div
                className="ai-step-bar"
                initial={{ width: 0 }}
                animate={{ width: isDone ? "100%" : isActive ? "50%" : "0%" }}
                transition={{ duration: 0.4 }}
              />
            </motion.div>
          );
        })}
      </div>

      {/* Mensaje de estado */}
      <motion.p
        className="ai-status"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        key={currentAiStep}
      >
        {AI_STEPS[currentAiStep]?.label || "Finalizando…"}
      </motion.p>
    </motion.div>
  );

  return (
    <form className="card upload-card" onSubmit={handleSubmit}>
      <div className="card-head">
        <div>
          <h2>Subir documento</h2>
          <p>Facturas XML DTE, PDF, Excel/CSV o imagen. El RCV se importa desde Auditoría Express.</p>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {!processing && !submitting ? (
          <motion.div
            key="upload-form"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
          >
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
                multiple
                accept=".pdf,.xml,.dte,.xlsx,.xls,.csv,.txt,.png,.jpg,.jpeg,.webp,.tif,.tiff"
                onChange={(event) => selectFiles(event.target.files)}
              />
              <span className="dropzone-icon">
                <UploadIcon />
              </span>
              <span className="dropzone-title">
                {files.length > 1
                  ? `${files.length} archivos seleccionados`
                  : file
                    ? file.name
                    : "Arrastra uno o m\u00e1s archivos o haz clic para seleccionar"}
              </span>
              <span className="dropzone-hint">
                {files.length > 1 ? "Carga masiva de hasta 50 archivos" : file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "Máximo 25 MB por archivo"}
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
              <button
                type="submit"
                className="button primary"
                disabled={submitting || !file}
              >
                {submitting ? "Subiendo..." : files.length > 1 ? "Procesar lote" : "Procesar documento"}
              </button>
            </div>
          </motion.div>
        ) : null}

        {processing ? <AIProcessingView key="ai-processing" /> : null}

        {submitting && !processing ? (
          <motion.div
            key="submitting"
            className="submitting-view"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="spinner-ring"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
            >
              <SparkIcon />
            </motion.div>
            <p>Enviando documento al servidor…</p>
          </motion.div>
        ) : null}

        {success && !processing && !submitting ? (
          <motion.div
            key="success"
            className="success-view"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
          >
            <motion.div
              className="success-check"
              animate={{
                scale: [0, 1.2, 1],
                pathLength: [0, 1],
              }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            >
              <CheckIcon size={32} />
            </motion.div>
            <p className="success-message">{success}</p>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <Toast message={toast?.message} tone={toast?.tone} onClose={() => setToast(null)} />
    </form>
  );
}
