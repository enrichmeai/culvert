package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.finops.BudgetGovernancePolicy;
import com.enrichmeai.culvert.finops.BudgetViolationMode;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.google.cloud.bigquery.BigQuery;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration sanity test for the cost-tracking wiring in
 * {@link DefaultRuntimeContext} (T13.4 / issue #72).
 *
 * <p>Verifies that a context built with a mocked {@link BigQueryFinOpsSink}
 * and a {@link BudgetGovernancePolicy} correctly exposes both via
 * {@link DefaultRuntimeContext#finops()} and
 * {@link DefaultRuntimeContext#governance()}.
 *
 * <p>No live GCP credentials or network required — the {@link BigQuery}
 * client is mocked with Mockito.
 */
@ExtendWith(MockitoExtension.class)
class RuntimeContextCostWiringTest {

    @Mock
    private BigQuery bigQueryClient;

    @Test
    void contextWiredWithSinkAndBudgetPolicyReturnsBothCorrectly() {
        // Build a BigQueryFinOpsSink backed by a mocked BigQuery client.
        BigQueryFinOpsSink sink = new BigQueryFinOpsSink(
                bigQueryClient, "test-project", "finops", BigQueryFinOpsSink.DEFAULT_TABLE);

        // Build a BudgetGovernancePolicy at $10 ceiling in BLOCK mode.
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK);

        // Wire both into a DefaultRuntimeContext via the builder convenience method.
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("run-cost-wire", "test")
                .config(Map.of())
                .register(FinOpsSink.class, sink)
                .budgetPolicy(policy)
                .build();

        // finops() must return the sink we registered.
        FinOpsSink resolvedSink = ctx.finops();
        assertThat(resolvedSink)
                .as("ctx.finops() must return the registered BigQueryFinOpsSink")
                .isSameAs(sink);

        // governance() must return the BudgetGovernancePolicy we registered.
        GovernancePolicy resolvedPolicy = ctx.governance();
        assertThat(resolvedPolicy)
                .as("ctx.governance() must return the registered BudgetGovernancePolicy")
                .isSameAs(policy)
                .isInstanceOf(BudgetGovernancePolicy.class);
    }

    @Test
    void budgetPolicyConvenienceIsEquivalentToExplicitRegister() {
        BudgetGovernancePolicy policy =
                new BudgetGovernancePolicy(25.0, BudgetViolationMode.WARN);

        // Using .budgetPolicy() shorthand
        DefaultRuntimeContext ctxConvenience = DefaultRuntimeContext
                .builder("run-conv", "test")
                .budgetPolicy(policy)
                .build();

        // Using explicit .register(GovernancePolicy.class, ...)
        DefaultRuntimeContext ctxExplicit = DefaultRuntimeContext
                .builder("run-expl", "test")
                .register(GovernancePolicy.class, policy)
                .build();

        assertThat(ctxConvenience.governance())
                .as("budgetPolicy() convenience must register against GovernancePolicy.class")
                .isSameAs(ctxExplicit.governance());
    }
}
