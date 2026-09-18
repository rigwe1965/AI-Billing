import type { ReactNode } from "react";

export function Card({ title, children, style }: { title?: string; children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: 16,
        ...style,
      }}
    >
      {title && <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-secondary)" }}>{title}</h3>}
      {children}
    </div>
  );
}
