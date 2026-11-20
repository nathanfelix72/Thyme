import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/understand", label: "Understand" },
  { to: "/plan", label: "Plan" },
  { to: "/shop", label: "Shop" },
  { to: "/budget", label: "Budget" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { ready, signedIn, email, isAdmin, signOut } = useAuth();

  return (
    <div className="shell">
      <div className="atmosphere" aria-hidden="true" />
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Thyme</span>
        </NavLink>
        <nav className="nav" aria-label="Primary">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                isActive ? "nav-link is-active" : "nav-link"
              }
            >
              {link.label}
            </NavLink>
          ))}
          {isAdmin ? (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                isActive ? "nav-link is-active" : "nav-link"
              }
            >
              Admin
            </NavLink>
          ) : null}
          {ready && signedIn ? (
            <>
              <span className="nav-user" title={email || undefined}>
                {email || "Signed in"}
              </span>
              <button type="button" className="nav-link nav-btn" onClick={() => void signOut()}>
                Log out
              </button>
            </>
          ) : (
            <NavLink
              to="/login"
              className={({ isActive }) =>
                isActive ? "nav-link is-active" : "nav-link"
              }
            >
              Log in
            </NavLink>
          )}
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
