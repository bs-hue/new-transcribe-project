import { Link } from 'react-router-dom';

import { buttonVariants } from '@/shared/ui/button-variants';

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        That address doesn&apos;t exist. It may have moved, or the link may be incomplete.
      </p>
      <Link to="/" className={buttonVariants({ variant: 'outline' })}>
        Back to overview
      </Link>
    </div>
  );
}
