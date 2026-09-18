import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { colorForIndex } from "../../theme/palette";
import { EmptyState } from "./SpendByCategoryChart";

type TrendPoint = Record<string, string | number>;

export function TrendLineChart({ data, seriesNames, currency }: { data: TrendPoint[]; seriesNames: string[]; currency: string }) {
  if (data.length === 0) {
    return <EmptyState />;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid stroke="var(--gridline)" vertical={false} />
        <XAxis dataKey="period" tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={{ stroke: "var(--baseline)" }} tickLine={false} />
        <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} axisLine={false} tickLine={false} width={70} />
        <Tooltip
          contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }}
          formatter={(value) => `${currency} ${Number(value).toFixed(2)}`}
        />
        {seriesNames.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {seriesNames.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={colorForIndex(i)}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
