import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Combine class names, resolving Tailwind conflicts.
 *
 * Plain string concatenation would leave both `p-2` and `p-4` in the class list,
 * and which one wins depends on stylesheet order — unpredictable. `twMerge`
 * keeps the last one, so a caller can always override a component's defaults.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
