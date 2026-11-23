import { useEffect, useState } from "react";
import { api } from "../api";

const ROWS: [string, string, string][] = [
  ["price_tolerance_pct", "Price tolerance (%)", "How far a unit price may sit above the PO before it needs approval."],
  ["line_variance_cap", "Max variance per line (₹)", "Even inside the % tolerance, no single line may go over by more than this."],
  ["total_rounding", "Rounding allowance (₹)", "Allowed gap between the computed and the printed total."],
  ["duplicate_window_days", "Duplicate window (days)", "Same vendor and amount inside this window is flagged as a possible duplicate."],
  ["confidence_floor", "Confidence floor (0–1)", "Critical fields read below this are sent to a person to confirm."],
  ["po_inference_min_score", "PO inference: min score", "When no PO is printed, the best candidate must score at least this."],
  ["po_inference_margin", "PO inference: margin", "…and beat the next candidate by this much, otherwise it's held."],
];

export default function Settings({ health }: { health: { llm: string | null; ocr: boolean } | null }) {
  const [s, setS] = useState<Record<string, any> | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.settings().then(setS);
  }, []);

  async function save() {
    setS(await api.saveSettings(s!));
    setMsg("Saved. New runs use these values.");
  }

  if (!s) return <div className="muted pad">Loading…</div>;
  return (
    <div className="dash settings">
      <h1>Settings</h1>
      <section>
        <h3>Tolerances</h3>
        <table className="grid form">
          <tbody>
            {ROWS.map(([k, label, help]) => (
              <tr key={k}>
                <td>
                  <b>{label}</b>
                  <div className="muted small">{help}</div>
                </td>
                <td className="right">
                  <input type="number" step="any" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} />
                </td>
              </tr>
            ))}
            <tr>
              <td>
                <b>Use LLM for extraction</b>
                <div className="muted small">
                  {health?.llm
                    ? `Key found: ${health.llm}. Turn off to force the rules parser.`
                    : "No API key set on the server, so the rules parser (and OCR for scans) is used."}
                </div>
              </td>
              <td className="right">
                <input type="checkbox" checked={!!s.use_llm} onChange={(e) => setS({ ...s, use_llm: e.target.checked })} />
              </td>
            </tr>
          </tbody>
        </table>
        <div className="actions">
          <button className="btn" onClick={save}>
            Save
          </button>
          <span className="muted">{msg}</span>
        </div>
      </section>

      <section>
        <h3>Demo data</h3>
        <p className="muted">
          Reset puts the vendor master, POs, goods receipts and the ledger back to their starting state and clears the run
          history. Use it before a demo so every test invoice behaves as expected.
        </p>
        <div className="actions">
          <button
            className="btn ghost"
            onClick={async () => {
              await api.reset();
              setS(await api.settings());
              setMsg("Demo data reset.");
            }}
          >
            Reset demo data
          </button>
          <button
            className="btn ghost"
            onClick={async () => {
              await api.clearCache();
              setMsg("Extraction cache cleared. Next runs read the files again.");
            }}
          >
            Clear extraction cache
          </button>
        </div>
      </section>
    </div>
  );
}
