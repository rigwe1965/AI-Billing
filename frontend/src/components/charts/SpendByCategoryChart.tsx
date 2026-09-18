import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colorForIndex } from "../../theme/palette";

interface DataPoint {
  name: string;
  value: number;
}

export function SpendByCategoryChart({ data, currency }: { data: DataPoint[]; currency: string }) {
  if (data.length === 0) {
    return <EmptyState />;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
        <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={false} tickLine={false} width={70} />
        <Tooltip
          cursor={{ fill: "var(--gridline)", opacity: 0.4 }}
          contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }}
          formatter={(value) => [`${currency} ${Number(value).toFixed(2)}`, "Spend"]}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={56}>
          {data.map((_, i) => (
            <Cell key={i} fill={colorForIndex(i)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function EmptyState() {
  return (
    <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 13 }}>
      No data yet
    </div>
  );
}
