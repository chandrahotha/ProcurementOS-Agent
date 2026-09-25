// P16 Mission Report, wired: composer (format choice), export with
// manifest header, export history note, mission lock path.
"use client";

import { use, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

export default function ReportPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [fmt, setFmt] = useState<"CSV" | "XLSX" | "PDF">("CSV");
  const [note, setNote] = useState("");
  const [history, setHistory] = useState<string[]>([]);

  async function exportReport() {
    setNote("");
    try {
      const { blob, filename } = await api.exportFile(id, fmt, readToken());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setHistory((h) => [`${new Date().toLocaleTimeString()} — ${filename}`, ...h]);
      setNote(`Exported ${filename} with evidence appendix (tenant-scoped).`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "export failed");
    }
  }

  return (
    <Screen code="P16" title="Mission Report" breadcrumb="Mission / Report"
      primary="Export report" state="success">
      <div className="gate-grid">
        <label>Format
          <select value={fmt} onChange={(e) => setFmt(e.target.value as typeof fmt)}>
            <option>CSV</option>
            <option>XLSX</option>
            <option>PDF</option>
          </select>
        </label>
        <button type="button" onClick={() => void exportReport()}>Export</button>
        {note ? <p role="status">{note}</p> : null}
      </div>
      {history.length > 0 ? (
        <section>
          <h2>Exports this session</h2>
          <ul>{history.map((h, i) => <li key={i} className="mono">{h}</li>)}</ul>
        </section>
      ) : null}
      <p>After export, the audit completeness check runs server-side and the
        mission locks. Reopening means a new plan version, never a rewrite.</p>
    </Screen>
  );
}
