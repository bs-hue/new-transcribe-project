import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Spinner } from "@/components/shared";
import { useAuth } from "@/lib/auth";
import { DashboardPage } from "@/pages/DashboardPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { JobDetailPage } from "@/pages/JobDetailPage";
import { JobsPage } from "@/pages/JobsPage";
import { LoginPage } from "@/pages/LoginPage";
import { NewJobPage } from "@/pages/NewJobPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { SearchPage } from "@/pages/SearchPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TranscriptPage } from "@/pages/TranscriptPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  // Wait for the stored token to be checked, so an already-signed-in user is
  // never bounced to the login screen on a page refresh.
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />

        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/new" element={<NewJobPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />

        <Route path="history" element={<HistoryPage />} />
        <Route path="history/:videoId" element={<TranscriptPage />} />

        <Route path="search" element={<SearchPage />} />
        <Route path="settings" element={<SettingsPage />} />

        {/* Links shared before the rename should still work. */}
        <Route path="library" element={<Navigate to="/history" replace />} />
        <Route path="library/:videoId" element={<LegacyVideoRedirect />} />
        <Route path="users" element={<Navigate to="/settings" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** `/library/:videoId` moved to `/history/:videoId`. */
function LegacyVideoRedirect() {
  const path = window.location.pathname.replace("/library/", "/history/");
  return <Navigate to={path} replace />;
}
