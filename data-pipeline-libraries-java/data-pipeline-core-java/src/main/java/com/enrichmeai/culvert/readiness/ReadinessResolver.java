package com.enrichmeai.culvert.readiness;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;

/**
 * The readiness rule, in one place, so every backend answers the same way. A backend fetches the
 * unit's expected set and the period's attempts for those inputs, in the order they were recorded,
 * and hands them here.
 *
 * <h2>The anti-join</h2>
 * <p>Readiness is the <strong>expected set minus the ready set</strong>, not a count over the rows
 * that are present. "8 of 8 inputs present" is satisfied by the wrong 8, and by 8 where one failed.
 * Here an attempt for an input the catalogue does not expect, or for another period, is ignored,
 * and every expected input is reported by name with its own state.
 *
 * <h2>Within one attempt: the earliest terminal event wins</h2>
 * <p>The ledger is append-only, so an attempt's state is resolved on read, by the rule
 * {@code JobControlRepository} uses: once an attempt is {@link AttemptState#VALIDATED} or
 * {@link AttemptState#FAILED}, a later event for the same {@code runId} does not change it. A late
 * failure cannot un-validate an input, and a late validation cannot clear a failure.
 *
 * <h2>Across attempts: only a declared retry supersedes a failure</h2>
 * <p>A failed attempt stays failed: a retry takes a new {@code runId} (CONTRACT.md §7). The
 * question is what the input's state is once a retry has run. The rule:
 * <ul>
 *   <li>An attempt is <em>superseded</em> when another attempt of the same input and period names
 *       it in {@link InputAttempt#retryOf()}. The attempts nobody supersedes are the standing ones.
 *   <li>If any standing attempt failed, the input is {@link InputState#FAILED}.
 *   <li>Otherwise, if any standing attempt is unfinished, it is {@link InputState#PENDING}.
 *   <li>Otherwise, if a standing attempt validated it, it is {@link InputState#READY}.
 *   <li>With no attempt at all, it is {@link InputState#MISSING}.
 * </ul>
 * <p>So a failure followed by a successful <em>declared retry</em> of it is ready. The failed
 * attempt is not rewritten; it is answered. A later success that does <em>not</em> name the
 * failure leaves the input failed: recency alone never buries a failure. That is the 0.2.0 bug
 * ({@code get_entity_status} let a later row hide a recorded failure), and this rule cannot repeat
 * it, because nothing here orders attempts by time.
 *
 * <p>If retry links form a cycle, so that every attempt is superseded, all of the input's attempts
 * stand, and any failure among them keeps it failed.
 */
public final class ReadinessResolver {

    private ReadinessResolver() {
    }

    /**
     * @param unit       the unit checked
     * @param period     the period checked
     * @param expected   the unit's expected inputs; empty means the unit is not declared
     * @param attempts   events in the order they were recorded; others are ignored
     * @return the readiness, one status per expected input in name order
     */
    public static Readiness resolve(String unit, String period, Set<String> expected,
                                    List<InputAttempt> attempts) {
        Objects.requireNonNull(expected, "expected must not be null");
        Objects.requireNonNull(attempts, "attempts must not be null");
        List<InputStatus> statuses = new ArrayList<>();
        for (String input : new TreeSet<>(expected)) {
            List<InputAttempt> mine = new ArrayList<>();
            for (InputAttempt a : attempts) {
                if (a.input().equals(input) && a.period().equals(period)) {
                    mine.add(a);
                }
            }
            statuses.add(resolveInput(input, mine));
        }
        return new Readiness(unit, period, !expected.isEmpty(), statuses);
    }

    private static InputStatus resolveInput(String input, List<InputAttempt> events) {
        if (events.isEmpty()) {
            return new InputStatus(input, InputState.MISSING, Optional.empty());
        }
        // Each attempt's state: its earliest terminal event, else PRODUCED. Its retry link: the first
        // one recorded. Attempts keep the order their first event was recorded in.
        Map<String, AttemptState> state = new LinkedHashMap<>();
        Map<String, String> retryOf = new LinkedHashMap<>();
        for (InputAttempt e : events) {
            AttemptState current = state.get(e.runId());
            if (current == null || !current.isTerminal()) {
                state.put(e.runId(), e.state());
            }
            e.retryOf().ifPresent(previous -> retryOf.putIfAbsent(e.runId(), previous));
        }
        Set<String> superseded = new HashSet<>(retryOf.values());
        List<String> standing = new ArrayList<>();
        for (String run : state.keySet()) {
            if (!superseded.contains(run)) {
                standing.add(run);
            }
        }
        if (standing.isEmpty()) {
            standing.addAll(state.keySet());
        }
        for (AttemptState wanted : List.of(AttemptState.FAILED, AttemptState.PRODUCED, AttemptState.VALIDATED)) {
            for (String run : standing) {
                if (state.get(run) == wanted) {
                    return new InputStatus(input, switch (wanted) {
                        case FAILED -> InputState.FAILED;
                        case PRODUCED -> InputState.PENDING;
                        case VALIDATED -> InputState.READY;
                    }, Optional.of(run));
                }
            }
        }
        throw new IllegalStateException("unreachable: every attempt has a state");
    }
}
