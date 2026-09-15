import { createBrowserRouter } from 'react-router-dom';

import { AppShell } from '@/app/layouts/AppShell';
import { HomePage } from '@/app/pages/HomePage';
import { NotFoundPage } from '@/app/pages/NotFoundPage';

/**
 * Route table.
 *
 * Authenticated routes nest inside `AppShell`, so Phase 1 can add a single guard
 * at this level rather than repeating a check in every page. Phase 3 adds the
 * transcription routes (`/jobs`, `/jobs/:id`, `/transcripts/:id`) as children
 * here.
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
