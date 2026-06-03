package com.enrichmeai.culvert.gcp.bigquery;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link CostAnalysisQueries}.
 *
 * <p>All assertions are offline (classpath-only) — no live GCP, no network.
 *
 * <p>T13.4 / issue #72.
 */
class CostAnalysisQueriesTest {

    // --- all four named blocks load non-empty ---------------------------------

    @ParameterizedTest
    @ValueSource(strings = {"cost_by_run", "cost_by_stage", "top_expensive_runs_7d", "budget_breach_log"})
    void loadQueryReturnsNonEmptyForAllFourNames(String name) {
        String sql = CostAnalysisQueries.loadQuery(name);
        assertThat(sql)
                .as("SQL for query '%s' must be non-empty", name)
                .isNotBlank();
    }

    // --- content spot-checks --------------------------------------------------

    @Test
    void costByRunReferencesRunIdAndEstimatedCostUsd() {
        String sql = CostAnalysisQueries.loadQuery("cost_by_run");
        assertThat(sql).containsIgnoringCase("run_id");
        assertThat(sql).containsIgnoringCase("estimated_cost_usd");
    }

    @Test
    void costByStageUnnestsLabels() {
        // The labels column is ARRAY<STRUCT>; stage must be accessed via UNNEST.
        String sql = CostAnalysisQueries.loadQuery("cost_by_stage");
        assertThat(sql).containsIgnoringCase("unnest");
        assertThat(sql).containsIgnoringCase("stage");
    }

    @Test
    void topExpensiveRuns7dContainsIntervalSevenDay() {
        String sql = CostAnalysisQueries.loadQuery("top_expensive_runs_7d");
        assertThat(sql).containsIgnoringCase("INTERVAL 7 DAY");
        assertThat(sql).containsIgnoringCase("LIMIT 10");
    }

    @Test
    void budgetBreachLogHasPositionalParameter() {
        String sql = CostAnalysisQueries.loadQuery("budget_breach_log");
        assertThat(sql).contains("?");
        assertThat(sql).containsIgnoringCase("estimated_cost_usd");
    }

    // --- error path -----------------------------------------------------------

    @Test
    void unknownNameThrowsIllegalArgumentException() {
        assertThatThrownBy(() -> CostAnalysisQueries.loadQuery("does_not_exist"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("does_not_exist");
    }

    @Test
    void nullNameThrowsNullPointerException() {
        assertThatThrownBy(() -> CostAnalysisQueries.loadQuery(null))
                .isInstanceOf(NullPointerException.class);
    }
}
