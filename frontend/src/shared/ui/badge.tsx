import { type HTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

type Tone = "default" | "success" | "warning" | "danger";

const tones: Record<Tone, string> = {
  default: "bg-muted text-foreground",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-danger/12 text-danger",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-2xs font-semibold tracking-wide",
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
