import { type SelectHTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-md border border-border bg-card px-3 text-sm tracking-tight text-foreground",
        "outline-none transition-[border-color,box-shadow] duration-150",
        "focus-visible:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
