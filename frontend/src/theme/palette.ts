// Fixed categorical hue order -- never cycled, never reassigned by rank.
// Matches the CSS custom properties in index.css (light/dark both defined there).
export const CATEGORICAL_SERIES = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
] as const;

export const STATUS_COLORS = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
} as const;

/** Assigns a fixed categorical color to each distinct key, in first-seen
 * order, folding anything past the 8th distinct key into a repeat of slot 8
 * ("Other") rather than generating a new hue. */
export function colorForIndex(index: number): string {
  return CATEGORICAL_SERIES[Math.min(index, CATEGORICAL_SERIES.length - 1)];
}

export function statusForPercentUsed(percentUsed: number): keyof typeof STATUS_COLORS {
  if (percentUsed >= 100) return "critical";
  if (percentUsed >= 80) return "warning";
  return "good";
}
