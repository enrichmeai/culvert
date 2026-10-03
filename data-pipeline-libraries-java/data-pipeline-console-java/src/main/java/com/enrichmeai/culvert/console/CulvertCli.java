package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.autoconfig.DiscoveryFailure;

import java.io.PrintStream;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Supplier;

/**
 * The {@code culvert} command line: read-only questions about pipeline runs, answered through
 * the contracts, on whichever backend is installed.
 *
 * <pre>
 * culvert runs                                          active runs (created or running)
 * culvert run &lt;runId&gt;                                   one run
 * culvert entities --system &lt;id&gt; --date &lt;YYYY-MM-DD&gt;   each entity's latest status
 * culvert failures --system &lt;id&gt; --date &lt;YYYY-MM-DD&gt;   the failed runs
 * culvert adapters                                      what AutoConfig bound, and what failed to load
 * </pre>
 *
 * <p>Exit codes: 0 done (an empty list is still 0); 1 the run was not found, no
 * {@code JobControlRepository} is installed, the backend failed, or {@code adapters} found providers
 * that failed to load; 2 usage error. {@code --help} prints the usage and exits 0.
 */
public final class CulvertCli {

    static final String USAGE = String.join(System.lineSeparator(),
            "Usage: culvert <command>",
            "  runs                                          active runs (created or running)",
            "  run <runId>                                   one run",
            "  entities --system <id> --date <YYYY-MM-DD>    each entity's latest status",
            "  failures --system <id> --date <YYYY-MM-DD>    the failed runs",
            "  adapters                                      bound adapters, unbound contracts, load failures",
            "Exit codes: 0 done, 1 run not found / no backend / backend error / adapters failed to load, 2 usage.");

    static final String COST_NOTE = "Note: this reads the whole job-control table on every backend"
            + " (BigQuery and Athena rank it, DynamoDB scans it). Run it on demand, not in a loop.";

    private final AutoConfig autoConfig;
    private final Supplier<ConsoleReadService> console;

    /**
     * @param autoConfig what {@code culvert adapters} reports on
     * @param console    the read service; asked for only by the commands that read runs
     */
    public CulvertCli(AutoConfig autoConfig, Supplier<ConsoleReadService> console) {
        this.autoConfig = Objects.requireNonNull(autoConfig, "autoConfig");
        this.console = Objects.requireNonNull(console, "console");
    }

    public static void main(String[] args) {
        AutoConfig autoConfig = AutoConfig.discover();
        int code = new CulvertCli(autoConfig, () -> ConsoleReadService.from(autoConfig))
                .run(args, System.out, System.err);
        System.exit(code);
    }

    /** Run one command. Returns the exit code. */
    public int run(String[] args, PrintStream out, PrintStream err) {
        if (args == null || args.length == 0) {
            return usage(err, "no command given");
        }
        if (args[0].equals("--help") || args[0].equals("-h") || args[0].equals("help")) {
            out.println(USAGE);
            return 0;
        }
        try {
            switch (args[0]) {
                case "runs":
                    return args.length == 1 ? runs(out, err) : usage(err, "runs takes no arguments");
                case "run":
                    return args.length == 2 ? run(args[1], out, err) : usage(err, "run takes one run id");
                case "entities":
                case "failures":
                    return bySystemAndDate(args, out, err);
                case "adapters":
                    return args.length == 1 ? adapters(out) : usage(err, "adapters takes no arguments");
                default:
                    return usage(err, "unknown command: " + args[0]);
            }
        } catch (NoBackendException e) {
            err.println(e.getMessage());
            return 1;
        } catch (RuntimeException e) {
            // A backend or discovery failure: name it, so it is not mistaken for an empty answer.
            err.println("culvert " + args[0] + " failed: " + e.getClass().getName() + ": " + e.getMessage());
            return 1;
        }
    }

    private int runs(PrintStream out, PrintStream err) {
        ConsoleReadService service = service();
        err.println(COST_NOTE);
        List<RunView> runs = service.pendingRuns(Optional.empty());
        out.println("Active runs (created or running) only, not the run history: " + runs.size());
        runs.forEach(r -> out.println("  " + r.summary()));
        return 0;
    }

    private int run(String runId, PrintStream out, PrintStream err) {
        Optional<RunView> found = service().run(runId);
        if (found.isEmpty()) {
            err.println("No run with id " + runId);
            return 1;
        }
        RunView r = found.get();
        out.println(r.summary());
        out.println("  status: " + r.status().getValue() + (r.terminal() ? " (final)" : ""));
        out.println("  system: " + r.systemId() + ", pipeline: " + r.pipelineName()
                + ", extract date: " + r.extractDate() + ", type: " + r.jobType());
        r.entityType().ifPresent(v -> out.println("  entity: " + v));
        r.sourceFile().ifPresent(v -> out.println("  source: " + v));
        r.targetTable().ifPresent(v -> out.println("  target: " + v));
        out.println("  records: " + r.recordCount() + ", errors: " + r.errorCount()
                + ", retries attempted: " + r.retryCount());
        r.failureStage().ifPresent(v -> out.println("  failure stage: " + v.getValue()));
        r.errorCode().ifPresent(v -> out.println("  error code: " + v));
        r.errorMessage().ifPresent(v -> out.println("  error: " + v));
        r.errorFilePath().ifPresent(v -> out.println("  quarantined records: " + v));
        out.println("  created: " + r.createdAt() + ", updated: " + r.updatedAt());
        r.startedAt().ifPresent(v -> out.println("  started: " + v));
        r.completedAt().ifPresent(v -> out.println("  completed: " + v));
        return 0;
    }

    private int bySystemAndDate(String[] args, PrintStream out, PrintStream err) {
        Map<String, String> flags = new LinkedHashMap<>();
        for (int i = 1; i < args.length; i += 2) {
            String flag = args[i];
            if (!(flag.equals("--system") || flag.equals("--date"))) {
                return usage(err, args[0] + " takes --system <id> --date <YYYY-MM-DD>, not " + flag);
            }
            if (i + 1 >= args.length || args[i + 1].isBlank() || args[i + 1].startsWith("--")) {
                return usage(err, flag + " needs a value");
            }
            if (flags.put(flag, args[i + 1]) != null) {
                return usage(err, flag + " is given twice");
            }
        }
        if (!flags.containsKey("--system") || !flags.containsKey("--date")) {
            return usage(err, args[0] + " needs both --system and --date");
        }
        LocalDate date;
        try {
            date = LocalDate.parse(flags.get("--date"));
        } catch (DateTimeParseException e) {
            return usage(err, "--date must be YYYY-MM-DD, not " + flags.get("--date"));
        }
        String system = flags.get("--system");
        ConsoleReadService service = service();
        err.println(COST_NOTE);
        if (args[0].equals("entities")) {
            List<EntityStatusView> rows = service.entityStatus(system, date);
            out.println("Entities for " + system + " on " + date + ": " + rows.size());
            rows.forEach(e -> out.println("  " + e.entityType() + "  " + e.status() + "  run " + e.runId()
                    + "  records " + e.recordCount() + "  errors " + e.errorCount()
                    + e.completedAt().map(t -> "  completed " + t).orElse("")));
        } else {
            List<FailureView> rows = service.failures(system, date);
            out.println("Failed runs for " + system + " on " + date + ": " + rows.size()
                    + ". A failed run stays failed; a retry runs under a new run id.");
            rows.forEach(f -> out.println("  " + f.runId() + "  " + f.entityType() + "  at " + f.failureStage()
                    + "  " + f.errorCode() + ": " + f.errorMessage() + "  failed " + f.failedAt()
                    + "  retries attempted " + f.retryCount()
                    + f.errorFilePath().map(p -> "  quarantined " + p).orElse("")));
        }
        return 0;
    }

    private int adapters(PrintStream out) {
        Map<String, List<?>> bindings = new LinkedHashMap<>();
        bindings.put("BlobStore", autoConfig.blobStores());
        bindings.put("Warehouse", autoConfig.warehouses());
        bindings.put("JobControlRepository", autoConfig.jobControls());
        bindings.put("SecretProvider", autoConfig.secretProviders());
        bindings.put("FinOpsSink", autoConfig.finOpsSinks());
        bindings.put("AuditEventPublisher", autoConfig.auditEventPublishers());
        bindings.put("LineageEmitter", autoConfig.lineageEmitters());
        bindings.put("ObservabilityHook", autoConfig.observabilityHooks());
        bindings.put("StageMetricsHook", autoConfig.stageMetricsHooks());
        bindings.put("GovernancePolicy", autoConfig.governancePolicies());
        bindings.put("Pipeline", autoConfig.pipelines());
        bindings.put("PipelineStage", autoConfig.stages());
        bindings.put("RuntimeContext", autoConfig.runtimeContexts());
        bindings.put("Source", autoConfig.sources());
        bindings.put("Sink", autoConfig.sinks());
        bindings.put("Transform", autoConfig.transforms());

        out.println("Contracts and the adapters bound to them:");
        bindings.forEach((contract, impls) -> out.println("  " + contract + ": " + (impls.isEmpty()
                ? "(unbound)"
                : String.join(", ", impls.stream().map(i -> i.getClass().getName()).toList()))));

        List<DiscoveryFailure> failures = autoConfig.failures();
        if (failures.isEmpty()) {
            out.println("Discovery failures: none");
        } else {
            out.println("Discovery failures: " + failures.size()
                    + " (registered providers that could not be loaded)");
            failures.forEach(f -> out.println("  " + f.contract().getSimpleName() + ": " + f.providerClass()
                    + ": " + f.cause()));
        }
        return failures.isEmpty() ? 0 : 1;
    }

    private ConsoleReadService service() {
        try {
            return console.get();
        } catch (IllegalStateException e) {
            throw new NoBackendException(e.getMessage());
        }
    }

    /** No usable {@code JobControlRepository}: none installed, or the selector matched none. */
    private static final class NoBackendException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        NoBackendException(String message) {
            super(message);
        }
    }

    private static int usage(PrintStream err, String problem) {
        err.println(problem);
        err.println(USAGE);
        return 2;
    }
}
