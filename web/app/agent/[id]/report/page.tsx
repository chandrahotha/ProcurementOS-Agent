// P16 Mission Report, wired: composer (format choice), export with
// manifest header, export history note, mission lock path.
"use client";

import { use, useState } from "react";
import { Screen } from "@/components/Screen";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, Field, StateBadge } from "@/components/ui";

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
    <Screen code="P16" title="Mission Report" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Report" }]}
      primary="Export report" onPrimary={() => void exportReport()} status="Manifest header + evidence appendix" state="success">
      <Card className="max-w-xl">
        <div className="gate-grid">
          <Field label="Format">
            <select value={fmt} onChange={(e) => setFmt(e.target.value as typeof fmt)}>
              <option>CSV</option>
              <option>XLSX</option>
              <option>PDF</option>
            </select>
          </Field>
          <div className="row">
            <button type="button" className="primary" onClick={() => void exportReport()}>Export</button>
          </div>
          {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
        </div>
      </Card>
      {history.length > 0 ? (
        <section>
          <h2 className="mb-3 text-sm font-semibold tracking-tight">Exports this session</h2>
          <div className="table-card">
            <table>
              <caption className="sr-only">Exports this session</caption>
              <tbody>
                {history.map((h, i) => (
                  <tr key={`${h}-${i}`}>
                    <td className="mono">{h}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <p className="max-w-xl text-xs text-text-2">
        After export, the audit completeness check runs server-side and the
        mission locks. Reopening means a new plan version, never a rewrite.
      </p>
    </Screen>
  );
}
