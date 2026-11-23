import { useEffect, useState } from "react";
import { api, ApiError, fmtDate, go, inr, today } from "../api";
import { Empty, Field, Icon, Modal, PageHeader, Status, toast } from "../components";

export default function PODetail({ no }: { no: string }) {
  const [po, setPo] = useState<any>(null);
  const [err, setErr] = useState("");
  const [receiving, setReceiving] = useState(false);

  const load = () => api.po(no).then(setPo).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
  }, [no]);

  if (err) return <div className="page"><Empty>{err}</Empty></div>;
  if (!po) return <div className="page muted pad">Loading…</div>;

  const ordered = po.lines.reduce((a: number, l: any) => a + l.value, 0);
  const received = po.lines.reduce((a: number, l: any) => a + l.received * l.rate, 0);
  const toReceive = po.lines.some((l: any) => l.received < l.qty);

  async function toggle() {
    const next = po.status === "open" ? "closed" : "open";
    try {
      setPo(await api.setPoStatus(no, next));
      toast(next === "closed" ? `${no} closed. New invoices against it will be held.` : `${no} reopened`);
    } catch (e: any) {
      toast(e.message, "err");
    }
  }

  return (
    <div className="page">
      <PageHeader
        crumbs={[["Purchase orders", "#/pos"]]}
        title={
          <span className="titlewith">
            <span className="mono">{po.po_no}</span> <Status s={po.status} />
          </span>
        }
        sub={
          <>
            <a href={`#/vendors/${po.vendor_id}`} className="link">{po.vendor}</a> · raised {fmtDate(po.po_date)}
          </>
        }
        actions={
          <>
            <button className="btn ghost" onClick={toggle}>
              {po.status === "open" ? "Close PO" : "Reopen PO"}
            </button>
            {po.status === "open" && toReceive && (
              <button className="btn" onClick={() => setReceiving(true)}>
                <Icon name="truck" /> Record goods receipt
              </button>
            )}
          </>
        }
      />

      <div className="stats">
        <div className="stat">
          <span>Ordered</span>
          <b>{inr(ordered, 0)}</b>
          <em>{po.lines.length} line(s), before GST</em>
        </div>
        <div className="stat">
          <span>Received</span>
          <b>{inr(received, 0)}</b>
          <em>{ordered ? Math.round((received / ordered) * 100) : 0}% of order value</em>
        </div>
        <div className="stat">
          <span>Billed</span>
          <b>{inr(po.billed, 0)}</b>
          <em>{po.invoices.filter((i: any) => i.status !== "on_hold").length} invoice(s) approved or paid</em>
        </div>
        <div className="stat">
          <span>Left to bill</span>
          <b className={ordered - po.billed < 0 ? "neg" : ""}>{inr(ordered - po.billed, 0)}</b>
          <em>PO value minus billed</em>
        </div>
      </div>

      <section className="card flush">
        <div className="cardhead">
          <h3>Lines</h3>
          <span className="muted small">Quantities: ordered → received (GRN) → billed</span>
        </div>
        <table className="grid">
          <thead>
            <tr>
              <th>#</th>
              <th>Item</th>
              <th>HSN</th>
              <th className="right">Rate</th>
              <th className="right">GST</th>
              <th className="right">Ordered</th>
              <th className="right">Received</th>
              <th className="right">Billed</th>
              <th className="right">On hold</th>
              <th className="right">Value</th>
            </tr>
          </thead>
          <tbody>
            {po.lines.map((l: any) => (
              <tr key={l.line_no}>
                <td className="muted">{l.line_no}</td>
                <td>{l.item}</td>
                <td className="mono muted">{l.hsn || "–"}</td>
                <td className="right mono">{inr(l.rate)}</td>
                <td className="right mono">{l.gst_rate}%</td>
                <td className="right mono">{l.qty} {l.unit}</td>
                <td className={`right mono ${l.received < l.qty ? "warnc" : ""}`}>{l.received}</td>
                <td className="right mono">{l.billed}</td>
                <td className="right mono">{l.on_hold || "–"}</td>
                <td className="right mono">{inr(l.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="twocol">
        <section className="card flush">
          <div className="cardhead">
            <h3>Goods receipts</h3>
          </div>
          {po.receipts.length === 0 ? (
            <Empty>Nothing received yet. Invoices against this PO will be held until goods arrive.</Empty>
          ) : (
            <table className="grid">
              <tbody>
                {po.receipts.map((r: any) => (
                  <tr key={r.grn_no}>
                    <td className="mono strong nowrap">{r.grn_no}</td>
                    <td className="muted nowrap">{fmtDate(r.grn_date)}</td>
                    <td>{r.lines.map((l: any) => `${l.qty} × ${l.item}`).join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card flush">
          <div className="cardhead">
            <h3>Invoices against this PO</h3>
          </div>
          {po.invoices.length === 0 ? (
            <Empty>No invoices yet.</Empty>
          ) : (
            <table className="grid clickable">
              <tbody>
                {po.invoices.map((i: any, k: number) => (
                  <tr key={k} onClick={() => i.run_id && go(`#/run/${i.run_id}`)} className={i.run_id ? "" : "static"}>
                    <td className="mono strong">{i.invoice_no}</td>
                    <td className="muted nowrap">{fmtDate(i.invoice_date)}</td>
                    <td className="right mono">{inr(i.total)}</td>
                    <td>
                      <Status s={i.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {receiving && (
        <Receive
          po={po}
          onClose={() => setReceiving(false)}
          onDone={(updated, grn) => {
            setReceiving(false);
            setPo(updated);
            toast(`${grn} recorded on ${po.po_no}`);
          }}
        />
      )}
    </div>
  );
}

function Receive({ po, onClose, onDone }: { po: any; onClose: () => void; onDone: (po: any, grn: string) => void }) {
  const open = po.lines.filter((l: any) => l.received < l.qty);
  const [date, setDate] = useState(today());
  const [qty, setQty] = useState<Record<number, string>>(
    Object.fromEntries(open.map((l: any) => [l.line_no, String(l.qty - l.received)]))
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setErrors({});
    try {
      const before = new Set(po.receipts.map((r: any) => r.grn_no));
      const updated = await api.receive(po.po_no, {
        grn_date: date,
        lines: Object.entries(qty).map(([line_no, q]) => ({ line_no: Number(line_no), qty: q })),
      });
      const grn = updated.receipts.find((r: any) => !before.has(r.grn_no))?.grn_no || "Receipt";
      onDone(updated, grn);
    } catch (e) {
      const err = e as ApiError;
      setErrors(err.fields || {});
      toast(err.message, "err");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Record goods receipt"
      sub={`What arrived at stores against ${po.po_no}. Leave a line at 0 if nothing came.`}
      onClose={onClose}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy} onClick={save}>
            {busy ? "Saving…" : "Save receipt"}
          </button>
        </>
      }
    >
      <div className="formgrid">
        <Field label="Received on" error={errors.grn_date}>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      {errors.form && <div className="error">{errors.form}</div>}
      <table className="grid edit">
        <thead>
          <tr>
            <th>Item</th>
            <th className="right">Ordered</th>
            <th className="right">Already in</th>
            <th className="right" style={{ width: 130 }}>Received now</th>
          </tr>
        </thead>
        <tbody>
          {open.map((l: any) => (
            <tr key={l.line_no} className={errors[`line_${l.line_no}`] ? "bad" : ""}>
              <td>
                {l.item}
                {errors[`line_${l.line_no}`] && <div className="ferr">{errors[`line_${l.line_no}`]}</div>}
              </td>
              <td className="right mono">{l.qty}</td>
              <td className="right mono">{l.received}</td>
              <td>
                <input className="right" inputMode="decimal" value={qty[l.line_no] ?? ""}
                  onChange={(e) => setQty({ ...qty, [l.line_no]: e.target.value })} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Modal>
  );
}
