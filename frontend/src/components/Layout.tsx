import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import { watchSystemTheme } from "../lib/theme";

const STORAGE_KEY = "thyme-sidebar-collapsed";

const mainLinks = [
  { to: "/", label: "Home", end: true, icon: "⌂" },
  { to: "/find", label: "Find", icon: "◎" },
  { to: "/library", label: "Library", icon: "▤" },
  { to: "/upload", label: "Upload", icon: "↑" },
  { to: "/plan", label: "Plan", icon: "▦" },
  { to: "/shop", label: "Shop", icon: "▣" },
  { to: "/budget", label: "Budget", icon: "◈" },
  { to: "/ai-settings", label: "AI", icon: "✦" },
  { to: "/profile", label: "Profile", icon: "⚙" },
];

export function Layout() {
  const { ready, signedIn, email, isAdmin, signOut } = useAuth();
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => watchSystemTheme(), []);

  useEffect(() => {
    if (!ready || !signedIn) {
      setDisplayName(null);
      return;
    }
    let cancelled = false;
    apiFetch("/api/settings")
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setDisplayName(data.display_name || null);
      })
      .catch(() => {
        /* ignore */
      });
    return () => {
      cancelled = true;
    };
  }, [ready, signedIn]);

  return (
    <div className={`shell${collapsed ? " sidebar-collapsed" : ""}`}>
      <div className="atmosphere" aria-hidden="true" />
      <aside className="sidebar" aria-label="Primary">
        <div className="sidebar-top">
          <NavLink to="/" className="brand" end>
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">Thyme</span>
          </NavLink>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>

        <nav className="sidebar-nav">
          {mainLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                isActive ? "sidebar-link is-active" : "sidebar-link"
              }
              title={link.label}
            >
              <span className="sidebar-icon" aria-hidden="true">
                {link.icon}
              </span>
              <span className="sidebar-label">{link.label}</span>
            </NavLink>
          ))}
          {isAdmin ? (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                isActive ? "sidebar-link is-active" : "sidebar-link"
              }
              title="Admin"
            >
              <span className="sidebar-icon" aria-hidden="true">
                ★
              </span>
              <span className="sidebar-label">Admin</span>
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-foot">
          {ready && signedIn ? (
            <>
              <span
                className="sidebar-user"
                title={email || undefined}
              >
                <span className="sidebar-icon" aria-hidden="true">
                  ●
                </span>
                <span className="sidebar-label">
                  {displayName || email || "Signed in"}
                </span>
              </span>
              <button
                type="button"
                className="sidebar-link sidebar-btn"
                onClick={() => void signOut()}
                title="Log out"
              >
                <span className="sidebar-icon" aria-hidden="true">
                  →
                </span>
                <span className="sidebar-label">Log out</span>
              </button>
            </>
          ) : (
            <NavLink
              to="/login"
              className={({ isActive }) =>
                isActive ? "sidebar-link is-active" : "sidebar-link"
              }
              title="Log in"
            >
              <span className="sidebar-icon" aria-hidden="true">
                →
              </span>
              <span className="sidebar-label">Log in</span>
            </NavLink>
          )}
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
