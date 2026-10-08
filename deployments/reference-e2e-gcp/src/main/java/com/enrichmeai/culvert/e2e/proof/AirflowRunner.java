package com.enrichmeai.culvert.e2e.proof;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * How the harness runs Airflow commands for scenarios 4 and 6 (#232, #234).
 *
 * <ul>
 *   <li>{@link Local}: an {@code airflow} install on the harness's host, with its own metadata
 *       database; the harness starts the scheduler.</li>
 *   <li>{@link Composer}: a Cloud Composer 2 environment. Commands go through
 *       {@code gcloud composer environments run}, the DAG and its stores module are uploaded with
 *       {@code gcloud composer environments storage dags import}, and the environment runs its own
 *       scheduler.</li>
 * </ul>
 */
interface AirflowRunner {

    /** Where the commands run, for the evidence. */
    String describe();

    /**
     * Put the DAG and its stores module where Airflow loads them, and wait until Airflow runs that
     * DAG file.
     */
    void setup();

    /**
     * Run an {@code airflow} command, for example {@code ("tasks", "test", dag, task, date)}. The
     * first two words are the command group and the command.
     */
    Proc run(String label, String... args);

    /**
     * Whether {@link #run}'s exit code is the Airflow command's own. When false, the scenarios judge
     * by Airflow's output lines alone.
     */
    boolean exitCodeIsTheCommands();

    /** Start a scheduler the harness owns, or return null when the environment runs its own. */
    Proc startScheduler(Map<String, String> extraEnv);

    // ------------------------------------------------------------------ local

    final class Local implements AirflowRunner {
        private final String airflow;
        private final Supplier<Map<String, String>> env;
        private final Path workdir;
        private final Path dag;
        private final String dagId;
        private final boolean reset;

        Local(String airflow, Supplier<Map<String, String>> env, Path workdir, Path dag, String dagId, boolean reset) {
            this.airflow = airflow;
            this.env = env;
            this.workdir = workdir;
            this.dag = dag;
            this.dagId = dagId;
            this.reset = reset;
        }

        @Override
        public String describe() {
            return "local Airflow, " + airflow;
        }

        @Override
        public void setup() {
            Path dags = workdir.resolve("airflow").resolve("dags");
            try {
                Files.createDirectories(dags);
                Files.copy(dag, dags.resolve(dagId + ".py"), StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
            // --reset empties Airflow's metadata database too: it allows one DAG run per logical date.
            Proc migrate = reset ? run("airflow-db-reset", "db", "reset", "--yes") : run("airflow-db-migrate", "db", "migrate");
            if (migrate.waitFor(600) != 0) {
                throw new IllegalStateException("airflow db " + (reset ? "reset" : "migrate") + " failed:\n" + migrate.out());
            }
            // Register the DAG now, so unpausing it later finds it rather than racing the scheduler's parse.
            Proc reserialize = run("airflow-dags-reserialize", "dags", "reserialize");
            if (reserialize.waitFor(300) != 0) {
                throw new IllegalStateException("airflow dags reserialize failed:\n" + reserialize.out());
            }
            Proc list = run("airflow-dags-list", "dags", "list-import-errors");
            list.waitFor(300);
            if (!list.out().contains("No data found")) {
                throw new IllegalStateException("the DAG does not import:\n" + list.out());
            }
        }

        @Override
        public Proc run(String label, String... args) {
            List<String> command = new ArrayList<>();
            command.add(airflow);
            command.addAll(List.of(args));
            return Proc.start(label, command, env.get(), workdir.toFile());
        }

        @Override
        public boolean exitCodeIsTheCommands() {
            return true;
        }

        @Override
        public Proc startScheduler(Map<String, String> extraEnv) {
            Map<String, String> e = env.get();
            e.putAll(extraEnv);
            return Proc.start("airflow-scheduler", List.of(airflow, "scheduler"), e, workdir.toFile());
        }
    }

    // ------------------------------------------------------------------ Cloud Composer

    final class Composer implements AirflowRunner {
        private final String gcloud;
        private final String environment;
        private final String location;
        private final List<Path> uploads;
        private final String dagId;
        private final AirflowState state;
        private final long registerSeconds;
        private final long pollMillis;

        /**
         * @param uploads the files for the environment's DAG folder, in upload order, the DAG last:
         *     the stores module first, so the scheduler never parses a DAG whose import is not there
         *     yet. Airflow puts the DAG folder on {@code sys.path}, so the DAG imports the stores
         *     module from there.
         * @param registerSeconds how long to wait for the scheduler to parse the uploaded DAG
         * @param pollMillis how often to look meanwhile
         */
        Composer(String gcloud, String environment, String location, List<Path> uploads, String dagId,
                 AirflowState state, long registerSeconds, long pollMillis) {
            this.gcloud = gcloud;
            this.environment = environment;
            this.location = location;
            this.uploads = uploads;
            this.dagId = dagId;
            this.state = state;
            this.registerSeconds = registerSeconds;
            this.pollMillis = pollMillis;
        }

        @Override
        public String describe() {
            return "Cloud Composer environment " + environment + " (" + location + "), through " + gcloud;
        }

        @Override
        public void setup() {
            for (Path file : uploads) {
                Proc upload = gcloud("composer-dags-import", List.of("composer", "environments", "storage", "dags",
                        "import", "--environment=" + environment, "--location=" + location, "--source=" + file));
                if (upload.waitFor(300) != 0) {
                    throw new IllegalStateException("uploading " + file + " failed:\n" + upload.out());
                }
            }
            // Registered is not enough: after a re-upload (a red run's broken DAG, or the real one
            // after it) the previous version stays registered until the scheduler re-parses. Wait
            // until the source Airflow parsed is the file just uploaded.
            String uploaded = read(uploads.get(uploads.size() - 1));
            long deadline = System.nanoTime() + registerSeconds * 1_000_000_000L;
            String lastError = null;
            while (true) {
                String parsed = null;
                try {
                    parsed = state.source(dagId);
                    lastError = null;
                } catch (IllegalStateException e) {
                    // A web server restarting after an upload answers 5xx for a while: keep waiting.
                    lastError = e.getMessage();
                }
                if (parsed != null && parsed.strip().equals(uploaded.strip())) {
                    break;
                }
                // Import errors are reported with the timeout, not at once: one recorded before the
                // upload stays listed until the re-parse clears it.
                if (System.nanoTime() > deadline) {
                    String why = lastError != null ? "; the last call failed: " + lastError
                            : parsed == null ? "; it is not registered" : "; it still runs an earlier version";
                    List<String> errors = lastError != null ? List.of() : state.importErrors(dagId);
                    throw new IllegalStateException(dagId + ": Airflow did not parse the uploaded file within "
                            + registerSeconds + "s (" + state.describe() + ")" + why
                            + (errors.isEmpty() ? "" : ". Import errors:\n" + String.join("\n", errors)));
                }
                Proc.sleep(pollMillis);
            }
        }

        @Override
        public Proc run(String label, String... args) {
            if (args.length < 2) {
                throw new IllegalArgumentException("an airflow command needs a group and a command: " + List.of(args));
            }
            // gcloud composer environments run ENV --location=LOC GROUP COMMAND -- ARGS...
            List<String> command = new ArrayList<>(List.of("composer", "environments", "run", environment,
                    "--location=" + location, args[0], args[1]));
            if (args.length > 2) {
                command.add("--");
                command.addAll(List.of(args).subList(2, args.length));
            }
            return gcloud(label, command);
        }

        @Override
        public boolean exitCodeIsTheCommands() {
            // gcloud's exit code is not relied on to carry the Airflow command's: judge by its output.
            return false;
        }

        @Override
        public Proc startScheduler(Map<String, String> extraEnv) {
            return null;
        }

        private static String read(Path file) {
            try {
                return Files.readString(file);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }

        private Proc gcloud(String label, List<String> args) {
            List<String> command = new ArrayList<>();
            command.add(gcloud);
            command.addAll(args);
            return Proc.start(label, command, Map.of(), null);
        }
    }
}
