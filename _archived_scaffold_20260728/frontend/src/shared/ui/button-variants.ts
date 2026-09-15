import { cva, type VariantProps } from 'class-variance-authority';

/**
 * Button styles, expressed as variants.
 *
 * Kept in its own file, separate from the component, for two reasons: hot-reload
 * only works cleanly when a module exports components alone, and these classes
 * are reused by elements that are not buttons — a react-router `Link` styled as
 * a button, for instance.
 *
 * Every colour is a semantic token (`bg-primary`, never `bg-indigo-600`), so the
 * theme can change without touching this file. Sizes meet the 44px minimum touch
 * target from UI_UX_SPECIFICATION §9 by default; `sm` is for dense desktop
 * contexts such as table rows.
 */
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm ' +
    'font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 ' +
    '[&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        outline: 'border border-input bg-background hover:bg-muted',
        ghost: 'hover:bg-muted',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
      },
      size: {
        default: 'h-11 px-5 py-2',
        sm: 'h-9 px-3',
        lg: 'h-12 px-8',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
);

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;
