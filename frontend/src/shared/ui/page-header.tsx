import type { ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

type Props = {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
};

/** Encabezado de página unificado (jerarquía tipo Apple HIG). */
export function PageHeader({ title, description, actions, className }: Props) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-3 pb-1", className)}>
      <div className="min-w-0">
        <h1 className="page-title">{title}</h1>
        {description ? <p className="page-subtitle">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
