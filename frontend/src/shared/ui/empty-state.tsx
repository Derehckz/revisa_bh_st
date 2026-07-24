import { Inbox } from "lucide-react";
import { cn } from "@/shared/lib/utils";

export function EmptyState({
  title,
  description,
  className,
}: {
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Inbox className="h-5 w-5" strokeWidth={1.5} />
      </div>
      <p className="text-[0.9375rem] font-semibold tracking-tight text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-sm leading-snug text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}
