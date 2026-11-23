import { useEffect, useRef, useState } from "react";
import { api, go, inr, RunRow, shortTime } from "../api";
import { Chip, Empty, Icon, PageHeader } from "../components";

export default function Inbox() {
  const [samples, setSamples] = useState<{ name: string; note: string }[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.samples().then(setSamples).catch(() => {});
    api.runs().then((r) => setRuns(r.slice(0, 6))).catch(() => {});
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
    <div className="page">
      <PageHeader
        title="Process an invoice"
        sub="Upload a vendor invoice. It's read, checked against the PO, goods receipts and everything already billed, and comes back with a decision and the reasons for it."
      />
      <section>
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
          <span className="dropicon">
            <Icon name="upload" size={22} />
          </span>
          {busy ? (
            <b>Starting {busy}…</b>
          ) : (
            <>
              <b>Drop an invoice here, or click to choose a file</b>
              <span className="muted small">PDF, JPG or PNG · scanned and phone photos work too</span>
            </>
          )}
        </div>
        {err && <div className="error">{err}</div>}

        <h2 className="sechead">Recent runs</h2>
        {runs.length === 0 ? (
          <Empty>Nothing processed yet. Upload an invoice above or run one of the samples below.</Empty>
        ) : (
          <div className="tablewrap"><table className="grid clickable">
            <thead>
              <tr>
                <th>When</th>
                <th>File</th>
                <th>Vendor</th>
                <th>Invoice</th>
                <th className="right">Amount</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} onClick={() => go(`#/run/${r.id}`)}>
                  <td className="muted nowrap">{shortTime(r.created_at)}</td>
                  <td className="mono">{r.file_name}</td>
                  <td>{r.vendor_name || "–"}</td>
                  <td className="mono">{r.invoice_no || "–"}</td>
                  <td className="right mono">{inr(r.total, 0)}</td>
                  <td>
                    <Chip d={r.state === "done" ? r.decision : null} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        {runs.length > 0 && (
          <p>
            <a href="#/dashboard" className="link">
              All runs and totals on the dashboard →
            </a>
          </p>
        )}

        <h2 className="sechead">
          Sample invoices <span className="muted small">seven test cases, run them in order</span>
        </h2>
        <div className="tablewrap"><table className="grid samples">
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
        </table></div>
      </section>
    </div>
  );
}
