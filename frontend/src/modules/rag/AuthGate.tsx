import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

export function AuthGate({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  const { ready, signedIn } = useAuth();

  if (!ready) {
    return (
      <section className="page-panel">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">Checking sign-in…</p>
      </section>
    );
  }

  if (!signedIn) {
    return (
      <section className="page-panel">
        <p className="eyebrow">{eyebrow}</p>
        <h1>Sign in required</h1>
        <p className="lede">
          Recipe upload and search are per-user. Log in with Cognito to continue.
        </p>
        <div className="settings-actions" style={{ marginTop: "1.25rem" }}>
          <Link className="primary-link-btn" to="/login">
            Log in
          </Link>
        </div>
      </section>
    );
  }

  return <>{children}</>;
}
