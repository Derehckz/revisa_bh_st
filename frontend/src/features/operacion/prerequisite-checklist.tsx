import type { PrerequisiteItem } from "@/shared/api/types";
import { CheckCircle2, Circle, AlertCircle } from "lucide-react";

type Props = {
  items: PrerequisiteItem[];
};

export function PrerequisiteChecklist({ items }: Props) {
  if (!items.length) return null;

  return (
    <ul className="space-y-1 rounded-md border border-border bg-muted/40 p-3 text-sm">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Requisitos</p>
      {items.map((item) => {
        const blocking = item.blocking !== false;
        const Icon = item.ok ? CheckCircle2 : blocking ? AlertCircle : Circle;
        const tone = item.ok ? "text-green-700" : blocking ? "text-amber-800" : "text-muted-foreground";
        return (
          <li key={item.id} className={`flex items-start gap-2 ${tone}`}>
            <Icon size={16} className="mt-0.5 shrink-0" />
            <span>
              {item.label}
              {!item.ok && item.message ? (
                <span className="block text-xs text-muted-foreground">{item.message}</span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
