package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.orchestration.DagSpec;
import com.enrichmeai.culvert.orchestration.StageGate;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.InputStatus;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;

import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * One run of the fan-out on the control plane (#231): for each unit, {@code load >> validate >>
 * publish}, every stage claimed, gated and recorded.
 *
 * <p>Per stage:
 * <ol>
 *   <li><b>Claim</b> {@code StageKey(unit, stage, period)} without waiting. {@code Completed}: skip,
 *       the stage never runs twice. {@code Held}: another worker has it; stop the unit, and the run
 *       exits non-zero.
 *   <li><b>Gate</b>: re-check the task's gate ({@link StageGate}) from the same {@link DagSpec} the
 *       DAG is rendered from. Closed: release the claim without completing it, and stop the unit.
 *   <li><b>Work</b>: trivial I/O over {@code records} records, and the input's readiness events:
 *       {@code load} publishes the unit's input as produced, {@code validate} rules on it.
 *   <li><b>Complete</b> the claim.
 * </ol>
 *
 * <p>Each unit that acquires a stage gets one job-control run: created at its first acquired
 * stage, {@code succeeded} at the end, or failed with the reason. A unit with nothing to do (every
 * stage already completed, or the first one held) writes no job-control row.
 */
public final class ControlPlaneRun {

    public static final String LOAD = "load";
    public static final String VALIDATE = "validate";
    public static final String PUBLISH = "publish";

    /** The stages, in order. */
    public static final List<String> STAGES = List.of(LOAD, VALIDATE, PUBLISH);

    /** The job-control system id and pipeline name. */
    public static final String SYSTEM_ID = "reference-e2e";
    public static final String PIPELINE_NAME = "reference-e2e-gcp";

    private static final DateTimeFormatter RUN_ID_TS =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);
    private static final SecureRandom RANDOM = new SecureRandom();

    /** What happened to one stage of one unit. */
    public enum Outcome {
        /** Claimed, gate open, worked, completed. */
        DONE,
        /** Already completed by an earlier claimant; not run again. */
        SKIPPED,
        /** Another claimant holds it. */
        HELD,
        /** Claimed, but its gate was closed; released without completing. */
        GATE_CLOSED,
        /** Claimed and worked, but the work failed; released without completing. */
        FAILED
    }

    /**
     * @param runId the unit's job-control run, or {@code null} if it wrote none
     */
    public record StageResult(String unit, String stage, Outcome outcome, String claimant, String runId,
                              long records, String detail) {

        @Override
        public String toString() {
            return unit + "/" + stage + " " + outcome + " claimant=" + claimant
                    + (runId == null ? "" : " run=" + runId)
                    + (outcome == Outcome.DONE ? " records=" + records : "")
                    + (detail.isEmpty() ? "" : " :: " + detail);
        }
    }

    /** Every stage's result, in unit then stage order. */
    public record Report(List<StageResult> results) {

        public Report {
            results = List.copyOf(results);
        }

        /** 0 when nothing failed or was held; 1 if a stage failed or a gate was closed; 2 if held only. */
        public int exitCode() {
            if (results.stream().anyMatch(r -> r.outcome() == Outcome.FAILED || r.outcome() == Outcome.GATE_CLOSED)) {
                return 1;
            }
            return results.stream().anyMatch(r -> r.outcome() == Outcome.HELD) ? 2 : 0;
        }

        /** The results for one unit and stage. */
        public List<StageResult> of(String unit, String stage) {
            return results.stream().filter(r -> r.unit().equals(unit) && r.stage().equals(stage)).toList();
        }

        /** Two reports as one, for the duplicate trigger. */
        public Report and(Report other) {
            List<StageResult> all = new ArrayList<>(results);
            all.addAll(other.results);
            return new Report(all);
        }
    }

    /** A stage's work failed, with what to record in job control. */
    static final class StageFailure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final String code;
        final FailureStage failureStage;

        StageFailure(String code, FailureStage failureStage, String message) {
            super(message);
            this.code = code;
            this.failureStage = failureStage;
        }
    }

    private final ControlPlane store;
    private final List<String> units;
    private final DagSpec spec;
    private final String period;
    private final List<String> stages;
    private final int records;
    private final Faults faults;
    private final Runnable crash;
    private final Runnable hang;
    private final StageGate gate;
    private final AtomicBoolean crashed = new AtomicBoolean();
    private Duration recordDelay = Duration.ZERO;

    /**
     * @param store   the control-plane stores
     * @param units   the units of the fan-out
     * @param period  the period, an ISO date (it is the job-control {@code extract_date})
     * @param stages  which stages to run; a subset fires them as a scheduler might, early or alone
     * @param maxConcurrency  at most this many units at once (#199)
     * @param records records per stage
     * @param faults  the harness's switches
     * @param crash   what "kill the worker" does; {@code ControlPlaneMain} halts the JVM
     */
    public ControlPlaneRun(ControlPlane store, List<String> units, String period, List<String> stages,
                           int maxConcurrency, int records, Faults faults, Runnable crash) {
        this(store, units, period, stages, maxConcurrency, records, faults, crash, crash);
    }

    /**
     * @param hang what "the worker hangs" does ({@link Faults#hangAfterRecords()}); it must not
     *             return while the worker should look hung. {@code ControlPlaneMain} sleeps.
     */
    public ControlPlaneRun(ControlPlane store, List<String> units, String period, List<String> stages,
                           int maxConcurrency, int records, Faults faults, Runnable crash, Runnable hang) {
        this.store = Objects.requireNonNull(store, "store must not be null");
        this.units = List.copyOf(units);
        if (this.units.isEmpty()) {
            throw new IllegalArgumentException("at least one unit is needed");
        }
        LocalDate.parse(period); // an ISO date, or DateTimeParseException naming it
        this.period = period;
        for (String stage : stages) {
            if (!STAGES.contains(stage)) {
                throw new IllegalArgumentException("unknown stage '" + stage + "'; the stages are " + STAGES);
            }
        }
        this.stages = STAGES.stream().filter(stages::contains).toList();
        this.spec = ReferenceDag.spec(this.units, maxConcurrency);
        if (records < 1) {
            throw new IllegalArgumentException("records must be at least 1, got " + records);
        }
        if (faults.killAfterRecords() != null && faults.killAfterRecords() > records) {
            // A kill that can never fire would let the harness record a clean run as proof 2.
            throw new IllegalArgumentException("--fault.kill-after=" + faults.killAfterRecords()
                    + " is more than --records=" + records + ", so the kill would never happen");
        }
        if (faults.hangAfterRecords() != null && faults.hangAfterRecords() > records) {
            throw new IllegalArgumentException("--fault.hang-after=" + faults.hangAfterRecords()
                    + " is more than --records=" + records + ", so the hang would never happen");
        }
        this.records = records;
        this.faults = Objects.requireNonNull(faults, "faults must not be null");
        this.crash = Objects.requireNonNull(crash, "crash must not be null");
        this.hang = Objects.requireNonNull(hang, "hang must not be null");
        this.gate = new StageGate(store.claims(), store.readiness());
    }

    /**
     * Spend {@code delay} on each record, standing in for real I/O, so that concurrent triggers
     * overlap (proof 1) and a kill lands mid-stage (proof 2). Default zero.
     */
    public ControlPlaneRun withRecordDelay(Duration delay) {
        if (delay.isNegative()) {
            throw new IllegalArgumentException("the record delay must not be negative, got " + delay);
        }
        this.recordDelay = delay;
        return this;
    }

    /** The spec the run checks its gates against, and the DAG is rendered from. */
    public DagSpec spec() {
        return spec;
    }

    /** The input a unit expects for the period: one, named after the unit. */
    public static String inputOf(String unit) {
        return unit + ".raw";
    }

    /**
     * Run every unit, at most {@code maxConcurrency} at once. With {@link Faults#duplicateTrigger()},
     * run the whole thing twice at once, as {@code claimant#1} and {@code claimant#2}.
     */
    public Report run(String claimant) {
        if (!faults.duplicateTrigger()) {
            return runOnce(claimant);
        }
        ExecutorService twice = Executors.newFixedThreadPool(2);
        try {
            Future<Report> first = twice.submit(() -> runOnce(claimant + "#1"));
            Future<Report> second = twice.submit(() -> runOnce(claimant + "#2"));
            return join(first).and(join(second));
        } finally {
            twice.shutdownNow();
        }
    }

    private Report runOnce(String claimant) {
        for (String unit : units) {
            store.readiness().declareExpected(unit, Set.of(inputOf(unit)));
        }
        ExecutorService pool = Executors.newFixedThreadPool(Math.min(spec.maxConcurrency(), units.size()));
        try {
            List<Future<List<StageResult>>> running = new ArrayList<>();
            for (String unit : units) {
                running.add(pool.submit(() -> runUnit(unit, claimant)));
            }
            List<StageResult> all = new ArrayList<>();
            for (Future<List<StageResult>> unit : running) {
                all.addAll(join(unit));
            }
            return new Report(all);
        } finally {
            pool.shutdownNow();
        }
    }

    /** The unit's job-control run, once it has one: so an unexpected error can still fail it. */
    private static final class RunHolder {
        String runId;
    }

    private List<StageResult> runUnit(String unit, String claimant) {
        RunHolder run = new RunHolder();
        try {
            return runUnit(unit, claimant, run);
        } catch (RuntimeException e) {
            // Not a stage failure: a store or the gate threw. Never leave the run 'running'.
            try {
                fail(run.runId, "STAGE_ERROR", unit + ": " + e, FailureStage.UNKNOWN);
            } catch (RuntimeException alsoFailed) {
                e.addSuppressed(alsoFailed);
            }
            throw e;
        }
    }

    private List<StageResult> runUnit(String unit, String claimant, RunHolder run) {
        List<StageResult> out = new ArrayList<>();
        String runId = null;
        long total = 0;
        for (String stage : stages) {
            ClaimResult claimed = store.claims().tryClaim(new StageKey(unit, stage, period), claimant, Duration.ZERO);
            if (claimed instanceof ClaimResult.Completed done) {
                out.add(new StageResult(unit, stage, Outcome.SKIPPED, claimant, runId, 0,
                        "completed by " + done.completedBy()));
                continue;
            }
            if (claimed instanceof ClaimResult.Held) {
                out.add(new StageResult(unit, stage, Outcome.HELD, claimant, runId, 0, "held by another claimant"));
                fail(runId, "STAGE_HELD", unit + "/" + stage + " is held by another claimant", FailureStage.UNKNOWN);
                return out;
            }
            try (Claim claim = ((ClaimResult.Acquired) claimed).claim()) {
                StageGate.Result open = gate.check(ReferenceDag.task(spec, unit, stage), unit, period);
                if (!open.isOpen()) {
                    out.add(new StageResult(unit, stage, Outcome.GATE_CLOSED, claimant, runId, 0, open.toString()));
                    fail(runId, "GATE_CLOSED", open.toString(), FailureStage.UNKNOWN);
                    return out;
                }
                if (runId == null) {
                    runId = startJob(unit);
                    run.runId = runId;
                }
                long n;
                try {
                    n = work(unit, stage, runId);
                } catch (StageFailure f) {
                    out.add(new StageResult(unit, stage, Outcome.FAILED, claimant, runId, 0, f.getMessage()));
                    fail(runId, f.code, f.getMessage(), f.failureStage);
                    return out;
                }
                claim.complete();
                total += n;
                out.add(new StageResult(unit, stage, Outcome.DONE, claimant, runId, n, ""));
            }
        }
        if (runId != null) {
            store.jobControl().updateStatus(runId, JobStatus.SUCCEEDED, Optional.of(total));
        }
        return out;
    }

    private String startJob(String unit) {
        String runId = RUN_ID_TS.format(Instant.now()) + String.format("-%04x", RANDOM.nextInt(0x10000));
        store.jobControl().createJob(PipelineJob.builder(runId, SYSTEM_ID, PIPELINE_NAME, LocalDate.parse(period),
                JobStatus.CREATED).entityType(unit).build());
        store.jobControl().updateStatus(runId, JobStatus.RUNNING, Optional.empty());
        return runId;
    }

    private void fail(String runId, String code, String message, FailureStage stage) {
        if (runId != null) {
            store.jobControl().markFailed(runId, code, message, stage, Optional.empty());
        }
    }

    /** The stage's trivial I/O and its readiness events. Returns the records handled. */
    private long work(String unit, String stage, String runId) {
        long handled = 0;
        for (int i = 0; i < records; i++) {
            killIfDue(stage, handled);
            pause();
            handled++;
        }
        killIfDue(stage, handled);
        String input = inputOf(unit);
        switch (stage) {
            case LOAD -> store.readiness().publish(InputAttempt.of(input, period, runId, AttemptState.PRODUCED));
            case VALIDATE -> validate(unit, input, runId);
            default -> { }
        }
        return handled;
    }

    /**
     * Rule on the input's standing attempt. A pending attempt (produced, not yet ruled on) gets
     * its verdict under its own run id. A failed one can only be answered by a declared retry
     * (#198), so a re-validation is published as a new attempt naming it.
     */
    private void validate(String unit, String input, String runId) {
        InputStatus status = store.readiness().readiness(unit, period).inputs().stream()
                .filter(s -> s.input().equals(input)).findFirst()
                .orElseThrow(() -> new StageFailure("INPUT_NOT_DECLARED", FailureStage.VALIDATION,
                        input + " is not declared for " + unit));
        AttemptState verdict = faults.failValidation().contains(unit) ? AttemptState.FAILED : AttemptState.VALIDATED;
        switch (status.state()) {
            case PENDING -> store.readiness().publish(
                    InputAttempt.of(input, period, status.runId().orElseThrow(), verdict));
            case FAILED -> store.readiness().publish(
                    InputAttempt.retry(input, period, runId, verdict, status.runId().orElseThrow()));
            case READY -> {
                return; // already validated; nothing to rule on
            }
            case MISSING -> throw new StageFailure("INPUT_MISSING", FailureStage.VALIDATION,
                    input + " was never produced for " + period);
        }
        if (verdict == AttemptState.FAILED) {
            throw new StageFailure("INPUT_INVALID", FailureStage.VALIDATION,
                    input + " failed validation for " + period);
        }
    }

    private void pause() {
        if (recordDelay.isZero()) {
            return;
        }
        try {
            Thread.sleep(recordDelay.toMillis());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted mid-record", e);
        }
    }

    private void killIfDue(String stage, long handled) {
        if (!stage.equals(faults.killStage())) {
            return;
        }
        Integer kill = faults.killAfterRecords();
        if (kill != null && handled == kill && crashed.compareAndSet(false, true)) {
            crash.run();
        }
        Integer stall = faults.hangAfterRecords();
        if (stall != null && handled == stall && crashed.compareAndSet(false, true)) {
            hang.run();
        }
    }

    private static <T> T join(Future<T> future) {
        try {
            return future.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted", e);
        } catch (ExecutionException e) {
            if (e.getCause() instanceof RuntimeException r) {
                throw r;
            }
            if (e.getCause() instanceof Error err) {
                throw err;
            }
            throw new IllegalStateException(e.getCause());
        }
    }
}
