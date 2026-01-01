# Implementation Prompt: File Management & Archiving (LOA-PLAT-002)

**Ticket:** LOA-PLAT-002  
**Status:** Ready for Implementation  
**Effort:** 14 person-days (2-3 sprints)  
**Priority:** P0 - Critical Path First

---

## 🎯 IMPLEMENTATION OBJECTIVE

Complete the file management & archiving component to achieve:
- ✅ **All 7 acceptance criteria met**
- ✅ **100% test coverage** (120+ test cases)
- ✅ **Production-ready** code with audit trail
- ✅ **Airflow integration** examples
- ✅ **Complete documentation**

---

## 📋 PHASE 1: CRITICAL PATH (Days 1-9) - START HERE

### Task 1.1: Archive Policy Engine (Days 1-3)
**Objective:** Implement config-driven archive path resolution (AC 1)

**Files to Create:**
```
gdw_data_core/core/file_management/policy.py (NEW)
gdw_data_core/core/file_management/types.py (NEW)
archive_config.yaml (EXAMPLE)
```

**Implementation Requirements:**

1. **Create `policy.py` with:**
   - `CollisionStrategy` enum (TIMESTAMP, UUID, VERSION)
   - `ArchivePolicy` dataclass
   - `ArchivePolicyEngine` class with:
     - YAML configuration loading
     - Template variable resolution (entity, year, month, day, run_id)
     - Policy-based archive path generation
     - Collision detection and handling
     - Support for patterns like: `archive/{entity}/{year}/{month}/{day}/{filename}`

2. **Create `types.py` with:**
   - `ArchiveStatus` enum (SUCCESS, FAILED, PARTIAL, COLLISION_RESOLVED)
   - `ArchiveResult` dataclass with:
     - success, source_path, archive_path, archived_at, status
     - file_size, file_checksum, original_filename
     - to_xcom_dict() for Airflow compatibility
     - to_dict() and from_xcom_dict() methods

3. **Create `archive_config.yaml` example:**
   ```yaml
   archive_policies:
     - name: "standard_daily"
       pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
       collision_strategy: "timestamp"
       retention_days: 365
       enabled: true
     
     - name: "audit_logs"
       pattern: "archive/audit_logs/{year}/{month}/{filename}"
       collision_strategy: "uuid"
       retention_days: 2555
       enabled: true
   
   default_policy: "standard_daily"
   ```

**Acceptance Criteria:**
- [ ] `ArchivePolicyEngine` loads YAML configs
- [ ] Template variables resolved correctly
- [ ] Collision strategies implemented (timestamp, UUID, version)
- [ ] AC 1 & 1a satisfied: Config-driven paths with dynamic templating
- [ ] 20+ unit tests passing

**Code References:**
See `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md` Section 1 for complete code examples.

---

### Task 1.2: Update FileArchiver for Audit Integration (Days 3-4)
**Objective:** Implement audit trail recording (AC 3)

**Files to Modify:**
```
gdw_data_core/core/file_management/archiver.py (MODIFY)
gdw_data_core/core/file_management/__init__.py (UPDATE exports)
```

**Implementation Requirements:**

1. **Update `FileArchiver.__init__()` to accept:**
   ```python
   def __init__(
       self,
       source_bucket: str,
       archive_bucket: str,
       archive_prefix: str = 'archive',
       policy_engine: Optional[ArchivePolicyEngine] = None,
       audit_logger: Optional[AuditLogger] = None
   ):
   ```

2. **Update `archive_file()` method to:**
   - Accept entity and policy_name parameters
   - Use policy_engine for path resolution
   - Return `ArchiveResult` (not string)
   - Log operation to audit trail with:
     - Original path
     - Archive path
     - File size
     - File checksum
     - Timestamp
     - Status (SUCCESS/FAILED)
   - Handle FileNotFoundError gracefully
   - Record failures to audit trail

3. **Update `archive_batch()` to:**
   - Return Dict[str, ArchiveResult]
   - Support entity and policy_name parameters
   - Maintain detailed results for each file

4. **Keep existing methods:**
   - `restore_from_archive()`
   - `list_archived_files()`
   - Add new: `_default_archive_path()` as fallback

**Acceptance Criteria:**
- [ ] `archive_file()` returns `ArchiveResult`
- [ ] Audit trail records all operations
- [ ] AC 3 & 3a satisfied: Metadata logging
- [ ] AC 3b satisfied: Structured success signal
- [ ] XCom serialization works
- [ ] 25+ unit tests passing

**Code References:**
See `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md` Section 2.2 for updated archiver code.

---

### Task 1.3: Fix Error File Movement (Day 5)
**Objective:** Implement actual file movement to error bucket

**Files to Modify:**
```
gdw_data_core/core/file_management/lifecycle.py (MODIFY)
```

**Implementation Requirements:**

1. **Update `FileLifecycleManager.__init__()` to accept:**
   ```python
   def __init__(
       self,
       gcs_bucket: str,
       archive_bucket: str,
       error_bucket: str = None,  # ADD THIS
       error_handler: Optional[ErrorHandler] = None,
       monitoring: Optional[ObservabilityManager] = None
   ):
   ```

2. **Fix `handle_error_file()` method to:**
   - Add error_bucket parameter to __init__
   - Actually move the file to error bucket (copy + delete)
   - Generate error path: `error/{timestamp}/{filename}`
   - Log error file movement
   - Increment monitoring metrics
   - Return error path on success, None on failure

3. **Update `complete_lifecycle()` to:**
   - Pass error_bucket to handle_error_file calls
   - Ensure error files are moved, not just marked

**Acceptance Criteria:**
- [ ] Files actually moved to error bucket
- [ ] Atomic copy + delete operation
- [ ] Error paths generated correctly
- [ ] Audit trail records error movements
- [ ] 10+ error scenario unit tests passing

**Code References:**
See `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md` Section 3 for error handling code.

---

### Task 1.4: Build Comprehensive Test Suite (Days 6-9, Parallel)
**Objective:** Achieve 100% test coverage (120+ test cases)

**Files to Create:**
```
gdw_data_core/tests/unit/core/test_archive_policy.py (NEW - 20+ cases)
gdw_data_core/tests/unit/core/test_archiver.py (NEW - 25+ cases)
gdw_data_core/tests/unit/core/test_file_validator.py (NEW - 20+ cases)
gdw_data_core/tests/unit/core/test_metadata.py (NEW - 15+ cases)
gdw_data_core/tests/unit/core/test_lifecycle.py (NEW - 20+ cases)
gdw_data_core/tests/unit/core/test_integrity.py (NEW - 10+ cases)
gdw_data_core/tests/unit/core/conftest.py (NEW - fixtures)
```

**Test Coverage Requirements:**

**Archive Policy Tests (20+ cases):**
- Config loading from YAML
- Policy retrieval and defaults
- Template variable resolution
- Collision strategy application (timestamp, UUID, version)
- Missing variable error handling
- Disabled policy handling
- Invalid config error handling

**Archiver Tests (25+ cases):**
- Archive file with policy engine
- Archive result structure and serialization
- Audit trail recording
- GCS operations (mocked)
- File not found handling
- Permission denied handling
- Batch operations
- Collision resolution
- XCom compatibility
- Error state recording

**Validator Tests (20+ cases):**
- File existence validation
- Empty file detection
- Corruption detection
- CSV format validation
- Encoding validation
- Sample record validation
- Column extraction
- Delimiter validation
- Aggregate error collection

**Metadata Tests (15+ cases):**
- File size extraction
- Timestamp extraction
- Row counting
- Column parsing
- Checksum calculation
- All metadata extraction

**Lifecycle Tests (20+ cases):**
- Complete lifecycle flow
- Validation state transitions
- Processing state transitions
- Archive state transitions
- Error handling in each stage
- Error file movement
- Metadata extraction integration
- Monitoring integration

**Integrity Tests (10+ cases):**
- MD5 hash calculation
- SHA256 hash calculation
- Hash verification
- Size verification
- Checksum mismatch handling

**Test Infrastructure:**
- Create mock GCS client
- Create temporary test files
- Create sample CSV data
- Use pytest fixtures
- Mock storage.Client()
- Mock AuditLogger

**Acceptance Criteria:**
- [ ] 100+ unit test cases written
- [ ] 100% code coverage for archiver.py
- [ ] 100% code coverage for policy.py
- [ ] 100% code coverage for types.py
- [ ] All error scenarios tested
- [ ] All tests passing
- [ ] No critical linting issues
- [ ] Coverage report generated

**Code References:**
See `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md` Section 4 for sample test code.

---

## 📊 PHASE 1 COMPLETION CHECKLIST

**By End of Day 5 (Critical Path):**
- [ ] Archive Policy Engine complete (policy.py, types.py)
- [ ] archive_config.yaml example created
- [ ] FileArchiver updated with audit integration
- [ ] Error file movement fixed in lifecycle
- [ ] All P0 features implemented
- [ ] Code compiles without errors
- [ ] Ready for testing phase

**By End of Day 9 (Full Phase 1):**
- [ ] 120+ unit tests written and passing
- [ ] 100% code coverage achieved
- [ ] All error scenarios tested
- [ ] Code reviewed by lead engineer
- [ ] No critical linting issues
- [ ] Acceptance criteria 1-3 satisfied
- [ ] Ready for Phase 2

---

## 🔄 PHASE 2: COMPLETION (Days 10-14)

### Task 2.1: Multi-Backend Abstraction (Days 10-11)

**Create abstract base class:**
```
gdw_data_core/core/file_management/base.py (NEW)
```

**Refactor to:**
```
gdw_data_core/core/file_management/gcs_archiver.py (NEW - from archiver.py)
gdw_data_core/core/file_management/s3_archiver.py (NEW - skeleton)
gdw_data_core/core/file_management/factory.py (NEW)
```

**Requirements:**
- Create `BaseFileArchiver` abstract class
- Move GCS logic to `GCSFileArchiver`
- Create `S3FileArchiver` skeleton
- Storage factory pattern
- All tests still passing
- Backward compatibility maintained

---

### Task 2.2: Complete Documentation (Days 12-14)

**Create documentation files:**
```
docs/file_management/ARCHIVING_STANDARDS.md (NEW)
docs/file_management/ARCHIVE_CONFIGURATION_GUIDE.md (NEW)
docs/file_management/INTEGRATION_GUIDE.md (NEW)
examples/dags/example_archive_dag.py (NEW)
docs/file_management/TROUBLESHOOTING.md (NEW)
```

**Documentation Requirements:**
- Archiving Standards (path conventions, policies, best practices)
- Configuration Guide (YAML schema, examples, collision strategies)
- Integration Guide (usage examples, patterns, monitoring)
- Airflow DAG Example (complete working example with XCom)
- Troubleshooting Guide (common issues, debug patterns)

---

## ✅ PHASE 3: VALIDATION (Days 15-17)

### Task 3.1: Integration Testing
- End-to-end lifecycle tests
- GCS integration tests (with test bucket)
- Policy engine integration

### Task 3.2: Performance Testing
- Batch operation performance (100, 1000 files)
- Large file handling (>1GB)
- Policy engine performance

### Task 3.3: Security Review
- GCS bucket access patterns
- Credentials handling
- Error message sanitization
- Audit log content

### Task 3.4: UAT with Stakeholders
- Airflow DAG testing
- Real data archiving
- Error scenario validation
- Documentation review
- Go/no-go decision

---

## 🛠️ IMPLEMENTATION GUIDELINES

### Code Quality Standards
- ✅ Type hints on all functions
- ✅ Docstrings on all public methods with examples
- ✅ No hardcoded values (use configuration)
- ✅ Comprehensive error handling
- ✅ Proper logging with context
- ✅ No critical linting issues
- ✅ <10% code complexity

### Testing Standards
- ✅ Unit test per public method
- ✅ Error scenario coverage
- ✅ GCS mock tests (not real calls)
- ✅ Edge case coverage
- ✅ >95% code coverage target
- ✅ Fast test execution (<5 sec)

### Documentation Standards
- ✅ README for each module
- ✅ Docstring examples
- ✅ Configuration examples
- ✅ Integration examples
- ✅ Troubleshooting guide
- ✅ API reference

---

## 📦 DEPENDENCIES NEEDED

Add to `gdw_data_core/pyproject.toml`:
```python
dependencies = [
    # ...existing...
    "pyyaml>=6.0",  # For YAML config loading
    "google-cloud-storage>=2.10.0",  # Already listed
]
```

---

## 🧪 LOCAL TESTING CHECKLIST

Before committing:
```bash
# 1. Run all tests with coverage
pytest gdw_data_core/tests/unit/core/test_archive*.py -v --cov=gdw_data_core/core/file_management --cov-report=html

# 2. Check for linting issues
pylint gdw_data_core/core/file_management/

# 3. Type checking
mypy gdw_data_core/core/file_management/

# 4. Verify imports work
python -c "from gdw_data_core.core.file_management import FileArchiver, ArchivePolicyEngine, ArchiveResult"

# 5. Run docstring examples
doctest gdw_data_core/core/file_management/archiver.py -v
```

---

## 📋 DAILY STANDUP TEMPLATE

**Each day report:**
- What was completed?
- What are we working on today?
- What blockers do we have?
- Test coverage %?
- Any code quality issues?

---

## 🎯 SUCCESS CRITERIA

### By End of Phase 1 (Day 9)
- [ ] Policy engine fully functional
- [ ] Audit integration working
- [ ] Error handling fixed
- [ ] 120+ tests passing (100% coverage)
- [ ] AC 1, 1a, 2, 2a, 3, 3a, 3b all satisfied
- [ ] Ready for phase 2

### By End of Phase 2 (Day 14)
- [ ] Multi-backend abstraction complete
- [ ] Complete documentation
- [ ] All examples working
- [ ] Integration tests passing

### By End of Phase 3 (Day 17)
- [ ] Performance tests passing
- [ ] Security review passed
- [ ] UAT approved by stakeholders
- [ ] Production ready
- [ ] Ready for deployment

---

## 📞 BLOCKERS & ESCALATION

**If blocked on:**
- **Dependencies:** Contact Tech Lead
- **GCS access:** Contact DevOps
- **Design questions:** Contact Principal Engineer
- **Resource issues:** Contact Engineering Lead
- **Timeline concerns:** Contact Project Manager

---

## 🚀 READY TO BEGIN?

**Before starting:**
1. [ ] Read `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md` fully
2. [ ] Review `IMPLEMENTATION_CHECKLIST.md` for detailed tasks
3. [ ] Attend team kickoff meeting
4. [ ] Clone feature branch
5. [ ] Set up local test environment
6. [ ] Review existing code in `gdw_data_core/core/file_management/`

**Start with:**
1. Create `gdw_data_core/core/file_management/policy.py`
2. Create sample `archive_config.yaml`
3. Write tests for policy engine
4. Then proceed to Task 1.2

---

## 📚 REFERENCE DOCUMENTS

- **Code Examples:** `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md`
- **Task Details:** `IMPLEMENTATION_CHECKLIST.md`
- **Technical Review:** `FILE_MANAGEMENT_IMPLEMENTATION_REVIEW.md`
- **Ticket Description:** `TICKET_DESCRIPTION_FILE_MANAGEMENT_ARCHIVING.md`

---

## ✨ FINAL NOTES

- **Copy-paste ready code available** in implementation guide
- **Don't reinvent the wheel** - use provided examples
- **Test as you go** - don't leave testing for the end
- **Commit frequently** - small, reviewable commits
- **Ask questions early** - don't get stuck
- **Celebrate wins** - Phase 1 completion is major milestone

---

**Good luck! You've got this. 🎯**

**Timeline:** 14 days  
**Resources:** 3-4 engineers + QA  
**Estimated Completion:** 2-3 weeks from start


