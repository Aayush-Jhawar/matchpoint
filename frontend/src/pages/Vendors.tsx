import { useEffect, useState } from "react";
import { api, ApiError, go } from "../api";
import { checkGstin, IFSC_RE } from "../gstin";
import { Empty, Field, Icon, Modal, PageHeader, Status, toast } from "../components";

export default function Vendors() {
  const [vendors, setVendors] = useState<any[] | null>(null);
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    api.vendors().then(setVendors).catch(() => setVendors([]));
  }, []);

  const rows = (vendors || []).filter((v) =>
    !q || `${v.name} ${v.gstin} ${v.vendor_id}`.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="page">
      <PageHeader
        title="Vendors"
        sub="The vendor master. Invoices are matched to vendors by GSTIN, and paid only to the bank account on file."
        actions={
          <button className="btn" onClick={() => setAdding(true)}>
            <Icon name="plus" /> Add vendor
          </button>
        }
      />
      <div className="toolbar">
        <div className="searchbox">
          <Icon name="search" />
          <input placeholder="Search name, GSTIN or ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {vendors === null ? (
        <div className="muted pad">Loading…</div>
      ) : rows.length === 0 ? (
        <Empty>No vendors match.</Empty>
      ) : (
        <div className="tablewrap">
          <table className="grid clickable">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>GSTIN</th>
                <th>State</th>
                <th>Bank account on file</th>
                <th className="right">Open POs</th>
                <th className="right">Invoices</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => (
                <tr key={v.vendor_id} onClick={() => go(`#/vendors/${v.vendor_id}`)}>
                  <td>
                    <div className="strong">{v.name}</div>
                    <div className="muted small">{v.vendor_id}</div>
                  </td>
                  <td className="mono">{v.gstin}</td>
                  <td>{v.state_name}</td>
                  <td className="mono">
                    xxxx{v.account_no.slice(-4)} <span className="muted">· {v.ifsc}</span>
                  </td>
                  <td className="right mono">{v.open_pos}</td>
                  <td className="right mono">{v.invoices}</td>
                  <td>
                    <Status s={v.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {adding && (
        <VendorForm
          onClose={() => setAdding(false)}
          onDone={(v) => {
            setAdding(false);
            toast(`${v.name} added as ${v.vendor_id}`);
            go(`#/vendors/${v.vendor_id}`);
          }}
        />
      )}
    </div>
  );
}

const EMPTY = { name: "", address: "", gstin: "", bank_name: "", account_no: "", ifsc: "", phone: "", email: "", status: "active" };

export function VendorForm({ vendor, onClose, onDone }: { vendor?: any; onClose: () => void; onDone: (v: any) => void }) {
  const editing = !!vendor;
  const [f, setF] = useState<Record<string, string>>(() => (vendor ? { ...EMPTY, ...vendor } : { ...EMPTY }));
  const [confirmAcct, setConfirmAcct] = useState(vendor?.account_no || "");
  const [verified, setVerified] = useState(false);
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.value });

  const g = checkGstin(f.gstin);
  const ifscOk = IFSC_RE.test(f.ifsc.trim().toUpperCase());
  const bankChanged =
    editing && ["bank_name", "account_no", "ifsc"].some((k) => (f[k] || "").trim().toUpperCase() !== (vendor[k] || "").toUpperCase());
  const acctMismatch = confirmAcct !== f.account_no;

  async function save() {
    if (acctMismatch) {
      setErrors({ account_confirm: "The two account numbers don't match." });
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      const body = { ...f, verified, verification_note: note };
      const v = editing ? await api.updateVendor(vendor.vendor_id, body) : await api.createVendor(body);
      onDone(v);
    } catch (e) {
      const err = e as ApiError;
      setErrors(err.fields || {});
      toast(err.message, "err");
      setBusy(false);
    }
  }

  return (
    <Modal
      title={editing ? `Edit ${vendor.name}` : "Add vendor"}
      sub={editing ? `${vendor.vendor_id} · changes are logged on the vendor's history` : "State and PAN are read from the GSTIN."}
      onClose={onClose}
      wide
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" disabled={busy || (bankChanged && (!verified || note.trim().length < 10))} onClick={save}>
            {busy ? "Saving…" : editing ? "Save changes" : "Add vendor"}
          </button>
        </>
      }
    >
      <h3 className="formsec">Company</h3>
      <div className="formgrid">
        <Field label="Legal name" error={errors.name} span={2}>
          <input value={f.name} onChange={set("name")} placeholder="As on the GST certificate" />
        </Field>
        <Field label="GSTIN" error={errors.gstin || (f.gstin.length >= 15 && !g.ok ? g.message : undefined)}
          hint={g.ok ? <span className="okc">✓ {g.message}</span> : g.message || "15 characters"}>
          <input className="mono" value={f.gstin} maxLength={15}
            onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase().replace(/\s/g, "") })} />
        </Field>
        <Field label="Status" hint={f.status === "blocked" ? "Invoices from blocked vendors are held." : undefined}>
          <select value={f.status} onChange={set("status")}>
            <option value="active">Active</option>
            <option value="blocked">Blocked</option>
          </select>
        </Field>
        <Field label="Registered address" error={errors.address} span={2}>
          <textarea rows={2} value={f.address} onChange={set("address")} />
        </Field>
      </div>

      <h3 className="formsec">Contact on file</h3>
      <div className="formgrid">
        <Field label="Phone" error={errors.phone} hint="AP calls this number, never the one on an invoice, to verify bank changes.">
          <input value={f.phone} onChange={set("phone")} placeholder="020-2712 0458" />
        </Field>
        <Field label="Accounts email" error={errors.email}>
          <input type="email" value={f.email} onChange={set("email")} placeholder="accounts@vendor.in" />
        </Field>
      </div>

      <h3 className="formsec">
        Bank account {editing && <span className="lockhint"><Icon name="lock" size={13} /> changes need a call-back</span>}
      </h3>
      <div className="formgrid">
        <Field label="Bank and branch" error={errors.bank_name} span={2}>
          <input value={f.bank_name} onChange={set("bank_name")} placeholder="HDFC Bank, Bhosari" />
        </Field>
        <Field label="Account number" error={errors.account_no}>
          <input className="mono" inputMode="numeric" value={f.account_no}
            onChange={(e) => setF({ ...f, account_no: e.target.value.replace(/\D/g, "") })} />
        </Field>
        <Field label="Re-enter account number" error={errors.account_confirm || (confirmAcct && acctMismatch ? "Doesn't match yet" : undefined)}
          hint={confirmAcct && !acctMismatch ? <span className="okc">✓ Matches</span> : "Typed twice, never pasted from an email."}>
          <input className="mono" inputMode="numeric" value={confirmAcct} onPaste={(e) => e.preventDefault()}
            onChange={(e) => setConfirmAcct(e.target.value.replace(/\D/g, ""))} />
        </Field>
        <Field label="IFSC" error={errors.ifsc || (f.ifsc.length >= 11 && !ifscOk ? "Format: 4 letters, 0, 6 letters/digits" : undefined)}
          hint={ifscOk ? <span className="okc">✓ Valid format</span> : undefined}>
          <input className="mono" maxLength={11} value={f.ifsc} onChange={(e) => setF({ ...f, ifsc: e.target.value.toUpperCase() })} />
        </Field>
      </div>

      {bankChanged && (
        <div className="verify">
          <div className="vtitle">
            <Icon name="alert" /> You're changing where this vendor gets paid
          </div>
          <p>
            Fake "our bank account has changed" emails are the most common AP fraud. Before saving, call{" "}
            <b>{vendor.phone || "the vendor"}</b> (the number already on file, not one from the request) and confirm the new
            details with someone you know there.
          </p>
          <label className="checkline">
            <input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} />I called the number on
            file and the vendor confirmed the new account
          </label>
          <Field label="Who confirmed it, and when" error={errors.verified}>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Spoke to R. Patil (accounts), 23 Nov, 3:10 pm" />
          </Field>
        </div>
      )}
    </Modal>
  );
}
