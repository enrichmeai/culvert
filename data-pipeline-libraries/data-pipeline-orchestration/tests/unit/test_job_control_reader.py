"""Unit tests for the BigQuery job-control reader (`_job_control`).

The module had no tests at all, which is how its recency-wins collapse
(``ROW_NUMBER() ... ORDER BY updated_at DESC``) survived — spine AD-3 forbids
recency, and AD-14 rule 2 names this reader specifically.

The behaviour under test is not visible from a return value, because the
collapse happens inside BigQuery. So it is asserted two ways, and both must
hold for the fix to be non-deletable:

1. against the precedence table itself, semantically (failure outranks every
   other status), and
2. against the SQL actually handed to the client, so a query that stopped using
   that table would fail here.
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from data_pipeline_core.job_control_api import JobStatus

from data_pipeline_orchestration._job_control import (
    FAILED,
    SUCCEEDED,
    _PRECEDENCE_CASE,
    _STATUS_PRECEDENCE,
    _UNDECIDED_RANK,
    BigQueryJobControl,
)

SYSTEM_ID = "generic"
EXTRACT_DATE = date(2026, 4, 9)


def _rank(status: str) -> int:
    """Rank the reader's SQL assigns to a status; lower wins."""
    for value, rank in _STATUS_PRECEDENCE:
        if value == status:
            return rank
    return _UNDECIDED_RANK


class TestStatusPrecedence(unittest.TestCase):
    """AD-3: a terminal state is immutable and failure beats recency."""

    def test_failure_outranks_every_other_status(self):
        for status in JobStatus:
            if status is JobStatus.FAILED:
                continue
            self.assertLess(
                _rank(FAILED), _rank(status.value),
                f"'failed' must win over '{status.value}' (AD-3)",
            )

    def test_terminal_success_outranks_every_non_terminal_status(self):
        """Otherwise an in-flight re-run stalls a DAG whose entity is loaded."""
        for status in (JobStatus.CREATED, JobStatus.RUNNING, JobStatus.RETRYING):
            self.assertLess(
                _rank(SUCCEEDED), _rank(status.value),
                f"'succeeded' must win over '{status.value}'",
            )

    def test_failure_still_outranks_success(self):
        self.assertLess(_rank(FAILED), _rank(SUCCEEDED))

    def test_vocabulary_is_jobstatus_not_restated_literals(self):
        """AD-17: one vocabulary, lowercase wire values."""
        self.assertEqual(FAILED, JobStatus.FAILED.value)
        self.assertEqual(SUCCEEDED, JobStatus.SUCCEEDED.value)
        for value, _rank_ in _STATUS_PRECEDENCE:
            self.assertIn(value, {s.value for s in JobStatus})

    def test_case_expression_renders_the_precedence(self):
        self.assertIn(f"WHEN '{FAILED}' THEN {_rank(FAILED)}", _PRECEDENCE_CASE)
        self.assertIn(f"WHEN '{SUCCEEDED}' THEN {_rank(SUCCEEDED)}", _PRECEDENCE_CASE)
        self.assertIn(f"ELSE {_UNDECIDED_RANK}", _PRECEDENCE_CASE)


class TestGetEntityStatusSql(unittest.TestCase):
    """The query the reader actually sends."""

    def setUp(self):
        self.reader = BigQueryJobControl("test-project")
        self.client = MagicMock()
        self.client.query.return_value.result.return_value = []

    def _sql(self, method="get_entity_status"):
        with patch.object(BigQueryJobControl, "_client", return_value=self.client):
            getattr(self.reader, method)(SYSTEM_ID, EXTRACT_DATE)
        return self.client.query.call_args.args[0]

    def _params(self):
        job_config = self.client.query.call_args.kwargs["job_config"]
        return {p.name: p.value for p in job_config.query_parameters}

    def test_orders_by_precedence_before_recency(self):
        """Recency may only break a tie; it must not be the primary key."""
        sql = self._sql()
        order_by = sql.split("ORDER BY", 1)[1]
        precedence_at = order_by.index("CASE status")
        recency_at = order_by.index("updated_at DESC")
        self.assertLess(
            precedence_at, recency_at,
            "updated_at must not outrank the terminal-state precedence (AD-3)",
        )

    def test_does_not_collapse_by_recency_alone(self):
        """The exact defect AD-14 rule 2 names."""
        sql = " ".join(self._sql().split())
        self.assertNotIn("ORDER BY updated_at DESC) = 1", sql)

    def test_partitions_by_entity_type(self):
        self.assertIn("PARTITION BY entity_type", " ".join(self._sql().split()))

    def test_binds_system_and_date_as_parameters(self):
        self._sql()
        params = self._params()
        self.assertEqual(params["system_id"], SYSTEM_ID)
        self.assertEqual(params["extract_date"], EXTRACT_DATE)

    def test_get_failed_jobs_binds_the_status_vocabulary(self):
        sql = self._sql("get_failed_jobs")
        self.assertIn("status = @status", sql)
        self.assertEqual(self._params()["status"], FAILED)


if __name__ == "__main__":
    unittest.main()
