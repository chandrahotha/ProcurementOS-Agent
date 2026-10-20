// P11 Negotiation Studio: the ladder (opening / target / walk-away) drawn as
// a track, a draft editor, and a bound-violation error. Nothing is sent
// here: the walk-away is a hard wall enforced by the API, and sending
// needs an EXTERNAL_COMM approval quorum.
//
// The ladder values are minor units (paise) of the mission currency.
"use client";

import { use, useState } from "react";
import { Screen } from "@/components/Screen";
import { AdvancePanel } from "@/components/AdvancePanel";
import { api } from "@/lib/api-client";
import { readToken } from "@/lib/token";
import { Card, EmptyState, Field, StateBadge } from "@/components/ui";
import { NegotiationLadder } from "@/components/intel";

type Ladder = { opening: number; target: number; walk_away: number; concessions: number[] };

export default function NegotiationPage(props: { params: Promise<{ id: string }> }) {
  const { id } = use(props.params);
  const [candidate, setCandidate] = useState("151220");
  const [batna, setBatna] = useState("168000");
  const [price, setPrice] = useState("149000");
  const [text, setText] = useState(
    "We can hold INR 1,240.00 per piece for 1000 pieces if the order lands this quarter.",
  );
  const [ladder, setLadder] = useState<Ladder | null>(null);
  const [note, setNote] = useState("");

  async function draft() {
    setNote("");
    try {
      const out = await api.draft(
        id,
        {
          supplier_id: "SYN-SUP-01",
          candidate_cost_minor: Number(candidate),
          batna_cost_minor: Number(batna),
          draft_price_minor: Number(price),
          text,
        },
        readToken(),
      );
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
        <Card className="grid gap-3">
          <h2 className="card-title">Concession ladder</h2>
          <NegotiationLadder
            ladder={ladder}
            draftPrice={Number(price)}
            candidateCost={Number(candidate)}
            batnaCost={Number(batna)}
          />
          <div className="table-card">
            <table>
              <caption className="sr-only">Negotiation ladder rungs</caption>
              <thead>
                <tr>
                  <th scope="col">Opening</th>
                  <th scope="col">Target</th>
                  <th scope="col">Walk-away</th>
                  <th scope="col">Rungs</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td data-label="Opening" className="mono">{ladder.opening}</td>
                  <td data-label="Target" className="mono">{ladder.target}</td>
                  <td data-label="Walk-away" className="mono">{ladder.walk_away}</td>
                  <td data-label="Rungs" className="mono">
                    {ladder.concessions.join(" → ")}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-2">
            Walk-away is the hard wall: a draft above it is refused by the API, and
            the rungs land on the target without overshooting it.
          </p>
        </Card>
      ) : (
        <EmptyState icon="chart" title="No ladder yet"
          body="Draft inside the ladder — the opening, target, and walk-away compute from the candidate and BATNA costs." />
      )}
      <AdvancePanel missionId={id} toState="approval" label="Advance to approval (Manager)"
        onAdvanced={() => setNote("State: approval.")} />
    </Screen>
  );
}
