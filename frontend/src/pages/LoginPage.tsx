import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width: 320,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <h2 style={{ margin: "0 0 8px" }}>AI Spend Management</h2>
        <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4, borderRadius: 6, border: "1px solid var(--border)" }}
          />
        </label>
        <label style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4, borderRadius: 6, border: "1px solid var(--border)" }}
          />
        </label>
        {error && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>{error}</div>}
        <button
          type="submit"
          disabled={submitting}
          style={{
            padding: "10px 12px",
            borderRadius: 6,
            border: "none",
            background: "var(--series-1)",
            color: "white",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {submitting ? "Logging in..." : "Log in"}
        </button>
      </form>
    </div>
  );
}
