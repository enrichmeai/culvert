# JIRA TICKET: CORE-DQ-004 | Hybrid DQ Strategy & Capability Expansion

## 📋 Summary
Integrate the new Dataplex DQ standard into existing data pipelines while maintaining the current `gdw_data_core` quality checkers. This enables a hybrid quality strategy where managed services and custom code coexist.

---

## 📖 Description
**As a** Pipeline Engineer,  
**I want** to update my pipelines to optionally use Dataplex for quality checks alongside existing library-based validations,  
**So that** we can leverage the best tool for each specific data quality requirement (e.g., managed Spark for scale, custom Python for business logic).

### 🎯 Business Value
- **Operational Flexibility**: Choose between library-based "runtime" checks and Dataplex "post-load" scans.
- **Enhanced Coverage**: Combine custom statistical anomalies (IQR) with Dataplex's managed data profiling.
- **Risk Mitigation**: No forced migration; existing quality controls remain fully functional while new capabilities are added.
- **Governance Alignment**: Aggregate quality metrics from both engines into a unified view.

---

## ✅ Acceptance Criteria
- [ ] **Hybrid Pipeline Pattern**: Updated reference pipelines showing coexistence of `DataQualityChecker` and `DataplexChecker`.
- [ ] **DQ YAML Deployment**: Domain-specific YAML rule files created and deployed for assets utilizing Dataplex.
- [ ] **Unified Reporting**: Verification that results from both existing checkers and Dataplex scans are captured in the pipeline audit trail.
- [ ] **Documentation Update**: Quality guide updated to include the new Dataplex-centric standard as an additional capability.
- [ ] **Validation**: Verify that all pipelines continue to produce accurate quality alerts after the integration.

---

## 🛠 Hybrid Workflow
1. **Define Strategy**: Determine if a dataset needs Dataplex (large scale) or Library (fine-grained control) checks.
2. **Define Rules**: Create a `dq_rules.yaml` for Dataplex-managed assets.
3. **Update Code**: Add `checker.check_via_dataplex(...)` to the pipeline while keeping existing `checker.check_*` calls where necessary.
4. **Deploy & Monitor**: Monitor results from both engines in the unified reporting dashboard.

---

## 📋 Sub-Tasks
- [ ] Inventory pipelines that would benefit from Dataplex's managed Spark engine.
- [ ] Create/Deploy DQ YAMLs for high-volume data domains.
- [ ] Update migration pipelines to use the hybrid orchestration pattern.
- [ ] Update the central `DATA_QUALITY_GUIDE.md` to document the hybrid approach.
- [ ] Verify audit trail compatibility for unified reporting.

---

## 📚 References
- **Implementation Ticket**: `tickets/TICKET_DESCRIPTION_DATAPLEX_IMPLEMENTATION.md` (CORE-DQ-003)
- **Investigation Ticket**: `tickets/TICKET_DESCRIPTION_DATAPLEX_INVESTIGATION.md` (CORE-DQ-002)
