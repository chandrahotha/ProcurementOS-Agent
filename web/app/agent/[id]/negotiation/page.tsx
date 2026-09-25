// P11 Negotiation Studio, wired: ladders + drafts, zero sends. Bound
// violations are refused by the API (walk-away is a hard wall).
"use client";

import { use, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";

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
    <Screen code="P11" title="Negotiation Studio" breadcrumb="Mission / Negotiation"
      primary="Draft" state="success">
      <div className="gate-grid">
        <div className="row">
          <label>Candidate cost (minor)
            <input value={candidate} onChange={(e) => setCandidate(e.target.value)} />
          </label>
          <label>BATNA cost (minor)
            <input value={batna} onChange={(e) => setBatna(e.target.value)} />
          </label>
        </div>
        <label>Draft price (minor)
          <input value={price} onChange={(e) => setPrice(e.target.value)} />
        </label>
        <label>Message text
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <button type="button" onClick={() => void draft()}>Draft inside ladder</button>
        {note ? <p role="status">{note}</p> : null}
      </div>
      {ladder ? (
        <table>
          <thead><tr><th>Opening</th><th>Target</th><th>Walk-away</th><th>Concessions</th></tr></thead>
          <tbody>
            <tr>
              <td className="mono">{ladder.opening}</td>
              <td className="mono">{ladder.target}</td>
              <td className="mono">{ladder.walk_away}</td>
              <td className="mono">{ladder.concessions.join(" → ")}</td>
            </tr>
          </tbody>
        </table>
      ) : null}
      <AdvancePanel missionId={id} toState="approval" label="Advance to approval (Manager)"
        onAdvanced={() => setNote("State: approval.")} />
    </Screen>
  );
}
