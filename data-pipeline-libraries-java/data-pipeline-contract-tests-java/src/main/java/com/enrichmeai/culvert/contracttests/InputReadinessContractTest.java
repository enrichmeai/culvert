package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.InputState;
import com.enrichmeai.culvert.readiness.InputStatus;
import com.enrichmeai.culvert.readiness.Readiness;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import static com.enrichmeai.culvert.readiness.AttemptState.FAILED;
import static com.enrichmeai.culvert.readiness.AttemptState.PRODUCED;
import static com.enrichmeai.culvert.readiness.AttemptState.VALIDATED;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link InputReadiness} implementation must pass (#198).
 *
 * <p>The three cases the issue names are pinned here:
 * <ul>
 *   <li>(a) a missing input is named in the result, not counted;
 *   <li>(b) a failed input does not read as ready, and reads as failed rather than missing;
 *   <li>(c) a failed attempt answered by a declared retry that validated reads as ready, while a
 *       later success that is not a declared retry leaves the input failed.
 * </ul>
 * <p>Names are fresh per test, so state may persist between tests.
 */
public abstract class InputReadinessContractTest {

    /** The implementation under test. */
    protected abstract InputReadiness readiness();

    private final String tag = UUID.randomUUID().toString().substring(0, 8);
    private static final String PERIOD = "2026-10";

    private String unit(String name) {
        return name + "-" + tag;
    }

    private String in(String name) {
        return name + "-" + tag;
    }

    private void publish(String input, String runId, AttemptState state) {
        readiness().publish(InputAttempt.of(in(input), PERIOD, runId + "-" + tag, state));
    }

    private void retry(String input, String runId, AttemptState state, String previous) {
        readiness().publish(InputAttempt.retry(in(input), PERIOD, runId + "-" + tag, state, previous + "-" + tag));
    }

    private Readiness check(String unit) {
        return readiness().readiness(unit(unit), PERIOD);
    }

    private InputStatus status(Readiness r, String input) {
        return r.inputs().stream().filter(s -> s.input().equals(in(input))).findFirst().orElseThrow();
    }

    @Test
    void aUnitIsReadyWhenEveryExpectedInputIsValidated() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", PRODUCED);
        publish("orders", "r1", VALIDATED);
        publish("customers", "r2", VALIDATED);

        Readiness r = check("cdp");
        assertThat(r.isReady()).as(r.toString()).isTrue();
        assertThat(r.inputs()).extracting(InputStatus::input).containsExactly(in("customers"), in("orders"));
        assertThat(status(r, "orders").runId()).contains("r1-" + tag);
    }

    @Test
    void a_aMissingInputIsNamedInTheResult() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers"), in("products")));
        publish("orders", "r1", VALIDATED);

        Readiness r = check("cdp");
        assertThat(r.isReady()).isFalse();
        assertThat(r.missing()).containsExactly(in("customers"), in("products"));
        assertThat(status(r, "customers")).isEqualTo(new InputStatus(in("customers"), InputState.MISSING, Optional.empty()));
    }

    @Test
    void theWrongInputsBeingPresentDoNotMakeAUnitReady() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", VALIDATED);
        publish("refunds", "r2", VALIDATED);   // present and validated, but not expected

        Readiness r = check("cdp");
        assertThat(r.isReady()).as("2 validated inputs present, but not the 2 expected").isFalse();
        assertThat(r.missing()).containsExactly(in("customers"));
        assertThat(r.inputs()).extracting(InputStatus::input).doesNotContain(in("refunds"));
    }

    @Test
    void b_aFailedInputIsNotReadyAndIsReportedAsFailedNotMissing() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", VALIDATED);
        publish("customers", "r2", PRODUCED);
        publish("customers", "r2", FAILED);

        Readiness r = check("cdp");
        assertThat(r.isReady()).isFalse();
        assertThat(r.failed()).containsExactly(in("customers"));
        assertThat(r.missing()).isEmpty();
        assertThat(status(r, "customers").runId()).contains("r2-" + tag);
    }

    @Test
    void c_aFailureAnsweredByADeclaredRetryThatValidatedIsReady() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        publish("orders", "r1", FAILED);
        retry("orders", "r2", PRODUCED, "r1");
        assertThat(status(check("cdp"), "orders").state()).as("the retry is under way").isEqualTo(InputState.PENDING);

        retry("orders", "r2", VALIDATED, "r1");
        Readiness r = check("cdp");
        assertThat(r.isReady()).as(r.toString()).isTrue();
        assertThat(status(r, "orders").runId()).as("the retry decided it").contains("r2-" + tag);
    }

    @Test
    void c_aLaterSuccessThatIsNotADeclaredRetryDoesNotBuryTheFailure() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        publish("orders", "r1", FAILED);
        publish("orders", "r2", VALIDATED);   // later, but names no attempt it retries

        Readiness r = check("cdp");
        assertThat(r.isReady()).isFalse();
        assertThat(status(r, "orders")).isEqualTo(new InputStatus(in("orders"), InputState.FAILED, Optional.of("r1-" + tag)));
    }

    @Test
    void c_aRetryThatAlsoFailsLeavesTheInputFailedOnTheRetry() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        publish("orders", "r1", FAILED);
        retry("orders", "r2", FAILED, "r1");

        assertThat(status(check("cdp"), "orders"))
                .isEqualTo(new InputStatus(in("orders"), InputState.FAILED, Optional.of("r2-" + tag)));

        retry("orders", "r3", VALIDATED, "r2");
        assertThat(check("cdp").isReady()).as("a retry of the retry answered it").isTrue();
    }

    @Test
    void aProducedButUnvalidatedInputIsPendingNotReady() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        publish("orders", "r1", PRODUCED);

        Readiness r = check("cdp");
        assertThat(r.isReady()).isFalse();
        assertThat(r.inState(InputState.PENDING)).containsExactly(in("orders"));
    }

    @Test
    void aLateFailureCannotUnvalidateAnAttemptAndALateValidationCannotClearAFailure() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", VALIDATED);
        publish("orders", "r1", FAILED);       // late event for a settled attempt
        publish("customers", "r2", FAILED);
        publish("customers", "r2", VALIDATED); // late event for a settled attempt

        Readiness r = check("cdp");
        assertThat(status(r, "orders").state()).isEqualTo(InputState.READY);
        assertThat(status(r, "customers").state()).isEqualTo(InputState.FAILED);
    }

    @Test
    void anAttemptForAnotherPeriodDoesNotCount() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        readiness().publish(InputAttempt.of(in("orders"), "2026-09", "r1-" + tag, VALIDATED));

        assertThat(check("cdp").missing()).containsExactly(in("orders"));
    }

    @Test
    void anUndeclaredUnitIsNeverReady() {
        Readiness r = check("never-declared");
        assertThat(r.declared()).isFalse();
        assertThat(r.isReady()).as("no expected set must not mean trivially ready").isFalse();
        assertThat(r.inputs()).isEmpty();
        assertThat(readiness().expected(unit("never-declared"))).isEmpty();
    }

    @Test
    void aDeclarationReplacesTheUnitsExpectedSet() {
        readiness().declareExpected(unit("cdp"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", VALIDATED);
        assertThat(check("cdp").isReady()).isFalse();

        readiness().declareExpected(unit("cdp"), Set.of(in("orders")));
        assertThat(readiness().expected(unit("cdp"))).containsExactly(in("orders"));
        assertThat(check("cdp").isReady()).isTrue();
    }

    @Test
    void oneInputServesEveryUnitThatExpectsIt() {
        readiness().declareExpected(unit("cdp-a"), Set.of(in("orders")));
        readiness().declareExpected(unit("cdp-b"), Set.of(in("orders"), in("customers")));
        publish("orders", "r1", VALIDATED);

        assertThat(check("cdp-a").isReady()).isTrue();
        assertThat(check("cdp-b").missing()).containsExactly(in("customers"));
    }

    @Test
    void badArgumentsAreRejected() {
        assertThatThrownBy(() -> readiness().declareExpected(unit("cdp"), Set.of()))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> readiness().declareExpected(" ", Set.of("x")))
                .isInstanceOf(IllegalArgumentException.class);
        List<String> withBlank = new ArrayList<>(List.of("x", " "));
        assertThatThrownBy(() -> readiness().declareExpected(unit("cdp"), Set.copyOf(withBlank)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> readiness().publish(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> readiness().readiness(" ", PERIOD)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> InputAttempt.retry("x", PERIOD, "r1", FAILED, "r1"))
                .as("an attempt cannot retry itself").isInstanceOf(IllegalArgumentException.class);
    }
}
