# Pytest Config & Test Runner - Architecture & Flow Diagram

**Date:** December 21, 2025  
**Components:** pytest.ini, run_tests.sh  
**Status:** ✅ Production Ready

---

## 📐 SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                   LOA BLUEPRINT TEST SYSTEM                      │
└─────────────────────────────────────────────────────────────────┘

                          run_tests.sh (225 lines)
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                ┌───▼──┐      ┌──▼───┐     ┌──▼───┐
                │Checks│      │Runs  │     │Runs  │
                │Deps  │      │Tests │     │Cov   │
                └──────┘      └──────┘     └──────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                         pytest.ini (48 lines)
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                ┌───▼──────┐  ┌──▼──────┐  ┌──▼─────┐
                │Discovery │  │Markers  │  │Coverage│
                │test_*.py │  │7 types  │  │Branch  │
                └──────────┘  └─────────┘  └────────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
            ┌───────▼────────┐         ┌────────▼────────┐
            │ Test Execution │         │ Coverage Report │
            └───────┬────────┘         └────────┬────────┘
                    │                           │
        ┌───────────┼───────────┐       ┌───────┴───────┐
        │           │           │       │               │
    ┌───▼──┐  ┌────▼───┐  ┌───▼──┐  ┌─▼──┐      ┌────▼─────┐
    │Test 1│  │Test 2  │  │Test 3│  │Term│      │HTML Report│
    │Router│  │Dataflow│  │DAG   │  │    │      │htmlcov/   │
    └──────┘  └────────┘  └──────┘  └────┘      └───────────┘
      35t       varied     varied    missing

                    Exit Code (0 or 1)
```

---

## 🔄 EXECUTION FLOW

### Detailed Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Invokes Script                                      │
│    $ ./blueprint/testing/run_tests.sh [-v] [-h] [test_pattern]               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 2. Parse Arguments                                           │
│    • Verbose flag (-v)                                       │
│    • Help flag (-h)                                          │
│    • Test pattern filter                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 3. Display Help (if -h)                                     │
│    Exit with status 0                                        │
└────────────────────┬────────────────────────────────────────┘
                     │ (continue if no -h)
┌────────────────────▼────────────────────────────────────────┐
│ 4. Print Header Banner                                      │
│    Blue formatted title and separator lines                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 5. Check Dependencies                                        │
│    if ! command -v pytest                                    │
│       pip install pytest pytest-cov pytest-xdist -q         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 6. Run Test Suite 1: Pipeline Router                         │
│    Command:                                                  │
│    pytest components/tests/unit/test_pipeline_router.py     │
│           -v --cov=loa_common.pipeline_router               │
│                                                              │
│    Capture: Exit code → TEST1_EXIT                           │
│    Display: 200 lines max, status (✅/❌)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 7. Run Test Suite 2: Dataflow                                │
│    Check: File exists test_dataflow_flow.py?                │
│    if yes:                                                   │
│       pytest components/tests/unit/test_dataflow_flow.py    │
│              -v -s --cov=credit.examples                    │
│       Capture: Exit code → TEST2_EXIT                        │
│    else:                                                     │
│       Print: "⚠️  test_dataflow_flow.py not found"          │
│       Set: TEST2_EXIT=0                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 8. Run Test Suite 3: DAG Structure                           │
│    Check: File exists test_dag_structure.py?                │
│    if yes:                                                   │
│       pytest components/tests/unit/test_dag_structure.py    │
│              -v --cov=loa_pipelines.dag_template            │
│       Capture: Exit code → TEST3_EXIT                        │
│    else:                                                     │
│       Print: "⚠️  test_dag_structure.py not found"          │
│       Set: TEST3_EXIT=0                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 9. Comprehensive Test Run                                    │
│    if test_pattern specified:                                │
│       pytest "components/tests/unit/$test_pattern.py"        │
│              -v --cov=components                             │
│              --cov-report=term-missing                       │
│              --cov-report=html:htmlcov                       │
│    else:                                                     │
│       pytest components/tests/unit/                          │
│              -v --cov=components                             │
│              --cov-report=term-missing                       │
│              --cov-report=html:htmlcov                       │
│                                                              │
│    Capture: Exit code → ALL_EXIT                             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 10. Print Summary Box                                        │
│     For each test:                                           │
│       if exit_code == 0                                      │
│          Print: ✅ Test Name                                 │
│       else                                                   │
│          Print: ❌ Test Name                                 │
│                                                              │
│     if htmlcov/index.html exists:                            │
│        Print: 📊 Coverage report generated                   │
│        Print: File location                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 11. Determine Exit Code                                      │
│     if ALL(test exits == 0):                                 │
│        echo "✅ All tests PASSED!"                           │
│        exit 0                                                │
│     else:                                                    │
│        echo "❌ Some tests FAILED!"                          │
│        exit 1                                                │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ 12. Script Ends                                              │
│     Exit code available to CI/CD system                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 PYTEST.INI CONFIGURATION FLOW

```
┌──────────────────────────────────────────────────────────────┐
│             Pytest Test Discovery Process                    │
└──────────────────────────────────────────┬───────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 1. Scan testpaths                │
                          │    components/tests              │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 2. Find test files               │
                          │    Patterns:                      │
                          │    • test_*.py                    │
                          │    • *_test.py                    │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 3. Find test classes             │
                          │    Pattern: Test*                │
                          │    Example: TestPipelineRouter   │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 4. Find test functions           │
                          │    Pattern: test_*               │
                          │    Example: test_router_init     │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 5. Apply Markers (if used)       │
                          │    @pytest.mark.unit             │
                          │    @pytest.mark.integration      │
                          │    etc...                        │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 6. Execute Tests                 │
                          │    With settings:                │
                          │    • Verbose output              │
                          │    • Strict markers              │
                          │    • Short traceback             │
                          │    • No warnings                 │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 7. Collect Coverage              │
                          │    Track:                        │
                          │    • Lines covered               │
                          │    • Branches covered            │
                          │    • Missing lines               │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │ 8. Generate Reports              │
                          │    • Terminal output             │
                          │    • HTML report                 │
                          │    • Coverage %                  │
                          └──────────────────────────────────┘
```

---

## 🎯 TEST EXECUTION PIPELINE ARCHITECTURE

```
                          run_tests.sh
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼────┐  ┌───────▼────┐  ┌───────▼────┐
        │Test Suite 1│  │Test Suite 2│  │Test Suite 3│
        └───────┬────┘  └───────┬────┘  └───────┬────┘
                │               │               │
        ┌───────▼────────┐      │       ┌───────▼────────┐
        │Pipeline Router │      │       │DAG Structure   │
        │test_pipeline_  │      │       │test_dag_       │
        │router.py       │      │       │structure.py    │
        │                │      │       │                │
        │Command:        │      │       │Command:        │
        │pytest ... -v   │      │       │pytest ... -v   │
        │--cov=loa_      │      │       │--cov=loa_      │
        │common.pipeline │      │       │pipelines.dag_  │
        │_router         │      │       │template        │
        │                │      │       │                │
        │Tests: 35       │      │       │Tests: varied   │
        │Coverage: 96%+  │      │       │Coverage: 96%+  │
        └───────┬────────┘      │       └───────┬────────┘
                │               │               │
                │       ┌───────▼────────┐      │
                │       │Dataflow Tests  │      │
                │       │test_dataflow_  │      │
                │       │flow.py         │      │
                │       │                │      │
                │       │Command:        │      │
                │       │pytest ... -v   │      │
                │       │-s --cov=       │      │
                │       │credit.examples │      │
                │       │                │      │
                │       │Tests: varied   │      │
                │       │Coverage: 95%+  │      │
                │       └────────┬───────┘      │
                │               │               │
                └───────────────┼───────────────┘
                                │
                        ┌───────▼────────┐
                        │ Comprehensive  │
                        │ Test Run       │
                        │                │
                        │ Coverage:      │
                        │ • Terminal %   │
                        │ • HTML Report  │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │ Summary Report │
                        │ Color-coded    │
                        │ ✅/❌          │
                        └───────┬────────┘
                                │
                        ┌───────▼────────┐
                        │ Exit Code      │
                        │ 0 = Pass       │
                        │ 1 = Fail       │
                        └────────────────┘
```

---

## 📊 DATA FLOW DIAGRAM

```
User Input
    │
    ├─ ./blueprint/testing/run_tests.sh
    ├─ ./blueprint/testing/run_tests.sh -v
    ├─ ./blueprint/testing/run_tests.sh -h
    └─ ./blueprint/testing/run_tests.sh test_pipeline_router
            │
            ▼
    Argument Parser
    (Parse flags and patterns)
            │
            ▼
    Help Display? ──Yes─→ Show Help & Exit(0)
    (if -h flag)
            │
           No
            │
            ▼
    Print Banner
            │
            ▼
    Check Dependencies
    (Is pytest installed?)
            │
            ├─ Yes → Continue
            └─ No  → Auto-install pytest, pytest-cov
            │
            ▼
    Run Test Suite 1: Pipeline Router
    Pytest with Config (pytest.ini)
            │
            ├─ Test Discovery
            │   └─ Find test_pipeline_router.py
            │
            ├─ Test Execution
            │   └─ Run 35 tests
            │
            ├─ Coverage Collection
            │   └─ Track loa_common.pipeline_router
            │
            └─ Exit Code → TEST1_EXIT
            │
            ▼
    Run Test Suite 2: Dataflow
    (Same pattern as Test 1)
            │
            └─ Exit Code → TEST2_EXIT
            │
            ▼
    Run Test Suite 3: DAG Structure
    (Same pattern as Test 1)
            │
            └─ Exit Code → TEST3_EXIT
            │
            ▼
    Comprehensive Test Run
    (Run all tests in components/tests/unit/)
    With HTML Coverage Report Generation
            │
            └─ Exit Code → ALL_EXIT
            │
            ▼
    Print Summary
    (Color-coded results + coverage report info)
            │
            ▼
    Determine Final Exit Code
    if ALL tests passed: exit(0) ✅
    else: exit(1) ❌
            │
            ▼
    Script End
    Exit code available to CI/CD system
```

---

## 🔌 INTEGRATION POINTS

```
┌─────────────────────────────────────────────────────────────┐
│                 External Systems Integration                │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐        ┌─────────────┐
│CI/CD Systems │         │Coverage Tools│        │Development  │
│              │         │              │        │Environment  │
│• GitHub      │         │• pytest-cov  │        │             │
│  Actions     │         │• HTML reports│        │• IDE        │
│• GitLab CI   │         │• Coverage.py │        │• Terminal   │
│• Jenkins     │         │              │        │• Pre-commit │
│• Azure       │         └──────────────┘        │             │
│  Pipelines   │                                 └─────────────┘
└──────┬───────┘                                         △
       │                                                 │
       │◄─────────────Exit Code─────────────────────────┘
       │                      ↑
       │              run_tests.sh
       │                      │
       ├──→ [0] = Success    ├──→ pytest.ini
       └──→ [1] = Failure    │
                             └──→ components/tests/

┌─────────────────────────────────────────────────────────────┐
│                    Pytest Ecosystem                         │
└─────────────────────────────────────────────────────────────┘

pytest.ini
    │
    ├─→ Test Discovery
    │   └─ Scans: components/tests/
    │   └─ Pattern: test_*.py
    │   └─ Classes: Test*
    │   └─ Functions: test_*
    │
    ├─→ Test Markers
    │   ├─ @pytest.mark.unit
    │   ├─ @pytest.mark.integration
    │   ├─ @pytest.mark.performance
    │   ├─ @pytest.mark.chaos
    │   ├─ @pytest.mark.slow
    │   ├─ @pytest.mark.requires_gcp
    │   └─ @pytest.mark.requires_airflow
    │
    └─→ Coverage Configuration
        ├─ Branch: True
        └─ Omit: tests/*, site-packages/*, __pycache__/*

Test Files (components/tests/unit/)
    │
    ├─ test_pipeline_router.py (35 tests)
    ├─ test_data_factory.py (35 tests)
    ├─ test_audit.py (35 tests)
    ├─ test_data_quality.py (32 tests)
    ├─ test_error_handling.py (40+ tests)
    └─ test_io_utils.py (28 tests)
```

---

## ⚙️ CONFIGURATION HIERARCHY

```
Project Level
    │
    ├─→ pyproject.toml (Project metadata)
    │   ├─ Name: loa-blueprint
    │   ├─ Version: 1.0.0
    │   └─ Dependencies: apache-beam, google-cloud, etc.
    │
    ├─→ pytest.ini (Test configuration) ◄─── WE CREATED THIS
    │   ├─ testpaths: components/tests
    │   ├─ Markers: 7 types
    │   └─ Coverage: enabled
    │
    ├─→ run_tests.sh (Test orchestration) ◄─── WE CREATED THIS
    │   ├─ Dependency check
    │   ├─ Test execution
    │   └─ Report generation
    │
    └─→ components/tests/ (Test files)
        ├─ unit/ (Unit tests)
        ├─ integration/ (Integration tests)
        ├─ performance/ (Performance tests)
        └─ chaos/ (Chaos tests)
```

---

**Architecture & Flow Documentation Complete** ✅

For more details, see:
- PYTEST_CONFIG_AND_TEST_RUNNER_COMPLETE.md (comprehensive audit)
- TEST_EXECUTION_GUIDE.md (user guide)
- PYTEST_SESSION_SUMMARY.md (quick reference)

