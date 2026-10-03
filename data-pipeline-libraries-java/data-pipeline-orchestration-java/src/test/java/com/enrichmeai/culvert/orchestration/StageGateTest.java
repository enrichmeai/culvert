package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The gate predicate's shape, its validation, and its runtime re-check (#197). */
class StageGateTest {

    /** Completions only. A gate check that tried to claim would throw here. */
    static final class CompletionsOnly implements StageClaim {
        final Set<StageKey> completed;

        CompletionsOnly(Set<StageKey> completed) {
            this.completed = completed;
        }

        @Override
        public ClaimResult tryClaim(StageKey key, String claimant, Duration maxWait) {
            throw new AssertionError("a gate check must never claim a stage, but claimed " + key);
        }

        @Override
        public Optional<ClaimResult.Completed> completion(StageKey key) {
            return completed.contains(key)
                    ? Optional.of(new ClaimResult.Completed(key, "worker-1", Instant.EPOCH))
                    : Optional.empty();
        }
    }

    static TaskSpec gated(String taskId, Serializable value) {
        Map<String, Serializable> params = new HashMap<>();
        params.put(StageGate.COMPLETED, value);
        return new TaskSpec(taskId, taskId, List.of(), params);
    }

    static StageKey key(String stage) {
        return new StageKey("orders", stage, "2026-10-03");
    }

    // ---------------------------------------------------------------- shape

    @Test
    void anUngatedTaskHasNoRequiredStages() {
        TaskSpec t = new TaskSpec("load", "load", List.of(), Map.of("table", "raw.orders"));
        assertThat(StageGate.requiredStages(t)).isEmpty();
    }

    @Test
    void theRequiredStagesComeBackInTheOrderGiven() {
        assertThat(StageGate.requiredStages(gated("publish", new ArrayList<>(List.of("validate", "load")))))
                .containsExactly("validate", "load");
    }

    /** Every malformed gate is refused, naming the task, with the reason. */
    static Stream<Object[]> malformedGates() {
        return Stream.of(
                new Object[]{gated("publish", "load"), "must be a List of stage names"},
                new Object[]{gated("publish", null), "must be a List of stage names"},
                new Object[]{gated("publish", new ArrayList<>()), "empty"},
                new Object[]{gated("publish", new ArrayList<>(List.of("load", " "))), "non-blank stage name"},
                new Object[]{gated("publish", new ArrayList<>(List.of(7))), "non-blank stage name"},
                new Object[]{gated("publish", new ArrayList<>(List.of("publish"))), "its own stage"},
                new Object[]{gated("publish", new ArrayList<>(List.of("load", "load"))), "twice"},
                new Object[]{new TaskSpec("publish", "publish", List.of(),
                        Map.of("culvert.gate.complete", new ArrayList<>(List.of("load")))), "unknown gate key"},
                new Object[]{new TaskSpec("publish", "publish", List.of(),
                        Map.of("culvert.gate", "load")), "unknown gate key"});
    }

    @ParameterizedTest
    @MethodSource("malformedGates")
    void aMalformedGateIsRefusedNamingTheTask(TaskSpec task, String reason) {
        assertThatThrownBy(() -> StageGate.requiredStages(task))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("task 'publish'")
                .hasMessageContaining(reason);
    }

    @Test
    void validateNamesTheFirstMalformedTaskInTheDag() {
        TaskSpec ok = new TaskSpec("load", "load", List.of(), Map.of());
        TaskSpec bad = gated("publish", "load");
        DagSpec dag = new DagSpec("d", null, List.of(ok, bad), List.of(new DagSpec.Edge("load", "publish")));
        assertThatThrownBy(() -> StageGate.validate(dag)).hasMessageContaining("task 'publish'");
    }

    @Test
    void aGatedTaskSurvivesSerializationAcrossTheWorkerBoundary() throws Exception {
        TaskSpec t = gated("publish", new ArrayList<>(List.of("load", "validate")));
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(t);
        }
        TaskSpec back;
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
            back = (TaskSpec) in.readObject();
        }
        assertThat(back).isEqualTo(t);
        assertThat(StageGate.requiredStages(back)).containsExactly("load", "validate");
    }

    // ---------------------------------------------------------------- runtime re-check

    @Test
    void theGateOpensOnlyWhenEveryRequiredStageIsCompletedForTheUnitAndPeriod() {
        TaskSpec t = gated("publish", new ArrayList<>(List.of("load", "validate")));

        StageGate none = new StageGate(new CompletionsOnly(Set.of()));
        assertThat(none.check(t, "orders", "2026-10-03").waitingOn())
                .containsExactly(key("load"), key("validate"));

        StageGate half = new StageGate(new CompletionsOnly(Set.of(key("load"))));
        StageGate.Result r = half.check(t, "orders", "2026-10-03");
        assertThat(r.isOpen()).isFalse();
        assertThat(r.waitingOn()).containsExactly(key("validate"));

        StageGate all = new StageGate(new CompletionsOnly(Set.of(key("load"), key("validate"))));
        assertThat(all.check(t, "orders", "2026-10-03").isOpen()).isTrue();
    }

    @Test
    void aCompletionForAnotherUnitOrPeriodDoesNotOpenTheGate() {
        TaskSpec t = gated("publish", new ArrayList<>(List.of("load")));
        StageGate gate = new StageGate(new CompletionsOnly(Set.of(
                new StageKey("refunds", "load", "2026-10-03"),
                new StageKey("orders", "load", "2026-10-02"))));
        assertThat(gate.check(t, "orders", "2026-10-03").waitingOn()).containsExactly(key("load"));
    }

    @Test
    void anUngatedTaskIsAlwaysOpen() {
        TaskSpec t = new TaskSpec("load", "load", List.of(), Map.of());
        assertThat(new StageGate(new CompletionsOnly(Set.of())).check(t, "orders", "2026-10-03").isOpen())
                .isTrue();
    }

    @Test
    void requireOpenThrowsNamingTheTaskAndWhatItWaitsOn() {
        TaskSpec t = gated("publish", new ArrayList<>(List.of("load", "validate")));
        StageGate gate = new StageGate(new CompletionsOnly(Set.of(key("load"))));
        assertThatThrownBy(() -> gate.requireOpen(t, "orders", "2026-10-03"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("Gate closed for task 'publish': not completed: [orders/validate/2026-10-03]");

        new StageGate(new CompletionsOnly(Set.of(key("load"), key("validate"))))
                .requireOpen(t, "orders", "2026-10-03");
    }

    @Test
    void aBlankUnitOrPeriodIsRejectedEvenForAnUngatedTask() {
        StageGate gate = new StageGate(new CompletionsOnly(Set.of()));
        TaskSpec t = new TaskSpec("load", "load", List.of(), Map.of());
        assertThatThrownBy(() -> gate.check(t, " ", "2026-10-03")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> gate.check(t, "orders", "")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new StageGate(null)).isInstanceOf(NullPointerException.class);
    }
}
