import type * as React from 'react';

import { cn } from '@/shared/lib/utils';
import { buttonVariants, type ButtonVariantProps } from '@/shared/ui/button-variants';

export type ButtonProps = React.ComponentProps<'button'> & ButtonVariantProps;

export function Button({ className, variant, size, type = 'button', ...props }: ButtonProps) {
  // Defaulting to type="button" avoids the classic bug where a button inside a
  // form submits it by accident.
  return (
    <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
