# Documentation Index — Edge Hub Service

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-02
> **Owner:** Edge Platform Team | **Review Cadence:** Quarterly

Use this index to navigate the Edge Hub specification set. All documents are living artifacts; changes must go through the standard PR review process with at least one owner approval.

---

## Specification Documents

| Domain | # | Document | Purpose | Audience |
|--------|---|----------|---------|----------|
| Product | 01 | [Product Vision](01_product/01_product_vision.md) | Why we build this; problems, goals, KPIs, stakeholders | All |
| Product | 02 | [Business Requirements](01_product/02_business_requirements.md) | What must be built; priorities, compliance | PM, Engineering Lead |
| Product | 03 | [User Stories](01_product/03_user_stories.md) | Who needs what; acceptance criteria per story | PM, QA |
| Product | 04 | [Scope Boundaries](01_product/04_scope_boundaries.md) | In scope, out of scope, deferred scope, explicit non-goals | PM, Engineering Lead |
| Product | 05 | [Domain Glossary](01_product/05_domain_glossary.md) | Canonical vocabulary and entity definitions | All |
| Product | 06 | [Functional Flow](01_product/06_functional_flow.md) | User journeys and system interactions | PM, Designers |
| Product | 07 | [Interactive Prototype](01_product/07_interactive_prototype.html) | Clickable prototype for UI/UX validation | PM, Designers, QA |
| Architecture | 01 | [System Architecture](02_architecture/01_system_architecture.md) | Component topology, network, trust zones | Architects, Engineers |
| Architecture | 02 | [Functional Specification](02_architecture/02_functional_spec.md) | How each service behaves; error handling | Engineers |
| Architecture | 03 | [Constraints & Invariants](02_architecture/03_constraints_and_invariants.md) | Version pinning, backward-compat guarantees | Architects |
| Architecture | 04 | [Runtime Assumptions](02_architecture/04_runtime_assumptions.md) | Environment expectations and dependencies | Engineers, SRE |
| Architecture | 05 | [Eventing & Async Flows](02_architecture/05_eventing_and_async_flows.md) | Kafka topics, consumer groups, schema versioning | Engineers |
| Architecture | 06 | [Data Model Specification](02_architecture/06_data_model_spec.md) | Schema definitions, indexes, constraints | Engineers, DBA |
| Architecture | 07 | [API Contracts](02_architecture/07_api_contracts.yaml) | Machine-readable API schemas; errors, security | Engineers, QA |
| Hardware | 01 | [Hardware Specification](03_hardware/01_hardware_spec.md) | Device constraints, BOM, connectivity | Engineers, Procurement |
| Quality | 01 | [Non-Functional Requirements](04_quality/01_non_functional_requirements.md) | SLOs, availability, RTO/RPO | Architects, SRE |
| Quality | 02 | [Acceptance Test Specification](04_quality/02_acceptance_test_spec.md) | P0 happy path + sad path tests | QA, Engineers |
| Quality | 03 | [Integration Test Specification](04_quality/03_integration_test_spec.md) | Service-to-service tests | QA, Engineers |
| Quality | 04 | [Performance Test Specification](04_quality/04_performance_test_spec.md) | Load, stress, soak tests | SRE, QA |
| Quality | 05 | [Failure Modes & Edge Cases](04_quality/05_failure_modes_and_edge_cases.md) | Failure handling, recovery | Engineers, SRE |
| Quality | 06 | [Traceability Matrix](04_quality/06_traceability_matrix.md) | Requirement-to-test mapping | PM, QA |
| Operations | 01 | [Observability Specification](05_operations/01_observability_spec.md) | SLI/SLO, alerts, runbooks | SRE, Engineers |
| Operations | 02 | [Deployment & Operations](05_operations/02_deployment_and_operations.md) | Runbooks, env vars, incident response | SRE, Operators |
| AI Context | 01 | [Prompt Context (LLM)](06_ai_context/01_prompt_context.md) | Condensed system context for AI-assisted development | Engineers, AI tools |
| AI Context | 02 | [Sample Payloads & Fixtures](06_ai_context/02_sample_payloads_and_fixtures.md) | Example requests, events, responses | Engineers, QA |
| ADR | 01 | [Use Kafka](07_adr/01_use_kafka.md) | Decision record for event streaming | Architects |
| ADR | 02 | [Choose Postgres](07_adr/02_choose_postgres.md) | Decision record for relational DB | Architects |
| ADR | 03 | [Eventual Consistency Model](07_adr/03_eventual_consistency_model.md) | Decision record for data consistency | Architects |
| Privacy | 01 | [Privacy & Compliance](08_privacy/01_privacy_and_compliance.md) | GDPR, data retention, encryption, privacy masking, governance | Legal, InfoSec, Operators |
| Research | 01 | [AI Efficiency in Parcel Sorting](09_research/01_ai_efficiency_parcel_sorting_centres.md) | Background research and optimization strategies | Product, Data Science |
| Future Vision | 01 | [Feature Proposals & Expansion Roadmap](09_research/future_vision.md) | Expansion use cases, phased implementation plan, ROI projections | Product, Architects, Engineering Lead |

---

## Document Status Key

| Status | Meaning |
|--------|---------|
| Draft | Under active authorship; not reviewed |
| Review | Awaiting stakeholder sign-off |
| Production | Approved; governs implementation |
| Deprecated | Superseded; retained for audit trail |

---

## Change Control

- All changes require a PR with description of change and rationale.
- Breaking changes (schema, API, topic names) require Architecture Review Board sign-off.
- Traceability Matrix (doc 06 in Quality) must be updated whenever requirements or test specs change.
