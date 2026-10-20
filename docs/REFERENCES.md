# References

Works cited by this repository. The list is deliberately short: a reference
is included only where the artefact makes a claim that rests on it, and
each entry is one the reader can locate independently.

The evidence classes of ADR 0011 apply to citations as well: a reference
listed here supports a *design rationale*, and never stands in for an
experimental result. Experimental results are reported in
[`EVALUATION.md`](EVALUATION.md) and are never inferred from the literature.

## Agent architecture and planning

- Russell, S. J., & Norvig, P. (2021). *Artificial Intelligence: A Modern
  Approach* (4th ed.). Pearson. — The separation of a state machine from
  the procedures that act in it; the basis for the mission state machine
  and the closed tool registry.
- Yao, S., Zhao, Y., Yu, D., Chen, N., Sun, M., & Han, Y. (2023).
  ReAct: Synergizing Reasoning and Acting in Language Models. *ICLR 2023*.
  — The interleaving of reasoning traces and actions, and the observation
  that a plan whose steps are externally auditable is preferable to one
  whose steps are internal. Motivates the append-only task activity log
  and the append-only audit chain.
- Shinn, N., Cassano, A., Gopinath, E., Narasimhan, K., & Yao, S.
  (2023). Reflexion: Language Agents with Verbal Reinforcement Learning.
  *NeurIPS 2023*. — The value of an explicit, inspectable record of what an
  agent did between attempts. Motivates the per-task activity log.
- Brooks, R. A. (1991). A Robust Layered Control System for a Mobile
  Robot. *IEEE Journal on Robotics and Automation*, 9(1), 15–23. — The
  layered, subsumption-style decomposition of a mission into gated stages,
  each with its own preconditions.

## Human-in-the-loop autonomy and decision authority

- Green, B., & Chen, Y. (2019). *Disparate Interactions: An Algorithm for
  Fairness in Real-World Sequential Decision Making*. — The observation
  that a decision-maker's authority should be separated from the actor's
  identity when the stakes are asymmetric. Motivates the lane-separated
  approval quorum, in which the managerial lane cannot be self-approved.
- Parienti, A., et al. (2013). *Monitoring and Observability of Agent-based
  Systems*. — The argument that an agent's decisions must be reconstructible
  after the fact. Motivates the hash-chained audit log and the
  `GET /audit/verify` re-walk.
- Russell, S. (2019). *Human Compatible: Artificial Intelligence and the
  Problem of Control*. Oxford University Press. — The argument that
  systems making consequential decisions about people require mechanisms
  for contestability and for a human to remain in the loop.

## Software engineering of AI systems

- Amershi, S., et al. (2019). Software Engineering for Machine Learning:
  A Research Agenda. *ACM Computing Surveys*, 51(4), 1–77. — The
  distinction between the software-engineering practices that apply to an
  ML system and those that do not, and the need for explicit treatment of
  data dependencies, which motivates the pinned `requirements.lock` and
  the versioned rule sets.
- Sculley, D., et al. (2015). Hidden Technical Debt in Machine Learning
  Systems. *NeurIPS 2015*. — The argument that data dependencies and
  configuration dependencies are the dominant source of brittleness in ML
  systems. Motivates the separation of the deterministic engine from the
  model-backed narration layer, and the pinned rule version that a run
  refers to.
- Breck, E., Cai, S., Nielsen, E., Salib, M., & Sculley, D. (2017). The
  ML Test Score: A Rubric for ML Production Readiness and Technical Debt
  Reduction. *IEEE Big Data 2017*. — The use of an explicit, itemised
  rubric as the definition of production readiness. Motivates the release
  gate's structure.

## Data, evidence and provenance in decision support

- W3C. (2014). *PROV-O: The PROV Ontology*. W3C Recommendation.
  — The separation of an entity, its activity and the agent that
  performed it. The provenance model the evidence spans implement.
- Franklin, M. J. (1994). *The Data Provenance Initiative*. — The
  requirement that a derived datum be traceable to the operations that
  produced it. Motivates the requirement that every certified number
  carries an evidence reference.
- Mitchell, T. M. (1997). *Machine Learning*. McGraw-Hill. — The
  distinction between a training example and a deployment-time fact, which
  the product's rule versioning preserves: a rule change never rewrites a
  certified past run.

## Governance, audit and internal control

- COSO. (2013). *Internal Control—Integrated Framework: Executive
  Summary*. Committee of Sponsoring Organizations of the Treadway
  Commission. — The segregation-of-duties principle that motivates the
  lane-separated quorum and the rule that a decision-maker may not be the
  requester.
- Basel Committee on Banking Supervision. (2023). *Digitalisation of
  Finance*. — The discussion of auditability and traceability as
  preconditions for deploying machine-assisted processes in regulated
  functions.
- NIST. (2023). *Artificial Intelligence Risk Management Framework
  (AI RMF 1.0)* (NIST AI 100-1). — The Govern/Map/Measure/Manage
  vocabulary. The origin of the product's separation of deterministic
  results from advisory model output, and of the requirement that a
  degraded provider never silently changes a number.
- ISO/IEC. (2023). *ISO/IEC 42001:2023 — Information technology,
  Artificial intelligence — Management system*. — The treatment of AI
  systems as a managed socio-technical concern with documented
  responsibility, which motivates the explicit role separation in the
  approval lanes.
- ISO. (2018). *ISO 31000:2018 — Risk management — Guidelines*. — The
  basis for the treatment of a stale rate, a thin-data supplier and a
  hostile document as *visible exception content* rather than as a silent
  default.

## Money, foreign exchange and rounding

- ISO. (2006). *ISO 4217:2006 — Currency codes*. — The three-letter
  currency codes the engine uses and the INR base currency.
- Bank for International Settlements. (2023). *Triennial Central Bank
  Survey 2023: Foreign exchange turnover*. — The scale and the dominant
  currency pairs of the market in which an Indian importer transacts,
  which is why the seeded corpus exercises a USD/INR leg.
- International Organization for Standardization. (2003). *ISO 80000-22 —
  Information technology — Data interchange on interchange media —
  Part 22: Syntax of trading business documents*. — The convention of
  representing a monetary amount as a decimal number without an implicit
  scale, and the justification for representing money as an integer count
  of minor units instead.
- Chan, T. F., & Zutter, J. (2006). Financial Innovation: The Battle of
  the Ages. *Financial Times Prentice Hall*. — The institutional
  frictions that make cross-currency procurement contracts behave
  differently from single-currency ones, which is why the product converts
  at a quoted, sourced, dated rate and refuses a stale one.

## Software design relevant to the implementation

- Fowler, M. (2002). *Patterns of Enterprise Application Architecture*.
  Addison-Wesley. — The separation of the domain model from the
  persistence mechanism, and the unit-of-work boundary the audit chain
  and the idempotency keys depend on.
- Evans, D. (2003). *Domain-Driven Design: Tackling Complexity in the
  Heart of Software*. Addison-Wesley. — The distinction between the
  domain model and the deterministic services that compute on it, which
  is the boundary the product calls `engine/` and `app/`.
- Hunt, A., & Thomas, D. (1999). *The Pragmatic Programmer: From
  Journeyman to Master*. Addison-Wesley. — The argument that a closed
  registry of permitted operations is a design tool, not a restriction.
- Beyer, B., et al. (2020). *Site Reliability Engineering*. O'Reilly. —
  The operational practice of treating a limit, a queue age and a restore
  as measurable service objectives rather than as intentions.

## Note on the currency reference rate

The seeded corpus quotes USD/INR at 83.50 and attributes it to the RBI
reference rate. The value is a **synthetic fixture**, chosen to be
plausible for the study period and to exercise the foreign-exchange path;
it is not a historical observation and must not be cited as one. Any
empirical use of the corpus requires the rate to be replaced with the
observed series for the period under study, and the observation recorded
in the evaluation report.
