import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { AskInsightResponse } from "../api/types";
import { Card } from "../components/ui/Card";

interface QaPair {
  question: string;
  answer: string;
}

export function InsightsPage() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<QaPair[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<AskInsightResponse>("/api/insights/ask", { question });
      setHistory((prev) => [...prev, { question, answer: result.answer }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to get an answer.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Insights</h2>
      <p style={{ margin: 0, color: "var(--text-muted)", fontSize: 13 }}>
        Ask questions about your spend data in plain English. Answers are AI-generated
        commentary on figures the costing engine already computed — never a source of
        truth for a cost number themselves.
      </p>

      <form onSubmit={handleAsk} style={{ display: "flex", gap: 8 }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Which department spent the most last month?"
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text-primary)",
          }}
        />
        <button type="submit" disabled={loading || !question.trim()} style={{ padding: "8px 16px", cursor: "pointer" }}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </form>

      {error && <div style={{ color: "var(--status-critical)" }}>{error}</div>}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {history
          .slice()
          .reverse()
          .map((qa, i) => (
            <Card key={i}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{qa.question}</div>
              <div style={{ whiteSpace: "pre-wrap" }}>{qa.answer}</div>
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                AI-generated — informational only
              </div>
            </Card>
          ))}
      </div>
    </div>
  );
}
