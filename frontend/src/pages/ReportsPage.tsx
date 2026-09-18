import { useState } from "react";
import { downloadFile } from "../api/client";
import { Card } from "../components/ui/Card";

export function ReportsPage() {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(kind: "excel" | "pdf") {
    setDownloading(kind);
    setError(null);
    try {
      const ext = kind === "excel" ? "xlsx" : "pdf";
      await downloadFile(`/api/reports/${kind}`, `ai_spend_report.${ext}`);
    } catch {
      setError("Failed to download report");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 560 }}>
      <h2 style={{ margin: 0 }}>Reports</h2>
      <Card title="Export">
        <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Reports reflect only your own department's data if you're a department lead, or every department if
          you're admin/finance.
        </p>
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={() => handleDownload("excel")} disabled={downloading !== null} style={buttonStyle}>
            {downloading === "excel" ? "Downloading..." : "Download Excel (.xlsx)"}
          </button>
          <button onClick={() => handleDownload("pdf")} disabled={downloading !== null} style={buttonStyle}>
            {downloading === "pdf" ? "Downloading..." : "Download PDF summary"}
          </button>
        </div>
        {error && <p style={{ color: "var(--status-critical)", marginTop: 12 }}>{error}</p>}
      </Card>
    </div>
  );
}

const buttonStyle: React.CSSProperties = {
  padding: "10px 16px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--surface)",
  cursor: "pointer",
  fontWeight: 600,
};
