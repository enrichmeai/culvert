package com.enrichmeai.culvert.audit;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Java half of the cross-language conformance suite ({@code docs/CONTRACT.md}
 * §10.6), reading the shared fixtures at {@code tests/contract/fixtures/}.
 *
 * <p>Python reads the same bytes. That shared file — not a mirrored assertion
 * in each language — is what stops the two emitters drifting on column names,
 * event kinds or payload keys.
 *
 * <p><strong>A missing fixture file fails this suite.</strong> It must never
 * skip. The external review flagged a sibling project whose parity test pointed
 * at a directory deleted months earlier: it skipped silently while CI stayed
 * green, so the guard reported success while checking nothing. A guard that
 * cannot fail is worse than no guard, because it is believed.
 */
class AuditEventConformanceTest {

    /**
     * Locate the fixtures from the module directory. Walks up rather than
     * assuming a fixed depth, so moving the module does not silently break the
     * link — it would fail, which is the point.
     */
    private static Path fixtures() {
        Path dir = Paths.get("").toAbsolutePath();
        for (int i = 0; i < 6 && dir != null; i++) {
            Path candidate = dir.resolve("tests/contract/fixtures/audit_events.json");
            if (Files.exists(candidate)) {
                return candidate;
            }
            dir = dir.getParent();
        }
        throw new AssertionError(
                "Conformance fixtures not found: tests/contract/fixtures/audit_events.json. "
                        + "This is a FAILURE, never a skip — docs/CONTRACT.md §10.6 promises a "
                        + "shipped conformance suite, and a guard that quietly disables itself "
                        + "reports green while checking nothing.");
    }

    private static String read() throws IOException {
        return Files.readString(fixtures());
    }

    /** Minimal extraction — avoids adding a JSON dependency to core for one test. */
    private static List<String> stringArray(String json, String key) {
        List<String> out = new ArrayList<>();
        int at = json.indexOf("\"" + key + "\"");
        if (at < 0) {
            return out;
        }
        int open = json.indexOf('[', at);
        int close = json.indexOf(']', open);
        for (String piece : json.substring(open + 1, close).split(",")) {
            String cleaned = piece.trim().replace("\"", "");
            if (!cleaned.isEmpty()) {
                out.add(cleaned);
            }
        }
        return out;
    }

    @Test
    void everyContractEventKindExistsInJava() throws IOException {
        String json = read();
        List<String> runLevel = stringArray(json, "run_level_kinds");
        List<String> aggregate = stringArray(json, "aggregate_kinds");

        List<String> all = new ArrayList<>(runLevel);
        all.addAll(aggregate);

        assertThat(all)
                .as("fixtures must enumerate all 7 kinds from docs/CONTRACT.md §4")
                .hasSize(7);

        for (String kind : all) {
            assertThat(EventKind.fromWire(kind)).isNotNull();
        }
        assertThat(EventKind.values()).hasSize(all.size());
    }

    @Test
    void runLevelClassificationMatchesTheFixtures() throws IOException {
        String json = read();

        for (String kind : stringArray(json, "run_level_kinds")) {
            assertThat(EventKind.fromWire(kind).isRunLevel())
                    .as("%s is run-level: a failed append must fail the pipeline", kind)
                    .isTrue();
        }
        for (String kind : stringArray(json, "aggregate_kinds")) {
            assertThat(EventKind.fromWire(kind).isRunLevel())
                    .as("%s is an aggregate: a failed append dead-letters, never halts ingestion", kind)
                    .isFalse();
        }
    }

    @Test
    void requiredPayloadKeysMatchTheFixtures() throws IOException {
        String json = read();
        // The block is keyed by kind; pull each kind's array out of it.
        int block = json.indexOf("\"required_payload_keys\"");
        assertThat(block).as("fixtures must declare required_payload_keys").isGreaterThan(0);
        String section = json.substring(block, json.indexOf('}', block));

        for (EventKind kind : EventKind.values()) {
            List<String> expected = stringArray(section, kind.name());
            assertThat(expected)
                    .as("fixtures must pin payload keys for %s", kind)
                    .isNotEmpty();
            assertThat(kind.requiredPayloadKeys())
                    .as("%s payload keys must match the shared fixtures exactly", kind)
                    .containsExactlyInAnyOrderElementsOf(expected);
        }
    }

    @Test
    void aMissingRequiredPayloadKeyIsRejectedAtConstruction() {
        // The whole point of binding the keys: fail here, loudly, rather than
        // reading back as NULL from a JSON path in a query months later.
        assertThatThrownBy(() -> AuditEvent.of(
                "run-1", "Generic", "customers", EventKind.RECORD_REJECTED,
                Instant.now(), Map.of("count", 2)))       // quarantine_uri missing
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("quarantine_uri")
                .hasMessageContaining("CONTRACT.md");
    }

    @Test
    void contractVersionIsStampedByTheTypeNotTheCaller() throws IOException {
        String json = read();
        int at = json.indexOf("\"contract_version\"");
        String fixtureVersion = json.substring(json.indexOf('"', json.indexOf(':', at)) + 1,
                json.indexOf('"', json.indexOf('"', json.indexOf(':', at)) + 1));

        AuditEvent event = AuditEvent.of("run-1", "Generic", "customers",
                EventKind.RUN_START, Instant.now(), Map.of("source_file", "gs://b/f.csv"));

        assertThat(event.contractVersion()).isEqualTo(ContractVersion.CURRENT);
        assertThat(event.contractVersion())
                .as("the library's version must match what the fixtures declare")
                .isEqualTo(fixtureVersion);
    }

    @Test
    void everyFixtureCaseConstructsAndCarriesItsRequiredKeys() throws IOException {
        String json = read();
        // Each case's event_kind, in fixture order.
        List<String> kinds = new ArrayList<>();
        int idx = json.indexOf("\"cases\"");
        String cases = json.substring(idx);
        int from = 0;
        while (true) {
            int k = cases.indexOf("\"event_kind\"", from);
            if (k < 0) {
                break;
            }
            int q1 = cases.indexOf('"', cases.indexOf(':', k)) + 1;
            kinds.add(cases.substring(q1, cases.indexOf('"', q1)));
            from = k + 1;
        }

        assertThat(kinds).as("fixtures must exercise every kind").hasSize(7);

        Map<String, Object> stub = new LinkedHashMap<>();
        for (String kindName : kinds) {
            EventKind kind = EventKind.fromWire(kindName);
            stub.clear();
            for (String key : kind.requiredPayloadKeys()) {
                stub.put(key, "x");
            }
            AuditEvent event = AuditEvent.of("run-1", "Generic", "customers",
                    kind, Instant.now(), Map.copyOf(stub));
            assertThat(event.payload().keySet())
                    .containsAll(Set.copyOf(kind.requiredPayloadKeys()));
            assertThat(event.failureIsFatal()).isEqualTo(kind.isRunLevel());
        }
    }

    @Test
    void anUnknownEventKindIsRejectedAndNamesTheValidOnes() {
        assertThatThrownBy(() -> EventKind.fromWire("STAGE_COMPLETED"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("RUN_START")
                .hasMessageContaining("CONTRACT.md");
    }
}
