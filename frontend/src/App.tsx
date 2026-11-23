import { useEffect, useState } from "react";
import { api } from "./api";
import { Icon, Toasts } from "./components";
import Inbox from "./pages/Inbox";
import RunView from "./pages/RunView";
import Dashboard from "./pages/Dashboard";
import POs from "./pages/POs";
import PODetail from "./pages/PODetail";
import Vendors from "./pages/Vendors";
import VendorDetail from "./pages/VendorDetail";
import Settings from "./pages/Settings";

function useHash() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const on = () => {
      setHash(window.location.hash || "#/");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

const NAV: [string, string, string, string[]][] = [
  ["#/", "Process invoice", "upload", ["", "run"]],
  ["#/dashboard", "Runs", "runs", ["dashboard"]],
  ["#/pos", "Purchase orders", "po", ["pos"]],
  ["#/vendors", "Vendors", "vendors", ["vendors"]],
  ["#/settings", "Settings", "settings", ["settings"]],
];

export default function App() {
  const hash = useHash();
  const [health, setHealth] = useState<{ llm: string | null; ocr: boolean } | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const parts = hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  const page = parts[0] || "";

  let body;
  if (page === "run" && parts[1]) body = <RunView key={parts[1]} id={parts[1]} />;
  else if (page === "dashboard") body = <Dashboard />;
  else if (page === "pos" && parts[1]) body = <PODetail key={parts[1]} no={parts[1]} />;
  else if (page === "pos") body = <POs />;
  else if (page === "vendors" && parts[1]) body = <VendorDetail key={parts[1]} id={parts[1]} />;
  else if (page === "vendors") body = <Vendors />;
  else if (page === "settings") body = <Settings health={health} />;
  else body = <Inbox />;

  return (
    <div className="shell">
      <aside className="side">
        <a href="#/" className="brand">
          <span className="logo">
            <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
              <rect width="20" height="20" rx="5" fill="currentColor" />
              <path d="M5.5 10.5l3 3 6-7" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span>
            <b>Matchpoint</b>
            <small>Kaveri Auto Components</small>
          </span>
        </a>
        <nav>
          <span className="navlabel">Accounts payable</span>
          {NAV.map(([href, label, icon, keys]) => (
            <a key={href} href={href} className={keys.includes(page) ? "on" : ""}>
              <Icon name={icon} />
              {label}
            </a>
          ))}
        </nav>
        <div className="sidefoot">
          <div className="reader" title="How invoices are being read">
            <span className={`pulse ${health ? "up" : "down"}`} />
            {health === null ? "Backend offline" : health.llm ? `Reading with ${health.llm}` : `Reading with rules${health.ocr ? " + OCR" : ""}`}
          </div>
          <div className="credit">
            Built by Aayush Jhawar
            <br />
            Zamp ASA case study · PS-1 ·{" "}
            <a href="https://github.com/Aayush-Jhawar/matchpoint" target="_blank" rel="noreferrer">
              GitHub
            </a>
          </div>
        </div>
      </aside>
      <main className="content">{body}</main>
      <Toasts />
    </div>
  );
}
