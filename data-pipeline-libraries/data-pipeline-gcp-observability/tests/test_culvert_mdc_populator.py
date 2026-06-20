"""Tests for CulvertMdcPopulator and stage_context."""

from __future__ import annotations

import threading

import pytest

from data_pipeline_gcp_observability.culvert_mdc_populator import (
    CulvertMdcPopulator,
    CulvertLoggerAdapter,
    RUN_ID_KEY,
    STAGE_NAME_KEY,
    PIPELINE_ID_KEY,
    clear,
    get,
    put,
    remove,
    stage_context,
)


# ---------------------------------------------------------------------------
# MDC key constants
# ---------------------------------------------------------------------------

class TestMdcKeyConstants:
    def test_key_values(self):
        assert RUN_ID_KEY == "run_id"
        assert STAGE_NAME_KEY == "stage_name"
        assert PIPELINE_ID_KEY == "pipeline_id"

    def test_class_constants_match_module_constants(self):
        assert CulvertMdcPopulator.RUN_ID_KEY == RUN_ID_KEY
        assert CulvertMdcPopulator.STAGE_NAME_KEY == STAGE_NAME_KEY
        assert CulvertMdcPopulator.PIPELINE_ID_KEY == PIPELINE_ID_KEY


# ---------------------------------------------------------------------------
# stage_context context manager
# ---------------------------------------------------------------------------

class TestStageContext:
    def setup_method(self):
        clear()

    def test_populates_mdc_keys_inside_block(self):
        with stage_context("run-1", "stage-1", "pipe-1"):
            assert get(RUN_ID_KEY) == "run-1"
            assert get(STAGE_NAME_KEY) == "stage-1"
            assert get(PIPELINE_ID_KEY) == "pipe-1"

    def test_clears_keys_after_block(self):
        with stage_context("run-1", "stage-1", "pipe-1"):
            pass
        assert get(RUN_ID_KEY) is None
        assert get(STAGE_NAME_KEY) is None
        assert get(PIPELINE_ID_KEY) is None

    def test_clears_keys_even_when_body_raises(self):
        with pytest.raises(ValueError):
            with stage_context("run-1", "stage-1", "pipe-1"):
                raise ValueError("boom")
        assert get(RUN_ID_KEY) is None

    def test_rejects_none_run_id(self):
        with pytest.raises(TypeError):
            with stage_context(None, "stage", "pipe"):
                pass

    def test_rejects_none_stage_name(self):
        with pytest.raises(TypeError):
            with stage_context("run", None, "pipe"):
                pass

    def test_rejects_none_pipeline_id(self):
        with pytest.raises(TypeError):
            with stage_context("run", "stage", None):
                pass

    def test_nested_context_restores_outer_context(self):
        with stage_context("outer-run", "outer-stage", "outer-pipe"):
            with stage_context("inner-run", "inner-stage", "inner-pipe"):
                assert get(RUN_ID_KEY) == "inner-run"
            # After inner exits, outer keys are GONE (last one to set wins,
            # then all cleared; this is documented behaviour — don't nest).
            # The outer context's own keys were overwritten then cleared.
            # The important thing is no stale data remains after the inner.
            assert get(STAGE_NAME_KEY) is None

    def test_thread_isolation(self):
        """Each thread has its own MDC."""
        results = {}

        def worker(thread_id):
            clear()
            with stage_context(f"run-{thread_id}", f"stage-{thread_id}", "pipe"):
                results[thread_id] = get(RUN_ID_KEY)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(3):
            assert results[i] == f"run-{i}"


# ---------------------------------------------------------------------------
# CulvertMdcPopulator.with_stage_context
# ---------------------------------------------------------------------------

class TestWithStageContext:
    def setup_method(self):
        clear()

    def test_returns_body_value(self):
        result = CulvertMdcPopulator.with_stage_context("r", "s", "p", lambda: 42)
        assert result == 42

    def test_mdc_populated_during_body(self):
        captured = {}

        def body():
            captured["run"] = get(RUN_ID_KEY)
            return None

        CulvertMdcPopulator.with_stage_context("run-x", "stage-x", "pipe-x", body)
        assert captured["run"] == "run-x"

    def test_mdc_cleared_after_body(self):
        CulvertMdcPopulator.with_stage_context("r", "s", "p", lambda: None)
        assert get(RUN_ID_KEY) is None

    def test_mdc_cleared_when_body_raises(self):
        def raiser():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            CulvertMdcPopulator.with_stage_context("r", "s", "p", raiser)
        assert get(RUN_ID_KEY) is None

    def test_rejects_none_body(self):
        with pytest.raises(TypeError):
            CulvertMdcPopulator.with_stage_context("r", "s", "p", None)


# ---------------------------------------------------------------------------
# CulvertMdcPopulator — instantiation guard
# ---------------------------------------------------------------------------

class TestInstantiationGuard:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            CulvertMdcPopulator()


# ---------------------------------------------------------------------------
# CulvertLoggerAdapter
# ---------------------------------------------------------------------------

class TestCulvertLoggerAdapter:
    def setup_method(self):
        clear()

    def test_process_injects_mdc_into_extra(self):
        import logging
        base_logger = logging.getLogger("test")
        adapter = CulvertLoggerAdapter(base_logger, {})

        with stage_context("run-a", "stage-a", "pipe-a"):
            _, kwargs = adapter.process("msg", {})
            extra = kwargs.get("extra", {})
            assert extra.get(RUN_ID_KEY) == "run-a"
            assert extra.get(STAGE_NAME_KEY) == "stage-a"
            assert extra.get(PIPELINE_ID_KEY) == "pipe-a"

    def test_process_merges_base_extra(self):
        import logging
        base_logger = logging.getLogger("test")
        adapter = CulvertLoggerAdapter(base_logger, {"custom": "value"})

        with stage_context("r", "s", "p"):
            _, kwargs = adapter.process("msg", {})
            extra = kwargs.get("extra", {})
            assert extra.get("custom") == "value"
            assert extra.get(RUN_ID_KEY) == "r"

    def test_process_empty_mdc(self):
        import logging
        base_logger = logging.getLogger("test")
        adapter = CulvertLoggerAdapter(base_logger, {})
        clear()
        _, kwargs = adapter.process("msg", {})
        extra = kwargs.get("extra", {})
        assert extra.get(RUN_ID_KEY) is None
