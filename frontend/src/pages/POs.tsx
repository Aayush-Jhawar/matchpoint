import { useEffect, useState } from "react";
import { api, inr } from "../api";

export default function POs() {
  const [pos, setPos] = useState<any[]>([]);
  useEffect(() => {
    api.pos().then(setPos).catch(() => {});
  }, []);
  return (
    <div className="dash">
      <h1>Open purchase orders</h1>
      <p className="lede">
        How much of each PO has been billed, what is sitting on hold, and how much has actually been received. Values are
        before tax.
      </p>
      <table className="grid pos">
        <thead>
          <tr>
            <th>PO</th>
            <th>Vendor</th>
            <th className="right">Value</th>
            <th className="right">Received</th>
            <th className="right">Billed</th>
            <th className="right">On hold</th>
            <th style={{ width: "28%" }}>Usage</th>
          </tr>
        </thead>
        <tbody>
          {pos.map((p) => {
            const max = Math.max(p.value, p.billed + p.on_hold);
            const pct = (x: number) => `${(x / max) * 100}%`;
            return (
              <tr key={p.po_no}>
                <td className="mono">{p.po_no}</td>
                <td>{p.vendor}</td>
                <td className="right mono">{inr(p.value, 0)}</td>
                <td className="right mono">{inr(p.received_value, 0)}</td>
                <td className="right mono">{inr(p.billed, 0)}</td>
                <td className="right mono">{p.on_hold ? inr(p.on_hold, 0) : "–"}</td>
                <td>
                  <div className="track mini">
                    <span className="billed" style={{ width: pct(p.billed) }} />
                    <span className="held" style={{ width: pct(p.on_hold) }} />
                    <i className="limit" style={{ left: pct(p.value) }} />
                    <i className="recv" style={{ left: pct(p.received_value) }} title="received" />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
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
        <span>
          <b className="sw limitk" /> PO value
        </span>
      </div>
    </div>
  );
}
