import { useEffect, useState } from "react";
import { api, fmtDate, go, inr, shortTime } from "../api";
import { Empty, Icon, PageHeader, Status, toast } from "../components";
import { VendorForm } from "./Vendors";

const FIELD: Record<string, string> = {
  created: "Vendor created", name: "Name", address: "Address", gstin: "GSTIN", state: "State", pan: "PAN",
  bank_name: "Bank", account_no: "Account number", ifsc: "IFSC", phone: "Phone", email: "Email", status: "Status",
};

export default function VendorDetail({ id }: { id: string }) {
  const [v, setV] = useState<any>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    api.vendor(id).then(setV).catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <div className="page"><Empty>{err}</Empty></div>;
  if (!v) return <div className="page muted pad">Loading…</div>;

  return (
    <div className="page">
      <PageHeader
        crumbs={[["Vendors", "#/vendors"]]}
        title={
          <span className="titlewith">
            {v.name} <Status s={v.status} />
          </span>
        }
        sub={`${v.vendor_id} · ${v.state_name}`}
        actions={
          <button className="btn ghost" onClick={() => setEditing(true)}>
            <Icon name="edit" /> Edit vendor
          </button>
        }
      />

      <div className="twocol">
        <section className="card">
          <h3>Registration</h3>
          <dl className="kv">
            <dt>GSTIN</dt>
            <dd className="mono">{v.gstin}</dd>
            <dt>PAN</dt>
            <dd className="mono">{v.pan}</dd>
            <dt>Address</dt>
            <dd>{v.address}</dd>
            <dt>Phone</dt>
            <dd>{v.phone || "–"}</dd>
            <dt>Email</dt>
            <dd>{v.email || "–"}</dd>
          </dl>
        </section>
        <section className="card">
          <h3>Pays to</h3>
          <dl className="kv">
            <dt>Bank</dt>
            <dd>{v.bank_name}</dd>
            <dt>Account</dt>
            <dd className="mono">{v.account_no}</dd>
            <dt>IFSC</dt>
            <dd className="mono">{v.ifsc}</dd>
          </dl>
          <p className="muted small">
            Invoices asking for payment to any other account are held for Treasury, however well they match.
          </p>
        </section>
      </div>

      <section className="card flush">
        <div className="cardhead">
          <h3>Purchase orders</h3>
          <a className="link" href="#/pos">All POs →</a>
        </div>
        {v.pos.length === 0 ? (
          <Empty>No POs raised on this vendor yet.</Empty>
        ) : (
          <table className="grid clickable">
            <tbody>
              {v.pos.map((p: any) => (
                <tr key={p.po_no} onClick={() => go(`#/pos/${p.po_no}`)}>
                  <td className="mono strong">{p.po_no}</td>
                  <td className="muted">{fmtDate(p.po_date)}</td>
                  <td className="right mono">{inr(p.taxable_value, 0)}</td>
                  <td>
                    <Status s={p.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="twocol">
        <section className="card flush">
          <div className="cardhead">
            <h3>Invoices</h3>
          </div>
          {v.invoices.length === 0 ? (
            <Empty>No invoices yet.</Empty>
          ) : (
            <table className="grid clickable">
              <tbody>
                {v.invoices.map((i: any, k: number) => (
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
        <section className="card flush">
          <div className="cardhead">
            <h3>Change history</h3>
          </div>
          {v.changes.length === 0 ? (
            <Empty>No changes recorded since the vendor master was loaded.</Empty>
          ) : (
            <ul className="history">
              {v.changes.map((c: any, k: number) => (
                <li key={k} className={["bank_name", "account_no", "ifsc"].includes(c.field) ? "bank" : ""}>
                  <div className="hrow">
                    <b>{FIELD[c.field] || c.field}</b>
                    <span className="muted small">{shortTime(c.changed_at)}</span>
                  </div>
                  {c.field !== "created" && (
                    <div className="mono small">
                      <s>{c.old_value || "empty"}</s> → {c.new_value || "empty"}
                    </div>
                  )}
                  {c.note && <div className="small">Verified: {c.note}</div>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {editing && (
        <VendorForm
          vendor={v}
          onClose={() => setEditing(false)}
          onDone={(nv) => {
            setEditing(false);
            setV(nv);
            toast("Vendor updated");
          }}
        />
      )}
    </div>
  );
}
