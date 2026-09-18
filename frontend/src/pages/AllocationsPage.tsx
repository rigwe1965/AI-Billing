import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ApiKeyMap, Department, Provider, TagMap, UnpricedUsageRow } from "../api/types";
import { Card } from "../components/ui/Card";

export function AllocationsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [keyMaps, setKeyMaps] = useState<ApiKeyMap[]>([]);
  const [tagMaps, setTagMaps] = useState<TagMap[]>([]);
  const [needsAllocation, setNeedsAllocation] = useState<UnpricedUsageRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [keyForm, setKeyForm] = useState({ provider_code: "", api_key_label: "", department_code: "", effective_from: today() });
  const [tagForm, setTagForm] = useState({ provider_code: "", tag_value: "", department_code: "", effective_from: today() });
  const [manualForm, setManualForm] = useState({ usage_record_id: "", department_code: "", allocation_percent: "" });

  function refresh() {
    Promise.all([
      api.get<Provider[]>("/api/providers"),
      api.get<Department[]>("/api/departments"),
      api.get<ApiKeyMap[]>("/api/allocations/api-key-map"),
      api.get<TagMap[]>("/api/allocations/tag-map"),
      api.get<UnpricedUsageRow[]>("/api/costs/needs-allocation"),
    ]).then(([p, d, k, t, n]) => {
      setProviders(p);
      setDepartments(d);
      setKeyMaps(k);
      setTagMaps(t);
      setNeedsAllocation(n);
      if (!keyForm.provider_code && p.length) {
        setKeyForm((f) => ({ ...f, provider_code: p[0].code }));
        setTagForm((f) => ({ ...f, provider_code: p[0].code }));
      }
      if (!keyForm.department_code && d.length) {
        setKeyForm((f) => ({ ...f, department_code: d[0].code }));
        setTagForm((f) => ({ ...f, department_code: d[0].code }));
        setManualForm((f) => ({ ...f, department_code: d[0].code }));
      }
    });
  }

  useEffect(refresh, []);

  async function submitKeyMap(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/allocations/api-key-map", keyForm);
      setKeyForm((f) => ({ ...f, api_key_label: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    }
  }

  async function submitTagMap(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/allocations/tag-map", tagForm);
      setTagForm((f) => ({ ...f, tag_value: "" }));
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    }
  }

  async function submitManual(usageRecordId: number) {
    setError(null);
    setMessage(null);
    try {
      await api.post("/api/allocations/manual", {
        usage_record_id: usageRecordId,
        splits: [{ department_code: manualForm.department_code, allocation_percent: 100 }],
        note: "Assigned via UI",
      });
      setMessage(`Usage record ${usageRecordId} allocated to ${manualForm.department_code}.`);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    }
  }

  async function reprocess() {
    setError(null);
    setMessage(null);
    try {
      const res = await api.post<{ checked: number; resolved: number }>("/api/allocations/reprocess-unallocated");
      setMessage(`Checked ${res.checked} record(s), resolved ${res.resolved}.`);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed");
    }
  }

  const providerName = (id: number) => providers.find((p) => p.id === id)?.name ?? id;
  const departmentName = (id: number) => departments.find((d) => d.id === id)?.name ?? id;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Allocation Mapping</h2>
      {error && <p style={{ color: "var(--status-critical)" }}>{error}</p>}
      {message && <p style={{ color: "var(--status-good)" }}>{message}</p>}

      <Card title="Usage needing allocation">
        {needsAllocation.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>Nothing needs manual allocation right now.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Usage record</th>
                <th>Provider</th>
                <th>SKU</th>
                <th>Quantity</th>
                <th>Period</th>
                <th>Assign to</th>
              </tr>
            </thead>
            <tbody>
              {needsAllocation.map((row) => (
                <tr key={row.cost_line_item_id}>
                  <td>{row.usage_record_id}</td>
                  <td>{row.provider}</td>
                  <td>{row.sku_code}</td>
                  <td>{row.quantity}</td>
                  <td>{row.period_start}</td>
                  <td>
                    <button onClick={() => submitManual(row.usage_record_id)} style={{ fontSize: 12, cursor: "pointer" }}>
                      Assign 100% to {manualForm.department_code}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>
          For a split across multiple departments, use the API directly (<code>POST /api/allocations/manual</code>)
          -- this quick action assigns 100% to the department selected in the Manual Split panel below.
        </p>
        <button onClick={reprocess} style={{ marginTop: 8, fontSize: 12, cursor: "pointer" }}>
          Re-check all unallocated usage against current mappings
        </button>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card title="API key -> department mapping">
          <form onSubmit={submitKeyMap} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <ProviderSelect value={keyForm.provider_code} onChange={(v) => setKeyForm({ ...keyForm, provider_code: v })} providers={providers} />
            <input required placeholder="api_key_label (e.g. key-eng)" value={keyForm.api_key_label} onChange={(e) => setKeyForm({ ...keyForm, api_key_label: e.target.value })} />
            <DepartmentSelect value={keyForm.department_code} onChange={(v) => setKeyForm({ ...keyForm, department_code: v })} departments={departments} />
            <input type="date" value={keyForm.effective_from} onChange={(e) => setKeyForm({ ...keyForm, effective_from: e.target.value })} />
            <button type="submit" style={buttonStyle}>Add mapping</button>
          </form>
          <table style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Provider</th><th>Key label</th><th>Department</th></tr>
            </thead>
            <tbody>
              {keyMaps.map((m) => (
                <tr key={m.id}><td>{providerName(m.provider_id)}</td><td>{m.api_key_label}</td><td>{departmentName(m.department_id)}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card title="Tag -> department mapping">
          <form onSubmit={submitTagMap} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <ProviderSelect value={tagForm.provider_code} onChange={(v) => setTagForm({ ...tagForm, provider_code: v })} providers={providers} />
            <input required placeholder="tag_value (e.g. proj-alpha)" value={tagForm.tag_value} onChange={(e) => setTagForm({ ...tagForm, tag_value: e.target.value })} />
            <DepartmentSelect value={tagForm.department_code} onChange={(v) => setTagForm({ ...tagForm, department_code: v })} departments={departments} />
            <input type="date" value={tagForm.effective_from} onChange={(e) => setTagForm({ ...tagForm, effective_from: e.target.value })} />
            <button type="submit" style={buttonStyle}>Add mapping</button>
          </form>
          <table style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Provider</th><th>Tag value</th><th>Department</th></tr>
            </thead>
            <tbody>
              {tagMaps.map((m) => (
                <tr key={m.id}><td>{providerName(m.provider_id)}</td><td>{m.tag_value}</td><td>{departmentName(m.department_id)}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card title="Manual split -- default department for quick-assign above">
        <DepartmentSelect value={manualForm.department_code} onChange={(v) => setManualForm({ ...manualForm, department_code: v })} departments={departments} />
      </Card>
    </div>
  );
}

function ProviderSelect({ value, onChange, providers }: { value: string; onChange: (v: string) => void; providers: Provider[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {providers.map((p) => (
        <option key={p.id} value={p.code}>{p.name}</option>
      ))}
    </select>
  );
}

function DepartmentSelect({ value, onChange, departments }: { value: string; onChange: (v: string) => void; departments: Department[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {departments.map((d) => (
        <option key={d.id} value={d.code}>{d.name}</option>
      ))}
    </select>
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

const buttonStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 6,
  border: "none",
  background: "var(--series-1)",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
  alignSelf: "flex-start",
};
