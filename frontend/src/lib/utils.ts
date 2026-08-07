import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes so later ones win instead of both being emitted.
 *  The standard shadcn/ui helper — every component uses it. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
