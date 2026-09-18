import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ConnectionTestResult, ConnectorStatus, PullResult } from "../api/types";
import { Card } from "../components/ui/Card";

export function ConnectorsPage() {
  const [statuses, setStatuses] = useState<ConnectorStatus[]>([]);
  const [testResults, setTestResults] = useState<Record<string, ConnectionTestResult>>({});
  const [pullRange, setPullRange] = useState({ period_start: firstOfMonth(), period_end: today() });
  const [pullResults, setPullResults] = useState<Record<string, PullResult | string>>({});

  function refresh() {
    api.get<ConnectorStatus[]>("/api/connectors").then(setStatuses);
  }

  useEffect(refresh, []);

  async function testConnection(code: string) {
    const result = await api.post<ConnectionTestResult>(`/api/connectors/${code}/test-connection`);
    setTestResults((r) => ({ ...r, [code]: result }));
  }

  async function triggerPull(code: string) {
    try {
      const result = await api.post<PullResult>(`/api/connectors/${code}/pull`, pullRange);
      setPullResults((r) => ({ ...r, [code]: result }));
    } catch (err) {
      setPullResults((r) => ({ ...r, [code]: err instanceof ApiError ? err.message : "Pull failed" }));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Provider Connectors</h2>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", maxWidth: 640 }}>
        Credentials are configured via environment variables on the server (see README). A connector with no
        credentials configured shows as unavailable here -- that's expected, not an error; use CSV import for that
        provider instead. Configured connectors also run automatically every night at 02:00.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
        <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 }}>
          Pull range start
          <input type="date" value={pullRange.period_start} onChange={(e) => setPullRange({ ...pullRange, period_start: e.target.value })} />
        </label>
        <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: 4 }}>
          Pull range end
          <input type="date" value={pullRange.period_end} onChange={(e) => setPullRange({ ...pullRange, period_end: e.target.value })} />
        </label>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {statuses.map((s) => (
          <Card key={s.provider_code} title={s.provider_code}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              Status:{" "}
              <strong style={{ color: s.supports_usage_pull ? "var(--status-good)" : "var(--status-warning)" }}>
                {s.supports_usage_pull ? "Ready" : "Unavailable"}
              </strong>
            </div>
            {s.requires_prerequisite && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
                Requires: {s.requires_prerequisite}
              </div>
            )}
            {s.unavailable_reason && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>{s.unavailable_reason}</div>
            )}

            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <button onClick={() => testConnection(s.provider_code)} style={smallButton}>
                Test connection
              </button>
              <button onClick={() => triggerPull(s.provider_code)} disabled={!s.supports_usage_pull} style={smallButton}>
                Pull now
              </button>
            </div>

            {testResults[s.provider_code] && (
              <div style={{ fontSize: 12, color: testResults[s.provider_code].ok ? "var(--status-good)" : "var(--status-critical)" }}>
                {testResults[s.provider_code].detail}
              </div>
            )}
            {pullResults[s.provider_code] && (
              <div style={{ fontSize: 12, marginTop: 4 }}>
                {typeof pullResults[s.provider_code] === "string" ? (
                  <span style={{ color: "var(--status-critical)" }}>{pullResults[s.provider_code] as string}</span>
                ) : (
                  <span>
                    Pulled {(pullResults[s.provider_code] as PullResult).usage_records_created} record(s),{" "}
                    {(pullResults[s.provider_code] as PullResult).needs_pricing_rule_count} need pricing,{" "}
                    {(pullResults[s.provider_code] as PullResult).needs_allocation_count} need allocation.
                  </span>
                )}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function firstOfMonth() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

const smallButton: React.CSSProperties = {
  fontSize: 12,
  padding: "6px 10px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface-raised)",
  cursor: "pointer",
};
