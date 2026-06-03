package com.enrichmeai.culvert.finops;

import com.enrichmeai.culvert.governance.DataClassification;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * Unit tests for {@link BudgetGovernancePolicy}, {@link BudgetExceededException},
 * and {@link BudgetViolationMode}.
 *
 * <p>No live GCP services are required; all tests are pure-Java.
 */
class BudgetGovernancePolicyTest {

    private static final double CEILING_USD = 10.0;
    private static final String RUN_ID = "test-run-001";

    // JUL log capture infrastructure
    private Logger budgetLogger;
    private CapturingHandler logCapture;
    private Level originalLevel;

    @BeforeEach
    void attachLogCapture() {
        budgetLogger = Logger.getLogger(BudgetGovernancePolicy.class.getName());
        logCapture = new CapturingHandler();
        budgetLogger.addHandler(logCapture);
        originalLevel = budgetLogger.getLevel();
        budgetLogger.setLevel(Level.ALL);
        // Prevent propagation to root logger during tests to avoid console noise
        budgetLogger.setUseParentHandlers(false);
    }

    @AfterEach
    void detachLogCapture() {
        budgetLogger.removeHandler(logCapture);
        budgetLogger.setLevel(originalLevel);
        budgetLogger.setUseParentHandlers(true);
    }

    // -------------------------------------------------------------------------
    // BLOCK mode tests
    // -------------------------------------------------------------------------

    @Test
    void block_mode_throws_when_cost_exceeds_ceiling() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
        CostMetrics overBudget = metricsWithCost(CEILING_USD + 0.01);

        assertThatThrownBy(() -> policy.checkBudget(overBudget, RUN_ID))
                .isInstanceOf(BudgetExceededException.class);
    }

    @Test
    void block_mode_does_not_throw_when_cost_under_ceiling() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
        CostMetrics underBudget = metricsWithCost(CEILING_USD - 0.01);

        assertThatCode(() -> policy.checkBudget(underBudget, RUN_ID))
                .doesNotThrowAnyException();
    }

    @Test
    void block_mode_does_not_throw_when_cost_equals_ceiling_boundary() {
        // Boundary: cost == ceiling is ALLOWED (strict > semantics).
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
        CostMetrics exactCeiling = metricsWithCost(CEILING_USD);

        assertThatCode(() -> policy.checkBudget(exactCeiling, RUN_ID))
                .doesNotThrowAnyException();
    }

    @Test
    void block_mode_zero_cost_is_allowed() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThatCode(() -> policy.checkBudget(CostMetrics.zero(RUN_ID), RUN_ID))
                .doesNotThrowAnyException();
    }

    // -------------------------------------------------------------------------
    // WARN mode tests
    // -------------------------------------------------------------------------

    @Test
    void warn_mode_never_throws_when_cost_exceeds_ceiling() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.WARN);
        CostMetrics overBudget = metricsWithCost(CEILING_USD + 100.0);

        assertThatCode(() -> policy.checkBudget(overBudget, RUN_ID))
                .doesNotThrowAnyException();
    }

    @Test
    void warn_mode_logs_warning_when_cost_exceeds_ceiling() throws Exception {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.WARN);
        CostMetrics overBudget = metricsWithCost(CEILING_USD + 5.0);

        policy.checkBudget(overBudget, RUN_ID);

        assertThat(logCapture.records).hasSize(1);
        LogRecord record = logCapture.records.get(0);
        assertThat(record.getLevel()).isEqualTo(Level.WARNING);
        assertThat(record.getMessage()).contains(RUN_ID);
    }

    @Test
    void warn_mode_does_not_log_when_cost_within_ceiling() throws Exception {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.WARN);
        CostMetrics underBudget = metricsWithCost(CEILING_USD - 1.0);

        policy.checkBudget(underBudget, RUN_ID);

        assertThat(logCapture.records).isEmpty();
    }

    // -------------------------------------------------------------------------
    // BudgetExceededException content tests
    // -------------------------------------------------------------------------

    @Test
    void exception_message_contains_run_id() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
        CostMetrics over = metricsWithCost(CEILING_USD + 1.0);

        assertThatThrownBy(() -> policy.checkBudget(over, RUN_ID))
                .isInstanceOf(BudgetExceededException.class)
                .hasMessageContaining(RUN_ID);
    }

    @Test
    void exception_message_contains_projected_cost_and_ceiling() {
        double ceiling = 25.0;
        double projected = 30.5;
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(ceiling, BudgetViolationMode.BLOCK);
        CostMetrics over = metricsWithCost(projected);

        assertThatThrownBy(() -> policy.checkBudget(over, RUN_ID))
                .isInstanceOf(BudgetExceededException.class)
                .hasMessageContaining("30.5")
                .hasMessageContaining("25.0");
    }

    @Test
    void exception_typed_accessors_carry_run_id_cost_ceiling() {
        double ceiling = 5.0;
        double projectedCost = 7.77;
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(ceiling, BudgetViolationMode.BLOCK);

        try {
            policy.checkBudget(metricsWithCost(projectedCost), RUN_ID);
        } catch (BudgetExceededException ex) {
            assertThat(ex.getRunId()).isEqualTo(RUN_ID);
            assertThat(ex.getProjectedCostUsd()).isEqualTo(projectedCost);
            assertThat(ex.getCeilingUsd()).isEqualTo(ceiling);
            return;
        }
        throw new AssertionError("BudgetExceededException was not thrown");
    }

    // -------------------------------------------------------------------------
    // GovernancePolicy contract methods (pass-through defaults)
    // -------------------------------------------------------------------------

    @Test
    void classify_returns_internal_for_any_field_and_table() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThat(policy.classify("email", "users")).isEqualTo(DataClassification.INTERNAL);
        assertThat(policy.classify("amount", "transactions")).isEqualTo(DataClassification.INTERNAL);
    }

    @Test
    void masking_for_returns_empty() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThat(policy.maskingFor("ssn", "employees")).isEmpty();
    }

    @Test
    void retention_for_returns_empty() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThat(policy.retentionFor("audit_log")).isEmpty();
    }

    // -------------------------------------------------------------------------
    // Constructor validation
    // -------------------------------------------------------------------------

    @Test
    void constructor_rejects_negative_ceiling() {
        assertThatThrownBy(() -> new BudgetGovernancePolicy(-1.0, BudgetViolationMode.BLOCK))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("ceilingUsd");
    }

    @Test
    void constructor_rejects_null_mode() {
        assertThatThrownBy(() -> new BudgetGovernancePolicy(CEILING_USD, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructor_accepts_zero_ceiling() {
        // A zero ceiling blocks everything > 0 (any non-zero projected cost).
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(0.0, BudgetViolationMode.BLOCK);

        assertThatThrownBy(() -> policy.checkBudget(metricsWithCost(0.01), RUN_ID))
                .isInstanceOf(BudgetExceededException.class);
    }

    @Test
    void check_budget_rejects_null_metrics() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThatThrownBy(() -> policy.checkBudget(null, RUN_ID))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void check_budget_rejects_null_run_id() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);

        assertThatThrownBy(() -> policy.checkBudget(metricsWithCost(1.0), null))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // Import safety: assert no com.google.cloud / org.apache.beam in source
    // -------------------------------------------------------------------------

    @Test
    void budget_governance_policy_has_no_gcp_or_beam_imports() throws Exception {
        // CWD for surefire is the module directory
        // (data-pipeline-libraries-java/data-pipeline-core-java).
        // We check for import statements specifically (lines starting with "import ")
        // so that documentary comments mentioning GCP do not trigger a false positive.
        Path src = Paths.get(
                "src/main/java/com/enrichmeai/culvert/finops/BudgetGovernancePolicy.java");
        List<String> importLines = Files.lines(src)
                .filter(line -> line.startsWith("import "))
                .collect(java.util.stream.Collectors.toList());

        for (String importLine : importLines) {
            assertThat(importLine)
                    .as("BudgetGovernancePolicy must not import com.google.cloud.*")
                    .doesNotContain("com.google.cloud");
            assertThat(importLine)
                    .as("BudgetGovernancePolicy must not import org.apache.beam.*")
                    .doesNotContain("org.apache.beam");
        }
    }

    @Test
    void budget_exceeded_exception_has_no_gcp_or_beam_imports() throws Exception {
        Path src = Paths.get(
                "src/main/java/com/enrichmeai/culvert/finops/BudgetExceededException.java");
        List<String> importLines = Files.lines(src)
                .filter(line -> line.startsWith("import "))
                .collect(java.util.stream.Collectors.toList());

        for (String importLine : importLines) {
            assertThat(importLine)
                    .as("BudgetExceededException must not import com.google.cloud.*")
                    .doesNotContain("com.google.cloud");
            assertThat(importLine)
                    .as("BudgetExceededException must not import org.apache.beam.*")
                    .doesNotContain("org.apache.beam");
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static CostMetrics metricsWithCost(double costUsd) {
        return CostMetrics.builder(RUN_ID)
                .estimatedCostUsd(costUsd)
                .build();
    }

    /** Captures JUL log records for assertion. */
    private static final class CapturingHandler extends Handler {
        final List<LogRecord> records = new ArrayList<>();

        @Override
        public void publish(LogRecord record) {
            records.add(record);
        }

        @Override
        public void flush() { }

        @Override
        public void close() { }
    }
}
