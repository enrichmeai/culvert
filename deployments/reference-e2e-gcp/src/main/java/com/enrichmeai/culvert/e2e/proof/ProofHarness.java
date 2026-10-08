package com.enrichmeai.culvert.e2e.proof;

import com.enrichmeai.culvert.e2e.ReferenceE2EMain;
import com.enrichmeai.culvert.e2e.controlplane.ControlPlaneMain;
import com.enrichmeai.culvert.e2e.controlplane.ControlPlaneRun;
import com.enrichmeai.culvert.e2e.controlplane.ReferenceDag;
import com.enrichmeai.culvert.orchestration.StageGate;
import com.enrichmeai.culvert.orchestration.TaskSpec;
import com.enrichmeai.culvert.postgres.PostgresReadiness;
import com.enrichmeai.culvert.postgres.PostgresStageClaim;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import org.postgresql.ds.PGSimpleDataSource;

import java.io.File;
import java.io.IOException;
import java.io.Serializable;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * The Phase 3 proof harness (#232): <em>"A step cannot double-start, and an interrupted run
 * resumes exactly where it stopped."</em>
 *
 * <p>Each scenario starts real worker processes ({@link ControlPlaneMain}), and for 4 and 6 a real
 * Airflow, then asserts on the control store's own state: {@code stage_completions}, the
 * job-control ledger, the readiness ledger, the Airflow metadata database and {@code culvert} CLI
 * output. Never on timing alone. Each prints its evidence rows and PASS or FAIL.
 *
 * <p>Everything it talks to is configuration: the PostgreSQL URL, the Airflow command and its
 * metadata database, the Python interpreter. See {@code proof/README.md}.
 */
public final class ProofHarness {

    static final Map<Integer, String> TITLES = new LinkedHashMap<>();

    static {
        TITLES.put(1, "Trigger the same unit, stage and period twice at once");
        TITLES.put(2, "Kill a worker partway through stage 2 of 3, then re-run");
        TITLES.put(3, "A dead holder's claim is released");
        TITLES.put(4, "Fire a downstream task before its upstream completes (Airflow)");
        TITLES.put(5, "Leave one input missing, then fail one");
        TITLES.put(6, "Fan out N units with max_concurrency=2 (Airflow)");
        TITLES.put(7, "A full run on PostgreSQL job control, read with culvert");
    }

    private static final Pattern STAGE_LINE = Pattern.compile(
            "^(\\S+)/(\\S+) (DONE|SKIPPED|HELD|GATE_CLOSED|FAILED) claimant=(\\S+)(?: run=(\\S+))?(?: records=(\\d+))?(?: :: (.*))?$");

    enum Verdict { PASS, FAIL, NOT_RUN }

    /** One scenario's outcome and the evidence behind it. */
    static final class Result {
        final int number;
        final List<String> evidence = new ArrayList<>();
        boolean failed;
        String notRun;

        Result(int number) {
            this.number = number;
        }

        /** Evidence is printed as it is found, so a scenario that stalls still shows how far it got. */
        private void emit(String line) {
            evidence.add(line);
            System.out.println(line);
            System.out.flush();
        }

        void note(String line) {
            emit("    " + line);
        }

        void rows(String heading, List<String> rows) {
            emit("    " + heading + (rows.isEmpty() ? " (none)" : ""));
            rows.forEach(r -> emit("      " + r));
        }

        boolean check(boolean ok, String what) {
            emit("  " + (ok ? "[ok]   " : "[FAIL] ") + what);
            failed |= !ok;
            return ok;
        }

        Verdict verdict() {
            // A failed check outranks a part that could not run.
            return failed ? Verdict.FAIL : notRun != null ? Verdict.NOT_RUN : Verdict.PASS;
        }
    }

    private final Map<String, String> opts;
    private final String jdbcUrl;
    private final String user;
    private final String password;
    private final String classpath;
    private final LocalDate base;
    private final Path workdir;

    ProofHarness(Map<String, String> opts) {
        this.opts = opts;
        this.jdbcUrl = opts.getOrDefault("jdbc-url", "jdbc:postgresql://localhost:55432/culvert");
        this.user = opts.getOrDefault("pg-user", "postgres");
        this.password = opts.get("pg-password");
        this.classpath = opts.getOrDefault("classpath", System.getProperty("java.class.path"));
        this.base = LocalDate.parse(opts.getOrDefault("period-base", "2025-01-01"));
        this.workdir = Path.of(opts.getOrDefault("workdir", System.getProperty("java.io.tmpdir") + "/culvert-proof"));
    }

    public static void main(String[] args) {
        Map<String, String> opts = ReferenceE2EMain.parseArgs(args);
        ProofHarness harness = new ProofHarness(opts);
        List<Integer> wanted = opts.getOrDefault("scenarios", "1,2,3,4,5,6,7").equals("all")
                ? new ArrayList<>(TITLES.keySet())
                : Arrays.stream(opts.getOrDefault("scenarios", "1,2,3,4,5,6,7").split(","))
                        .map(String::trim).map(Integer::valueOf).toList();
        System.exit(harness.run(wanted));
    }

    int run(List<Integer> wanted) {
        prepare();
        List<Result> results = new ArrayList<>();
        for (int n : wanted) {
            Result r = new Result(n);
            System.out.println("=== Scenario " + n + ": " + TITLES.get(n) + "  (period " + period(n) + ")");
            try {
                switch (n) {
                    case 1 -> duplicateTrigger(r);
                    case 2 -> killMidStage(r);
                    case 3 -> deadHolderReleased(r);
                    case 4 -> earlyDownstreamInAirflow(r);
                    case 5 -> readinessGate(r);
                    case 6 -> maxConcurrencyInAirflow(r);
                    case 7 -> culvertCli(r);
                    default -> throw new IllegalArgumentException("no scenario " + n);
                }
            } catch (RuntimeException e) {
                r.check(false, "the scenario threw: " + e);
            }
            System.out.println("  => " + r.verdict() + (r.notRun != null ? " (" + r.notRun + ")" : ""));
            System.out.println();
            results.add(r);
        }
        System.out.println("=== Summary");
        for (Result r : results) {
            System.out.printf("  %d. %-70s %s%n", r.number, TITLES.get(r.number), r.verdict());
        }
        if (results.stream().anyMatch(r -> r.verdict() == Verdict.FAIL)) {
            return 1;
        }
        return results.stream().anyMatch(r -> r.verdict() == Verdict.NOT_RUN) ? 3 : 0;
    }

    // ------------------------------------------------------------------ setup

    private void prepare() {
        try {
            Files.createDirectories(workdir);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        System.setProperty("culvert.postgres.url", jdbcUrl);
        System.setProperty("culvert.postgres.user", user);
        if (password != null) {
            System.setProperty("culvert.postgres.password", password);
        }
        ControlPlaneMain.applyDdl();
        if (Boolean.parseBoolean(opts.getOrDefault("reset", "false"))) {
            exec("TRUNCATE job_control.pipeline_jobs, job_control.stage_claims, job_control.stage_completions, "
                    + "job_control.readiness_expected, job_control.readiness_attempts RESTART IDENTITY");
            System.out.println("--reset: emptied the control-plane tables in " + jdbcUrl);
        }
        List<String> periods = TITLES.keySet().stream().map(n -> period(n)).toList();
        List<String> used = rows("SELECT period FROM job_control.stage_completions WHERE period = ANY(?) "
                + "UNION SELECT period FROM job_control.readiness_attempts WHERE period = ANY(?) "
                + "UNION SELECT extract_date::text FROM job_control.pipeline_jobs WHERE extract_date::text = ANY(?)",
                periods.toArray(String[]::new), periods.toArray(String[]::new), periods.toArray(String[]::new));
        if (!used.isEmpty()) {
            throw new IllegalStateException("periods " + used + " already have control-plane rows, so their evidence "
                    + "would be mixed with an earlier run's. Pass --period-base=<another date>, or --reset on a "
                    + "database used only for the proof.");
        }
        System.out.println("Control store: " + jdbcUrl + " (job_control.sql applied); periods " + periods.get(0)
                + " .. " + periods.get(periods.size() - 1));
        System.out.println();
    }

    String period(int scenario) {
        return base.plusDays(scenario - 1L).toString();
    }

    // ------------------------------------------------------------------ 1

    private void duplicateTrigger(Result r) {
        String p = period(1);
        List<String> args = workerArgs(p, "orders,customers,products", 3, 20, 25);
        Proc a = worker("proof1-a", args);
        Proc b = worker("proof1-b", args);
        int ea = a.waitFor(300);
        int eb = b.waitFor(300);
        r.note("trigger proof1-a exit " + ea + ", trigger proof1-b exit " + eb + " (2 = it found a stage held)");
        List<String[]> lines = new ArrayList<>(stageLines(a));
        lines.addAll(stageLines(b));
        r.rows("stage lines from both triggers:", lines.stream().map(l -> l[0]).toList());

        Map<String, List<String>> doneBy = new TreeMap<>();
        Map<String, List<String>> others = new TreeMap<>();
        for (String[] l : lines) {
            String key = l[1] + "/" + l[2];
            (l[3].equals("DONE") ? doneBy : others).computeIfAbsent(key, k -> new ArrayList<>()).add(l[4] + " " + l[3]);
        }
        List<String> completions = rows("SELECT unit || '/' || stage || '  completed_by=' || completed_by "
                + "FROM job_control.stage_completions WHERE period = ? ORDER BY 1", p);
        r.rows("job_control.stage_completions:", completions);
        List<String> produced = rows("SELECT input || '  produced attempts=' || count(*) FROM job_control.readiness_attempts "
                + "WHERE period = ? AND state = 'produced' GROUP BY input ORDER BY 1", p);
        r.rows("job_control.readiness_attempts (produced, per input):", produced);
        List<String> runs = rows("SELECT DISTINCT ON (run_id) run_id || '  ' || entity_type || '  ' || status "
                + "FROM job_control.pipeline_jobs WHERE extract_date = ?::date ORDER BY run_id, seq DESC", p);
        r.rows("job_control.pipeline_jobs (current state per run):", runs);

        for (String unit : List.of("orders", "customers", "products")) {
            for (String stage : ControlPlaneRun.STAGES) {
                String key = unit + "/" + stage;
                List<String> done = doneBy.getOrDefault(key, List.of());
                r.check(done.size() == 1, key + ": done by exactly one trigger " + done
                        + "; the other saw " + others.getOrDefault(key, List.of("nothing: its unit had stopped on a held stage")));
            }
        }
        r.check(completions.size() == 9, "exactly one completion row per unit and stage (9)");
        r.check(runs.size() == 3 && runs.stream().allMatch(l -> l.endsWith("  succeeded")),
                "one run per unit in the ledger did the work, and each succeeded: no run left behind by the other trigger");
        r.check(produced.size() == 3 && produced.stream().allMatch(s -> s.endsWith("=1")),
                "each unit's input was produced once: load's work was not done twice");
        // Completed alone could mean the triggers ran one after the other; Held proves they overlapped.
        boolean collided = lines.stream().anyMatch(l -> l[3].equals("HELD"));
        r.check(collided, "the triggers overlapped: one found a stage Held by the other (otherwise this proves nothing)");
    }

    // ------------------------------------------------------------------ 2

    private void killMidStage(Result r) {
        String p = period(2);
        List<String> args = workerArgs(p, "orders", 1, 20, 25);
        List<String> killArgs = new ArrayList<>(args);
        killArgs.add("--fault.kill-after=10");
        Proc w1 = worker("proof2-w1", killArgs);
        int e1 = w1.waitFor(300);
        r.note("worker proof2-w1 (--fault.kill-after=10 in validate) exit " + e1);
        r.check(e1 == 137 && w1.out().contains("KILLED"), "the worker was killed (exit 137) partway through validate");
        List<String> afterKill = completions(p);
        r.rows("stage_completions after the kill:", afterKill);
        r.rows("pipeline_jobs after the kill:", runStates(p));

        Proc w2 = worker("proof2-w2", args);
        int e2 = w2.waitFor(300);
        r.note("worker proof2-w2 (the re-run) exit " + e2);
        List<String[]> lines = stageLines(w2);
        r.rows("re-run stage lines:", lines.stream().map(l -> l[0]).toList());
        r.rows("stage_completions after the re-run:", completions(p));
        r.rows("readiness_attempts:", rows("SELECT input || '  ' || run_id || '  ' || state FROM "
                + "job_control.readiness_attempts WHERE period = ? ORDER BY seq", p));

        r.check(afterKill.equals(List.of("orders/load  completed_by=proof2-w1")),
                "before the re-run, only stage 1 (load) is completed");
        r.check(has(lines, "orders", "load", "SKIPPED"), "stage 1 is not redone: the re-run skipped load");
        String[] validate = find(lines, "orders", "validate");
        r.check(validate != null && validate[3].equals("DONE") && "20".equals(validate[6]),
                "stage 2 restarts from its beginning: validate DONE over all 20 records, not the 10 left");
        r.check(rows("SELECT count(*) FROM job_control.stage_completions WHERE period = ? AND stage = 'publish'", p)
                .equals(List.of("1")) && has(lines, "orders", "publish", "DONE"), "stage 3 runs once");
        r.check(rows("SELECT count(*) FROM job_control.readiness_attempts WHERE period = ? AND state = 'produced'", p)
                .equals(List.of("1")), "the input was produced once");
        r.check(e2 == 0, "the re-run exits 0");
    }

    // ------------------------------------------------------------------ 3

    private void deadHolderReleased(Result r) {
        String p = period(3);
        // (a) A killed holder: its session ends with the process, and the server rolls back the claim.
        List<String> killArgs = new ArrayList<>(workerArgs(p, "customers", 1, 5, 0));
        killArgs.add("--fault.kill-after=2");
        int ek = worker("proof3-killed", killArgs).waitFor(300);
        long killedAt = System.nanoTime();
        Proc next = worker("proof3-next", workerArgs(p, "customers", 1, 5, 0));
        int en = next.waitFor(300);
        String[] v = find(stageLines(next), "customers", "validate");
        r.note("(a) killed holder: exit " + ek + "; the next worker's validate: " + (v == null ? "none" : v[0])
                + String.format(" (%.1fs after the kill, JVM start included)", (System.nanoTime() - killedAt) / 1e9));
        r.check(ek == 137 && en == 0 && v != null && v[3].equals("DONE"),
                "(a) after a kill, the next claimant acquires on its first attempt");

        // (b) A hung holder: alive and connected, holding its claim in an open transaction.
        String timeout = opts.getOrDefault("session-timeout", "5s");
        String db = jdbcUrl.replaceAll("^.*/([^/?]+)(\\?.*)?$", "$1");
        boolean set = !timeout.equals("server");
        // Restore exactly what the database had before, even if the harness is interrupted.
        List<String> before = rows("SELECT s FROM pg_db_role_setting rs JOIN pg_database d ON d.oid = rs.setdatabase, "
                + "unnest(rs.setconfig) s WHERE d.datname = ? AND rs.setrole = 0 "
                + "AND s LIKE 'idle_in_transaction_session_timeout=%'", db);
        String restore = before.isEmpty()
                ? "ALTER DATABASE \"" + db + "\" RESET idle_in_transaction_session_timeout"
                : "ALTER DATABASE \"" + db + "\" SET idle_in_transaction_session_timeout = '"
                        + before.get(0).substring(before.get(0).indexOf('=') + 1) + "'";
        Thread restorer = new Thread(() -> exec(restore), "session-timeout-restorer");
        if (set) {
            Runtime.getRuntime().addShutdownHook(restorer);
            exec("ALTER DATABASE \"" + db + "\" SET idle_in_transaction_session_timeout = '" + timeout + "'");
        }
        Proc hung = null;
        try {
            String effective = rows("SHOW idle_in_transaction_session_timeout").get(0);
            r.note("(b) idle_in_transaction_session_timeout for new sessions: " + effective
                    + (set ? " (set by the harness for this scenario)" : " (the server's own setting)"));
            List<String> hangArgs = new ArrayList<>(workerArgs(p, "orders", 1, 5, 0));
            hangArgs.add("--fault.hang-after=2");
            hung = worker("proof3-hung", hangArgs);
            boolean isHung = hung.awaitOutput("HUNG", 120);
            long hungAt = System.nanoTime();
            r.check(isHung, "(b) the worker hung in validate, holding its claim");
            r.rows("    its session, from pg_stat_activity:", sessions("proof3-hung"));
            long seconds = parseSeconds(effective);
            long deadline = hungAt + (seconds + 30) * 1_000_000_000L;
            int attempts = 0;
            String acquired = null;
            String firstAttempt = null;
            double after = -1;
            while (System.nanoTime() < deadline) {
                attempts++;
                Proc w = worker("proof3-w" + attempts, workerArgs(p, "orders", 1, 5, 0));
                w.waitFor(300);
                String[] line = find(stageLines(w), "orders", "validate");
                if (firstAttempt == null) {
                    firstAttempt = line == null ? "none" : line[3];
                }
                if (line != null && line[3].equals("DONE")) {
                    acquired = line[0];
                    after = (System.nanoTime() - hungAt) / 1e9;
                    break;
                }
                r.note(String.format("attempt %d at %.1fs: %s", attempts, (System.nanoTime() - hungAt) / 1e9,
                        line == null ? "no validate line" : line[0]));
                Proc.sleep(1000);
            }
            List<String> afterwards = sessions("proof3-hung");
            r.rows("    the hung worker's session afterwards:", afterwards);
            r.check("HELD".equals(firstAttempt), "(b) while the worker hung, the next claimant found validate Held: " + firstAttempt);
            r.check(acquired != null, "(b) a later claimant acquired validate with no manual step: " + acquired);
            r.check(acquired != null && after <= seconds + 8, String.format(
                    "(b) within the server's session timeout (%ds) plus one retry and a worker start (8s): %.1fs after the hang",
                    seconds, after));
            r.check(afterwards.isEmpty(), "(b) the server ended the hung worker's session");
            r.check(hung.alive(), "(b) the hung worker was still alive: the server released it, not a process exit");
            r.note("the harness never calls pg_terminate_backend; the server's timeout ended the session");
        } finally {
            if (hung != null) {
                hung.destroyTree();
            }
            if (set) {
                exec(restore);
                Runtime.getRuntime().removeShutdownHook(restorer);
                r.note("restored the database's idle_in_transaction_session_timeout: "
                        + (before.isEmpty() ? "none set" : before.get(0)));
            }
        }
    }

    // ------------------------------------------------------------------ 4

    private void earlyDownstreamInAirflow(Result r) {
        if (!airflowConfigured(r)) {
            return;
        }
        String p = period(4);
        airflowSetup(r);
        boolean exits = runner().exitCodeIsTheCommands();
        Proc first = runner().run("proof4-test1", "tasks", "test", ReferenceDag.DAG_ID, "orders__validate", p);
        int e1 = first.waitFor(600);
        r.note("airflow tasks test " + ReferenceDag.DAG_ID + " orders__validate " + p + "  -> exit " + e1
                + (exits ? "" : " (gcloud's; the check reads Airflow's output)"));
        r.rows("its gate line:", grep(first, "Gate closed"));
        r.check((exits ? e1 != 0 : !first.out().contains("Marking task as SUCCESS"))
                        && first.out().contains("Gate closed for task 'orders__validate': not completed: load"),
                "fired before load completed, validate fails on its gate, naming load");
        r.check(completions(p).isEmpty(), "nothing was completed by the early task");

        Proc load = worker("proof4-load", withStages(workerArgs(p, "orders", 1, 5, 0), "load"));
        r.note("worker proof4-load runs only orders/load: exit " + load.waitFor(300));
        r.rows("stage_completions:", completions(p));

        Proc second = runner().run("proof4-test2", "tasks", "test", ReferenceDag.DAG_ID, "orders__validate", p);
        int e2 = second.waitFor(600);
        r.note("the retry: airflow tasks test ... orders__validate " + p + "  -> exit " + e2);
        r.rows("its outcome lines:", grep(second, "Marking task as"));
        r.check((!exits || e2 == 0) && !second.out().contains("Gate closed")
                        && second.out().contains("Marking task as SUCCESS"),
                "after load's complete(), the retried validate runs");
        r.note("the retry is the harness re-running the task, as Airflow's retries would; the rendered DAG sets none");
    }

    // ------------------------------------------------------------------ 5

    private void readinessGate(Result r) {
        String p = period(5);
        // (a) The rule, on the store: Java's StageGate and the DAG's Python not_ready must agree.
        PGSimpleDataSource ds = dataSource();
        PostgresReadiness readiness = new PostgresReadiness(ds);
        StageGate gate = new StageGate(new PostgresStageClaim(ds), readiness);
        String unit = "proof5";
        TaskSpec publish = new TaskSpec(unit + "__publish", "publish", List.of(),
                Map.<String, Serializable>of(StageGate.READY, Boolean.TRUE));
        readiness.declareExpected(unit, p, Set.of("a", "b", "c"));
        readiness.publish(InputAttempt.of("a", p, "r1", AttemptState.PRODUCED));
        readiness.publish(InputAttempt.of("a", p, "r1", AttemptState.VALIDATED));
        readiness.publish(InputAttempt.of("c", p, "r2", AttemptState.PRODUCED));
        readiness.publish(InputAttempt.of("c", p, "r2", AttemptState.FAILED));
        List<String> step1 = gate.check(publish, unit, p).inputsNotReady();
        parity(r, "b missing, c failed", step1, unit, p);
        r.check(step1.equals(List.of("b=MISSING", "c=FAILED (r2)")), "the gate stays shut and names both inputs: " + step1);

        readiness.publish(InputAttempt.of("c", p, "r3", AttemptState.PRODUCED));
        readiness.publish(InputAttempt.of("c", p, "r3", AttemptState.VALIDATED));
        readiness.publish(InputAttempt.of("b", p, "r4", AttemptState.PRODUCED));
        readiness.publish(InputAttempt.of("b", p, "r4", AttemptState.VALIDATED));
        List<String> step2 = gate.check(publish, unit, p).inputsNotReady();
        parity(r, "b validated, c: an unlinked later success", step2, unit, p);
        r.check(step2.equals(List.of("c=FAILED (r2)")), "an unlinked later success does not open it: " + step2);

        readiness.publish(InputAttempt.retry("c", p, "r5", AttemptState.VALIDATED, "r2"));
        List<String> step3 = gate.check(publish, unit, p).inputsNotReady();
        parity(r, "c: a declared retry of r2 validates", step3, unit, p);
        r.check(step3.isEmpty(), "a declared retry that validates opens it");

        // (b) End to end through the worker: a failed validation, publish fired early, the retry.
        List<String> args = workerArgs(p, "orders", 1, 5, 0);
        List<String> failArgs = new ArrayList<>(args);
        failArgs.add("--fault.fail-validation=orders");
        Proc failing = worker("proof5-fail", failArgs);
        int ef = failing.waitFor(300);
        String[] v = find(stageLines(failing), "orders", "validate");
        r.note("worker with --fault.fail-validation=orders: exit " + ef + "; " + (v == null ? "no validate line" : v[0]));
        Proc early = worker("proof5-early", withStages(args, "publish"));
        early.waitFor(300);
        String[] gated = find(stageLines(early), "orders", "publish");
        r.note("publish fired on its own: " + (gated == null ? "no publish line" : gated[0]));
        r.check(gated != null && gated[3].equals("GATE_CLOSED") && gated[7] != null
                        && gated[7].contains("inputs not ready: [orders.raw=FAILED"),
                "the worker's publish gate is shut by the failed input");
        Proc retry = worker("proof5-retry", args);
        int er = retry.waitFor(300);
        r.rows("the re-run (exit " + er + "):", stageLines(retry).stream().map(l -> l[0]).toList());
        r.rows("readiness_attempts for orders.raw:", rows("SELECT run_id || '  ' || state || '  retry_of=' "
                + "|| coalesce(retry_of, '-') FROM job_control.readiness_attempts WHERE period = ? "
                + "AND input = 'orders.raw' ORDER BY seq", p));
        r.check(er == 0 && has(stageLines(retry), "orders", "publish", "DONE")
                        && rows("SELECT count(*) FROM job_control.readiness_attempts WHERE period = ? "
                        + "AND input = 'orders.raw' AND retry_of IS NOT NULL", p).equals(List.of("1")),
                "the re-run re-validates as a declared retry, and publish runs");
    }

    private void parity(Result r, String step, List<String> java, String unit, String p) {
        String python = opts.getOrDefault("python", pythonNextToAirflow());
        if (python == null) {
            r.note(step + ": Java " + java + "; the DAG's Python not checked");
            r.notRun = "the Java side passed, but the Python parity check needs --python or --airflow";
            return;
        }
        Proc py = Proc.start("python-not-ready", List.of(python, "-c",
                "import sys\nimport reference_e2e_control_plane_stores as s\n"
                        + "for item in s.input_readiness().not_ready(unit=sys.argv[1], period=sys.argv[2]):\n"
                        + "    print('NOT_READY_ITEM=' + item)\n"
                        + "print('NOT_READY_END')",
                unit, p), pythonEnv(), null);
        int exit = py.waitFor(120);
        List<String> items = new ArrayList<>();
        boolean ended = false;
        for (String line : py.lines()) {
            if (line.startsWith("NOT_READY_ITEM=")) {
                items.add(line.substring("NOT_READY_ITEM=".length()));
            } else if (line.equals("NOT_READY_END")) {
                ended = true;
            }
        }
        List<String> parsed = ended ? items : null;
        r.note(step + ": Java " + java + ", the DAG's Python " + (parsed == null ? "error:\n" + py.out() : parsed));
        r.check(exit == 0 && java.equals(parsed), "Java and the DAG's Python agree (" + step + ")");
    }

    // ------------------------------------------------------------------ 6

    private void maxConcurrencyInAirflow(Result r) {
        if (!airflowConfigured(r)) {
            return;
        }
        String p = period(6);
        // The stages' own gates must be open, so every task can run: the workers complete them first.
        Proc pre = worker("proof6-pre", workerArgs(p, "orders,customers,products", 3, 5, 0));
        r.note("workers complete every stage for " + p + " first, so the DAG's gates are open: exit " + pre.waitFor(300));
        airflowSetup(r);
        AirflowState state = airflowState();
        // On Composer the environment's own scheduler runs the DAG, and the task length is the
        // environment's CULVERT_PROOF_TASK_SECONDS (set by the Terraform, #234).
        Proc started = runner().startScheduler(Map.of("CULVERT_PROOF_TASK_SECONDS", opts.getOrDefault("task-seconds", "2")));
        Proc scheduler = started == null ? null : track(started);
        // If the harness itself is stopped, take the scheduler and its executors down with it.
        Thread reaper = scheduler == null ? null : new Thread(scheduler::destroyTree, "airflow-scheduler-reaper");
        if (reaper != null) {
            Runtime.getRuntime().addShutdownHook(reaper);
        }
        r.note("the DAG's task instances are read from " + state.describe());
        String runId = "proof6-" + p + "-" + System.currentTimeMillis();
        int max = 0;
        Map<Integer, Integer> histogram = new TreeMap<>();
        List<String> timeline = new ArrayList<>();
        String runState = null;
        try {
            Proc unpause = runner().run("proof6-unpause", "dags", "unpause", ReferenceDag.DAG_ID);
            int unpaused = unpause.waitFor(600);
            r.note("airflow dags unpause -> exit " + unpaused);
            Boolean paused = state.paused(ReferenceDag.DAG_ID);
            if (!r.check(Boolean.FALSE.equals(paused), "the DAG is registered and unpaused: is_paused=" + paused)) {
                r.rows("airflow said:", grep(unpause, ""));
                return;
            }
            Proc trigger = runner().run("proof6-trigger", "dags", "trigger", ReferenceDag.DAG_ID, "-e", p + "T00:00:00+00:00", "-r", runId);
            int triggered = trigger.waitFor(600);
            r.note("airflow dags trigger -e " + p + " -r " + runId + " -> exit " + triggered);
            if (!r.check(state.runState(ReferenceDag.DAG_ID, runId) != null, "the DAG run was created")) {
                r.rows("airflow said:", grep(trigger, ""));
                return;
            }
            long deadline = System.nanoTime() + Long.parseLong(opts.getOrDefault("airflow-run-seconds", "300")) * 1_000_000_000L;
            String last = "";
            while (System.nanoTime() < deadline) {
                // The cap is per DAG, across all of its runs: count every run's queued and running tasks.
                List<String> active = state.active(ReferenceDag.DAG_ID);
                max = Math.max(max, active.size());
                histogram.merge(active.size(), 1, Integer::sum);
                String now = active.toString();
                if (!now.equals(last)) {
                    timeline.add(active.size() + "  " + now);
                    last = now;
                }
                runState = state.runState(ReferenceDag.DAG_ID, runId);
                if ("success".equals(runState) || "failed".equals(runState)) {
                    break;
                }
                Proc.sleep(200);
            }
        } finally {
            runner().run("proof6-pause", "dags", "pause", ReferenceDag.DAG_ID).waitFor(600);
            if (scheduler != null) {
                scheduler.destroyTree();
                Runtime.getRuntime().removeShutdownHook(reaper);
            }
        }
        r.rows("each change in the DAG's queued and running task instances (count  tasks):", timeline);
        r.note("samples by count of queued+running tasks: " + histogram);
        r.rows("task_instance states for " + runId + ":", state.taskStates(ReferenceDag.DAG_ID, runId));
        r.check("success".equals(runState), "the triggered run finished: " + runState);
        r.check(max <= 2, "never more than 2 of the DAG's tasks queued or running at once (max " + max + ")");
        r.check(max == 2, "the cap was reached: 2 tasks did run at once, so the limit was what held them");
    }

    // ------------------------------------------------------------------ 7

    private void culvertCli(Result r) {
        String p = period(7);
        Proc ok = worker("proof7-ok", workerArgs(p, "orders", 1, 5, 0));
        int eo = ok.waitFor(300);
        List<String> failArgs = new ArrayList<>(workerArgs(p, "customers", 1, 5, 0));
        failArgs.add("--fault.fail-validation=customers");
        int ef = worker("proof7-failed", failArgs).waitFor(300);
        List<String> killArgs = new ArrayList<>(workerArgs(p, "products", 1, 5, 0));
        killArgs.add("--fault.kill-after=2");
        int ek = worker("proof7-killed", killArgs).waitFor(300);
        r.note("workers: orders exit " + eo + ", customers (fail validation) exit " + ef + ", products (killed) exit " + ek);
        List<String> ledger = runStates(p);
        r.rows("job_control.pipeline_jobs, read directly:", ledger);
        String succeeded = runOf(p, "orders");
        String failed = runOf(p, "customers");
        String running = runOf(p, "products");

        Proc runs = cli("runs");
        int e1 = runs.waitFor(120);
        r.rows("culvert runs  (exit " + e1 + ")", grep(runs, ""));
        r.check(e1 == 0 && running != null && runs.out().contains(running + " running"),
                "culvert runs lists the killed run, still running: " + running);
        Proc one = cli("run", String.valueOf(succeeded));
        int e2 = one.waitFor(120);
        r.rows("culvert run " + succeeded + "  (exit " + e2 + ")", grep(one, ""));
        r.check(e2 == 0 && one.out().contains("status: succeeded") && one.out().contains("records: 15"),
                "culvert run shows the orders run succeeded with its 15 records");
        Proc failures = cli("failures", "--system", ControlPlaneRun.SYSTEM_ID, "--date", p);
        int e3 = failures.waitFor(120);
        r.rows("culvert failures --system " + ControlPlaneRun.SYSTEM_ID + " --date " + p + "  (exit " + e3 + ")",
                grep(failures, ""));
        r.check(e3 == 0 && failed != null && failures.out().contains(failed) && failures.out().contains("validation"),
                "culvert failures shows the customers run, failed at validation: " + failed);
    }

    private String runOf(String p, String unit) {
        List<String> ids = rows("SELECT DISTINCT run_id FROM job_control.pipeline_jobs WHERE extract_date = ?::date "
                + "AND entity_type = ?", p, unit);
        return ids.size() == 1 ? ids.get(0) : null;
    }

    // ------------------------------------------------------------------ workers, Airflow, CLI

    private List<String> workerArgs(String period, String units, int maxConcurrency, int records, int delayMs) {
        return new ArrayList<>(List.of("--period=" + period, "--units=" + units, "--max-concurrency=" + maxConcurrency,
                "--records=" + records, "--record-delay-ms=" + delayMs));
    }

    private static List<String> withStages(List<String> args, String stages) {
        List<String> out = new ArrayList<>(args);
        out.add("--stages=" + stages);
        return out;
    }

    private Proc worker(String claimant, List<String> args) {
        List<String> command = new ArrayList<>(javaCommand(ControlPlaneMain.class.getName()));
        command.addAll(args);
        command.add("--claimant=" + claimant);
        return track(Proc.start(claimant, command, workerEnv(claimant), null));
    }

    /** Every process the harness started; a shutdown hook kills any still alive (a hung worker never exits). */
    private final List<Proc> started = java.util.Collections.synchronizedList(new ArrayList<>());

    private Proc track(Proc p) {
        if (started.isEmpty()) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                synchronized (started) {
                    started.stream().filter(Proc::alive).forEach(Proc::destroyTree);
                }
            }, "proof-process-reaper"));
        }
        started.add(p);
        return p;
    }

    private Proc cli(String... args) {
        List<String> command = new ArrayList<>(javaCommand("com.enrichmeai.culvert.console.CulvertCli"));
        command.addAll(List.of(args));
        return Proc.start("culvert", command, workerEnv("proof-culvert-cli"), null);
    }

    private List<String> javaCommand(String mainClass) {
        return List.of(ProcessHandle.current().info().command().orElse("java"), "-cp", classpath,
                "-Dorg.slf4j.simpleLogger.defaultLogLevel=error", mainClass);
    }

    private Map<String, String> workerEnv(String applicationName) {
        Map<String, String> env = new HashMap<>();
        // The application name tags the worker's sessions in pg_stat_activity (scenario 3).
        env.put("CULVERT_POSTGRES_URL", jdbcUrl + (jdbcUrl.contains("?") ? "&" : "?") + "ApplicationName=" + applicationName);
        env.put("CULVERT_POSTGRES_USER", user);
        if (password != null) {
            env.put("CULVERT_POSTGRES_PASSWORD", password);
        }
        env.put("CULVERT_JOBCONTROLREPOSITORY_PROVIDER", "PostgresJobControlRepository");
        env.put("JAVA_TOOL_OPTIONS", "");
        return env;
    }

    private boolean airflowConfigured(Result r) {
        if (opts.get("airflow") == null && opts.get("composer-env") == null) {
            r.notRun = "no --airflow (a local Airflow 2.9.3) or --composer-env (a Cloud Composer environment) to run it";
            return false;
        }
        return true;
    }

    private AirflowRunner runner;
    private AirflowState airflowState;

    /** A local Airflow (--airflow), or a Cloud Composer environment (--composer-env, #234). */
    private AirflowRunner runner() {
        if (runner == null) {
            if (opts.get("composer-env") != null) {
                String location = required("composer-location", "the Composer environment's region");
                runner = new AirflowRunner.Composer(opts.getOrDefault("gcloud", "gcloud"), opts.get("composer-env"),
                        location, List.of(storesFile(), stagedDag()), ReferenceDag.DAG_ID, airflowState(),
                        Long.parseLong(opts.getOrDefault("composer-register-seconds", "600")), 5_000);
            } else {
                runner = new AirflowRunner.Local(opts.get("airflow"), this::airflowEnv, workdir, dagFile(),
                        ReferenceDag.DAG_ID, Boolean.parseBoolean(opts.getOrDefault("reset", "false")));
            }
        }
        return runner;
    }

    /**
     * Airflow's state: its REST API when --airflow-api is given (always on Composer, whose metadata
     * database is not reachable), else its metadata database.
     */
    private AirflowState airflowState() {
        if (airflowState == null) {
            String api = opts.get("airflow-api");
            if (api != null) {
                java.util.function.Supplier<String> auth = opts.get("airflow-api-user") != null
                        ? AirflowState.Rest.basic(opts.get("airflow-api-user"), opts.getOrDefault("airflow-api-password", ""))
                        : AirflowState.Rest.bearerFrom(List.of(opts.getOrDefault("airflow-token-command",
                                opts.getOrDefault("gcloud", "gcloud") + " auth print-access-token").split(" ")));
                airflowState = new AirflowState.Rest(api, auth);
            } else if (opts.get("composer-env") != null) {
                throw new IllegalArgumentException("--composer-env needs --airflow-api: the environment's airflow_uri "
                        + "(Composer's metadata database is not reachable)");
            } else {
                String jdbc = opts.getOrDefault("airflow-db-jdbc", "jdbc:postgresql://localhost:55432/airflow");
                airflowState = new AirflowState.Jdbc(jdbc, () -> {
                    try {
                        return dataSource(jdbc).getConnection();
                    } catch (SQLException e) {
                        throw new IllegalStateException(jdbc + ": " + e.getMessage(), e);
                    }
                });
            }
        }
        return airflowState;
    }

    private String required(String option, String what) {
        String value = opts.get(option);
        if (value == null) {
            throw new IllegalArgumentException("--" + option + " is required: " + what);
        }
        return value;
    }

    private Path dagFile() {
        return Path.of(opts.getOrDefault("dag", "dags/" + ReferenceDag.DAG_ID + ".py"));
    }

    /**
     * The DAG under its own name, {@code <dag_id>.py}: an upload keeps the file's name, so a
     * {@code --dag=} copy (the red runs) must replace the DAG, not land beside it as a second file
     * declaring the same dag_id.
     */
    private Path stagedDag() {
        Path staged = workdir.resolve("composer-upload").resolve(ReferenceDag.DAG_ID + ".py");
        try {
            Files.createDirectories(staged.getParent());
            Files.copy(dagFile(), staged, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return staged;
    }

    private Path storesFile() {
        return Path.of(opts.getOrDefault("stores-dir", "proof/airflow"), "reference_e2e_control_plane_stores.py");
    }

    private String pythonNextToAirflow() {
        String airflow = opts.get("airflow");
        if (airflow == null) {
            return null;
        }
        File python = new File(new File(airflow).getParentFile(), "python");
        return python.canExecute() ? python.getPath() : null;
    }

    private Map<String, String> pythonEnv() {
        Map<String, String> env = new HashMap<>();
        env.put("PYTHONPATH", Path.of(opts.getOrDefault("stores-dir", "proof/airflow")).toAbsolutePath().toString());
        env.put("CULVERT_POSTGRES_DSN", opts.getOrDefault("dsn", dsnFromJdbc()));
        return env;
    }

    private Map<String, String> airflowEnv() {
        Map<String, String> env = pythonEnv();
        Path home = workdir.resolve("airflow");
        env.put("AIRFLOW_HOME", home.toString());
        env.put("AIRFLOW__CORE__DAGS_FOLDER", home.resolve("dags").toString());
        env.put("AIRFLOW__CORE__LOAD_EXAMPLES", "False");
        env.put("AIRFLOW__CORE__EXECUTOR", opts.getOrDefault("airflow-executor", "LocalExecutor"));
        env.put("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
                opts.getOrDefault("airflow-db", "postgresql+psycopg2://postgres@localhost:55432/airflow"));
        env.put("AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL", "5");
        env.put("AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION", "False");
        return env;
    }

    private boolean airflowReady;

    private void airflowSetup(Result r) {
        if (airflowReady) {
            return;
        }
        r.note("Airflow: " + runner().describe());
        runner().setup();
        airflowReady = true;
    }

    private String dsnFromJdbc() {
        Matcher m = Pattern.compile("^jdbc:postgresql://([^:/?]+)(?::(\\d+))?/([^?]+).*$").matcher(jdbcUrl);
        if (!m.matches()) {
            throw new IllegalArgumentException("cannot derive a libpq DSN from " + jdbcUrl + "; pass --dsn");
        }
        return "host=" + m.group(1) + " port=" + (m.group(2) == null ? "5432" : m.group(2)) + " dbname=" + m.group(3)
                + " user=" + user + (password == null ? "" : " password=" + password);
    }

    // ------------------------------------------------------------------ evidence helpers

    /** Each stage line of a worker: [line, unit, stage, outcome, claimant, run, records, detail]. */
    static List<String[]> stageLines(Proc p) {
        List<String[]> out = new ArrayList<>();
        for (String line : p.lines()) {
            Matcher m = STAGE_LINE.matcher(line);
            if (m.matches()) {
                out.add(new String[]{line, m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), m.group(7)});
            }
        }
        return out;
    }

    static String[] find(List<String[]> lines, String unit, String stage) {
        return lines.stream().filter(l -> l[1].equals(unit) && l[2].equals(stage)).findFirst().orElse(null);
    }

    static boolean has(List<String[]> lines, String unit, String stage, String outcome) {
        String[] l = find(lines, unit, stage);
        return l != null && l[3].equals(outcome);
    }

    static List<String> grep(Proc p, String text) {
        return p.lines().stream().filter(l -> l.contains(text)).filter(l -> !l.isBlank())
                .map(l -> l.length() > 220 ? l.substring(0, 220) + "..." : l).collect(Collectors.toList());
    }

    private List<String> completions(String p) {
        return rows("SELECT unit || '/' || stage || '  completed_by=' || completed_by "
                + "FROM job_control.stage_completions WHERE period = ? ORDER BY 1", p);
    }

    private List<String> runStates(String p) {
        return rows("SELECT DISTINCT ON (run_id) run_id || '  ' || entity_type || '  ' || status || "
                + "coalesce('  ' || error_code, '') FROM job_control.pipeline_jobs WHERE extract_date = ?::date "
                + "ORDER BY run_id, seq DESC", p);
    }

    private List<String> sessions(String applicationName) {
        return rows("SELECT application_name || '  pid=' || pid || '  state=' || coalesce(state, '-') "
                + "FROM pg_stat_activity WHERE application_name = ?", applicationName);
    }

    static long parseSeconds(String setting) {
        Matcher m = Pattern.compile("^(\\d+)(ms|s|min)?$").matcher(setting.trim());
        if (!m.matches()) {
            return 0;
        }
        long n = Long.parseLong(m.group(1));
        return switch (m.group(2) == null ? "ms" : m.group(2)) {
            case "s" -> n;
            case "min" -> n * 60;
            default -> n / 1000;
        };
    }

    private PGSimpleDataSource dataSource() {
        return dataSource(jdbcUrl);
    }

    private PGSimpleDataSource dataSource(String url) {
        PGSimpleDataSource ds = new PGSimpleDataSource();
        ds.setURL(url);
        ds.setUser(user);
        if (password != null) {
            ds.setPassword(password);
        }
        return ds;
    }

    private void exec(String sql) {
        try (Connection c = dataSource().getConnection(); Statement s = c.createStatement()) {
            s.execute(sql);
        } catch (SQLException e) {
            throw new IllegalStateException(sql + ": " + e.getMessage(), e);
        }
    }

    private List<String> rows(String sql, Object... params) {
        return rowsAt(jdbcUrl, sql, params);
    }

    private List<String> rowsAt(String url, String sql, Object... params) {
        try (Connection c = dataSource(url).getConnection(); PreparedStatement ps = c.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                if (params[i] instanceof String[] array) {
                    ps.setArray(i + 1, c.createArrayOf("text", array));
                } else {
                    ps.setObject(i + 1, params[i]);
                }
            }
            List<String> out = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    out.add(rs.getString(1));
                }
            }
            return out;
        } catch (SQLException e) {
            throw new IllegalStateException(sql + ": " + e.getMessage(), e);
        }
    }
}
