import { type ButtonHTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

type Variant = "default" | "outline" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  default: "bg-primary text-primary-foreground hover:brightness-110 active:brightness-95",
  outline: "border border-border bg-card text-foreground hover:bg-muted/80",
  ghost: "text-foreground hover:bg-muted/80",
  danger: "bg-danger text-white hover:brightness-110",
};

const sizes: Record<Size, string> = {
  sm: "h-8 rounded-md px-3 text-xs",
  md: "h-9 rounded-md px-3.5 text-sm",
  lg: "h-11 rounded-lg px-5 text-[0.9375rem]",
};

export function Button({ className, variant = "default", size = "md", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 font-medium tracking-tight transition-[background,opacity,filter] duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:pointer-events-none disabled:opacity-40",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
