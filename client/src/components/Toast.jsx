import { useEffect } from "react";
import { motion } from "framer-motion";
import { CloseIcon } from "./Icons";

export default function Toast({ message, tone = "info", onClose, duration = 6000 }) {
  useEffect(() => {
    if (!message || !onClose) return undefined;
    const timer = window.setTimeout(onClose, duration);
    return () => window.clearTimeout(timer);
  }, [message, onClose, duration]);

  if (!message) return null;

  return (
    <motion.div
      className={`toast toast-${tone}`}
      role="status"
      aria-live="polite"
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.98 }}
      transition={{ duration: 0.2 }}
    >
      <span className="toast-message">{message}</span>
      <button type="button" className="toast-close" onClick={onClose} title="Cerrar aviso">
        <CloseIcon />
      </button>
    </motion.div>
  );
}
