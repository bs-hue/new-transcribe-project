import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ApiError, api, setUnauthorizedHandler, tokenStore } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  /** True until the stored token has been checked, so the app does not flash
   *  the login screen at someone who is already signed in. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  // Any 401 from anywhere in the app drops us back to signed-out.
  useEffect(() => setUnauthorizedHandler(() => setUser(null)), []);

  // A token in localStorage is only a claim — verify it against the server
  // before trusting it, since it may have expired or the account been disabled.
  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    tokenStore.set(result.access_token);
    setUser(result.user);
  }, []);

  const value = useMemo(
    () => ({ user, loading, signIn, signOut }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>.");
  return context;
}

export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  return error instanceof ApiError ? error.message : fallback;
}
