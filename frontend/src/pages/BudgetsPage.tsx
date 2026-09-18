import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Alert, BudgetStatus, Department } from "../api/types";
import { Card } from "../components/ui/Card";
import { BudgetProgressBar } from "../components/ui/BudgetProgressBar";
import { useAuth } from "../auth/AuthContext";

export function BudgetsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin_finance";

  const [statuses, setStatuses] = useState<BudgetStatus[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ department_code: "", period: currentPeriod(), amount: "" });

  function refresh() {
    Promise.all([
      api.get<BudgetStatus[]>("/api/budgets/status"),
      api.get<Alert[]>("/api/budgets/alerts"),
      api.get<Department[]>("/api/departments"),
    ]).then(([s, a, d]) => {
      setStatuses(s);
      setAlerts(a);
      setDepartments(d);
      if (!form.department_code && d.length) setForm((f) => ({ ...f, department_code: d[0].code }));
    });
  }

  useEffect(refresh, []);

  async function submitBudget(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/budgets", { ...form, threshold_percents: [80, 100] });
      setForm((f) => ({ ...f, amount: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create budget");
    }
  }

  async function acknowledge(alertId: number) {
    await api.post(`/api/budgets/alerts/${alertId}/acknowledge`);
    refresh();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Budgets &amp; Alerts</h2>

      {isAdmin && (
        <Card title="Create a monthly budget">
          <form onSubmit={submitBudget} style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
            <label style={fieldLabel}>
              Department
              <select value={form.department_code} onChange={(e) => setForm({ ...form, department_code: e.target.value })}>
                {departments.map((d) => (
                  <option key={d.id} value={d.code}>{d.name}</option>
                ))}
              </select>
            </label>
            <label style={fieldLabel}>
              Period (YYYY-MM)
              <input required pattern="\d{4}-\d{2}" value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} />
            </label>
            <label style={fieldLabel}>
              Amount ($)
              <input required type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} style={{ width: 100 }} />
            </label>
            <button type="submit" style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--series-1)", color: "white", fontWeight: 600, cursor: "pointer" }}>
              Create
            </button>
          </form>
          {error && <p style={{ color: "var(--status-critical)", marginTop: 8 }}>{error}</p>}
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>
            Default alert thresholds: 80% and 100% of budget.
          </p>
        </Card>
      )}

      <Card title="Budget status">
        {statuses.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>No budgets configured yet.</p>
        ) : (
          statuses.map((s) => (
            <BudgetProgressBar
              key={s.budget_id}
              departmentName={s.department_name}
              period={s.period}
              amount={parseFloat(s.amount)}
              currentSpend={parseFloat(s.current_spend)}
              percentUsed={parseFloat(s.percent_used)}
              currency={s.currency}
            />
          ))
        )}
      </Card>

      <Card title="Alerts">
        {alerts.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>No alerts fired.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Threshold</th>
                <th>Spend at trigger</th>
                <th>Triggered</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>{a.threshold_percent}%</td>
                  <td>{a.current_spend_amount}</td>
                  <td>{new Date(a.triggered_at).toLocaleString()}</td>
                  <td>
                    <span style={{ color: a.status === "open" ? "var(--status-warning)" : "var(--status-good)" }}>{a.status}</span>
                  </td>
                  <td>
                    {a.status === "open" && (
                      <button onClick={() => acknowledge(a.id)} style={{ fontSize: 12, cursor: "pointer" }}>
                        Acknowledge
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

const fieldLabel: React.CSSProperties = { fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 };
