package com.enrichmeai.culvert.autoconfig;

import com.enrichmeai.culvert.autoconfig.fixtures.AlphaBlobStore;
import com.enrichmeai.culvert.autoconfig.fixtures.BravoBlobStore;
import com.enrichmeai.culvert.autoconfig.fixtures.NoNoArgBlobStore;
import com.enrichmeai.culvert.autoconfig.fixtures.ThrowingBlobStore;
import com.enrichmeai.culvert.autoconfig.fixtures.UnavailableBlobStore;
import com.enrichmeai.culvert.contracts.BlobStore;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.ServiceConfigurationError;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Auto-config registry tests.
 *
 * <p>Two groups. The first proves the data-pipeline-core classpath itself carries no
 * providers, so every lookup is empty. The second (Story 1.1) drives discovery through a
 * throwaway {@link URLClassLoader} carrying hand-written {@code META-INF/services} files, so
 * failure isolation and selection can be tested against a real {@link java.util.ServiceLoader}
 * without polluting the module's own classpath — the empty-classpath assumptions above
 * depend on that separation. Only the service <em>file</em> comes from the child loader; the
 * provider classes resolve through parent delegation, which is what makes
 * {@code service.isAssignableFrom(...)} succeed.
 */
class AutoConfigTest {

    private static final String SELECTOR = AutoConfig.selectorSystemProperty(BlobStore.class);

    @TempDir
    Path fixtureRoot;

    @BeforeEach
    @AfterEach
    void clearSelector() {
        System.clearProperty(SELECTOR);
    }

    // --- the core classpath carries no providers ---------------------------

    @Test
    void discoverReturnsAutoConfigInstance() {
        AutoConfig config = AutoConfig.discover();
        assertThat(config).isNotNull();
    }

    @Test
    void allLookupsEmptyWithoutImpls() {
        AutoConfig config = AutoConfig.discover();
        // The data-pipeline-core test classpath has no provider entries.
        assertThat(config.warehouse()).isEmpty();
        assertThat(config.blobStore()).isEmpty();
        assertThat(config.secretProvider()).isEmpty();
        assertThat(config.jobControl()).isEmpty();
        assertThat(config.finOpsSink()).isEmpty();
        assertThat(config.observabilityHook()).isEmpty();
        assertThat(config.lineageEmitter()).isEmpty();
    }

    @Test
    void listGettersReturnEmptyListsWhenNoImpls() {
        AutoConfig config = AutoConfig.discover();
        assertThat(config.warehouses()).isEmpty();
        assertThat(config.blobStores()).isEmpty();
        assertThat(config.secretProviders()).isEmpty();
        assertThat(config.sources()).isEmpty();
        assertThat(config.sinks()).isEmpty();
        assertThat(config.transforms()).isEmpty();
        assertThat(config.pipelines()).isEmpty();
        assertThat(config.stages()).isEmpty();
    }

    @Test
    void discoveryOnACleanClasspathReportsNoFailures() {
        assertThat(AutoConfig.discover().failures()).isEmpty();
    }

    // --- AC 1: a failing provider must not hide the others ------------------

    @Test
    void aProviderWhoseConstructorThrowsDoesNotHideAGoodOne() throws IOException {
        // The thrower is listed FIRST — under the old catch-Throwable-around-the-loop
        // behaviour that truncated the list and AlphaBlobStore was never seen.
        AutoConfig config = AutoConfig.discover(
                loaderWith(ThrowingBlobStore.class, AlphaBlobStore.class));

        assertThat(config.blobStores()).hasSize(1);
        assertThat(config.blobStore()).containsInstanceOf(AlphaBlobStore.class);
    }

    @Test
    void aProviderWhoseConstructorThrowsIsRecordedAsAFailure() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(ThrowingBlobStore.class, AlphaBlobStore.class));

        assertThat(config.failures()).hasSize(1);
        DiscoveryFailure failure = config.failures().get(0);
        assertThat(failure.contract()).isEqualTo(BlobStore.class);
        assertThat(failure.providerClass()).isEqualTo(ThrowingBlobStore.class.getName());
        assertThat(failure.cause()).isInstanceOf(ServiceConfigurationError.class);
        // ServiceConfigurationError wraps the constructor's throwable rather than
        // repeating its message, so the reason is in the cause chain.
        assertThat(failure.cause()).hasRootCauseMessage("fixture refuses to be constructed");
    }

    @Test
    void aProviderWithNoNoArgConstructorDoesNotHideAGoodOne() throws IOException {
        // Different JDK code path from the throwing case: the error is raised while
        // advancing the iterator, not while instantiating.
        AutoConfig config = AutoConfig.discover(
                loaderWith(NoNoArgBlobStore.class, AlphaBlobStore.class));

        assertThat(config.blobStore()).containsInstanceOf(AlphaBlobStore.class);
        assertThat(config.failures()).hasSize(1);
        assertThat(config.failures().get(0).toString()).contains(NoNoArgBlobStore.class.getName());
    }

    // --- AC 3: the single-provider case is unchanged ------------------------

    @Test
    void aSingleProviderWithNoSelectorResolvesAsBefore() throws IOException {
        AutoConfig config = AutoConfig.discover(loaderWith(AlphaBlobStore.class));

        assertThat(config.blobStore()).containsInstanceOf(AlphaBlobStore.class);
        assertThat(config.blobStores()).hasSize(1);
        assertThat(config.failures()).isEmpty();
    }

    // --- AC 2: ambiguity fails fast; a selector decides ---------------------

    @Test
    void ambiguityWithoutASelectorFailsFast() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(AlphaBlobStore.class, BravoBlobStore.class));

        assertThat(config.blobStores()).hasSize(2);
        assertThatThrownBy(config::blobStore)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(AlphaBlobStore.class.getName())
                .hasMessageContaining(BravoBlobStore.class.getName())
                .hasMessageContaining(AutoConfig.selectorEnvVar(BlobStore.class));
    }

    @Test
    void theSelectorPicksTheNamedProviderByFullyQualifiedName() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(AlphaBlobStore.class, BravoBlobStore.class));
        System.setProperty(SELECTOR, BravoBlobStore.class.getName());

        assertThat(config.blobStore()).containsInstanceOf(BravoBlobStore.class);
    }

    @Test
    void theSelectorPicksTheNamedProviderBySimpleName() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(AlphaBlobStore.class, BravoBlobStore.class));
        System.setProperty(SELECTOR, BravoBlobStore.class.getSimpleName());

        assertThat(config.blobStore()).containsInstanceOf(BravoBlobStore.class);
    }

    @Test
    void aSelectorNamingAnUndiscoveredProviderFailsRatherThanFallingBack() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(AlphaBlobStore.class, BravoBlobStore.class));
        System.setProperty(SELECTOR, "com.example.TypoBlobStore");

        assertThatThrownBy(config::blobStore)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("com.example.TypoBlobStore")
                .hasMessageContaining(AlphaBlobStore.class.getName());
    }

    // --- AC 4: opting out is "absent", not "throw" --------------------------

    @Test
    void anUnavailableProviderIsNotACandidateAndCausesNoAmbiguity() throws IOException {
        AutoConfig config = AutoConfig.discover(
                loaderWith(UnavailableBlobStore.class, AlphaBlobStore.class));

        // Availability is filtered BEFORE the ambiguity check, so a gated-out adapter
        // never makes an otherwise-unambiguous classpath fail.
        assertThat(config.blobStores()).hasSize(1);
        assertThat(config.blobStore()).containsInstanceOf(AlphaBlobStore.class);
        assertThat(config.failures()).isEmpty();
    }

    @Test
    void anUnavailableSoleProviderResolvesToEmptyWithoutAnError() throws IOException {
        AutoConfig config = AutoConfig.discover(loaderWith(UnavailableBlobStore.class));

        assertThat(config.blobStore()).isEmpty();
        assertThat(config.failures()).isEmpty();
    }

    // --- helpers ------------------------------------------------------------

    /**
     * A class loader whose only extra resource is a {@code META-INF/services} file for
     * {@link BlobStore} listing the given providers, in order.
     */
    private ClassLoader loaderWith(Class<?>... providers) throws IOException {
        Path services = fixtureRoot.resolve("META-INF").resolve("services");
        Files.createDirectories(services);
        Files.write(
                services.resolve(BlobStore.class.getName()),
                Arrays.stream(providers).map(Class::getName).toList());
        URL root = fixtureRoot.toUri().toURL();
        return new URLClassLoader(new URL[] {root}, getClass().getClassLoader());
    }
}
