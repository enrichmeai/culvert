#!/usr/bin/env python
"""
Library Fix Validation Script
Validates all 8 gaps from LIBRARY_FIX_PROMPT.md are implemented correctly.
"""

import sys


def validate_gap1_hdr_trl_parser():
    """GAP 1: HDR/TRL Record Parser with configurable patterns"""
    from gdw_data_core.core.file_management import (
        HDRTRLParser,
        HeaderRecord,
        TrailerRecord,
        ParsedFileMetadata,
        DEFAULT_HDR_PATTERN,
        DEFAULT_TRL_PATTERN,
        DEFAULT_HDR_PREFIX,
        DEFAULT_TRL_PREFIX,
    )

    # Test default parser
    parser = HDRTRLParser()
    header = parser.parse_header("HDR|EM|Customer|20260101")
    assert header is not None, "Failed to parse header"
    assert header.system_id == "EM", f"Expected EM, got {header.system_id}"
    assert header.entity_type == "Customer", f"Expected Customer, got {header.entity_type}"

    trailer = parser.parse_trailer("TRL|RecordCount=100|Checksum=abc123")
    assert trailer is not None, "Failed to parse trailer"
    assert trailer.record_count == 100, f"Expected 100, got {trailer.record_count}"

    # Test custom patterns
    custom_parser = HDRTRLParser(
        hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
        trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
        hdr_prefix="HEADER:",
        trl_prefix="FOOTER:"
    )
    assert custom_parser.hdr_prefix == "HEADER:", "Custom prefix not set"

    print("  ✅ GAP 1: HDRTRLParser with configurable patterns - PASSED")
    return True


def validate_gap2_record_count():
    """GAP 2: Record Count Validator"""
    from gdw_data_core.core.file_management import validate_record_count

    lines = [
        "HDR|EM|Customer|20260101",
        "id,name,ssn",
        "1,John,123-45-6789",
        "2,Jane,987-65-4321",
        "TRL|RecordCount=2|Checksum=abc"
    ]

    is_valid, msg = validate_record_count(lines, expected_count=2, has_csv_header=True)
    assert is_valid, f"Expected valid, got: {msg}"

    is_valid, msg = validate_record_count(lines, expected_count=5, has_csv_header=True)
    assert not is_valid, "Expected invalid for wrong count"

    print("  ✅ GAP 2: Record Count Validator - PASSED")
    return True


def validate_gap3_checksum():
    """GAP 3: Checksum Validator"""
    from gdw_data_core.core.file_management import compute_checksum, validate_checksum

    lines = ["line1", "line2", "line3"]
    checksum = compute_checksum(lines, algorithm="md5")
    assert len(checksum) == 32, f"Expected 32 char MD5, got {len(checksum)}"

    is_valid, msg = validate_checksum(lines, checksum, algorithm="md5")
    assert is_valid, f"Expected valid checksum: {msg}"

    is_valid, msg = validate_checksum(lines, "wrongchecksum", algorithm="md5")
    assert not is_valid, "Expected invalid for wrong checksum"

    print("  ✅ GAP 3: Checksum Validator - PASSED")
    return True


def validate_gap4_job_control():
    """GAP 4: Job Control Operations"""
    from gdw_data_core.core.job_control import (
        JobControlRepository,
        JobStatus,
        PipelineJob,
        FailureStage,
    )
    from datetime import date

    # Test JobStatus enum
    assert JobStatus.PENDING.value == "PENDING"
    assert JobStatus.RUNNING.value == "RUNNING"
    assert JobStatus.SUCCESS.value == "SUCCESS"
    assert JobStatus.FAILED.value == "FAILED"

    # Test FailureStage enum
    assert FailureStage.FILE_DISCOVERY.value == "FILE_DISCOVERY"
    assert FailureStage.ODP_LOAD.value == "ODP_LOAD"

    # Test PipelineJob model
    job = PipelineJob(
        run_id="test_run_001",
        system_id="EM",
        entity_type="Customer",
        extract_date=date(2026, 1, 1),
    )
    assert job.status == JobStatus.PENDING, "Default status should be PENDING"
    assert job.run_id == "test_run_001"

    # Test JobControlRepository can be instantiated
    # Note: actual DB operations need mock
    repo = JobControlRepository(project_id="test-project")
    assert repo.project_id == "test-project"
    assert repo.dataset == "job_control"
    assert repo.table == "pipeline_jobs"

    print("  ✅ GAP 4: Job Control Operations - PASSED")
    return True


def validate_gap5_entity_dependency():
    """GAP 5: Entity Dependency Check (Generic, no hardcoded config)"""
    from gdw_data_core.orchestration import EntityDependencyChecker
    import inspect

    # Verify constructor requires system_id and required_entities
    sig = inspect.signature(EntityDependencyChecker.__init__)
    params = list(sig.parameters.keys())
    assert 'system_id' in params, "system_id parameter missing"
    assert 'required_entities' in params, "required_entities parameter missing"

    # Verify no hardcoded SYSTEM_DEPENDENCIES in module
    import gdw_data_core.orchestration.dependency as dep_module
    module_attrs = dir(dep_module)
    assert 'SYSTEM_DEPENDENCIES' not in module_attrs, "Hardcoded SYSTEM_DEPENDENCIES found!"

    print("  ✅ GAP 5: EntityDependencyChecker (generic) - PASSED")
    return True


def validate_gap6_csv_parser():
    """GAP 6: HDR/TRL Skip in CSV Parser"""
    from gdw_data_core.pipelines.beam.transforms import ParseCsvLine
    import inspect

    # Verify constructor has hdr_prefix and trl_prefix parameters
    sig = inspect.signature(ParseCsvLine.__init__)
    params = list(sig.parameters.keys())
    assert 'skip_hdr_trl' in params, "skip_hdr_trl parameter missing"
    assert 'hdr_prefix' in params, "hdr_prefix parameter missing"
    assert 'trl_prefix' in params, "trl_prefix parameter missing"

    # Test instantiation with custom prefixes
    parser = ParseCsvLine(
        headers=["id", "name"],
        skip_hdr_trl=True,
        hdr_prefix="HEADER:",
        trl_prefix="FOOTER:"
    )
    assert parser.hdr_prefix == "HEADER:"
    assert parser.trl_prefix == "FOOTER:"

    print("  ✅ GAP 6: ParseCsvLine with HDR/TRL skip - PASSED")
    return True


def validate_gap7_duplicate_keys():
    """GAP 7: Duplicate Key Validator"""
    from gdw_data_core.core.data_quality import check_duplicate_keys

    records = [
        {"id": "1", "name": "John"},
        {"id": "2", "name": "Jane"},
        {"id": "1", "name": "Duplicate"},  # Duplicate
    ]

    has_dups, dups = check_duplicate_keys(records, key_fields=["id"])
    assert has_dups, "Should detect duplicates"
    assert len(dups) > 0, "Should return duplicate records"

    no_dup_records = [
        {"id": "1", "name": "John"},
        {"id": "2", "name": "Jane"},
    ]
    has_dups, dups = check_duplicate_keys(no_dup_records, key_fields=["id"])
    assert not has_dups, "Should not detect duplicates"

    print("  ✅ GAP 7: Duplicate Key Validator - PASSED")
    return True


def validate_gap8_row_type_validator():
    """GAP 8: Row Type Validator with configurable prefixes"""
    from gdw_data_core.core.data_quality import validate_row_types
    import inspect

    # Verify function has configurable prefixes
    sig = inspect.signature(validate_row_types)
    params = list(sig.parameters.keys())
    assert 'hdr_prefix' in params, "hdr_prefix parameter missing"
    assert 'trl_prefix' in params, "trl_prefix parameter missing"

    # Test with default prefixes
    lines = [
        "HDR|EM|Customer|20260101",
        "id,name,ssn",
        "1,John,123-45-6789",
        "TRL|RecordCount=1|Checksum=abc"
    ]
    is_valid, msg = validate_row_types(lines)
    assert is_valid, f"Expected valid: {msg}"

    # Test with custom prefixes
    custom_lines = [
        "HEADER:EM:Customer:20260101",
        "data line",
        "FOOTER:COUNT=1:HASH=abc"
    ]
    is_valid, msg = validate_row_types(
        custom_lines,
        hdr_prefix="HEADER:",
        trl_prefix="FOOTER:"
    )
    assert is_valid, f"Expected valid with custom prefixes: {msg}"

    print("  ✅ GAP 8: Row Type Validator with prefixes - PASSED")
    return True


def main():
    print("\n" + "="*60)
    print("LIBRARY FIX VALIDATION")
    print("="*60 + "\n")

    validations = [
        ("GAP 1", validate_gap1_hdr_trl_parser),
        ("GAP 2", validate_gap2_record_count),
        ("GAP 3", validate_gap3_checksum),
        ("GAP 4", validate_gap4_job_control),
        ("GAP 5", validate_gap5_entity_dependency),
        ("GAP 6", validate_gap6_csv_parser),
        ("GAP 7", validate_gap7_duplicate_keys),
        ("GAP 8", validate_gap8_row_type_validator),
    ]

    passed = 0
    failed = 0

    for name, func in validations:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: FAILED - {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    if failed == 0:
        print("\n✅ ALL LIBRARY GAPS VALIDATED SUCCESSFULLY!")
        print("   Library is ready for blueprint implementation.\n")
        return 0
    else:
        print(f"\n❌ {failed} validation(s) failed. Please fix before proceeding.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

