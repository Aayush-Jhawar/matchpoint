import { Fragment, useEffect, useMemo, useState } from "react";
import { api, ApiError, fmtDate, go, inr, today } from "../api";
import { Empty, Field, Icon, Modal, PageHeader, Status, toast } from "../components";

type Line = { item: string; hsn: string; qty: string; unit: string; rate: string; gst_rate: string };
const blank = (): Line => ({ item: "", hsn: "", qty: "", unit: "nos", rate: "", gst_rate: "18" });

export default function POs() {
  const [pos, setPos] = useState<any[] | null>(null);
  const [filter, setFilter] = useState<"open" | "closed" | "all">("open");
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);

  const load = () => api.pos("all").then(setPos).catch(() => setPos([]));
  useEffect(() => {
    load();
  }, []);

  const rows = (pos || []).filter(
    (p) =>
      (filter === "all" || p.status === filter) &&
      (!q || `${p.po_no} ${p.vendor}`.toLowerCase().includes(q.toLowerCase()))
  );
  const counts = { open: (pos || []).filter((p) => p.status === "open").length, closed: (pos || []).filter((p) => p.status === "closed").length };

  return (
    <div className="page">
      <PageHeader
        title="Purchase orders"
        sub="What's been ordered, received and billed. Invoices are matched against these."
        actions={
          <button className="btn" onClick={() => setCreating(true)}>
            <Icon name="plus" /> New purchase order
          </button>
        }
      />

      <div className="toolbar">
        <div className="seg">
          {(["open", "closed", "all"] as const).map((f) => (
            <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
              {f === "all" ? "All" : f === "open" ? "Open" : "Closed"}
              {f !== "all" && <span>{counts[f]}</span>}
            </button>
          ))}
        </div>
        <div className="searchbox">
          <Icon name="search" />
          <input placeholder="Search PO or vendor" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {pos === null ? (
        <div className="muted pad">Loading…</div>
      ) : rows.length === 0 ? (
        <Empty>No purchase orders here.</Empty>
      ) : (
        <div className="tablewrap">
          <table className="grid clickable">
            <thead>
              <tr>
                <th>PO</th>
                <th>Vendor</th>
                <th>Date</th>
                <th className="right">Value</th>
                <th style={{ width: "26%" }}>Billed vs received</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const max = Math.max(p.value, p.billed + p.on_hold, 1);
                const pct = (x: number) => `${(x / max) * 100}%`;
                return (
                  <tr key={p.po_no} onClick={() => go(`#/pos/${p.po_no}`)}>
                    <td className="mono strong">{p.po_no}</td>
                    <td>{p.vendor}</td>
                    <td className="muted nowrap">{fmtDate(p.po_date)}</td>
                    <td className="right mono">{inr(p.value, 0)}</td>
                    <td>
                      <div className="track mini">
                        <span className="billed" style={{ width: pct(p.billed) }} />
                        <span className="held" style={{ width: pct(p.on_hold) }} />
                        <i className="recv" style={{ left: pct(p.received_value) }} />
                      </div>
                      <div className="trackcap">
                        {inr(p.billed, 0)} billed · {inr(p.received_value, 0)} received
                      </div>
                    </td>
                    <td>
                      <Status s={p.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="legend">
        <span>
          <b className="sw billed" /> billed
        </span>
        <span>
          <b className="sw held" /> on hold
        </span>
        <span>
          <b className="sw recvk" /> received
        </span>
      </div>

      {creating && (
        <NewPO
          onClose={() => setCreating(false)}
          onDone={(po) => {
            setCreating(false);
            toast(`${po.po_no} created for ${po.vendor}`);
            go(`#/pos/${po.po_no}`);
          }}
        />
      )}
    </div>
  );
}

function NewPO({ onClose, onDone }: { onClose: () => void; onDone: (po: any) => void }) {
  const [vendors, setVendors] = useState<any[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [poNo, setPoNo] = useState("");
  const [poDate, setPoDate] = useState(today());
  const [lines, setLines] = useState<Line[]>([blank()]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.vendors().then((v) => setVendors(v.filter((x) => x.status === "active")));
    api.nextPo().then((r) => setPoNo(r.po_no));
  }, []);

  const vendor = vendors.find((v) => v.vendor_id === vendorId);
  const totals = useMemo(() => {
    let taxable = 0, tax = 0;
    for (const l of lines) {
      const v = (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0);
      taxable += v;
      tax += (v * (parseFloat(l.gst_rate) || 0)) / 100;
    }
    return { taxable, tax };
  }, [lines]);

  const set = (i: number, k: keyof Line, v: string) => setLines(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));

  async function save() {
    setBusy(true);
    setErrors({});
    try {
      const po = await api.createPo({ vendor_id: vendorId, po_no: poNo, po_date: poDate, lines });
      onDone(po);
    } catch (e) {
      const err = e as ApiError;
      setErrors(err.fields || {});
      toast(err.message, "err");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="New purchase order"
      sub="Raise a PO against an approved vendor. Amounts are before GST."
      onClose={onClose}
      wide
      footer={
        <>
          <span className="mtotal">
            Taxable {inr(totals.taxable)} · GST {inr(totals.tax)} · <b>Total {inr(totals.taxable + totals.tax)}</b>
          </span>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy} onClick={save}>
            {busy ? "Creating…" : "Create PO"}
          </button>
        </>
      }
    >
      <div className="formgrid">
        <Field label="Vendor" error={errors.vendor_id} span={2}
          hint={vendor ? `${vendor.gstin} · ${vendor.state_name}` : "Only active vendors are listed."}>
          <select value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
            <option value="">Choose a vendor…</option>
            {vendors.map((v) => (
              <option key={v.vendor_id} value={v.vendor_id}>
                {v.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="PO number" error={errors.po_no} hint="Next number in sequence. Change it only if needed.">
          <input value={poNo} onChange={(e) => setPoNo(e.target.value.toUpperCase())} className="mono" />
        </Field>
        <Field label="PO date" error={errors.po_date}>
          <input type="date" value={poDate} onChange={(e) => setPoDate(e.target.value)} />
        </Field>
      </div>

      <div className="lineshead">
        <h3>Line items</h3>
        {errors.lines && <span className="ferr">{errors.lines}</span>}
      </div>
      <table className="grid edit">
        <thead>
          <tr>
            <th style={{ width: 28 }}>#</th>
            <th>Item</th>
            <th style={{ width: 92 }}>HSN</th>
            <th style={{ width: 90 }} className="right">Qty</th>
            <th style={{ width: 80 }}>Unit</th>
            <th style={{ width: 110 }} className="right">Rate (₹)</th>
            <th style={{ width: 92 }}>GST</th>
            <th style={{ width: 120 }} className="right">Amount</th>
            <th style={{ width: 36 }} />
          </tr>
        </thead>
        <tbody>
          {lines.map((l, i) => {
            const amt = (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0);
            const err = errors[`line_${i}`];
            return (
              <Fragment key={i}>
                <tr className={err ? "bad" : ""}>
                  <td className="muted">{i + 1}</td>
                  <td>
                    <input value={l.item} placeholder="e.g. Hex bolt M10x40 gr 8.8" onChange={(e) => set(i, "item", e.target.value)} />
                  </td>
                  <td>
                    <input value={l.hsn} inputMode="numeric" placeholder="7318" onChange={(e) => set(i, "hsn", e.target.value.replace(/\D/g, ""))} />
                  </td>
                  <td>
                    <input className="right" value={l.qty} inputMode="decimal" onChange={(e) => set(i, "qty", e.target.value)} />
                  </td>
                  <td>
                    <input value={l.unit} onChange={(e) => set(i, "unit", e.target.value)} />
                  </td>
                  <td>
                    <input className="right" value={l.rate} inputMode="decimal" onChange={(e) => set(i, "rate", e.target.value)} />
                  </td>
                  <td>
                    <select value={l.gst_rate} onChange={(e) => set(i, "gst_rate", e.target.value)}>
                      {["0", "5", "12", "18", "28"].map((g) => (
                        <option key={g} value={g}>
                          {g}%
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="right mono">{amt ? inr(amt) : "–"}</td>
                  <td>
                    {lines.length > 1 && (
                      <button className="iconbtn" title="Remove line" onClick={() => setLines(lines.filter((_, j) => j !== i))}>
                        <Icon name="trash" />
                      </button>
                    )}
                  </td>
                </tr>
                {err && (
                  <tr className="errrow">
                    <td />
                    <td colSpan={8} className="ferr">
                      {err}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <button className="btn ghost small addline" onClick={() => setLines([...lines, blank()])}>
        <Icon name="plus" /> Add line
      </button>
    </Modal>
  );
}
