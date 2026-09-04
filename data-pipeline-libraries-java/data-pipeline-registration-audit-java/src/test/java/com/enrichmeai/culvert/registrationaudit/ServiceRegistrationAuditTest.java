package com.enrichmeai.culvert.registrationaudit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Reactor-wide audit of Culvert's {@code META-INF/services} registrations.
 *
 * <h2>What it guards</h2>
 *
 * <p>A registration is a public promise: "this class implements this contract, and
 * {@link java.util.ServiceLoader} can hand it to you." Seven registrations across three
 * clouds broke that promise — they named classes with no public no-arg constructor, so
 * every discovery pass raised {@code ServiceConfigurationError}. Before Story 1.1
 * {@code AutoConfig} swallowed those errors, so four of GCP's cloud-bound contracts were
 * unreachable through auto-config and nothing, anywhere, said so. Story 1.2 fixed or
 * withdrew all seven; this test is what stops the eighth.
 *
 * <p>The audit is deliberately <strong>structural, not behavioural</strong>: it checks
 * that a provider constructor <em>exists</em>, and never invokes it. That distinction is
 * the whole point. {@code AthenaWarehouse} and {@code DynamoDbJobControlRepository} have
 * working no-arg constructors that <em>throw</em> when {@code CULVERT_CLOUD} does not
 * select their family — that is a cloud gate working as designed, not a defect, and
 * {@code AutoConfig} records it as a named {@code DiscoveryFailure} rather than losing
 * it. {@code BigQueryWarehouse} and {@code BigQueryFinOpsSink} likewise throw without a
 * project or {@code FINOPS_DATASET}. A test that constructed providers would fail on all
 * four, would depend on ambient cloud credentials, and could make live API calls. So it
 * does not construct anything.
 *
 * <h2>Scope</h2>
 *
 * <p>Every {@code src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.*}
 * file under the repository root — that is, every registration that ships inside a
 * published jar and lands on a user's classpath. Registrations under
 * {@code src/test/resources} are deliberately out of scope: they are per-module test
 * fixtures (the {@code Recording*} hooks in {@code deployments/reference-e2e-gcp}) that are
 * never published, and a library module cannot depend on a deployment's test classes
 * without inverting the dependency graph.
 *
 * <h2>Why this lives in its own module</h2>
 *
 * <p>No other module sees every adapter, and making one do so would inflict a dozen cloud
 * SDKs on a published artifact. This module publishes nothing
 * ({@code maven.deploy.skip}), so its dependency list costs consumers nothing.
 *
 * <p>It depends on the modules that carry registrations, not on every adapter — see the
 * note in its pom. That list staying correct is not left to memory: a module that adds a
 * registration without being added there fails
 * {@link #everyRegisteredClassIsOnTheAuditClasspath()} with an explicit instruction, never
 * a silent skip.
 */
@DisplayName("META-INF/services registrations the reactor ships")
class ServiceRegistrationAuditTest {

    /** Only Culvert contract registrations are in scope. */
    private static final String CONTRACT_PREFIX = "com.enrichmeai.culvert.contracts.";

    /**
     * Appended wherever the audit tells someone to add a module to its classpath, because
     * for one module that advice does not work and the wall is worth naming in advance.
     */
    private static final String ADD_DEPENDENCY_CAVEAT =
            "Note: data-pipeline-gcp-dataflow cannot simply be added — it pulls Beam's GCP "
            + "IO closure (bigtable, firestore, spanner, pubsublite) in at versions no "
            + "module has ever built with, which does not resolve under the `mvn -o` this "
            + "project verifies with. If a Dataflow-module registration ever needs "
            + "auditing, that resolution has to be solved first.";

    /** Directories that never contain source-of-truth registrations. */
    private static final Set<String> PRUNED = Set.of(
            "target", ".git", ".claude", "node_modules", ".venv", "venv", "build");

    /**
     * Sanity floor for the filesystem walk. Its job is to fail loudly if the walk finds
     * nothing (a moved repo root, a renamed layout) rather than passing vacuously. Set
     * well below the real count so ordinary churn never trips it; the positive repo-root
     * marker in {@link #repositoryRoot()} is the real guard.
     */
    private static final int MINIMUM_EXPECTED_REGISTRATIONS = 8;

    /** One line of one service file: the contract it registers against and the impl. */
    private record Registration(Path file, String contract, String implementation) {

        String location() {
            return file + " -> " + implementation;
        }
    }

    // ---------------------------------------------------------------- the audit

    @Test
    @DisplayName("every registered class exposes a provider ServiceLoader can construct")
    void everyRegisteredClassIsConstructableByServiceLoader() {
        List<Registration> registrations = shippedRegistrations();
        List<String> problems = new ArrayList<>();

        for (Registration registration : registrations) {
            Class<?> impl;
            try {
                // initialize=false: resolve the class without running static initialisers.
                impl = Class.forName(registration.implementation(), false, loader());
            } catch (ClassNotFoundException | LinkageError e) {
                continue; // reported by everyRegisteredClassIsOnTheAuditClasspath
            }

            if (!Modifier.isPublic(impl.getModifiers())) {
                problems.add(registration.location()
                        + " — the class is not public, so ServiceLoader cannot access it.");
                continue;
            }
            if (impl.isInterface() || Modifier.isAbstract(impl.getModifiers())) {
                problems.add(registration.location()
                        + " — the class is abstract or an interface; it cannot be instantiated.");
                continue;
            }
            switch (providerVerdict(impl)) {
                case CONSTRUCTABLE -> { /* the good case */ }
                case NOT_CONSTRUCTABLE -> problems.add(registration.location()
                        + " — no public no-arg constructor and no public static provider() "
                        + "method, so ServiceLoader raises ServiceConfigurationError on every "
                        + "discovery pass. Either give it a constructor that can honestly "
                        + "self-configure from the environment, or withdraw the registration "
                        + "and record why in the service file (see the gcp-observability "
                        + "LineageEmitter file for the precedent).");
                case UNVERIFIABLE -> problems.add(registration.location()
                        + " — COULD NOT BE VERIFIED: resolving this class's constructors needs "
                        + "a parameter type that is missing from the audit's classpath, so the "
                        + "audit cannot tell whether a no-arg constructor exists. This is a "
                        + "failure, not a pass: add the module supplying that type to "
                        + "data-pipeline-registration-audit-java's test dependencies. "
                        + ADD_DEPENDENCY_CAVEAT);
            }
        }

        assertThat(problems)
                .as("registrations ServiceLoader cannot construct (Story 1.2)")
                .isEmpty();
    }

    @Test
    @DisplayName("every registered class actually implements the contract it registers against")
    void everyRegisteredClassImplementsItsContract() {
        List<String> problems = new ArrayList<>();

        for (Registration registration : shippedRegistrations()) {
            Class<?> contract;
            Class<?> impl;
            try {
                contract = Class.forName(registration.contract(), false, loader());
                impl = Class.forName(registration.implementation(), false, loader());
            } catch (ClassNotFoundException | LinkageError e) {
                continue; // reported by everyRegisteredClassIsOnTheAuditClasspath
            }
            if (!contract.isAssignableFrom(impl)) {
                problems.add(registration.location() + " — does not implement "
                        + registration.contract() + "; ServiceLoader would reject it.");
            }
        }

        assertThat(problems).as("registrations naming the wrong contract").isEmpty();
    }

    @Test
    @DisplayName("every registered class is visible to this audit (a new module must be added here)")
    void everyRegisteredClassIsOnTheAuditClasspath() {
        List<String> problems = new ArrayList<>();

        for (Registration registration : shippedRegistrations()) {
            try {
                Class.forName(registration.implementation(), false, loader());
            } catch (ClassNotFoundException | LinkageError e) {
                problems.add(registration.location()
                        + " — not loadable by the audit (" + e.getClass().getSimpleName()
                        + "). If the owning module is new, add it as a <scope>test</scope> "
                        + "dependency of data-pipeline-registration-audit-java so its "
                        + "registrations are checked instead of skipped. If the class was "
                        + "renamed or deleted, the service file is stale. "
                        + ADD_DEPENDENCY_CAVEAT);
            }
        }

        assertThat(problems).as("registrations the audit could not verify").isEmpty();
    }

    // ------------------------------------------------------- guards on the walk itself

    @Test
    @DisplayName("the walk actually finds the reactor's registrations (no vacuous pass)")
    void theWalkFindsTheReactorsRegistrations() {
        List<Registration> registrations = shippedRegistrations();

        assertThat(registrations)
                .as("registrations found under %s", repositoryRoot())
                .hasSizeGreaterThanOrEqualTo(MINIMUM_EXPECTED_REGISTRATIONS);

        // A registration this audit is pointless without: the pilot the whole
        // worker-side reconstruction convention was built on.
        assertThat(registrations)
                .extracting(Registration::implementation)
                .contains("com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse");
    }

    @Test
    @DisplayName("service files are parsed with ServiceLoader's own comment and blank-line rules")
    void serviceFileParsingMatchesServiceLoaderRules() throws IOException {
        Path file = Files.createTempFile("culvert-audit-", ".services");
        try {
            Files.writeString(file, String.join("\n",
                    "# a full-line comment",
                    "",
                    "   ",
                    "com.example.First   # trailing comment",
                    "  com.example.Second  ",
                    "# another comment"), StandardCharsets.UTF_8);

            assertThat(parse(file)).containsExactly("com.example.First", "com.example.Second");
        } finally {
            Files.deleteIfExists(file);
        }
    }

    @Test
    @DisplayName("a comment-only service file yields no registrations")
    void aCommentOnlyServiceFileYieldsNoRegistrations() throws IOException {
        // Story 1.2 and Story 1.5 withdrew registrations by emptying the file down to its
        // reasoning rather than deleting it — AC 3 requires the reason to live in the
        // service file. The walker must read those as zero entries, not choke on them.
        Path file = Files.createTempFile("culvert-audit-empty-", ".services");
        try {
            Files.writeString(file,
                    "# INTENTIONALLY EMPTY - no BlobStore is registered by this module.\n"
                            + "#\n"
                            + "# The reason it was withdrawn lives here.\n",
                    StandardCharsets.UTF_8);

            assertThat(parse(file)).isEmpty();
        } finally {
            Files.deleteIfExists(file);
        }
    }

    // ---------------------------------------------------------------- mechanics

    private static ClassLoader loader() {
        return ServiceRegistrationAuditTest.class.getClassLoader();
    }

    /**
     * Whether a class offers ServiceLoader something to construct — and, crucially, a
     * third answer for "the audit could not tell".
     *
     * <p>The third state is not fussiness. {@code getConstructor()} resolves the parameter
     * types of <em>every</em> public constructor, so a class whose only constructor takes a
     * type missing from this classpath raises {@link NoClassDefFoundError} — the same
     * outcome as a class with no no-arg constructor at all. Collapsing that into "fine"
     * would let exactly the defect this module exists to catch pass in silence, and
     * collapsing it into {@code NOT_CONSTRUCTABLE} would print a diagnosis the audit has
     * not actually made. So it is reported as its own failure, with its own remedy.
     */
    private enum ProviderVerdict { CONSTRUCTABLE, NOT_CONSTRUCTABLE, UNVERIFIABLE }

    private static ProviderVerdict providerVerdict(Class<?> impl) {
        // JDK 9+ ServiceLoader prefers a public static provider() method when present.
        // No adapter uses it today; honouring it keeps the audit true to what
        // ServiceLoader does rather than to what this codebase happens to do.
        try {
            Method provider = impl.getDeclaredMethod("provider");
            if (Modifier.isPublic(provider.getModifiers())
                    && Modifier.isStatic(provider.getModifiers())) {
                return ProviderVerdict.CONSTRUCTABLE;
            }
        } catch (NoSuchMethodException e) {
            // Fall through to the constructor check - the ordinary case.
        } catch (NoClassDefFoundError e) {
            return ProviderVerdict.UNVERIFIABLE;
        }

        try {
            Constructor<?> ctor = impl.getConstructor();
            return Modifier.isPublic(ctor.getModifiers())
                    ? ProviderVerdict.CONSTRUCTABLE
                    : ProviderVerdict.NOT_CONSTRUCTABLE;
        } catch (NoSuchMethodException e) {
            return ProviderVerdict.NOT_CONSTRUCTABLE;
        } catch (NoClassDefFoundError e) {
            return ProviderVerdict.UNVERIFIABLE;
        }
    }

    /**
     * Every contract registration the reactor publishes, in a stable order.
     *
     * @see #repositoryRoot() for the guard against a vacuous, rootless walk
     */
    private static List<Registration> shippedRegistrations() {
        Path root = repositoryRoot();
        List<Registration> registrations = new ArrayList<>();

        try (Stream<Path> tree = Files.walk(root)) {
            List<Path> serviceFiles = tree
                    .filter(path -> isNotPruned(root.relativize(path)))
                    .filter(Files::isRegularFile)
                    .filter(ServiceRegistrationAuditTest::isShippedContractServiceFile)
                    .sorted(Comparator.comparing(Path::toString))
                    .collect(Collectors.toList());

            for (Path file : serviceFiles) {
                String contract = file.getFileName().toString();
                for (String implementation : parse(file)) {
                    registrations.add(new Registration(root.relativize(file), contract, implementation));
                }
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not walk the reactor from " + root, e);
        }

        return registrations;
    }

    /**
     * Pruning is applied to the path <em>below the repository root</em>, never to the
     * absolute path. The repo is routinely checked out somewhere whose own directory
     * names collide with this list — a git worktree under {@code .claude/worktrees/},
     * for instance — and pruning on the absolute path silently discards the whole tree.
     * That is not hypothetical: it is what the first run of this audit did, which is why
     * {@link #theWalkFindsTheReactorsRegistrations()} exists.
     *
     * @param relative a path relative to {@link #repositoryRoot()}
     */
    private static boolean isNotPruned(Path relative) {
        for (Path segment : relative) {
            if (PRUNED.contains(segment.toString())) {
                return false;
            }
        }
        return true;
    }

    /**
     * A published registration: {@code <module>/src/main/resources/META-INF/services/}
     * plus a Culvert contract name. {@code src/test/resources} is out of scope — see the
     * class javadoc.
     */
    private static boolean isShippedContractServiceFile(Path file) {
        if (!file.getFileName().toString().startsWith(CONTRACT_PREFIX)) {
            return false;
        }
        String path = file.toString().replace('\\', '/');
        return path.contains("/src/main/resources/META-INF/services/");
    }

    /**
     * Parse a service file the way {@link java.util.ServiceLoader} does: {@code #} starts
     * a comment that runs to end of line, surrounding whitespace is stripped, and blank
     * lines are ignored.
     */
    private static List<String> parse(Path file) {
        try {
            List<String> names = new ArrayList<>();
            for (String raw : Files.readAllLines(file, StandardCharsets.UTF_8)) {
                int comment = raw.indexOf('#');
                String line = (comment >= 0 ? raw.substring(0, comment) : raw).trim();
                if (!line.isEmpty()) {
                    names.add(line);
                }
            }
            return names;
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read service file " + file, e);
        }
    }

    /**
     * The repository root, found by a positive marker rather than a hop count: the
     * nearest ancestor holding both a {@code pom.xml} and the
     * {@code data-pipeline-libraries-java} reactor. Failing here beats walking nothing
     * and passing.
     */
    private static Path repositoryRoot() {
        Path candidate = Path.of("").toAbsolutePath();
        while (candidate != null) {
            if (Files.isRegularFile(candidate.resolve("pom.xml"))
                    && Files.isDirectory(candidate.resolve("data-pipeline-libraries-java"))) {
                return candidate;
            }
            candidate = candidate.getParent();
        }
        throw new IllegalStateException(
                "Could not locate the repository root above " + Path.of("").toAbsolutePath()
                        + " (looking for a directory with both pom.xml and "
                        + "data-pipeline-libraries-java/). The audit walks the source tree, so "
                        + "it must run from inside a checkout.");
    }
}
