import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { BudgetStatus, CostSummaryRow, UnpricedUsageRow } from "../api/types";
import { Card } from "../components/ui/Card";
import { StatTile } from "../components/ui/StatTile";
import { SpendByCategoryChart } from "../components/charts/SpendByCategoryChart";
import { TrendLineChart } from "../components/charts/TrendLineChart";
import { BudgetProgressBar } from "../components/ui/BudgetProgressBar";
import { useAuth } from "../auth/AuthContext";

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<CostSummaryRow[] | null>(null);
  const [unpriced, setUnpriced] = useState<UnpricedUsageRow[]>([]);
  const [needsAllocation, setNeedsAllocation] = useState<UnpricedUsageRow[]>([]);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<CostSummaryRow[]>("/api/costs/summary"),
      api.get<UnpricedUsageRow[]>("/api/costs/unpriced"),
      api.get<UnpricedUsageRow[]>("/api/costs/needs-allocation"),
      api.get<BudgetStatus[]>("/api/budgets/status"),
    ])
      .then(([s, u, n, b]) => {
        setSummary(s);
        setUnpriced(u);
        setNeedsAllocation(n);
        setBudgetStatus(b);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <div style={{ color: "var(--status-critical)" }}>{error}</div>;
  if (summary === null) return <div style={{ color: "var(--text-muted)" }}>Loading...</div>;

  const currency = summary[0]?.currency ?? "USD";
  const totalSpend = summary.reduce((sum, r) => sum + parseFloat(r.total_amount), 0);

  const byDepartment = aggregateBy(summary, (r) => r.department ?? "(unallocated)");
  const byProvider = aggregateBy(summary, (r) => r.provider);

  const periods = [...new Set(summary.map((r) => r.period))].sort();
  const departments = [...new Set(summary.map((r) => r.department ?? "(unallocated)"))];
  const trendData = periods.map((period) => {
    const point: Record<string, string | number> = { period };
    for (const dept of departments) {
      point[dept] = summary
        .filter((r) => r.period === period && (r.department ?? "(unallocated)") === dept)
        .reduce((sum, r) => sum + parseFloat(r.total_amount), 0);
    }
    return point;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Dashboard</h2>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <StatTile label="Total spend (all time)" value={`${currency} ${totalSpend.toFixed(2)}`} />
        <StatTile label="Departments" value={String(departments.length)} />
        <StatTile label="Providers" value={String(byProvider.length)} />
      </div>

      {(unpriced.length > 0 || needsAllocation.length > 0) && (
        <Card title="Needs attention" style={{ borderColor: "var(--status-warning)" }}>
          {unpriced.length > 0 && (
            <p style={{ margin: "0 0 8px", fontSize: 13 }}>
              <strong>{unpriced.length}</strong> usage record(s) have no pricing rule configured -- their cost is
              not counted in totals above until a rate is added under Pricing Rates.
            </p>
          )}
          {needsAllocation.length > 0 && (
            <p style={{ margin: 0, fontSize: 13 }}>
              <strong>{needsAllocation.length}</strong> usage record(s) have no department resolved -- see
              Allocation Mapping to assign them.
            </p>
          )}
        </Card>
      )}

      {budgetStatus.length > 0 && (
        <Card title="Budget status">
          {budgetStatus.map((b) => (
            <BudgetProgressBar
              key={b.budget_id}
              departmentName={b.department_name}
              period={b.period}
              amount={parseFloat(b.amount)}
              currentSpend={parseFloat(b.current_spend)}
              percentUsed={parseFloat(b.percent_used)}
              currency={b.currency}
            />
          ))}
        </Card>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card title="Spend by department">
          <SpendByCategoryChart data={byDepartment} currency={currency} />
        </Card>
        <Card title="Spend by provider">
          <SpendByCategoryChart data={byProvider} currency={currency} />
        </Card>
      </div>

      <Card title={user?.role === "admin_finance" ? "Monthly trend by department" : "Monthly trend"}>
        <TrendLineChart data={trendData} seriesNames={departments} currency={currency} />
      </Card>
    </div>
  );
}

function aggregateBy(rows: CostSummaryRow[], keyFn: (r: CostSummaryRow) => string) {
  const totals = new Map<string, number>();
  for (const row of rows) {
    const key = keyFn(row);
    totals.set(key, (totals.get(key) ?? 0) + parseFloat(row.total_amount));
  }
  return [...totals.entries()].map(([name, value]) => ({ name, value }));
}
