import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
  display: "block",
  padding: "8px 12px",
  borderRadius: 6,
  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
  background: isActive ? "var(--surface)" : "transparent",
  textDecoration: "none",
  fontSize: 14,
  fontWeight: isActive ? 600 : 400,
});

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin_finance";

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav
        style={{
          width: 220,
          flexShrink: 0,
          borderRight: "1px solid var(--border)",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 16 }}>AI Spend Management</div>
        <NavLink to="/" style={linkStyle} end>
          Dashboard
        </NavLink>
        <NavLink to="/usage-import" style={linkStyle}>
          Usage Import
        </NavLink>
        <NavLink to="/budgets" style={linkStyle}>
          Budgets &amp; Alerts
        </NavLink>
        <NavLink to="/reports" style={linkStyle}>
          Reports
        </NavLink>
        <NavLink to="/insights" style={linkStyle}>
          Insights
        </NavLink>
        {isAdmin && (
          <>
            <div style={{ marginTop: 12, fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Admin
            </div>
            <NavLink to="/pricing" style={linkStyle}>
              Pricing Rates
            </NavLink>
            <NavLink to="/allocations" style={linkStyle}>
              Allocation Mapping
            </NavLink>
            <NavLink to="/connectors" style={linkStyle}>
              Provider Connectors
            </NavLink>
            <NavLink to="/users" style={linkStyle}>
              Users &amp; Departments
            </NavLink>
          </>
        )}
        <div style={{ marginTop: "auto", paddingTop: 16, borderTop: "1px solid var(--border)", fontSize: 12 }}>
          <div style={{ color: "var(--text-secondary)" }}>{user?.email}</div>
          <div style={{ color: "var(--text-muted)", marginBottom: 8 }}>{user?.role}</div>
          <NavLink to="/account" style={linkStyle}>
            Change password
          </NavLink>
          <button onClick={logout} style={{ fontSize: 12, padding: "4px 8px", cursor: "pointer" }}>
            Log out
          </button>
        </div>
      </nav>
      <main style={{ flex: 1, padding: 24, maxWidth: 1100 }}>{children}</main>
    </div>
  );
}
