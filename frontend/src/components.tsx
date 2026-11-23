import { Decision, DECISION_TEXT } from "./api";

export function Chip({ d }: { d: Decision | null }) {
  if (!d) return <span className="chip run">Running</span>;
  return <span className={`chip ${d.toLowerCase()}`}>{DECISION_TEXT[d]}</span>;
}

export function Dot({ status }: { status: string }) {
  return <span className={`dot ${status}`} />;
}

export function Conf({ v }: { v: number }) {
  const pct = Math.round(v * 100);
  const cls = v >= 0.85 ? "hi" : v >= 0.75 ? "mid" : "lo";
  return (
    <span className={`conf ${cls}`} title={`${pct}% confidence`}>
      <span className="cbar">
        <i style={{ width: `${pct}%` }} />
      </span>
      <em>{pct}</em>
    </span>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
