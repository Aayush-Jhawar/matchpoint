import { useEffect, useMemo, useState } from "react";
import { api, Decision, DECISION_TEXT, go, inr, RunRow, shortTime } from "../api";
import { Chip, Empty } from "../components";

type Filter = "ALL" | Decision;

export default function Dashboard() {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [q, setQ] = useState("");
  const [showSuperseded, setShowSuperseded] = useState(false);

  useEffect(() => {
    const load = () => {
      api.runs().then(setRuns).catch(() => {});
      api.stats().then(setStats).catch(() => {});
    };
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  const superseded = useMemo(() => new Set(runs.map((r) => r.parent_run).filter(Boolean) as string[]), [runs]);
  const rows = runs.filter(
    (r) =>
      (showSuperseded || !superseded.has(r.id)) &&
      (filter === "ALL" || r.decision === filter) &&
      (!q || `${r.vendor_name} ${r.invoice_no} ${r.po_no} ${r.file_name}`.toLowerCase().includes(q.toLowerCase()))
  );

  const owners = stats ? Object.entries(stats.holds_by_owner as Record<string, number>) : [];
  const maxOwner = Math.max(1, ...owners.map(([, n]) => n));

  return (
    <div className="dash">
      <h1>Dashboard</h1>
      {stats && (
        <div className="kpis">
          <div className="kpi">
            <span>Invoices processed</span>
            <b>{stats.processed}</b>
            <em>avg {(stats.avg_ms / 1000).toFixed(1)} s each</em>
          </div>
          <div className="kpi">
            <span>Touchless</span>
            <b>{stats.touchless_rate}%</b>
            <em>
              {stats.counts.AUTO_APPROVE + stats.counts.APPROVE_WITH_NOTE} approved without a person ·{" "}
              {inr(stats.value.AUTO_APPROVE + stats.value.APPROVE_WITH_NOTE, 0)}
            </em>
          </div>
          <div className="kpi amber">
            <span>On hold</span>
            <b>{stats.counts.HOLD}</b>
            <em>{inr(stats.value.HOLD, 0)} waiting on someone</em>
          </div>
          <div className="kpi red">
            <span>Rejected</span>
            <b>{stats.counts.REJECT}</b>
            <em>{inr(stats.blocked_value, 0)} not paid twice</em>
          </div>
          <div className="kpi owners">
            <span>Holds by owner</span>
            {owners.length === 0 && <em>none</em>}
            {owners.map(([o, n]) => (
              <div key={o} className="ob">
                <i>{o}</i>
                <span style={{ width: `${(n / maxOwner) * 100}%` }} />
                <b>{n}</b>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="toolbar">
        <div className="filters">
          {(["ALL", "AUTO_APPROVE", "APPROVE_WITH_NOTE", "HOLD", "REJECT"] as Filter[]).map((f) => (
            <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
              {f === "ALL" ? "All" : DECISION_TEXT[f]}
              {stats && f !== "ALL" && <span>{stats.counts[f]}</span>}
            </button>
          ))}
        </div>
        <label className="chk">
          <input type="checkbox" checked={showSuperseded} onChange={(e) => setShowSuperseded(e.target.checked)} /> show
          superseded runs
        </label>
        <input className="search" placeholder="Search vendor, invoice, PO" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {rows.length === 0 ? (
        <Empty>No runs yet. Process an invoice from the Process tab.</Empty>
      ) : (
        <table className="grid runs">
          <thead>
            <tr>
              <th>When</th>
              <th>Vendor</th>
              <th>Invoice</th>
              <th>PO</th>
              <th className="right">Amount</th>
              <th>Decision</th>
              <th>Owner</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} onClick={() => go(`#/run/${r.id}`)} className={superseded.has(r.id) ? "faded" : ""}>
                <td className="muted nowrap">{shortTime(r.created_at)}</td>
                <td>{r.vendor_name || r.file_name}</td>
                <td className="mono">{r.invoice_no || "–"}</td>
                <td className="mono">{r.po_no || "–"}</td>
                <td className="right mono">{inr(r.total)}</td>
                <td>
                  <Chip d={r.state === "done" ? r.decision : null} />
                </td>
                <td>{r.decision === "HOLD" || r.decision === "REJECT" ? r.owner : ""}</td>
                <td className="why">{r.state === "error" ? "pipeline error" : r.headline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
