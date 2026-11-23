import { ReactNode, useEffect, useState } from "react";
import { Decision, DECISION_TEXT } from "./api";

export function Chip({ d }: { d: Decision | null }) {
  if (!d) return <span className="chip run">Running</span>;
  return <span className={`chip ${d.toLowerCase()}`}>{DECISION_TEXT[d]}</span>;
}

export function Status({ s }: { s: string }) {
  const map: Record<string, string> = {
    open: "Open", closed: "Closed", active: "Active", blocked: "Blocked", paid: "Paid",
    approved: "Approved", on_hold: "On hold",
  };
  return <span className={`status ${s}`}>{map[s] || s}</span>;
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

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function PageHeader({
  title, sub, crumbs, actions,
}: { title: ReactNode; sub?: ReactNode; crumbs?: [string, string][]; actions?: ReactNode }) {
  return (
    <div className="pagehead">
      <div>
        {crumbs && (
          <div className="crumbs">
            {crumbs.map(([label, href], i) => (
              <span key={i}>
                <a href={href}>{label}</a>
                <span className="sep">/</span>
              </span>
            ))}
          </div>
        )}
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions && <div className="headactions">{actions}</div>}
    </div>
  );
}

export function Modal({
  title, sub, onClose, children, footer, wide,
}: { title: string; sub?: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", k);
      document.body.style.overflow = "";
    };
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true">
        <div className="mhead">
          <div>
            <h2>{title}</h2>
            {sub && <p>{sub}</p>}
          </div>
          <button className="iconbtn" onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </div>
        <div className="mbody">{children}</div>
        {footer && <div className="mfoot">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({
  label, error, hint, children, span,
}: { label: string; error?: string; hint?: ReactNode; children: ReactNode; span?: number }) {
  return (
    <label className={`field ${error ? "bad" : ""}`} style={span ? { gridColumn: `span ${span}` } : undefined}>
      <span className="flabel">{label}</span>
      {children}
      {error ? <span className="ferr">{error}</span> : hint ? <span className="fhint">{hint}</span> : null}
    </label>
  );
}

// ---- toasts: a tiny global queue, no context needed
type Toast = { id: number; text: string; kind: "ok" | "err" };
let push: (t: Toast) => void = () => {};
let seq = 0;
export function toast(text: string, kind: "ok" | "err" = "ok") {
  push({ id: ++seq, text, kind });
}
export function Toasts() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => {
    push = (t) => {
      setItems((xs) => [...xs, t]);
      setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== t.id)), 3800);
    };
  }, []);
  return (
    <div className="toasts">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`}>
          <Icon name={t.kind === "ok" ? "check" : "alert"} />
          {t.text}
        </div>
      ))}
    </div>
  );
}

// ---- icons: a handful of simple strokes, drawn to match
const PATHS: Record<string, string> = {
  upload: "M12 15V4m0 0-4 4m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3",
  runs: "M4 6h16M4 12h16M4 18h10",
  po: "M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm7 0v5h5M9 13h6M9 17h6",
  vendors: "M4 20V9l8-5 8 5v11M9 20v-6h6v6M3 20h18",
  settings: "M4 7h10M18 7h2M4 17h4M12 17h8M14 5v4M8 15v4",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5 10 17 19 7",
  alert: "M12 8v5m0 3.5v.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  truck: "M3 6h11v10H3zM14 10h4l3 3v3h-7M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm10 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  edit: "M4 20h4L19 9l-4-4L4 16v4Zm9-13 4 4",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  back: "M19 12H5m5-5-5 5 5 5",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm9 2-4-4",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  trash: "M5 7h14M10 11v6m4-6v6M6 7l1 13h10l1-13M9 7V4h6v3",
};
export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="icon">
      <path d={PATHS[name]} />
    </svg>
  );
}
