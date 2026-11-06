import { useId } from "react";
import { InfoIcon } from "./Icons";

export default function InfoHint({ title, children, align = "left" }) {
  const id = useId();
  return (
    <span className={`info-hint-wrap ${align}`}>
      <button
        type="button"
        className="info-hint"
        aria-label={title || "Más información"}
        aria-describedby={id}
      >
        <InfoIcon />
      </button>
      <span className="info-bubble" id={id} role="tooltip">
        {title ? <strong>{title}</strong> : null}
        {children ? <span>{children}</span> : null}
      </span>
    </span>
  );
}
