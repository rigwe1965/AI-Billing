import { STATUS_COLORS, statusForPercentUsed } from "../../theme/palette";

const STATUS_LABEL: Record<string, string> = {
  good: "On track",
  warning: "Near budget",
  critical: "Over budget",
};

export function BudgetProgressBar({
  departmentName,
  period,
  amount,
  currentSpend,
  percentUsed,
  currency,
}: {
  departmentName: string;
  period: string;
  amount: number;
  currentSpend: number;
  percentUsed: number;
  currency: string;
}) {
  const status = statusForPercentUsed(percentUsed);
  const barWidth = Math.min(percentUsed, 100);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
        <span>
          <strong>{departmentName}</strong> <span style={{ color: "var(--text-muted)" }}>({period})</span>
        </span>
        <span style={{ color: `var(--status-${status})`, fontWeight: 600 }}>
          {STATUS_LABEL[status]} &middot; {percentUsed.toFixed(1)}%
        </span>
      </div>
      <div style={{ height: 10, borderRadius: 4, background: "var(--gridline)", overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${barWidth}%`,
            background: STATUS_COLORS[status],
            borderRadius: 4,
            transition: "width 0.3s ease",
          }}
        />
      </div>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
        {currency} {currentSpend.toFixed(2)} of {amount.toFixed(2)} spent
      </div>
    </div>
  );
}
