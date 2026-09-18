import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { PricingRate, Provider } from "../api/types";
import { Card } from "../components/ui/Card";

export function PricingPage() {
  const [rates, setRates] = useState<PricingRate[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    provider_code: "",
    sku_code: "",
    unit: "per_1m_tokens",
    rate_amount: "",
    effective_from: new Date().toISOString().slice(0, 10),
  });

  function refresh() {
    Promise.all([api.get<PricingRate[]>("/api/pricing"), api.get<Provider[]>("/api/providers")]).then(([r, p]) => {
      setRates(r);
      setProviders(p);
      if (!form.provider_code && p.length > 0) setForm((f) => ({ ...f, provider_code: p[0].code }));
    });
  }

  useEffect(refresh, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/pricing", { ...form, rate_amount: form.rate_amount });
      setForm((f) => ({ ...f, sku_code: "", rate_amount: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create rate");
    }
  }

  const providerName = (id: number) => providers.find((p) => p.id === id)?.name ?? id;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Pricing Rates</h2>

      <Card title="Add a rate">
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Field label="Provider">
            <select value={form.provider_code} onChange={(e) => setForm({ ...form, provider_code: e.target.value })}>
              {providers.map((p) => (
                <option key={p.id} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="SKU code">
            <input required value={form.sku_code} onChange={(e) => setForm({ ...form, sku_code: e.target.value })} placeholder="claude-sonnet-input-tokens" />
          </Field>
          <Field label="Unit">
            <select value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })}>
              <option value="per_token">per_token</option>
              <option value="per_1k_tokens">per_1k_tokens</option>
              <option value="per_1m_tokens">per_1m_tokens</option>
              <option value="per_request">per_request</option>
              <option value="per_seat_month">per_seat_month</option>
            </select>
          </Field>
          <Field label="Rate ($)">
            <input required type="number" step="0.000001" value={form.rate_amount} onChange={(e) => setForm({ ...form, rate_amount: e.target.value })} style={{ width: 100 }} />
          </Field>
          <Field label="Effective from">
            <input required type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
          </Field>
          <button type="submit" style={{ padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--series-1)", color: "white", fontWeight: 600, cursor: "pointer" }}>
            Add
          </button>
        </form>
        {error && <p style={{ color: "var(--status-critical)", marginTop: 8 }}>{error}</p>}
      </Card>

      <Card title="Current & historical rates">
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>SKU</th>
              <th>Unit</th>
              <th>Rate</th>
              <th>Effective from</th>
              <th>Effective to</th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.id}>
                <td>{providerName(r.provider_id)}</td>
                <td>{r.sku_code}</td>
                <td>{r.unit}</td>
                <td>
                  {r.currency} {r.rate_amount}
                </td>
                <td>{r.effective_from}</td>
                <td>{r.effective_to ?? <span style={{ color: "var(--status-good)" }}>active</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 }}>
      {label}
      {children}
    </label>
  );
}
