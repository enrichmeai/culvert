package com.enrichmeai.culvert.readiness;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import static com.enrichmeai.culvert.readiness.AttemptState.FAILED;
import static com.enrichmeai.culvert.readiness.AttemptState.PRODUCED;
import static com.enrichmeai.culvert.readiness.AttemptState.VALIDATED;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The edges of the readiness rule that the shared contract does not reach. */
class ReadinessResolverTest {

    private static InputStatus only(List<InputAttempt> attempts) {
        return ReadinessResolver.resolve("u", "p", Set.of("in"), attempts).inputs().get(0);
    }

    @Test
    void aRetryOnlySupersedesAnAttemptOfTheSameInputAndPeriod() {
        List<InputAttempt> attempts = List.of(
                InputAttempt.of("in", "p", "r1", FAILED),
                InputAttempt.retry("other", "p", "r2", VALIDATED, "r1"),
                InputAttempt.retry("in", "q", "r3", VALIDATED, "r1"));
        assertThat(only(attempts)).isEqualTo(new InputStatus("in", InputState.FAILED, Optional.of("r1")));
    }

    @Test
    void anUnfinishedUnlinkedReRunBesideAValidatedAttemptIsPending() {
        List<InputAttempt> attempts = List.of(
                InputAttempt.of("in", "p", "r1", VALIDATED),
                InputAttempt.of("in", "p", "r2", PRODUCED));
        assertThat(only(attempts).state()).as("the input is being rewritten").isEqualTo(InputState.PENDING);
    }

    @Test
    void aRetryLinkToALaterOrUnknownAttemptSupersedesNothing() {
        // r1 claims to retry r2, which is recorded after it: a retry cannot precede what it retries.
        assertThat(only(List.of(
                InputAttempt.retry("in", "p", "r1", FAILED, "r2"),
                InputAttempt.of("in", "p", "r2", VALIDATED))).state()).isEqualTo(InputState.FAILED);
        assertThat(only(List.of(
                InputAttempt.of("in", "p", "r1", FAILED),
                InputAttempt.retry("in", "p", "r2", VALIDATED, "r0"))).state()).isEqualTo(InputState.FAILED);
    }

    @Test
    void aCycleOfRetryLinksCannotHideAFailureBehindAnotherAttempt() {
        // r1 and r2 name each other, beside an unrelated validated r3. Before the links had to point
        // back, both counted, r1 and r2 were both superseded, and r3 alone read READY. Now only r2's
        // link counts: r2 answers r1, and r2's own failure, which nothing answers, keeps it failed.
        List<InputAttempt> attempts = List.of(
                InputAttempt.retry("in", "p", "r1", FAILED, "r2"),
                InputAttempt.retry("in", "p", "r2", FAILED, "r1"),
                InputAttempt.of("in", "p", "r3", VALIDATED));
        assertThat(only(attempts)).isEqualTo(new InputStatus("in", InputState.FAILED, Optional.of("r2")));
    }

    @Test
    void twoRetriesOfOneFailureMustBothSucceed() {
        List<InputAttempt> attempts = List.of(
                InputAttempt.of("in", "p", "r1", FAILED),
                InputAttempt.retry("in", "p", "r2", VALIDATED, "r1"),
                InputAttempt.retry("in", "p", "r3", FAILED, "r1"));
        assertThat(only(attempts)).isEqualTo(new InputStatus("in", InputState.FAILED, Optional.of("r3")));
    }

    @Test
    void theFirstRetryLinkRecordedForAnAttemptIsTheOneThatCounts() {
        List<InputAttempt> attempts = List.of(
                InputAttempt.of("in", "p", "r1", FAILED),
                InputAttempt.of("in", "p", "r9", FAILED),
                InputAttempt.retry("in", "p", "r2", PRODUCED, "r1"),
                InputAttempt.retry("in", "p", "r2", VALIDATED, "r9"));
        assertThat(only(attempts)).as("r2 answers r1, not r9").isEqualTo(
                new InputStatus("in", InputState.FAILED, Optional.of("r9")));
    }

    @Test
    void anEmptyExpectedSetIsAnUndeclaredUnitAndNotReady() {
        Readiness r = ReadinessResolver.resolve("u", "p", Set.of(), List.of(InputAttempt.of("in", "p", "r1", VALIDATED)));
        assertThat(r.declared()).isFalse();
        assertThat(r.isReady()).isFalse();
        assertThat(r.toString()).contains("no expected inputs are declared for unit 'u'");
    }

    @Test
    void theResultNamesWhatIsNotReady() {
        Readiness r = ReadinessResolver.resolve("cdp", "2026-10", Set.of("a", "b", "c"), List.of(
                InputAttempt.of("a", "2026-10", "r1", VALIDATED),
                InputAttempt.of("b", "2026-10", "r2", FAILED)));
        assertThat(r.toString()).isEqualTo("Not ready: unit 'cdp' for 2026-10: [b=FAILED (r2), c=MISSING]");
    }

    @Test
    void wireValuesRoundTrip() {
        for (AttemptState s : AttemptState.values()) {
            assertThat(AttemptState.fromValue(s.getValue())).isEqualTo(s);
        }
        assertThatThrownBy(() -> AttemptState.fromValue("done")).isInstanceOf(IllegalArgumentException.class);
    }
}
