import { useEffect, useRef, useState } from "react";
import { api, go, inr, RunRow, shortTime } from "../api";
import { Chip, Empty } from "../components";

export default function Inbox() {
  const [samples, setSamples] = useState<{ name: string; note: string }[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => {});
    api.runs().then((r) => setRuns(r.slice(0, 8))).catch(() => {});
  }, []);

  async function start(p: Promise<{ id: string }>, label: string) {
    setBusy(label);
    setErr(null);
    try {
      const { id } = await p;
      go(`#/run/${id}`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(null);
    }
  }

  function onFiles(files: FileList | null) {
    if (!files || !files.length) return;
    start(api.upload(files[0]), files[0].name);
  }

  return (
    <div className="inbox">
      <section>
        <h1>Process an invoice</h1>
        <p className="lede">
          Drop a vendor invoice (PDF or photo). It is read, checked against the PO, goods receipts and everything
          already billed, and comes back with a decision and the reasons for it.
        </p>
        <div
          className={`drop ${drag ? "over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            onFiles(e.dataTransfer.files);
          }}
          onClick={() => input.current?.click()}
        >
          <input ref={input} type="file" accept=".pdf,.png,.jpg,.jpeg" hidden onChange={(e) => onFiles(e.target.files)} />
          {busy ? <span>Starting {busy}…</span> : <span>Drop invoice here, or click to choose a file</span>}
        </div>
        {err && <div className="error">{err}</div>}

        <h2>Test invoices</h2>
        <table className="grid samples">
          <tbody>
            {samples.map((s) => (
              <tr key={s.name}>
                <td className="mono">{s.name}</td>
                <td className="muted">{s.note}</td>
                <td className="right">
                  <a href={`/api/samples/${s.name}`} target="_blank" rel="noreferrer" className="link">
                    view
                  </a>
                  <button className="btn small" disabled={!!busy} onClick={() => start(api.runSample(s.name), s.name)}>
                    Run
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <aside>
        <h2>Recent runs</h2>
        {runs.length === 0 && <Empty>Nothing processed yet.</Empty>}
        <ul className="recent">
          {runs.map((r) => (
            <li key={r.id} onClick={() => go(`#/run/${r.id}`)}>
              <div className="row1">
                <span>{r.vendor_name || r.file_name}</span>
                <Chip d={r.state === "done" ? r.decision : null} />
              </div>
              <div className="row2">
                <span className="mono">{r.invoice_no || "–"}</span>
                <span>{inr(r.total, 0)}</span>
                <span className="muted">{shortTime(r.created_at)}</span>
              </div>
            </li>
          ))}
        </ul>
        {runs.length > 0 && (
          <a href="#/dashboard" className="link">
            All runs →
          </a>
        )}
      </aside>
    </div>
  );
}
