import { LayoutDashboard } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

import { cn } from '@/shared/lib/utils';

/**
 * The sidebar doubles as a module registry.
 *
 * Adding a future module (Transcription in Phase 3, then Insights, Search,
 * Translation) means appending an entry here — the shell itself never needs
 * reorganising, which is the point of designing it this way now
 * (UI_UX_SPECIFICATION §11).
 */
const NAV_ITEMS = [{ to: '/', label: 'Overview', icon: LayoutDashboard }];

export function AppShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Keyboard users should not have to tab through the whole nav to reach
          the content. Visible only when focused. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <div className="flex min-h-screen">
        {/* Below `md` the sidebar is hidden; Phase 3 replaces it with a drawer. */}
        <aside className="hidden w-60 shrink-0 border-r bg-card md:block">
          <div className="flex h-16 items-center border-b px-6">
            <span className="text-sm font-semibold tracking-tight">Transcript Agent</span>
          </div>
          <nav aria-label="Modules" className="p-3">
            <ul className="space-y-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                        isActive
                          ? 'bg-primary/10 font-medium text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon aria-hidden="true" className="size-4" />
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b px-6">
            <span className="text-sm font-semibold md:hidden">Transcript Agent</span>
            <span className="ml-auto text-xs text-muted-foreground">Phase 0 — foundation</span>
          </header>

          <main id="main-content" className="flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
