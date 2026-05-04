import { type HTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

type Tone = "default" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  default: "bg-muted text-foreground",
  success: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-red-100 text-red-800",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold", tones[tone], className)}
      {...props}
    />
  );
}
