package com.enrichmeai.culvert;

import com.enrichmeai.culvert.contracts.AuditEventPublisher;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.Pipeline;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.SecretProvider;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.contracts.Transform;
import com.enrichmeai.culvert.contracts.Warehouse;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Smoke test: every contract interface is importable and exposes the expected
 * public method surface. If any of these fail, the package layout or the
 * interface declarations have drifted.
 *
 * <p>Mirror of the Python {@code tests/test_contracts_importable.py} test.
 * Behavioural conformance is checked by Stage 4's contract-test suite, not
 * here.
 */
class ContractsImportableTest {

    @Test
    void all_fifteen_contracts_are_loadable() {
        // If any of these fail to load, the test fails at class load time.
        Class<?>[] contracts = new Class<?>[] {
                Source.class, Sink.class, Transform.class,
                Pipeline.class, PipelineStage.class, RuntimeContext.class,
                JobControlRepository.class, BlobStore.class, Warehouse.class,
                AuditEventPublisher.class, GovernancePolicy.class,
                LineageEmitter.class, ObservabilityHook.class,
                FinOpsSink.class, SecretProvider.class,
        };
        assertThat(contracts).hasSize(15);
        for (Class<?> c : contracts) {
            assertThat(c.isInterface())
                    .as("%s must be an interface", c.getName())
                    .isTrue();
        }
    }

    @Test
    void source_has_read_method() {
        assertHasMethod(Source.class, "read");
    }

    @Test
    void sink_has_write_method() {
        assertHasMethod(Sink.class, "write");
    }

    @Test
    void transform_has_apply_method() {
        assertHasMethod(Transform.class, "apply");
    }

    @Test
    void pipeline_has_name_stages_validate() {
        assertHasMethod(Pipeline.class, "name");
        assertHasMethod(Pipeline.class, "stages");
        assertHasMethod(Pipeline.class, "validate");
    }

    @Test
    void pipeline_stage_has_name_inputs_outputs_execute() {
        assertHasMethod(PipelineStage.class, "name");
        assertHasMethod(PipelineStage.class, "inputs");
        assertHasMethod(PipelineStage.class, "outputs");
        assertHasMethod(PipelineStage.class, "execute");
    }

    @Test
    void runtime_context_has_get_register_and_accessors() {
        assertHasMethod(RuntimeContext.class, "get");
        assertHasMethod(RuntimeContext.class, "register");
        assertHasMethod(RuntimeContext.class, "runId");
        assertHasMethod(RuntimeContext.class, "environment");
        assertHasMethod(RuntimeContext.class, "secrets");
        assertHasMethod(RuntimeContext.class, "observability");
        assertHasMethod(RuntimeContext.class, "lineage");
        assertHasMethod(RuntimeContext.class, "finops");
        assertHasMethod(RuntimeContext.class, "governance");
    }

    @Test
    void job_control_repository_has_all_eleven_methods() {
        Set<String> expected = Set.of(
                "createJob", "getJob", "updateStatus", "markFailed", "markRetrying",
                "getPendingJobs", "getEntityStatus", "getFailedJobs",
                "getFdpJobStatus", "cleanupPartialLoad", "updateCostMetrics");
        Set<String> actual = Arrays.stream(JobControlRepository.class.getDeclaredMethods())
                .map(Method::getName)
                .collect(Collectors.toSet());
        assertThat(actual).containsAll(expected);
    }

    @Test
    void blob_store_has_seven_methods() {
        Set<String> expected = Set.of(
                "get", "openInput", "openOutput", "put", "list", "exists", "delete", "copy");
        Set<String> actual = Arrays.stream(BlobStore.class.getDeclaredMethods())
                .map(Method::getName)
                .collect(Collectors.toSet());
        assertThat(actual).containsAll(expected);
    }

    @Test
    void warehouse_has_six_methods() {
        Set<String> expected = Set.of(
                "query", "execute", "loadFromUri", "merge", "copy", "tableExists");
        Set<String> actual = Arrays.stream(Warehouse.class.getDeclaredMethods())
                .map(Method::getName)
                .collect(Collectors.toSet());
        assertThat(actual).containsAll(expected);
    }

    @Test
    void audit_event_publisher_has_publish_and_flush() {
        assertHasMethod(AuditEventPublisher.class, "publish");
        assertHasMethod(AuditEventPublisher.class, "flush");
    }

    @Test
    void governance_policy_has_classify_masking_retention() {
        assertHasMethod(GovernancePolicy.class, "classify");
        assertHasMethod(GovernancePolicy.class, "maskingFor");
        assertHasMethod(GovernancePolicy.class, "retentionFor");
    }

    @Test
    void lineage_emitter_has_emit() {
        assertHasMethod(LineageEmitter.class, "emit");
    }

    @Test
    void observability_hook_has_metric_log_span_methods() {
        assertHasMethod(ObservabilityHook.class, "counter");
        assertHasMethod(ObservabilityHook.class, "gauge");
        assertHasMethod(ObservabilityHook.class, "histogram");
        assertHasMethod(ObservabilityHook.class, "log");
        assertHasMethod(ObservabilityHook.class, "span");
    }

    @Test
    void finops_sink_has_record() {
        assertHasMethod(FinOpsSink.class, "record");
    }

    @Test
    void secret_provider_has_get() {
        assertHasMethod(SecretProvider.class, "get");
    }

    private static void assertHasMethod(Class<?> iface, String name) {
        boolean hasIt = Arrays.stream(iface.getDeclaredMethods())
                .anyMatch(m -> m.getName().equals(name));
        assertThat(hasIt)
                .as("interface %s should declare method '%s'", iface.getName(), name)
                .isTrue();
    }
}
