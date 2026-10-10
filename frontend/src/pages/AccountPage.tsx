import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { Card } from "../components/ui/Card";

const MIN_LENGTH = 12;

export function AccountPage() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    if (form.next.length < MIN_LENGTH) {
      setError(`New password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (form.next !== form.confirm) {
      setError("New password and confirmation do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/api/auth/change-password", {
        current_password: form.current,
        new_password: form.next,
      });
      setForm({ current: "", next: "", confirm: "" });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Account</h2>
      <Card title="Change password">
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 320 }}>
          <label style={fieldLabel}>
            Current password
            <input
              required
              type="password"
              autoComplete="current-password"
              value={form.current}
              onChange={(e) => setForm({ ...form, current: e.target.value })}
            />
          </label>
          <label style={fieldLabel}>
            New password (min {MIN_LENGTH} characters)
            <input
              required
              type="password"
              autoComplete="new-password"
              minLength={MIN_LENGTH}
              value={form.next}
              onChange={(e) => setForm({ ...form, next: e.target.value })}
            />
          </label>
          <label style={fieldLabel}>
            Confirm new password
            <input
              required
              type="password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--series-1)", color: "white", fontWeight: 600, cursor: "pointer", alignSelf: "flex-start" }}
          >
            {submitting ? "Saving..." : "Change password"}
          </button>
        </form>
        {error && <p style={{ color: "var(--status-critical)", marginTop: 8 }}>{error}</p>}
        {success && <p style={{ marginTop: 8 }}>Password changed.</p>}
      </Card>
    </div>
  );
}

const fieldLabel: React.CSSProperties = { fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 };
