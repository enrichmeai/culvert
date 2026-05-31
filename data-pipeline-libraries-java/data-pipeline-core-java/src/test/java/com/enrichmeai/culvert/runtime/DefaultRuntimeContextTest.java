package com.enrichmeai.culvert.runtime;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.SecretProvider;
import com.enrichmeai.culvert.governance.DataClassification;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link DefaultRuntimeContext} (Sprint-9 T9.1).
 */
class DefaultRuntimeContextTest {

    @Test
    void builderCarriesIdentityAndConfig() {
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("run-1", "dev")
                .config(Map.of("table", "events"))
                .build();

        assertThat(ctx.runId()).isEqualTo("run-1");
        assertThat(ctx.environment()).isEqualTo("dev");
        assertThat(ctx.config()).containsEntry("table", "events");
    }

    @Test
    void configIsImmutable() {
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("run-1", "dev")
                .config(Map.of("k", "v"))
                .build();

        assertThatThrownBy(() -> ctx.config().put("x", "y"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void blankRunIdRejected() {
        assertThatThrownBy(() -> DefaultRuntimeContext.builder(" ", "dev"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void secretsThrowsWhenAbsent() {
        DefaultRuntimeContext ctx = DefaultRuntimeContext.builder("r", "dev").build();
        assertThatThrownBy(ctx::secrets)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SecretProvider");
    }

    @Test
    void secretsReturnsRegisteredProvider() {
        SecretProvider provider = (name, version) -> "shh";
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("r", "dev")
                .register(SecretProvider.class, provider)
                .build();

        assertThat(ctx.secrets().get("any")).isEqualTo("shh");
    }

    @Test
    void advisoryProtocolsHaveNoOpDefaults() {
        DefaultRuntimeContext ctx = DefaultRuntimeContext.builder("r", "dev").build();

        // None of these should throw; the no-op defaults absorb the calls.
        ObservabilityHook obs = ctx.observability();
        assertThat(obs).isNotNull();
        obs.counter("rows", 1L, Map.of());
        obs.gauge("g", 1.0, Map.of());
        obs.histogram("h", 1.0, Map.of());
        obs.log("INFO", "hello", Map.of());
        try (ObservabilityHook.Span span = obs.span("stage")) {
            span.setAttribute("k", "v");
        }

        assertThat(ctx.lineage()).isNotNull();
        assertThat(ctx.finops()).isNotNull();

        GovernancePolicy gov = ctx.governance();
        assertThat(gov.classify("col", "tbl")).isEqualTo(DataClassification.INTERNAL);
        assertThat(gov.maskingFor("col", "tbl")).isEmpty();
        assertThat(gov.retentionFor("tbl")).isEmpty();
    }

    @Test
    void registeredAdvisoryImplWins() {
        LineageEmitter custom = event -> { /* records nowhere, but identity matters */ };
        FinOpsSink customSink = (metrics, tags) -> { };
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("r", "dev")
                .register(LineageEmitter.class, custom)
                .register(FinOpsSink.class, customSink)
                .build();

        assertThat(ctx.lineage()).isSameAs(custom);
        assertThat(ctx.finops()).isSameAs(customSink);
    }

    @Test
    void getThrowsWhenUnregistered() {
        DefaultRuntimeContext ctx = DefaultRuntimeContext.builder("r", "dev").build();
        assertThatThrownBy(() -> ctx.get(Runnable.class))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Runnable");
    }

    @Test
    void getReturnsRegisteredAndRegisterOverrides() {
        Runnable first = () -> { };
        Runnable second = () -> { };
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("r", "dev")
                .register(Runnable.class, first)
                .build();

        assertThat(ctx.get(Runnable.class)).isSameAs(first);
        ctx.register(Runnable.class, second);
        assertThat(ctx.get(Runnable.class)).isSameAs(second);
    }

    @Test
    void fromAutoConfigBuildsUsableContextWithEmptyClasspath() {
        // The core test classpath has no provider entries, so AutoConfig
        // discovers nothing; the context must still build and the advisory
        // accessors must still return no-op defaults.
        DefaultRuntimeContext ctx = DefaultRuntimeContext.fromAutoConfig(
                "run-ac", "staging", Map.of("a", 1), AutoConfig.discover());

        assertThat(ctx.runId()).isEqualTo("run-ac");
        assertThat(ctx.environment()).isEqualTo("staging");
        assertThat(ctx.observability()).isNotNull();
        assertThatThrownBy(ctx::secrets).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void identitySurvivesSerializationButRegistryIsRebuilt() throws Exception {
        // T10.6 — serializable context boundary. Only runId/environment/config
        // cross the wire; the protocol registry is transient and rebuilt
        // worker-side from AutoConfig.discover(). An impl placed via register(...)
        // is driver-side only and does NOT survive serialization — that is the
        // whole point: adapters routinely wrap non-serializable cloud SDK handles.
        DefaultRuntimeContext ctx = DefaultRuntimeContext
                .builder("run-ser", "prod")
                .config(Map.of("k", "v"))
                .register(SecretProvider.class, new SerializableSecret())
                .build();
        // Touch the advisory accessors so the no-op defaults are materialised
        // into the (driver-side) registry before serialization. They must still
        // not be carried across by the wire — they re-materialise lazily.
        ctx.observability();
        ctx.lineage();
        ctx.finops();
        ctx.governance();
        // The driver-side context resolves the registered secret.
        assertThat(ctx.secrets().get("x")).isEqualTo("secret-x");

        DefaultRuntimeContext roundTripped = roundTrip(ctx);

        // 1. Identity + config survive.
        assertThat(roundTripped.runId()).isEqualTo("run-ser");
        assertThat(roundTripped.environment()).isEqualTo("prod");
        assertThat(roundTripped.config()).containsEntry("k", "v");

        // 2. The explicitly-registered SecretProvider did NOT cross the
        //    boundary; worker-side rebuild via AutoConfig discovers nothing on
        //    the core test classpath, so secrets() throws again.
        assertThatThrownBy(roundTripped::secrets)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SecretProvider");

        // 3. Advisory accessors still work post-deserialize — they re-materialise
        //    their no-op defaults via the lazy rebuild path, not from the wire.
        assertThat(roundTripped.observability()).isNotNull();
        assertThat(roundTripped.governance().classify("c", "t"))
                .isEqualTo(DataClassification.INTERNAL);
    }

    private static DefaultRuntimeContext roundTrip(DefaultRuntimeContext ctx) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(ctx);
        }
        try (ObjectInputStream in = new ObjectInputStream(
                new ByteArrayInputStream(bytes.toByteArray()))) {
            return (DefaultRuntimeContext) in.readObject();
        }
    }

    /** A serializable secret provider for the round-trip test. */
    static final class SerializableSecret implements SecretProvider, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public String get(String name, String version) {
            return "secret-" + name;
        }
    }
}
