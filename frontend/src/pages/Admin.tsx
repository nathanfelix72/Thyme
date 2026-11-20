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
};

export function Admin() {
  const { ready, signedIn, isAdmin } = useAuth();
  const [users, setUsers] = useState<CognitoUserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      <p className="lede">Everyone registered in the Thyme Cognito user pool.</p>

      {loading ? <p className="settings-status">Loading users…</p> : null}
      {error ? <p className="settings-status">{error}</p> : null}

      <div className="user-table-wrap">
        <table className="user-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Status</th>
              <th>Enabled</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username}>
                <td>{u.email || u.username}</td>
                <td>{u.status}</td>
                <td>{u.enabled ? "yes" : "no"}</td>
                <td>{u.created_at ? new Date(u.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
