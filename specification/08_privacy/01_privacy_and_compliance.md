# Privacy & Compliance Specification

> **Version:** 1.0.0 | **Status:** Production | **Last Updated:** 2026-03-01
> **Owner:** Legal / Privacy / InfoSec | **Review Cadence:** Quarterly

---

## Executive Summary

Edge Hub processes sensitive camera data at logistics facilities. This specification defines privacy-by-design principles, GDPR compliance controls, data handling procedures, and governance frameworks to ensure parcel tracking does not expose personal data, worker privacy, or facility security information.

---

## Regulatory Framework

### GDPR (General Data Protection Regulation) — EU/EEA

| Article | Requirement | Edge Hub Implementation |
|---------|------------|------------------------|
| **Article 4(1)** — Personal Data Definition | Any information relating to an identified or identifiable person | Applies to: worker presence (if tracked), facility visitor logs, camera feeds containing faces |
| **Article 5** — Data Protection Principles | Lawfulness, fairness, transparency, purpose limitation, data minimization, accuracy, integrity, confidentiality, accountability | Privacy masking (Section 2.2); consent frameworks (2.3); retention policies (2.4) |
| **Article 6** — Legal Basis | Contract, consent, legal obligation, vital interests, public task, legitimate interests | Logistics operations (contract); operator consent for monitoring (Section 2.3) |
| **Article 9** — Special Categories | Biometric data for identification; health/criminal data | **Edge Hub does NOT process:** Faces are masked before inference (Section 2.2) |
| **Article 12–14** — Rights to Transparency | Right to access, rectification, erasure, restriction, portability, objection | Data subject access request (DSAR) procedures (Section 3.2) |
| **Article 32** — Security & Encryption | Encrypt personal data in transit and at rest | AES-256-GCM encryption (Section 2.5); HTTPS for cloud sync (Section 2.6) |
| **Article 33–34** — Breach Notification | Notify supervisory authority within 72 hours; notify data subjects in high-risk scenarios | Incident response plan (Section 3.3) |
| **Article 35** — Data Protection Impact Assessment (DPIA) | Required for high-risk processing | DPIA checklist (Section 4) |
| **Article 44–49** — International Transfers | Mechanisms for GDPR-compliant transfers outside EU/EEA | Standard Contractual Clauses (SCCs) if cloud sync targets non-EU (Section 2.6) |

### CCPA (California Consumer Privacy Act) — USA/CA

| Right | Edge Hub Handling |
|------|-----------------|
| Right to Know | Camera data is operational; not sold. No third-party disclosure without consent. |
| Right to Delete | Parcel metadata retention capped at 90 days post-delivery (Section 2.4). |
| Right to Opt-Out | Facility operators can disable camera capture via `CAMERA_ID` env (unset = no capture). |
| Right to Non-Discrimination | No differential pricing/service based on camera coverage. |

### Other Jurisdictions

| Region | Standard | Edge Hub Approach |
|--------|----------|------------------|
| UK (post-GDPR) | UK GDPR, ICO guidelines | Equivalent to EU GDPR; privacy masking and encryption apply. |
| Canada | PIPEDA, provincial laws (ON, BC) | Consent-based; retention policy (90 days); audit trail. |
| Australia | Privacy Act, APPs | Privacy impact assessment; notifiable data breaches within 30 days. |

---

## Privacy-by-Design Principles

### 1. Privacy Masking at Ingestion

#### Requirement: SC-05 — Camera Feeds Must Apply Privacy Masking

**Goal:** Remove identifiable information (faces, license plates, worker ID badges) before any downstream processing.

**Implementation:**
- **When:** Masking applied in `camera-ingestion` service at frame capture or HTTP POST `/ingest`.
- **Techniques:**
  - Face detection (YOLO face detector or separate face-detection model) + Gaussian blur (25×25 kernel).
  - License plate detection (EasyOCR or similar) + pixelation (10×10 blocks).
  - Badge/ID cards (bounding box detection) + opacity masking (alpha = 0.2).
- **Verification:** No raw face pixels or text appear in MinIO `capture/{uuid}.jpg` or any downstream storage.
- **Fallback:** If privacy masking fails, log `PRIVACY_MASKING_FAILED` and reject frame (return HTTP 400 or skip topic publication).

**Configuration:**
```bash
PRIVACY_MASKING_ENABLED=true          # Enable/disable masking
PRIVACY_MASK_FACES=true               # Face blur
PRIVACY_MASK_PLATES=true              # License plate pixelation
PRIVACY_MASK_BLUR_KERNEL=25           # Gaussian blur size (pixels)
```

**Audit:** Every masked frame logged with `message="frame_masked"`, `faces_detected: int`, `plates_detected: int` (counts only, no pixel coordinates).

---

### 2. No PII in Kafka Topics

#### Requirement: SC-06 — No PII Stored in Kafka Topic Payloads or Vector Embeddings

**Scope:**
- Kafka topics: `frames`, `inference_results`, sync messages.
- Data fields: `camera_id`, `image_object_key`, `fingerprint`, `detections`, `parcel_id`, routing metadata.

**Allowed (Non-PII):**
- Parcel shape/texture embeddings (vector, no semantic link to person).
- Bounding box coordinates (x1, y1, x2, y2) — structural, not identifiable.
- Timestamps (aggregated, no individual tracking).
- Generic device IDs (`camera_id`, `edge_parcel_id").

**Prohibited (PII):**
- Worker names, employee IDs, shift assignments.
- Facility visitor logs, access logs from cameras.
- Raw or partially masked face/plate images.
- Health/safety incident metadata linked to individuals.

**Enforcement:**
- Code review checklist: audit all Kafka serialization code.
- CI schema validation: parse topic payloads as JSON; reject if top-level keys include `person_id`, `worker_name`, `visitor_*`.
- Runtime logging guardrails: redact fields matching PII patterns (email, SSN, phone).

---

### 3. Encryption at Rest

#### Requirement: SC-03 — AES-256-GCM Encryption for Sensitive Metadata

**Protected Fields:**
- `metadata_enc` column in `parcels` and `parcel_events` tables (Postgres).
- Parcel route history, routing rule outcomes (if containing sensitive business logic).

**Algorithm:**
- **Cipher:** AES-256-GCM (Authenticated Encryption with Associated Data).
- **Key:** 32 bytes (256 bits), provided via `ENCRYPTION_KEY` environment variable.
- **IV (Nonce):** Randomly generated 12 bytes per record; stored with ciphertext.
- **AAD (Associated Data):** `edge_parcel_id` + `created_at` (prevent swapping encrypted records).

**Implementation:**
```python
# Pseudocode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import secrets

key = bytes.fromhex(os.getenv("ENCRYPTION_KEY"))  # Must be 32 bytes
iv = secrets.token_bytes(12)
cipher = AESGCM(key)
plaintext = json.dumps(metadata_dict).encode()
aad = f"{edge_parcel_id}:{created_at}".encode()

ciphertext = cipher.encrypt(iv, plaintext, aad)
encrypted_record = {
    "enc_key_version": 1,          # For key rotation
    "iv": iv.hex(),
    "ciphertext": ciphertext.hex(),
    "aad_sample": aad.decode()[:50]  # For audit, not decryption
}
```

**Storage:**
- `metadata_enc` column stores JSON: `{ "enc_key_version", "iv", "ciphertext" }`.
- Never store plaintext metadata alongside encrypted fields.

**Decryption:**
- On read: extract `iv`, `ciphertext`, `enc_key_version`.
- Load key from `ENCRYPTION_KEY` (or key version map if rotating).
- Decrypt and verify AAD matches.
- Return plaintext to application layer only; never log plaintext.

---

### 4. Encryption in Transit

#### Requirement: SC-04 — HTTPS for Cloud Sync; TLS 1.2+ Internal (Optional)

**Cloud Sync (`CLOUD_SYNC_URL`):**
- Must use `https://` in production (enforced at startup via config validation).
- Must verify SSL/TLS certificate; reject self-signed unless in dev/test mode.
- Use HTTP/2 for transport.
- Cipher suite: TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384 or stronger.

**Internal Service-to-Service (Docker network):**
- Plain HTTP acceptable within trusted edge network (docker-compose bridge).
- Upgrade to internal TLS (mTLS) if edge host is shared with untrusted workloads (future phase).

**Implementation:**
```python
# Config validation at startup
if ENVIRONMENT == "production":
    assert CLOUD_SYNC_URL.startswith("https://"), "CLOUD_SYNC_URL must use HTTPS in production"
    # Verify cert:
    requests.post(CLOUD_SYNC_URL, verify=True)  # verify=True checks cert chain
else:
    # Dev: allow http://localhost
    assert CLOUD_SYNC_URL.startswith("http"), "CLOUD_SYNC_URL must be http:// in dev"
```

---

### 5. Data Retention & Deletion

#### Data Retention Policy

**Parcel Metadata:**
- Retain `parcels`, `parcel_events` rows for **90 days** post-delivery.
- Flag rows with `deleted_at` timestamp; hard-delete after 90 days via cron job.
- Rationale: Logistics reconciliation (reverse on-roads, claims); GDPR data minimization.

**Camera Artifacts (MinIO):**
- Retain `capture/{uuid}.jpg` for **30 days** (infrastructure operational windows).
- Delete after 30 days via S3 lifecycle policy or scheduled job.
- Rationale: Privacy (faces masked but image still exists); storage cost.

**Kafka Log Retention:**
- Broker retention: **7 days** (default Redpanda retention).
- DLQ messages: **30 days**.
- Rationale: Technical troubleshooting window; no PII in topics.

**Encryption Keys:**
- Retain old key versions in `encryption_key_version` table for **1 year** after rotation.
- Rationale: Allow decryption of historical records during audit/compliance review.
- After 1 year, securely destruct old key material.

**Configuration:**
```bash
PARCEL_RETENTION_DAYS=90
CAPTURE_RETENTION_DAYS=30
ENCRYPTION_KEY_RETENTION_YEARS=1
KAFKA_RETENTION_MS=604800000  # 7 days
```

**Deletion Procedure:**
```sql
-- Scheduled nightly cron job
DELETE FROM parcels WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '90 days';
DELETE FROM parcel_events WHERE created_at < NOW() - INTERVAL '90 days';
-- MinIO: S3 lifecycle rules or:
-- mc rm --recursive --force minio/parcels/capture/ --older-than 30d
```

---

### 6. Cloud Sync & Geographic Data Transfers

#### Data Exported to Cloud (`CLOUD_SYNC_URL`)

**Scope:**
- Outbox items from `sync_outbox` table (parcel identities, routing decisions).
- Excluded: raw camera images, encrypted metadata.

**Controls:**
- **Standard Contractual Clauses (SCCs):** If cloud endpoint is in non-GDPR-adequate country (e.g., USA), execute SCCs with cloud processor.
- **Data Processing Agreement (DPA):** Cloud provider must be GDPR-compliant data processor.
- **Encryption in Transit:** TLS 1.2+; cloud endpoint receives encrypted or pseudonymized payloads.

**Example: GDPR-compliant Sync Message**
```json
{
  "edge_parcel_id": "edge-parcel-abc123",
  "fingerprint_hash": "sha256:...",  // Hash, not full vector
  "routing_destination": "dock-A",
  "confidence_score": 0.92,
  "timestamp": "2026-03-01T12:34:56Z",
  "created_at_edge": "2026-03-01T12:34:00Z",
  "synced_at": "2026-03-01T12:34:56Z"
  // NO: raw images, worker names, facility location details
}
```

---

## Consent & Transparency

### Data Subject Rights (GDPR Articles 12–22)

| Right | How Edge Hub Supports |
|------|----------------------|
| **Right to Access (Art. 15)** | DSAR handler: API endpoint `POST /dsar` (admin panel) accepting subject email; query `parcels` rows with matching `created_by` or timestamp; export as CSV. |
| **Right to Rectification (Art. 16)** | Limited applicability; parcel metadata immutable by design. Allow deletion request (Art. 17) instead. |
| **Right to Erasure (Art. 17)** | Mark `parcels.deleted_at = NOW()`; flag for hard-delete after retention window. |
| **Right to Restrict (Art. 18)** | Not applicable; no ongoing profiling or decisions based on parcel data. |
| **Right to Data Portability (Art. 20)** | DSAR export includes portable JSON format. |
| **Right to Object (Art. 21)** | Facility operators can opt-out of camera capture (disable via `CAMERA_ID`). |
| **Right to Not Be Subject to Automated Decision-Making (Art. 22)** | Routing decisions are not fully automated; human-in-the-loop possible via local rules (FR-10). |

### Consent Mechanism

**Facility Operators (Camera Capture):**
- At facility bootstrap, operator must confirm: "I consent to camera capture and parcel tracking per privacy policy."
- Consent logged in `audit_log` table: `{ subject: "facility-admin-xyz", action: "camera_consent_granted", timestamp, ip_address }`.
- Configuration flag: `CONSENT_CAMERA_GRANTED=true` (must be explicit; default = false).

**Workers (Privacy Masking):**
- Camera masking is automatic; workers do not need individual consent.
- Facility signage: "This facility uses privacy-masked cameras for operational efficiency. Faces and badges are blurred before processing."

**Data Subject DSAR:**
- Support email: `privacy@logisticscompany.com`.
- Response time: 30 days (GDPR requirement).
- Log all DSAR submissions in `dsar_requests` table.

---

## Data Protection Impact Assessment (DPIA)

### DPIA Checklist (Art. 35, GDPR)

**Processing Activity:** Edge Hub parcel identification via camera infrared/RGB.

- [ ] **Necessity & Proportionality:** Is camera processing necessary? (Yes: reduces mis-sorts, improves throughput.)
- [ ] **Scope of Personal Data:** How much PII processed? (Minimal: only masked faces during privacy masking step; no PII in final outputs.)
- [ ] **Processing Necessity:** Could we achieve goal without cameras? (Alternate: manual labels or barcodes; camera offers resilience.)
- [ ] **Data Subject Expectations:** Do workers/parcel owners expect this processing? (Likely yes: logistics standard; disclosed in T&Cs.)
- [ ] **Data Accuracy:** Is fingerprint-based identity reliable? (95% target for top-1 accuracy; occasional mismatches reviewed manually.)
- [ ] **Safeguards:** Encryption at rest/transit, retention limits, access control. (✓ All present.)
- [ ] **Third-Party Processors:** Does cloud sync involve vendors? (Yes: cloud sync vendor = data processor; DPA required.)
- [ ] **Remediation:** Any high risks? (Low: privacy masking effective; encryption strong.)

**Conclusion:** ✅ **DPIA approved. Implement controls per Section 2 above. Review annually or upon material change.**

---

## Governance & Incident Response

### Data Governance Roles

| Role | Responsibility |
|------|-----------------|
| **Data Controller** | Logistics company facility/fleet operator — determines purposes, methods of processing. |
| **Data Processor** | Edge Hub team (design, ops support) — acts on controller's instructions. |
| **Privacy Officer** | Legal/Compliance — GDPR point of contact; DSAR review; audit trail. |
| **Security Owner** | InfoSec — key management, encryption, incident response. |
| **Ops Lead** | SRE — access control, retention, backup security. |

### Data Breach Notification

**Trigger:** Any unauthorized access, disclosure, or loss of encrypted metadata, Kafka topics, or database.

**Notification Timeline:**
1. **Immediate (< 1 hour):** InfoSec + Privacy Officer notified.
2. **Assessment (< 24 hours):** Determine scope (how many records affected), likelihood of PII exposure.
3. **Notification (< 72 hours):** If high risk of harm, notify supervisory authority (e.g., ICO for UK, CNIL for France).
4. **Public Disclosure (if required):** If > 100 subjects affected and high risk, notify data subjects.

**Example Scenarios:**
- 🔴 **Encryption key leaked:** HIGH RISK. Rotate key immediately; notify authority.
- 🔴 **Postgres credentials exposed in logs:** HIGH RISK. Rotate credentials; audit Kafka payloads for secrets.
- 🟡 **MinIO bucket temporarily accessible (16 hours):** MEDIUM RISK. Assess which captures were viewed; notify if faces detected.
- 🟢 **Qdrant vector index temporarily unavailable:** LOW RISK. No data loss; service recovers. No notification needed.

**Incident Response Runbook:**
```bash
# See specification/05_operations/02_deployment_and_operations.md § "Security Incident Response"
# Key steps:
# 1. Kill affected service (if leaking secrets).
# 2. Rotate credentials (encryption key, MINIO_ACCESS_KEY, etc.).
# 3. Audit logs: grep for PII patterns.
# 4. Notify Privacy Officer & Legal.
# 5. Post-mortem & controls improvement.
```

---

## Audit & Compliance Verification

### Annual Privacy Audit Checklist

| Control | Owner | Frequency | Evidence |
|---------|-------|-----------|----------|
| Privacy masking effectiveness | Analytics | Quarterly | Sample 100 frames; verify no faces/plates visible. |
| Encryption key rotation | InfoSec | Annual | Key version history; successful decryption test with old key. |
| Data retention compliance | Ops | Monthly | Delete logs showing 90-day parcel purge, 30-day capture cleanup. |
| Access control audit | Security | Quarterly | SSH logs; database query audit logs (no plaintext metadata reads). |
| DSAR processing | Privacy Officer | Per-request | DSAR log; response email sent, 30-day SLA verified. |
| Cloud sync DPA status | Legal | Annual | Verify processor agreement current; SCCs in place if needed. |
| Dependency security | InfoSec | Monthly | Scan container images for CVEs; audit ONNX Runtime version. |

### Third-Party Audit Readiness

**Documentation Required:**
- [ ] This Privacy & Compliance Spec (v1.0.0+).
- [ ] Data Processing Agreement (DPA) with cloud sync vendor.
- [ ] Standard Contractual Clauses (SCCs) if applicable.
- [ ] Privacy Policy (public-facing, operator-facing, linked from dashboard).
- [ ] Incident response runbook.
- [ ] Key rotation procedure.
- [ ] DSAR template response.

**Audit Scope:**
- Code review: privacy masking, encryption, log redaction.
- Infrastructure: network segmentation, TLS enforcement, backup encryption.
- Operational: key management, access logs, retention policies, incident logs.

---

## References & Further Reading

- **GDPR Text:** https://eur-lex.europa.eu/eli/reg/2016/679/oj
- **ICO Guidance (UK):** https://ico.org.uk/for-organisations/guide-to-the-general-data-protection-regulation/
- **EDPB Guidelines 05/2020 (Legitimate Interests):** https://edpb.ec.europa.eu/our-work-tools/our-documents_en
- **ISO 27001 (Information Security Management):** https://www.iso.org/standard/27001
- **NIST Privacy Framework:** https://www.nist.gov/privacy-framework
- **OWASP Top 10 Privacy Risks:** https://owasp.org/www-project-top-10-privacy-risks/

---

## Sign-Off

| Role | Name | Date | Approves |
|------|------|------|----------|
| Privacy Officer | TBD | — | Privacy & Compliance controls |
| InfoSec Lead | TBD | — | Encryption, key management |
| Legal / Compliance | TBD | — | GDPR & regulatory alignment |
| Product Owner | TBD | — | Business feasibility |

