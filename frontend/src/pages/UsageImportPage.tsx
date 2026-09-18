import { useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { CsvImportResult } from "../api/types";
import { Card } from "../components/ui/Card";

export function UsageImportPage() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;

    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.postForm<CsvImportResult>("/api/usage/import-csv", form);
      setResult(res);
      if (fileInput.current) fileInput.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 640 }}>
      <h2 style={{ margin: 0 }}>Usage Import</h2>

      <Card title="Upload a usage CSV">
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input ref={fileInput} type="file" accept=".csv" required />
          <button
            type="submit"
            disabled={submitting}
            style={{ alignSelf: "flex-start", padding: "8px 16px", borderRadius: 6, border: "none", background: "var(--series-1)", color: "white", fontWeight: 600, cursor: "pointer" }}
          >
            {submitting ? "Importing..." : "Import"}
          </button>
        </form>

        {error && <p style={{ color: "var(--status-critical)", marginTop: 12 }}>{error}</p>}

        {result && (
          <div style={{ marginTop: 16, fontSize: 13 }}>
            <p>
              Imported <strong>{result.usage_records_created}</strong> usage record(s), created{" "}
              <strong>{result.cost_line_items_created}</strong> cost line item(s).
            </p>
            {result.needs_pricing_rule_count > 0 && (
              <p style={{ color: "var(--status-warning)" }}>
                {result.needs_pricing_rule_count} record(s) have no matching pricing rule -- their cost was not
                estimated. Add a rate under Pricing Rates, then re-import or wait for the next reprocess.
              </p>
            )}
          </div>
        )}
      </Card>

      <Card title="CSV format">
        <p style={{ fontSize: 13, margin: "0 0 8px" }}>
          Required columns: <code>provider_code, sku_code, quantity, unit, period_start, period_end</code>
          <br />
          Optional: <code>department_code, tag_value, api_key_label</code>
        </p>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
          Dates use YYYY-MM-DD. If you're a department lead, leave department_code blank or set it to your own
          department -- other departments will be rejected.
        </p>
      </Card>
    </div>
  );
}
