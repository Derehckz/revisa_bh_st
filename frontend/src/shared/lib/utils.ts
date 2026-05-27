import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function toCurrency(value: number | null | undefined) {
  if (value == null) return "-";
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP" }).format(value);
}
