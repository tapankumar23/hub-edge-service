# Documentation Index — Edge Hub Service

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Edge Platform Team | **Review Cadence:** Quarterly

Use this index to navigate the Edge Hub specification set. All documents are living artifacts; changes must go through the standard PR review process with at least one owner approval.

---

## Specification Documents

| Domain | # | Document | Purpose | Audience |
|--------|---|----------|---------|----------|
| Product | 01 | [Product Vision](01_product_vision.md) | Why we build this; problems, goals, KPIs, stakeholders | All |
| Product | 02 | [Business Requirements](02_business_requirements.md) | What must be built; priorities, compliance | PM, Engineering Lead |
| Product | 03 | [User Stories](03_user_stories.md) | Who needs what; acceptance criteria per story | PM, QA |
| Product | 04 | [Scope Boundaries](04_scope_boundaries.md) | In scope, out of scope, deferred scope, explicit non-goals | PM, Engineering Lead |
| Product | 05 | [Domain Glossary](05_domain_glossary.md) | Canonical vocabulary and entity definitions | All |
| Architecture | 01 | [System Architecture](../02_architecture/01_system_architecture.md) | Component topology, network, trust zones | Architects, Engineers |
| Architecture | 02 | [Functional Specification](../02_architecture/02_functional_spec.md) | How each service behaves; error handling | Engineers |
| Architecture | 03 | [Constraints & Invariants](../02_architecture/03_constraints_and_invariants.md) | Version pinning, backward-compat guarantees | Architects |
| Architecture | 04 | [Runtime Assumptions](../02_architecture/04_runtime_assumptions.md) | Environment expectations and dependencies | Engineers, SRE |
| Architecture | 05 | [Eventing & Async Flows](../02_architecture/05_eventing_and_async_flows.md) | Kafka topics, consumer groups, schema versioning | Engineers |
| Architecture | 06 | [Data Model Specification](../02_architecture/06_data_model_spec.md) | Schema definitions, indexes, constraints | Engineers, DBA |
| Architecture | 07 | [API Contracts](../02_architecture/07_api_contracts.yaml) | Machine-readable API schemas; errors, security | Engineers, QA |
| Quality | 01 | [Non-Functional Requirements](../03_quality/01_non_functional_requirements.md) | SLOs, availability, RTO/RPO | Architects, SRE |
| Quality | 02 | [Acceptance Test Specification](../03_quality/02_acceptance_test_spec.md) | P0 happy path + sad path tests | QA, Engineers |
| Quality | 03 | [Integration Test Specification](../03_quality/03_integration_test_spec.md) | Service-to-service tests | QA, Engineers |
| Quality | 04 | [Performance Test Specification](../03_quality/04_performance_test_spec.md) | Load, stress, soak tests | SRE, QA |
| Quality | 05 | [Failure Modes & Edge Cases](../03_quality/05_failure_modes_and_edge_cases.md) | Failure handling, recovery | Engineers, SRE |
| Quality | 06 | [Traceability Matrix](../03_quality/06_traceability_matrix.md) | Requirement-to-test mapping | PM, QA |
| Operations | 01 | [Observability Specification](../04_operations/01_observability_spec.md) | SLI/SLO, alerts, runbooks | SRE, Engineers |
| Operations | 02 | [Deployment & Operations](../04_operations/02_deployment_and_operations.md) | Runbooks, env vars, incident response | SRE, Operators |
| Privacy & Compliance | 01 | [Privacy & Compliance Specification](../06_privacy_and_compliance.md) | GDPR, data retention, encryption, privacy masking, governance | Legal, InfoSec, Operators |
| AI Context | 01 | [Prompt Context (LLM)](../05_ai_context/01_prompt_context.md) | Condensed system context for AI-assisted development | Engineers, AI tools |
| AI Context | 02 | [Sample Payloads & Fixtures](../05_ai_context/02_sample_payloads_and_fixtures.md) | Example requests, events, responses | Engineers, QA |

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
- Traceability Matrix (doc 06) must be updated whenever requirements or test specs change.
