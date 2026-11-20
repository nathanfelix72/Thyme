import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  fetchAuthSession,
  getCurrentUser,
  signOut as amplifySignOut,
} from "aws-amplify/auth";
import { cognitoConfigured } from "../lib/amplify";

export type AuthState = {
  ready: boolean;
  signedIn: boolean;
  email: string | null;
  userId: string | null;
  isAdmin: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

async function readAuth(): Promise<Omit<AuthState, "ready" | "refresh" | "signOut">> {
  if (!cognitoConfigured) {
    return { signedIn: false, email: null, userId: null, isAdmin: false };
  }
  try {
    const user = await getCurrentUser();
    const session = await fetchAuthSession();
    const payload = session.tokens?.accessToken?.payload || {};
    const idPayload = session.tokens?.idToken?.payload || {};
    const groups = (payload["cognito:groups"] as string[] | undefined) || [];
    const email =
      (idPayload.email as string | undefined) ||
      user.signInDetails?.loginId ||
      null;
    return {
      signedIn: true,
      email,
      userId: user.userId,
      isAdmin: groups.includes("admins"),
    };
  } catch {
    return { signedIn: false, email: null, userId: null, isAdmin: false };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  const refresh = useCallback(async () => {
    const next = await readAuth();
    setSignedIn(next.signedIn);
    setEmail(next.email);
    setUserId(next.userId);
    setIsAdmin(next.isAdmin);
    setReady(true);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    if (cognitoConfigured) await amplifySignOut();
    await refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ ready, signedIn, email, userId, isAdmin, refresh, signOut }),
    [ready, signedIn, email, userId, isAdmin, refresh, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
