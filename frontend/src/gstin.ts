// Same checks as backend/app/gstin.py, so forms can flag problems while you type.
const CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export const STATES: Record<string, string> = {
  "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
  "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "18": "Assam",
  "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh",
  "24": "Gujarat", "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "32": "Kerala", "33": "Tamil Nadu",
  "36": "Telangana", "37": "Andhra Pradesh",
};

function checksum(first14: string) {
  let total = 0;
  for (let i = 0; i < 14; i++) {
    const prod = CHARS.indexOf(first14[i]) * (i % 2 ? 2 : 1);
    total += Math.floor(prod / 36) + (prod % 36);
  }
  return CHARS[(36 - (total % 36)) % 36];
}

export function checkGstin(raw: string): { ok: boolean; message: string; state?: string; pan?: string } {
  const g = raw.trim().toUpperCase();
  if (!g) return { ok: false, message: "" };
  if (g.length < 15) return { ok: false, message: `${15 - g.length} more character(s)` };
  if (!/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(g)) return { ok: false, message: "Not a valid GSTIN format" };
  if (checksum(g.slice(0, 14)) !== g[14]) return { ok: false, message: "Checksum doesn't match: check for a typo" };
  const state = STATES[g.slice(0, 2)];
  return { ok: true, message: `${state || "State " + g.slice(0, 2)} · PAN ${g.slice(2, 12)}`, state, pan: g.slice(2, 12) };
}

export const IFSC_RE = /^[A-Z]{4}0[A-Z0-9]{6}$/;
