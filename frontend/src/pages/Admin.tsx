import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

type CognitoUserRow = {
  username: string;
  email: string | null;
  status: string | null;
  enabled: boolean;
  created_at: string | null;
  is_admin: boolean;
};

export function Admin() {
  const { ready, signedIn, isAdmin, userId, email } = useAuth();
  const [users, setUsers] = useState<CognitoUserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [busyUser, setBusyUser] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !signedIn || !isAdmin) return;
    setLoading(true);
    apiFetch("/api/admin/users")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to load users");
        setUsers(data.users || []);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [ready, signedIn, isAdmin]);

  function isSelf(u: CognitoUserRow): boolean {
    const rowEmail = (u.email || "").toLowerCase();
    const myEmail = (email || "").toLowerCase();
    return (
      (!!userId && (u.username === userId || u.email === userId)) ||
      (!!myEmail && rowEmail === myEmail)
    );
  }

  /** Prefer Cognito group flag; fall back to auth session for the current user. */
  function rowIsAdmin(u: CognitoUserRow): boolean {
    if (u.is_admin) return true;
    return isSelf(u) && isAdmin;
  }

  async function setAdminFlag(u: CognitoUserRow, next: boolean) {
    if (isSelf(u) && !next) {
      setError("You cannot remove your own admin access.");
      return;
    }
    setBusyUser(u.username);
    setError(null);
    try {
      const res = await apiFetch(
        `/api/admin/users/${encodeURIComponent(u.username)}/admin`,
        {
          method: "PUT",
          body: JSON.stringify({ is_admin: next }),
        },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Update failed");
      setUsers((prev) =>
        prev.map((row) =>
          row.username === u.username
            ? { ...row, ...data, is_admin: Boolean(data.is_admin ?? next) }
            : row,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusyUser(null);
    }
  }

  if (!ready) {
    return (
      <section className="home">
        <p className="lede">Loading…</p>
      </section>
    );
  }

  if (!signedIn) {
    return (
      <section className="home">
        <h1>Admin</h1>
        <p className="lede">
          <Link to="/login">Log in</Link> as an admin to see users.
        </p>
      </section>
    );
  }

  if (!isAdmin) {
    return (
      <section className="home">
        <h1>Admin</h1>
        <p className="lede">
          Your account is not in the Cognito <code>admins</code> group.
        </p>
      </section>
    );
  }

  return (
    <section className="home">
      <p className="eyebrow">Admin</p>
      <h1>Users</h1>
      <p className="lede">
        Everyone registered in the Thyme Cognito user pool. Grant or revoke
        admin access for other accounts.
      </p>

      {loading ? <p className="settings-status">Loading users…</p> : null}
      {error ? <p className="settings-status">{error}</p> : null}

      <div className="user-table-wrap">
        <table className="user-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Status</th>
              <th>Enabled</th>
              <th>Admin</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const admin = rowIsAdmin(u);
              const self = isSelf(u);
              return (
                <tr key={u.username}>
                  <td>
                    {u.email || u.username}
                    {self ? " (you)" : ""}
                  </td>
                  <td>{u.status}</td>
                  <td>{u.enabled ? "yes" : "no"}</td>
                  <td>{admin ? "yes" : "no"}</td>
                  <td>
                    {u.created_at
                      ? new Date(u.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td>
                    {self && admin ? (
                      <span className="field-hint">You</span>
                    ) : (
                      <button
                        type="button"
                        className="text-btn"
                        disabled={busyUser === u.username}
                        onClick={() => void setAdminFlag(u, !admin)}
                      >
                        {busyUser === u.username
                          ? "…"
                          : admin
                            ? "Remove admin"
                            : "Make admin"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
