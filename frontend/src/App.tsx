import { useEffect, useState } from "react";
import { api } from "./api";
import Inbox from "./pages/Inbox";
import RunView from "./pages/RunView";
import Dashboard from "./pages/Dashboard";
import POs from "./pages/POs";
import Settings from "./pages/Settings";

function useHash() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const on = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const [health, setHealth] = useState<{ llm: string | null; ocr: boolean } | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const parts = hash.replace(/^#\/?/, "").split("/");
  const page = parts[0] || "";

  let body;
  if (page === "run" && parts[1]) body = <RunView key={parts[1]} id={parts[1]} />;
  else if (page === "dashboard") body = <Dashboard />;
  else if (page === "pos") body = <POs />;
  else if (page === "settings") body = <Settings health={health} />;
  else body = <Inbox />;

  const tab = (h: string, label: string, active: boolean) => (
    <a href={h} className={active ? "on" : ""}>
      {label}
    </a>
  );

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="mark">Matchpoint</span>
          <span className="org">Kaveri Auto Components · Accounts payable</span>
        </div>
        <nav>
          {tab("#/", "Process", page === "" || page === "run")}
          {tab("#/dashboard", "Dashboard", page === "dashboard")}
          {tab("#/pos", "Purchase orders", page === "pos")}
          {tab("#/settings", "Settings", page === "settings")}
        </nav>
        <div className="engine" title="How invoices are being read">
          {health === null ? "backend offline" : health.llm ? `reader: ${health.llm}` : `reader: rules${health.ocr ? " + OCR" : ""}`}
        </div>
      </header>
      <main>{body}</main>
      <footer className="foot">
        Matchpoint · built by Aayush Jhawar for the Zamp ASA case study (PS-1) ·{" "}
        <a href="https://github.com/Aayush-Jhawar" target="_blank" rel="noreferrer">
          github.com/Aayush-Jhawar
        </a>
      </footer>
    </div>
  );
}
