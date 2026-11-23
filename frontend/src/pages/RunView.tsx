import { useEffect, useMemo, useState } from "react";
import { api, go, inr, Payload, RunDetail, shortTime, Stage, STAGE_ORDER } from "../api";
import { Chip, Conf, Dot, PageHeader } from "../components";

const FIELD_LABELS: Record<string, string> = {
  vendor_name: "Vendor name",
  vendor_gstin: "Vendor GSTIN",
  buyer_gstin: "Billed to GSTIN",
  invoice_no: "Invoice number",
  invoice_date: "Invoice date",
  po_ref: "PO reference",
  taxable_value: "Taxable value",
  cgst: "CGST",
  sgst: "SGST",
  igst: "IGST",
  round_off: "Round off",
  total: "Invoice total",
  bank_name: "Bank",
  bank_account: "Account no.",
  ifsc: "IFSC",
  remarks: "Remarks on invoice",
};
const MONEY = new Set(["taxable_value", "cgst", "sgst", "igst", "round_off", "total"]);

function stagesFromEvents(run: RunDetail | null, live: Record<string, Stage>): Stage[] {
  const done: Record<string, Stage> = {};
  run?.payload?.stages.forEach((s) => (done[s.key] = s));
  run?.events.forEach((e) => {
    if (e.status === "done") done[e.stage] = e.data;
  });
  Object.assign(done, live);
  const runningKey = run?.state === "running"
    ? STAGE_ORDER.find(([k]) => !done[k] || done[k].status === "running")?.[0]
    : undefined;
  return STAGE_ORDER.map(([key, label]) =>
    done[key] && done[key].status !== "running"
      ? done[key]
      : { key, label, status: key === runningKey ? "running" : "pending", summary: "", facts: [], ms: 0, findings: [] }
  );
}

export default function RunView({ id }: { id: string }) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [live, setLive] = useState<Record<string, Stage>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let es: EventSource | null = null;
    let cancelled = false;
    api
      .run(id)
      .then((r) => {
        if (cancelled) return;
        setRun(r);
        if (r.state === "running") {
          es = new EventSource(`/api/runs/${id}/stream`);
          es.onmessage = (m) => {
            const ev = JSON.parse(m.data);
            if (ev.status === "done") setLive((prev) => ({ ...prev, [ev.stage]: ev.data }));
            if (ev.status === "running")
              setLive((prev) => ({ ...prev, [ev.stage]: { ...(prev[ev.stage] || {}), key: ev.stage, status: "running" } as Stage }));
            if (ev.status === "error") setErr(ev.data.error);
          };
          es.addEventListener("end", () => {
            es?.close();
            api.run(id).then((r2) => !cancelled && setRun(r2));
          });
          es.onerror = () => {
            es?.close();
            setTimeout(() => api.run(id).then((r2) => !cancelled && setRun(r2)), 800);
          };
        }
      })
      .catch((e) => setErr(e.message));
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [id]);

  const stages = useMemo(() => stagesFromEvents(run, live), [run, live]);
  const p = run?.payload ?? null;
  const finished = run?.state === "done" && p;
  const doneCount = stages.filter((s) => !["pending", "running"].includes(s.status)).length;

  if (err && !run) return <div className="error">{err}</div>;
  if (!run) return <div className="muted pad">Loading…</div>;

  return (
    <div className="runview">
      <PageHeader
        crumbs={[["Process invoice", "#/"]]}
        title={<span className="mono">{run.file_name}</span>}
        sub={
          <span className="meta">
            <span>Run {run.id}</span>
            <span>{shortTime(run.created_at)}</span>
            {run.method && <span>read with {run.method}</span>}
            {run.duration_ms != null && <span>{run.duration_ms < 1000 ? `${run.duration_ms} ms` : `${(run.duration_ms / 1000).toFixed(1)} s`}</span>}
            {run.parent_run && (
              <a className="link" href={`#/run/${run.parent_run}`}>
                re-run of {run.parent_run}
              </a>
            )}
            {run.children.length > 0 && (
              <a className="link warnlink" href={`#/run/${run.children[run.children.length - 1]}`}>
                superseded by a later re-run →
              </a>
            )}
          </span>
        }
        actions={
          <a className="btn ghost" href="#/">
            Process another
          </a>
        }
      />

      <div className="split">
        <div className="doc">
          <div className="dochead">
            <span>Invoice as received</span>
            <a className="link" href={`/api/runs/${id}/file`} target="_blank" rel="noreferrer">
              open original ↗
            </a>
          </div>
          <div className="docimg">
            <img src={`/api/runs/${id}/preview.png`} alt="invoice preview" />
          </div>
        </div>

        <div className="flow">
          {finished ? (
            <DecisionCard run={run} p={p!} />
          ) : (
            <div className="card progress">
              <div className="bar">
                <span style={{ width: `${(doneCount / STAGE_ORDER.length) * 100}%` }} />
              </div>
              <div>{err ? <span className="error">{err}</span> : `Working… ${doneCount} of ${STAGE_ORDER.length} stages`}</div>
            </div>
          )}

          <ol className="stages">
            {stages.map((s, i) => {
              const hasIssue = s.findings?.some((f) => f.level !== "note");
              const isOpen = open[s.key] ?? (finished ? hasIssue : false);
              const clickable = s.facts?.length || s.findings?.length;
              return (
                <li key={s.key} className={`stage ${s.status}`}>
                  <div className="srow" onClick={() => clickable && setOpen({ ...open, [s.key]: !isOpen })}>
                    <span className="num">{String(i + 1).padStart(2, "0")}</span>
                    <Dot status={s.status} />
                    <span className="slabel">{s.label}</span>
                    <span className="ssum">{s.status === "running" ? "running…" : s.summary}</span>
                    <span className="sms">{s.ms ? `${s.ms} ms` : ""}</span>
                    {clickable ? <span className="caret">{isOpen ? "–" : "+"}</span> : <span className="caret" />}
                  </div>
                  {isOpen && (
                    <div className="sbody">
                      {s.facts?.length > 0 && (
                        <dl>
                          {s.facts.map(([k, v], j) => (
                            <div key={j}>
                              <dt>{k}</dt>
                              <dd>{v}</dd>
                            </div>
                          ))}
                        </dl>
                      )}
                      {s.findings?.map((f, j) => (
                        <div key={j} className={`finding ${f.level}`}>
                          <b>{f.title}</b>
                          {f.detail && <p>{f.detail}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      {finished && <Details p={p!} />}
    </div>
  );
}

function DecisionCard({ run, p }: { run: RunDetail; p: Payload }) {
  const r = p.result;
  const blocking = r.reasons.filter((f) => f.level !== "note");
  const notes = r.reasons.filter((f) => f.level === "note");
  const ext = p.extraction?.fields || {};
  const [vals, setVals] = useState<Record<string, string>>(() =>
    Object.fromEntries((p.needs_confirmation || []).map((k) => [k, String(ext[k]?.value ?? "")]))
  );
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const superseded = run.children.length > 0;
  const shown = showAll ? blocking : blocking.slice(0, 1);

  async function rerun() {
    setBusy(true);
    const { id } = await api.rerun(run.id, { ...p.overrides, ...vals });
    go(`#/run/${id}`);
  }

  return (
    <div className={`card decision ${r.decision.toLowerCase()}`}>
      <div className="dtop">
        <Chip d={r.decision} />
        <span className="owner">
          {r.decision === "HOLD" || r.decision === "REJECT" ? `With ${r.owner}` : "Ready for payment run"}
        </span>
      </div>
      <h2>{r.headline}</h2>
      {r.action && (
        <p className="next">
          <span>Next step</span>
          {r.action}
        </p>
      )}

      {blocking.length > 0 && (
        <ul className="reasons">
          {shown.map((f, i) => (
            <li key={i} className={f.level}>
              <div className="rt">
                <b>{f.title}</b>
                <span className="who">{f.owner}</span>
              </div>
              <p>{f.detail}</p>
            </li>
          ))}
          {blocking.length > 1 && (
            <li className="more">
              <button className="linkbtn" onClick={() => setShowAll(!showAll)}>
                {showAll ? "Show only the main reason" : `Show ${blocking.length - 1} more issue${blocking.length > 2 ? "s" : ""} found on this invoice`}
              </button>
            </li>
          )}
        </ul>
      )}
      {notes.length > 0 && (
        <ul className="reasons notes">
          {notes.map((f, i) => (
            <li key={i}>
              <div className="rt">
                <b>{f.title}</b>
              </div>
              <p>{f.detail}</p>
            </li>
          ))}
        </ul>
      )}

      {p.needs_confirmation?.length > 0 && !superseded && (
        <div className="confirm">
          <div className="ctitle">Confirm what the scan says</div>
          {p.needs_confirmation.map((k) => (
            <label key={k}>
              <span>{FIELD_LABELS[k]}</span>
              <input value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
              <em>read as “{String(ext[k]?.value ?? "")}”, {Math.round((ext[k]?.confidence || 0) * 100)}%</em>
            </label>
          ))}
          <button className="btn" disabled={busy} onClick={rerun}>
            {busy ? "Re-running…" : "Confirm and re-run"}
          </button>
        </div>
      )}
      {Object.keys(p.overrides || {}).length > 0 && (
        <p className="muted small">
          Values confirmed by AP on this run: {Object.entries(p.overrides).map(([k, v]) => `${FIELD_LABELS[k] || k} = ${v}`).join(", ")}
        </p>
      )}
    </div>
  );
}

function Details({ p }: { p: Payload }) {
  const f = p.extraction?.fields || {};
  const [copied, setCopied] = useState(false);
  const bal = p.po_balance;
  return (
    <div className="details">
      <section className="card flush">
        <h3 className="cardh">What was read from the invoice</h3>
        <table className="grid fields">
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
              <th>Confidence</th>
              <th>Read from</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(FIELD_LABELS)
              .filter((k) => f[k] && f[k].value !== null)
              .map((k) => (
                <tr key={k} className={p.needs_confirmation?.includes(k) ? "flag" : ""}>
                  <td>{FIELD_LABELS[k]}</td>
                  <td className="mono">{MONEY.has(k) ? inr(Number(f[k].value)) : String(f[k].value)}</td>
                  <td>
                    <Conf v={f[k].confidence} />
                  </td>
                  <td className="src">{f[k].source}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>

      {p.line_table?.length > 0 && (
        <section className="card flush">
          <h3 className="cardh">Lines against PO and goods receipts</h3>
          <table className="grid lines">
            <thead>
              <tr>
                <th>Invoice line</th>
                <th>PO line</th>
                <th className="right">Billed qty</th>
                <th className="right">Received</th>
                <th className="right">Billed before</th>
                <th className="right">Open</th>
                <th className="right">Rate</th>
                <th className="right">PO rate</th>
                <th className="right">Var.</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {p.line_table.map((l, i) => (
                <tr key={i} className={l.status === "ok" ? "" : l.status.includes("within") ? "soft" : "bad"}>
                  <td>{l.description}</td>
                  <td className="muted">{l.po_item ? `${l.po_line}. ${l.po_item}` : "–"}</td>
                  <td className="right mono">{l.inv_qty}</td>
                  <td className="right mono">{l.received ?? "–"}</td>
                  <td className="right mono">{l.billed_before ?? "–"}</td>
                  <td className="right mono">{l.open_qty ?? "–"}</td>
                  <td className="right mono">{inr(l.inv_rate)}</td>
                  <td className="right mono">{l.po_rate != null ? inr(l.po_rate) : "–"}</td>
                  <td className="right mono">{l.var_pct != null ? `${l.var_pct > 0 ? "+" : ""}${l.var_pct.toFixed(2)}%` : "–"}</td>
                  <td>{l.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {bal && (
        <section className="card">
          <div className="cardrow">
            <h3>{bal.po_no} balance</h3>
            <a className="link small" href={`#/pos/${bal.po_no}`}>
              Open PO →
            </a>
          </div>
          <BalanceBar bal={bal} />
        </section>
      )}

      {p.result.vendor_message && (
        <section>
          <h3>Draft reply to vendor</h3>
          <div className="mail">
            <div className="subj">Subject: {p.result.vendor_message.subject}</div>
            <pre>{p.result.vendor_message.body}</pre>
            <button
              className="btn small ghost"
              onClick={() => {
                navigator.clipboard.writeText(`Subject: ${p.result.vendor_message!.subject}\n\n${p.result.vendor_message!.body}`);
                setCopied(true);
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function BalanceBar({ bal }: { bal: NonNullable<Payload["po_balance"]> }) {
  const max = Math.max(bal.value, bal.billed_before + bal.this_invoice);
  const w = (x: number) => `${(Math.max(0, x) / max) * 100}%`;
  const over = bal.remaining_after < 0;
  return (
    <div className="balance">
      <div className="track">
        <span className="billed" style={{ width: w(bal.billed_before) }} />
        <span className={`this ${over ? "over" : ""}`} style={{ width: w(bal.this_invoice) }} />
        <i className="limit" style={{ left: w(bal.value) }} />
      </div>
      <div className="legend">
        <span>
          <b className="sw billed" /> Billed before {inr(bal.billed_before, 0)}
        </span>
        <span>
          <b className={`sw this ${over ? "over" : ""}`} /> This invoice {inr(bal.this_invoice, 0)}
        </span>
        <span>PO value {inr(bal.value, 0)}</span>
        <span className={over ? "neg" : ""}>
          {over ? `Over by ${inr(-bal.remaining_after, 0)}` : `Left ${inr(bal.remaining_after, 0)}`}
        </span>
      </div>
    </div>
  );
}
