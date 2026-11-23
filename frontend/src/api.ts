export type Decision = "AUTO_APPROVE" | "APPROVE_WITH_NOTE" | "HOLD" | "REJECT";

export interface Finding {
  code: string;
  level: "reject" | "hold" | "note";
  owner: string;
  title: string;
  detail: string;
  action: string;
  stage: string;
}

export interface Stage {
  key: string;
  label: string;
  status: "ok" | "warn" | "fail" | "skip" | "running" | "pending";
  summary: string;
  facts: [string, string][];
  ms: number;
  findings: Finding[];
}

export interface Field {
  value: string | number | null;
  confidence: number;
  source: string | null;
}

export interface LineRow {
  description: string;
  inv_qty: number;
  inv_rate: number;
  amount: number;
  po_line?: number;
  po_item?: string;
  po_qty?: number;
  po_rate?: number;
  received?: number;
  billed_before?: number;
  open_qty?: number;
  var_pct?: number;
  status: string;
}

export interface Payload {
  result: {
    decision: Decision;
    label: string;
    owner: string;
    headline: string;
    action: string;
    other_issues: number;
    reasons: Finding[];
    vendor_message: { subject: string; body: string } | null;
  };
  stages: Stage[];
  extraction: { fields: Record<string, Field>; lines: any[] };
  method: string;
  line_table: LineRow[];
  po_balance: { po_no: string; value: number; billed_before: number; this_invoice: number; remaining_after: number } | null;
  po_candidates: { po_no: string; score: number }[] | null;
  needs_confirmation: string[];
  invoice: Record<string, any>;
  overrides: Record<string, string>;
}

export interface RunRow {
  id: string;
  created_at: string;
  finished_at: string | null;
  file_name: string;
  state: "running" | "done" | "error";
  decision: Decision | null;
  owner: string | null;
  headline: string | null;
  vendor_name: string | null;
  invoice_no: string | null;
  po_no: string | null;
  total: number | null;
  method: string | null;
  duration_ms: number | null;
  parent_run: string | null;
}

export interface RunDetail extends RunRow {
  payload: Payload | null;
  events: { seq: number; stage: string; status: string; data: any }[];
  children: string[];
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  health: () => j<{ llm: string | null; ocr: boolean; stage_delay_ms: number }>("/api/health"),
  samples: () => j<{ name: string; note: string; size: number }[]>("/api/samples"),
  runs: () => j<RunRow[]>("/api/runs"),
  run: (id: string) => j<RunDetail>(`/api/runs/${id}`),
  stats: () => j<any>("/api/stats"),
  pos: () => j<any[]>("/api/pos"),
  settings: () => j<Record<string, any>>("/api/settings"),
  saveSettings: (s: Record<string, any>) =>
    j<Record<string, any>>("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s) }),
  runSample: (name: string) => j<{ id: string }>(`/api/runs?sample=${encodeURIComponent(name)}`, { method: "POST" }),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return j<{ id: string }>("/api/runs", { method: "POST", body: fd });
  },
  rerun: (id: string, overrides: Record<string, string>) =>
    j<{ id: string }>(`/api/runs/${id}/rerun`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overrides }),
    }),
  reset: () => j("/api/reset", { method: "POST" }),
  clearCache: () => j("/api/cache/clear", { method: "POST" }),
};

export function inr(x: number | null | undefined, decimals = 2) {
  if (x === null || x === undefined || isNaN(x)) return "–";
  return "₹" + x.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function shortTime(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });
}

export const DECISION_TEXT: Record<Decision, string> = {
  AUTO_APPROVE: "Auto-approved",
  APPROVE_WITH_NOTE: "Approved, note",
  HOLD: "On hold",
  REJECT: "Rejected",
};

export const STAGE_ORDER: [string, string][] = [
  ["intake", "Intake"],
  ["extract", "Extract fields"],
  ["normalise", "Normalise"],
  ["validate", "Validate document"],
  ["vendor", "Match vendor"],
  ["po", "Find PO"],
  ["lines", "Match lines to PO & GRN"],
  ["history", "Check history"],
  ["decide", "Decide"],
  ["record", "Record"],
];

export function go(hash: string) {
  window.location.hash = hash;
}
