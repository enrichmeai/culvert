# File Management Ticket - Implementation Checklist & Roadmap

**Ticket:** LOA-PLAT-002  
**Estimated Effort:** 12-14 days  
**Target Completion:** 2-3 sprints

---

## Priority-Based Implementation Roadmap

### 🔴 PHASE 1: CRITICAL PATH (Sprint 1: 5-7 days)
**Objective:** Make ticket production-ready  
**Must Complete:** All P0 items

#### 1.1 Archive Policy Engine [2-3 days]

- [ ] Create `policy.py` module in `core/file_management/`
- [ ] Implement `CollisionStrategy` enum
  - [ ] TIMESTAMP strategy
  - [ ] UUID strategy
  - [ ] VERSION strategy
- [ ] Implement `ArchivePolicy` dataclass
- [ ] Implement `ArchivePolicyEngine` class
  - [ ] YAML configuration loading
  - [ ] Policy validation
  - [ ] Template variable resolution
  - [ ] Collision handling logic
- [ ] Create example `archive_config.yaml`
- [ ] Unit tests for policy engine (20+ test cases)
  - [ ] Config loading
  - [ ] Policy retrieval
  - [ ] Template resolution
  - [ ] Collision handling
  - [ ] Error scenarios

**Acceptance Criteria:**
- [ ] AC 1 met: Config-driven archiving paths
- [ ] AC 1a met: Dynamic path templating supported
- [ ] All collision strategies working
- [ ] Configuration examples provided

**Files to Create/Modify:**
```
NEW:
  - gdw_data_core/core/file_management/policy.py
  - archive_config.yaml (example)
  - gdw_data_core/tests/unit/core/test_archive_policy.py

MODIFY:
  - gdw_data_core/core/file_management/__init__.py
```

---

#### 1.2 Audit Integration [2 days]

- [ ] Create `types.py` module in `core/file_management/`
- [ ] Implement `ArchiveStatus` enum
- [ ] Implement `ArchiveResult` dataclass
  - [ ] to_xcom_dict() method
  - [ ] to_dict() method
  - [ ] from_xcom_dict() static method
- [ ] Update `FileArchiver` class
  - [ ] Accept `audit_logger` parameter
  - [ ] Accept `policy_engine` parameter
  - [ ] Update `archive_file()` to return `ArchiveResult`
  - [ ] Record operations to audit trail
  - [ ] Handle file metadata in result
- [ ] Update `FileLifecycleManager` class
  - [ ] Return structured results
  - [ ] Record lifecycle events to audit
- [ ] Unit tests for archiver (15+ test cases)
  - [ ] Archive result structure
  - [ ] Audit trail recording
  - [ ] XCom compatibility
  - [ ] Error scenarios

**Acceptance Criteria:**
- [ ] AC 3 met: Metadata logging implemented
- [ ] AC 3a met: Path + timestamp logged
- [ ] AC 3b met: Structured success signal returned
- [ ] XCom serialization working

**Files to Create/Modify:**
```
NEW:
  - gdw_data_core/core/file_management/types.py
  - gdw_data_core/tests/unit/core/test_archiver.py
  - gdw_data_core/tests/unit/core/test_archive_result.py

MODIFY:
  - gdw_data_core/core/file_management/archiver.py
  - gdw_data_core/core/file_management/lifecycle.py
  - gdw_data_core/core/file_management/__init__.py
```

---

#### 1.3 Fix Error File Movement [1 day]

- [ ] Update `FileLifecycleManager.handle_error_file()`
  - [ ] Accept `error_bucket` parameter in __init__
  - [ ] Implement actual file move (copy + delete)
  - [ ] Return error path
  - [ ] Log error movement
- [ ] Update `archive_file()` error handling
  - [ ] Move failed files to error bucket
  - [ ] Return error result with details
- [ ] Unit tests for error handling (10+ test cases)
  - [ ] File not found scenario
  - [ ] Error bucket move
  - [ ] Atomic operation verification
  - [ ] Error logging

**Acceptance Criteria:**
- [ ] Files actually moved to error bucket
- [ ] Error scenarios handled gracefully
- [ ] Audit trail records errors

**Files to Modify:**
```
- gdw_data_core/core/file_management/lifecycle.py
- gdw_data_core/tests/unit/core/test_lifecycle.py (create)
```

---

#### 1.4 Core Unit Test Suite [3-4 days]

**Coverage Target: 100% of core file management logic**

Create test files:
- [ ] `test_archive_policy.py` (20+ cases)
  - [ ] Config loading and parsing
  - [ ] Policy retrieval and defaults
  - [ ] Template variable resolution
  - [ ] Collision strategy application
  - [ ] Edge cases and errors

- [ ] `test_archiver.py` (25+ cases)
  - [ ] File archiving operations
  - [ ] Archive result structure
  - [ ] Audit trail integration
  - [ ] GCS operations (mocked)
  - [ ] Error scenarios

- [ ] `test_file_validator.py` (20+ cases)
  - [ ] File existence checks
  - [ ] CSV format validation
  - [ ] Encoding validation
  - [ ] Sample record validation
  - [ ] Error aggregation

- [ ] `test_metadata.py` (15+ cases)
  - [ ] Metadata extraction
  - [ ] Row counting
  - [ ] Column extraction
  - [ ] Checksum validation

- [ ] `test_lifecycle.py` (20+ cases)
  - [ ] Complete lifecycle flow
  - [ ] State transitions
  - [ ] Error handling
  - [ ] Atomic operations

- [ ] `test_integrity.py` (10+ cases)
  - [ ] Hash calculation
  - [ ] Checksum verification
  - [ ] Size verification

**Test Infrastructure:**
- [ ] Create `conftest.py` with fixtures
  - [ ] Mock GCS client
  - [ ] Temporary files
  - [ ] Sample data
- [ ] Create test mocks for storage client
- [ ] Set up coverage reporting

**Acceptance Criteria:**
- [ ] 100% code coverage for archiver.py
- [ ] 100% code coverage for validator.py
- [ ] 100% code coverage for metadata.py
- [ ] 100% code coverage for policy.py
- [ ] All tests passing
- [ ] No critical issues from linting

**Files to Create:**
```
NEW:
  - gdw_data_core/tests/unit/core/test_archive_policy.py
  - gdw_data_core/tests/unit/core/test_archiver.py
  - gdw_data_core/tests/unit/core/test_file_validator.py
  - gdw_data_core/tests/unit/core/test_metadata.py
  - gdw_data_core/tests/unit/core/test_lifecycle.py
  - gdw_data_core/tests/unit/core/test_integrity.py
  - gdw_data_core/tests/unit/core/conftest.py (if needed)
```

---

### ✅ PHASE 2: COMPLETION (Sprint 2: 3-4 days)
**Objective:** Production-ready with documentation and examples

#### 2.1 Abstraction Layer & Multi-Backend Support [2 days]

- [ ] Create `base.py` module with abstract base class
  - [ ] `BaseFileArchiver` abstract class
  - [ ] Define contract for all implementations
  - [ ] Define contract for collision handling
- [ ] Refactor `FileArchiver` as `GCSFileArchiver`
  - [ ] Inherit from `BaseFileArchiver`
  - [ ] Maintain full compatibility
  - [ ] Add specific GCS methods
- [ ] Create `S3FileArchiver` skeleton
  - [ ] Implement abstract methods
  - [ ] Document future implementation
- [ ] Create storage factory
  - [ ] Support GCS/S3 selection
  - [ ] Configuration-driven instantiation
- [ ] Unit tests for abstraction (15+ cases)
  - [ ] Abstract contract enforcement
  - [ ] Implementation compatibility
  - [ ] Factory pattern

**Acceptance Criteria:**
- [ ] Library readiness: Modular for multi-pipeline reuse
- [ ] BaseFileArchiver properly abstracted
- [ ] GCS/S3 switching supported
- [ ] No breaking changes to existing code

**Files to Create/Modify:**
```
NEW:
  - gdw_data_core/core/file_management/base.py
  - gdw_data_core/core/file_management/s3_archiver.py (skeleton)
  - gdw_data_core/core/file_management/factory.py
  - gdw_data_core/tests/unit/core/test_base_archiver.py

MODIFY:
  - gdw_data_core/core/file_management/archiver.py
  - gdw_data_core/core/file_management/__init__.py
```

---

#### 2.2 Documentation & Examples [1-1.5 days]

- [ ] Create `ARCHIVING_STANDARDS.md`
  - [ ] Path conventions
  - [ ] Policy definitions
  - [ ] Best practices
  - [ ] Retention policies
  - [ ] Directory structure examples

- [ ] Create `ARCHIVE_CONFIGURATION_GUIDE.md`
  - [ ] YAML schema documentation
  - [ ] Configuration examples
  - [ ] Policy examples
  - [ ] Variable templates
  - [ ] Collision strategy selection

- [ ] Create `INTEGRATION_GUIDE.md`
  - [ ] Usage examples
  - [ ] Airflow integration
  - [ ] Multi-pipeline patterns
  - [ ] Error handling patterns
  - [ ] Monitoring integration

- [ ] Create Airflow DAG example
  - [ ] `example_archive_dag.py`
  - [ ] Complete workflow
  - [ ] XCom usage
  - [ ] Error handling
  - [ ] Monitoring

- [ ] Create troubleshooting guide
  - [ ] Common issues
  - [ ] Debug patterns
  - [ ] Log interpretation
  - [ ] Recovery procedures

**Files to Create:**
```
NEW:
  - docs/file_management/ARCHIVING_STANDARDS.md
  - docs/file_management/ARCHIVE_CONFIGURATION_GUIDE.md
  - docs/file_management/INTEGRATION_GUIDE.md
  - examples/dags/example_archive_dag.py
  - docs/file_management/TROUBLESHOOTING.md
```

---

### 🎯 PHASE 3: VALIDATION & OPTIMIZATION (Sprint 3: 2-3 days)
**Objective:** Production validation and performance

#### 3.1 Integration Testing [1 day]

- [ ] End-to-end lifecycle tests
  - [ ] Validate → Process → Archive flow
  - [ ] Error scenarios
  - [ ] Batch operations
- [ ] GCS integration tests (with test bucket)
  - [ ] Actual file movement
  - [ ] Collision scenarios
  - [ ] Large file handling
- [ ] Policy engine integration
  - [ ] Config loading from file
  - [ ] Path resolution with real data
  - [ ] Policy changes without code changes

**Files to Create:**
```
NEW:
  - gdw_data_core/tests/integration/test_file_management_integration.py
  - gdw_data_core/tests/integration/conftest.py
```

---

#### 3.2 Performance & Load Testing [1 day]

- [ ] Batch operation performance
  - [ ] 100 files archiving
  - [ ] 1000 files archiving
  - [ ] Large files (>1GB)
- [ ] Policy engine performance
  - [ ] Config loading time
  - [ ] Path resolution time
  - [ ] Collision detection performance
- [ ] Create performance baselines

**Files to Create:**
```
NEW:
  - gdw_data_core/tests/performance/test_archive_performance.py
```

---

#### 3.3 Security Review [0.5 day]

- [ ] GCS bucket access patterns
- [ ] Credentials handling
- [ ] Error message sanitization
- [ ] Audit log content review
- [ ] Configuration security

---

#### 3.4 UAT with Stakeholders [1 day]

- [ ] Airflow DAG testing
- [ ] Real data archiving
- [ ] Error scenario validation
- [ ] Documentation clarity review
- [ ] Go/no-go decision

---

## Definition of Done Checklist

### Code Quality
- [ ] All code reviewed by 2+ engineers
- [ ] No critical linting issues
- [ ] Type hints on all functions
- [ ] Docstrings on all public methods
- [ ] No hardcoded values
- [ ] Configuration externalized

### Testing
- [ ] 100% unit test coverage
- [ ] 10+ integration test cases
- [ ] All error scenarios tested
- [ ] Performance baselines established
- [ ] Tests passing on CI/CD

### Documentation
- [ ] Archiving Standards document complete
- [ ] Configuration guide with examples
- [ ] Integration guide with patterns
- [ ] Airflow DAG example provided
- [ ] Troubleshooting guide written
- [ ] Code comments for complex logic

### Acceptance Criteria
- [ ] AC 1: Config-driven paths ✅
- [ ] AC 1a: Dynamic templating ✅
- [ ] AC 2: Atomic movement ✅
- [ ] AC 2a: Collision handling ✅
- [ ] AC 3: Metadata logging ✅
- [ ] AC 3a: Path + timestamp logging ✅
- [ ] AC 3b: Success signal ✅

### Production Readiness
- [ ] Security review passed
- [ ] Load testing completed
- [ ] Airflow integration tested
- [ ] Error scenarios validated
- [ ] Monitoring configured
- [ ] Rollback plan documented

---

## Resource Allocation

### Phase 1 (5-7 days)
- **Lead Engineer:** Policy Engine + Tests (3 days)
- **Senior Engineer:** Audit Integration + Error Fix (2.5 days)
- **QA:** Test Suite Development (4 days, parallel)
- **Tech Lead:** Code Review & Architecture (continuous)

### Phase 2 (3-4 days)
- **Engineer:** Abstraction Layer (2 days)
- **Tech Writer:** Documentation (1.5 days)
- **Engineer:** Examples & Integration (1 day)

### Phase 3 (2-3 days)
- **QA:** Integration & Performance Testing (1.5 days)
- **Security:** Security Review (0.5 days)
- **Team:** UAT & Finalization (1 day)

---

## Success Metrics

### Completion Metrics
- [ ] 100% of acceptance criteria met
- [ ] 100% of definition of done completed
- [ ] All 35 test cases passing
- [ ] Code coverage > 95%

### Quality Metrics
- [ ] Zero critical linting issues
- [ ] All code reviews approved
- [ ] Security review passed
- [ ] Performance tests baseline established

### Business Metrics
- [ ] Stakeholder UAT approved
- [ ] Documentation complete
- [ ] Team training completed
- [ ] Production deployment approved

---

## Risk Mitigation

### If behind schedule
1. Reduce scope: Move multi-backend support to future ticket
2. Extend timeline: Request 1 additional week
3. Add resources: Bring in additional engineer for tests

### If testing issues discovered
1. Extend test timeline: +2 days
2. Add performance testing: +1 day
3. Delay UAT if critical issues: until resolved

### If integration issues arise
1. Create tech debt ticket for resolution
2. Document workarounds
3. Plan refactoring for next version

---

## Sign-Off Checklist

### Product Owner
- [ ] Accept acceptance criteria completion
- [ ] Approve documentation
- [ ] Sign off on UAT results
- [ ] Approve production deployment

### Engineering Lead
- [ ] Approve code quality
- [ ] Verify test coverage
- [ ] Confirm security review
- [ ] Sign off on architecture

### QA Lead
- [ ] Approve test plan
- [ ] Verify test coverage
- [ ] Sign off on integration tests
- [ ] Approve release testing

### Security Team
- [ ] Review GCS operations
- [ ] Validate credential handling
- [ ] Approve configuration approach
- [ ] Sign off on security

---

## Timeline Summary

```
Day 1-2:   Policy Engine Development
Day 3-4:   Audit Integration Development
Day 5:     Error Handler Fix
Day 6-9:   Core Test Suite (parallel)
Day 10-11: Abstraction Layer & Documentation
Day 12-13: Integration Testing & Validation
Day 14:    UAT & Sign-off
```

**Total Effort:** 12-14 days  
**Team Size:** 3-4 engineers + QA + Tech Writer  
**Target Completion:** End of Sprint 2/Early Sprint 3

---

## Next Action Items

**By End of Week 1:**
1. [ ] Get approval from Product Owner
2. [ ] Allocate engineering resources
3. [ ] Create JIRA subtasks for each phase
4. [ ] Schedule team kickoff meeting
5. [ ] Set up CI/CD for tests

**By EOD Day 1 of Implementation:**
1. [ ] Create feature branch
2. [ ] Set up test infrastructure
3. [ ] Create empty files with TODOs
4. [ ] Begin policy engine development

---

**Prepared by:** Principal Engineer  
**Date:** December 31, 2025  
**Review Frequency:** Weekly sync meetings during implementation  
**Target Completion:** 3-4 weeks from start date

