# 03 — Domain Model: ProcurementOS-Agent

All tables tenant-scoped (`tenant_id`), UUID PKs (`uuid7`), `created_at/updated_at`, soft-delete where noted. Money = integer minor units + ISO 4217 (never float). Quantity = value (Decimal) + UOM + normalized value + conversion source/version. Timestamps UTC. Table prefix `pos_*` (shown without prefix below for readability).

## 1. Foundation (owned natively by this product)

- **Tenant**(id, name, status, retention_policy) · **User**(id, tenant_id, email, name, mfa_enrolled, status) · **Role**(id, tenant_id, name, permissions[]) — roles: Buyer, ProcurementManager, FinanceReviewer, ComplianceReviewer, Admin (admin = config only, cannot approve own missions).
- **Workspace**(id, tenant_id, name, budget_currency, members[]) — missions live in exactly one workspace; object-level membership enforced.
- **Supplier**(id, tenant_id, code, name, country, contacts[synthetic], status, created_by) + **SupplierSite**(id, supplier_id, locale, incoterm_default, lead_time_days).
- **Item**(id, tenant_id, sku, name, category, base_uom, spec) — catalog for mission lines.
- **Document**(id, tenant_id, mission_id, kind[quote|contract|price_history|cert|email|other], filename, mime, size, sha256, status[quarantined|clean|rejected], source) + **DocumentVersion**(id, document_id, version, s3_key, sha256, scan_verdict, created_at) — immutable versions.
- **EvidenceSpan**(id, tenant_id, mission_id, document_id, document_version, page, paragraph, table_ref, row, col, text_start, text_end, quoted_text, extractor, extractor_version, confidence, instruction_flag, created_at) — the atomic unit of provenance. `instruction_flag=true` quarantines the span from planning.
- **AIJob**(id, tenant_id, mission_id, purpose, provider, model_version, prompt_version, tool_version, input_hash, output_hash, status, error, created_by, timestamps) + **AIResult**(id, job_id, schema_name, payload_json, evidence_refs[], label) — AI never writes domain tables directly.
- **Approval**(id, tenant_id, mission_id, action_class, payload_hash, lane[finance|compliance|managerial], requested_by, approvers_required, decisions[{user_id, decision, reason, at}], status[pending|approved|rejected|expired], expires_at).
- **AuditEvent**(id, tenant_id, actor_id, mission_id, request_id, object_type, object_id, action, before_hash, after_hash, reason, source, at) — append-only, hash-chained per mission.

## 2. Product (mission) entities

- **Mission = product_case**(id, tenant_id, workspace_id, template_id?, title, category, currency, budget_cap_minor, deadline, autonomy_level[ASSISTED|SUPERVISED|GUARDED], state[intake|plan|evidence|analysis|scenarios|negotiation|approval|action|report], coverage_pct, rule_version, created_by, state_history[]).
- **MissionPlan**(id, mission_id, version, taskspecs[{key, title, tool, args_schema_ref, depends_on[], estimate_min, autonomy_class}], dag_hash, diff_from_prev, acknowledged_by, status[draft|acknowledged|superseded]).
- **MissionTask**(id, mission_id, plan_version, key, title, tool_name, args_json, idempotency_key, status[queued|running|needs_review|blocked|done|failed], attempts, assigned_role, result_ref, evidence_refs[], activity_log[], started_at, finished_at).
- **MissionRun**(id, mission_id, plan_version, trigger[auto|manual|replay], inputs_hash, rule_version, tool_versions{}, evidence_snapshot_hash, step_log[], status[ok|degraded|failed], sandbox bench diff, started/finished).
- **product_result** rows (one per module run): **SourcingResult**(mission_id, run_id, line_id, supplier_id, normalized_total_minor, rank, compliant_bool, evidence_refs[]) · **CostResult**(mission_id, run_id, supplier_id/scenario_id, tco_minor, build_up{price,freight,insurance,tooling,tax,discounts}, fx_sources[]) · **RiskResult**(mission_id, run_id, supplier_id, dimensions{quality,delivery,financial,compliance,geo}, weights_version, composite, band, evidence_refs[]) · **ScenarioResult**(mission_id, run_id, scenario_id, allocations[], objective_value, constraints_ok, savings_vs_baseline).
- **source_links**(result_id ↔ evidence_span_ids, with role [input|supporting|contested]) — every material number joins to ≥1 span or a recorded waiver.
- **rule_version**(version, effective_from, weights{…}, tolerances{…}, fx_policy, changelog) — pinned per run; reproducibility = inputs + evidence snapshot + rule_version + tool versions.

## 3. Conventions

- **Money:** minor-unit integers (e.g., `unit_price_minor`), `currency` ISO-4217 on every row, FX rows store (pair, rate Decimal(18,8), source, quoted_at). No float anywhere; rounding = banker's per-line then sum, versioned in `rule_version`.
- **Quantity:** `{value: Decimal, uom, normalized_value, normalized_uom, conv_source, conv_version}`. Unknown UOM blocks normalization → exception, never assumed.
- **Evidence:** required-field coverage = backed_fields / required_fields; confidence ≠ correctness; `instruction_flag` spans excluded from planning inputs but visible in Evidence Center with warning.
- **Audit:** every state transition, plan ack, correction, approval decision, dry-run, execution, waiver, dial change, and export writes an AuditEvent with before/after hashes and request_id. Timeline (P01/P15) is a read projection of AuditEvent + task activity.
- **Isolation:** all FKs stay inside `pos_*`; no cross-schema references. Seed rows carry `synthetic=true` + `SYNTHETIC-` code prefixes.
