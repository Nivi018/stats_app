// Alerta de error accionable: mensaje claro, correlation_id para soporte y pista de remediación.

import type { ReactNode } from "react";

export function ErrorAlert({
  title,
  message,
  correlationId,
  hint,
  className = "",
}: {
  title: string;
  message: string;
  correlationId?: string | null;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div role="alert" className={`border border-red-300 bg-red-50 p-5 text-sm text-red-800 ${className}`}>
      <p className="font-semibold">{title}</p>
      <p className="mt-1">{message}</p>
      {correlationId && (
        <p className="mt-2 text-xs">
          ID de correlación para soporte:{" "}
          <code className="break-all" title={correlationId}>
            {correlationId}
          </code>
        </p>
      )}
      {hint && <p className="mt-2 text-xs">{hint}</p>}
    </div>
  );
}
