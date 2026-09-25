// P11 Negotiation Studio, wired: ladders + drafts, zero sends. Bound
// violations are refused by the API (walk-away is a hard wall).
"use client";

import { use, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, Field, StateBadge } from "@/components/ui";

type Ladder = { opening: number; target: number; walk_away: number;
  concessions: number[] };

export default function NegotiationPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [candidate, setCandidate] = useState("9000");
  const [batna, setBatna] = useState("10000");
  const [price, setPrice] = useState("9500");
  const [text, setText] = useState("Hi, can you do 9500?");
  const [ladder, setLadder] = useState<Ladder | null>(null);
  const [note, setNote] = useState("");

  async function draft() {
    setNote("");
    try {
      const out = await api.draft(id, {
        supplier_id: "S-A",
        candidate_cost_minor: Number(candidate),
        batna_cost_minor: Number(batna),
        draft_price_minor: Number(price),
        text,
      }, readToken());
      setLadder(out.ladder);
      setNote("Draft stored. Sending needs EXTERNAL_COMM approval — never from here.");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "draft refused");
    }
  }

  return (
    <Screen code="P11" title="Negotiation Studio" breadcrumb={[{ label: "Mission Control", href: "/agent" }, { label: "Negotiation" }]}
      primary="Draft" onPrimary={() => void draft()} status="Ladder rungs never overshoot; walk-away is a hard wall" state="success">
      <Card className="max-w-xl">
        <div className="gate-grid">
          <div className="row">
            <Field label="Candidate cost (minor)">
              <input value={candidate} onChange={(e) => setCandidate(e.target.value)} />
            </Field>
            <Field label="BATNA cost (minor)">
              <input value={batna} onChange={(e) => setBatna(e.target.value)} />
            </Field>
          </div>
          <Field label="Draft price (minor)">
            <input value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
          <Field label="Message text">
            <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
          <div className="row">
            <button type="button" className="primary" onClick={() => void draft()}>Draft inside ladder</button>
          </div>
          {note ? <p role="status"><StateBadge state="info" /> {note}</p> : null}
        </div>
      </Card>
      {ladder ? (
        <div className="table-card">
          <table>
            <caption className="sr-only">Negotiation ladder</caption>
            <thead><tr><th scope="col">Opening</th><th scope="col">Target</th><th scope="col">Walk-away</th><th scope="col">Concessions</th></tr></thead>
            <tbody>
              <tr>
                <td data-label="Opening" className="mono">{ladder.opening}</td>
                <td data-label="Target" className="mono">{ladder.target}</td>
                <td data-label="Walk-away" className="mono">{ladder.walk_away}</td>
                <td data-label="Concessions" className="mono">{ladder.concessions.join(" → ")}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState icon="chart" title="No ladder yet"
          body="Draft inside the ladder — the opening, target, and walk-away compute from the candidate and BATNA costs." />
      )}
      <AdvancePanel missionId={id} toState="approval" label="Advance to approval (Manager)"
        onAdvanced={() => setNote("State: approval.")} />
    </Screen>
  );
}
