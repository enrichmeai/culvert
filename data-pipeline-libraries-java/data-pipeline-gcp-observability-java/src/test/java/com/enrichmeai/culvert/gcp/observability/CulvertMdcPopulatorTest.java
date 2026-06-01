package com.enrichmeai.culvert.gcp.observability;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.LoggerContext;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.OutputStreamAppender;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import net.logstash.logback.encoder.LogstashEncoder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

import static com.enrichmeai.culvert.gcp.observability.CulvertMdcPopulator.PIPELINE_ID_KEY;
import static com.enrichmeai.culvert.gcp.observability.CulvertMdcPopulator.RUN_ID_KEY;
import static com.enrichmeai.culvert.gcp.observability.CulvertMdcPopulator.STAGE_NAME_KEY;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link CulvertMdcPopulator}.
 *
 * <p>These tests wire a Logback {@link OutputStreamAppender} backed by
 * {@link LogstashEncoder} to a {@link ByteArrayOutputStream}, invoke a
 * simulated stage body, and assert that the captured JSON line contains
 * the expected MDC fields as top-level keys.
 *
 * <p>A second test category verifies that the MDC is cleared after stage
 * execution even when the stage body throws a runtime exception.
 */
class CulvertMdcPopulatorTest {

    private static final String LOGGER_NAME =
            CulvertMdcPopulatorTest.class.getName();

    private LoggerContext loggerContext;
    private ByteArrayOutputStream capturedOutput;
    private OutputStreamAppender<ILoggingEvent> appender;
    private Logger captureLogger;
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @BeforeEach
    void setUpCaptureAppender() {
        // Obtain the Logback LoggerContext from the SLF4J factory.
        loggerContext = (LoggerContext) LoggerFactory.getILoggerFactory();

        capturedOutput = new ByteArrayOutputStream();

        // Build a LogstashEncoder with renamed 'level' → 'severity'.
        LogstashEncoder encoder = new LogstashEncoder();
        encoder.setContext(loggerContext);
        // Match logback-cloud.xml: rename level field to severity.
        net.logstash.logback.fieldnames.LogstashFieldNames fieldNames =
                new net.logstash.logback.fieldnames.LogstashFieldNames();
        fieldNames.setLevel("severity");
        encoder.setFieldNames(fieldNames);
        encoder.start();

        appender = new OutputStreamAppender<>();
        appender.setContext(loggerContext);
        appender.setEncoder(encoder);
        appender.setOutputStream(capturedOutput);
        appender.start();

        captureLogger = loggerContext.getLogger(LOGGER_NAME);
        captureLogger.setLevel(Level.DEBUG);
        captureLogger.setAdditive(false); // suppress console noise during tests
        captureLogger.addAppender(appender);
    }

    @AfterEach
    void tearDownAppender() {
        captureLogger.detachAppender(appender);
        appender.stop();
        // Ensure the MDC is clean between tests regardless of test outcome.
        MDC.clear();
    }

    // -----------------------------------------------------------------------
    // JSON field assertions
    // -----------------------------------------------------------------------

    /**
     * A log line emitted inside a {@code withStageContext} call must contain
     * {@code run_id}, {@code stage_name}, and {@code pipeline_id} as
     * top-level JSON fields with the supplied values.
     */
    @Test
    void logLineInsideStageContextContainsMdcFields() throws Exception {
        org.slf4j.Logger slf4jLogger = LoggerFactory.getLogger(LOGGER_NAME);

        CulvertMdcPopulator.withStageContext(
                "run-abc-123",
                "ingest",
                "pipeline-xyz",
                () -> slf4jLogger.info("processing records"));

        String json = capturedOutput.toString(StandardCharsets.UTF_8).trim();
        assertThat(json).isNotEmpty();

        JsonNode node = MAPPER.readTree(firstLine(json));
        assertThat(node.has(RUN_ID_KEY))
                .as("JSON must contain run_id").isTrue();
        assertThat(node.get(RUN_ID_KEY).asText())
                .isEqualTo("run-abc-123");

        assertThat(node.has(STAGE_NAME_KEY))
                .as("JSON must contain stage_name").isTrue();
        assertThat(node.get(STAGE_NAME_KEY).asText())
                .isEqualTo("ingest");

        assertThat(node.has(PIPELINE_ID_KEY))
                .as("JSON must contain pipeline_id").isTrue();
        assertThat(node.get(PIPELINE_ID_KEY).asText())
                .isEqualTo("pipeline-xyz");

        // Verify severity field rename is working.
        assertThat(node.has("severity"))
                .as("JSON must contain severity (renamed from level)").isTrue();
        assertThat(node.get("severity").asText()).isEqualTo("INFO");

        // message must be present.
        assertThat(node.has("message"))
                .as("JSON must contain message").isTrue();
    }

    /**
     * The supplier variant must also expose MDC fields in the log line.
     */
    @Test
    void supplierVariantPopulatesMdcFieldsCorrectly() throws Exception {
        org.slf4j.Logger slf4jLogger = LoggerFactory.getLogger(LOGGER_NAME);

        String result = CulvertMdcPopulator.withStageContext(
                "run-supplier-1",
                "transform",
                "pipe-transform",
                () -> {
                    slf4jLogger.info("transforming");
                    return "done";
                });

        assertThat(result).isEqualTo("done");

        String json = capturedOutput.toString(StandardCharsets.UTF_8).trim();
        JsonNode node = MAPPER.readTree(firstLine(json));
        assertThat(node.get(RUN_ID_KEY).asText()).isEqualTo("run-supplier-1");
        assertThat(node.get(STAGE_NAME_KEY).asText()).isEqualTo("transform");
        assertThat(node.get(PIPELINE_ID_KEY).asText()).isEqualTo("pipe-transform");
    }

    // -----------------------------------------------------------------------
    // MDC cleared after execution
    // -----------------------------------------------------------------------

    /**
     * After {@code withStageContext} returns normally, the MDC must be
     * cleared for all three Culvert keys.
     */
    @Test
    void mdcIsClearedAfterNormalExecution() {
        CulvertMdcPopulator.withStageContext(
                "run-1", "stage-a", "pipe-1", () -> { /* no-op */ });

        assertThat(MDC.get(RUN_ID_KEY)).isNull();
        assertThat(MDC.get(STAGE_NAME_KEY)).isNull();
        assertThat(MDC.get(PIPELINE_ID_KEY)).isNull();
    }

    /**
     * When the stage body throws a {@link RuntimeException}, the MDC must
     * still be cleared for all three Culvert keys — the exception propagates
     * normally, but leaves no stale context.
     */
    @Test
    void mdcIsClearedEvenWhenStagethrows() {
        RuntimeException boom = new RuntimeException("stage failed");

        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext(
                        "run-throw", "stage-bad", "pipe-throw",
                        () -> { throw boom; })
        ).isSameAs(boom);

        // MDC must be cleared despite the exception.
        assertThat(MDC.get(RUN_ID_KEY)).isNull();
        assertThat(MDC.get(STAGE_NAME_KEY)).isNull();
        assertThat(MDC.get(PIPELINE_ID_KEY)).isNull();
    }

    // -----------------------------------------------------------------------
    // Null-argument validation
    // -----------------------------------------------------------------------

    @Test
    void constructorNotInstantiable() {
        assertThatThrownBy(() -> {
            java.lang.reflect.Constructor<?> c =
                    CulvertMdcPopulator.class.getDeclaredConstructor();
            c.setAccessible(true);
            c.newInstance();
        }).hasCauseInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void runnableVariantRejectsNullRunId() {
        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext(null, "s", "p", () -> { }))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void runnableVariantRejectsNullStageName() {
        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext("r", null, "p", () -> { }))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void runnableVariantRejectsNullPipelineId() {
        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext("r", "s", null, () -> { }))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void runnableVariantRejectsNullBody() {
        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext("r", "s", "p", (Runnable) null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void supplierVariantRejectsNullBody() {
        assertThatThrownBy(() ->
                CulvertMdcPopulator.withStageContext("r", "s", "p",
                        (java.util.function.Supplier<Object>) null))
                .isInstanceOf(NullPointerException.class);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /** Returns the first non-empty line from a multi-line string. */
    private static String firstLine(String text) {
        for (String line : text.split("\n")) {
            String trimmed = line.trim();
            if (!trimmed.isEmpty()) {
                return trimmed;
            }
        }
        return text;
    }
}
