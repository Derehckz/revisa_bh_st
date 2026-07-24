import { type HTMLAttributes, type TableHTMLAttributes, type ThHTMLAttributes, type TdHTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

export function TableWrapper({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("overflow-hidden rounded-lg border border-border bg-card", className)}
      {...props}
    />
  );
}

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full border-collapse text-sm tracking-tight", className)} {...props} />;
}

export function TH({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "sticky top-0 z-10 border-b border-border bg-muted/80 px-3 py-2.5 text-left",
        "text-2xs font-semibold uppercase tracking-[0.06em] text-muted-foreground backdrop-blur-sm",
        className
      )}
      {...props}
    />
  );
}

export function TD({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("border-b border-border/80 px-3 py-2.5 align-middle text-foreground", className)} {...props} />
  );
}
