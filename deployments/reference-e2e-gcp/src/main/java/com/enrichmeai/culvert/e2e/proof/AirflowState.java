package com.enrichmeai.culvert.e2e.proof;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.function.Supplier;

/**
 * What the harness reads from Airflow for scenarios 4 and 6 (#232, #234): whether the DAG is
 * registered and paused, its queued and running task instances, and a run's states.
 *
 * <p>Two readers, the same answers:
 * <ul>
 *   <li>{@link Jdbc}: Airflow's metadata database, read directly. The local default.</li>
 *   <li>{@link Rest}: Airflow's stable REST API ({@code /api/v1}, Airflow 2.9.3). On Cloud Composer
 *       the metadata database is not reachable, so this is the reader there (#234). It also runs
 *       against a local Airflow, which is how it is tested.</li>
 * </ul>
 */
interface AirflowState {

    /** Where it reads from, for the evidence. */
    String describe();

    /**
     * The source of the file Airflow last parsed the DAG from, or null if the DAG is not registered.
     * Comparing it with an uploaded file shows that Airflow runs that file, not an earlier one.
     */
    String source(String dagId);

    /** The DAG's import errors, empty when it imports. */
    List<String> importErrors(String dagId);

    /** Whether the DAG is paused; null if it is not registered. */
    Boolean paused(String dagId);

    /** {@code task@run:state} for every queued or running task instance of the DAG, across all its runs. */
    List<String> active(String dagId);

    /** The run's state, or null if there is no such run. */
    String runState(String dagId, String runId);

    /** {@code task  state} for each task instance of the run. */
    List<String> taskStates(String dagId, String runId);

    // ------------------------------------------------------------------ the metadata database

    /** Airflow's metadata database over JDBC. */
    final class Jdbc implements AirflowState {
        private final String url;
        private final Supplier<Connection> connect;

        Jdbc(String url, Supplier<Connection> connect) {
            this.url = url;
            this.connect = connect;
        }

        @Override
        public String describe() {
            return "Airflow's metadata database, " + url;
        }

        @Override
        public String source(String dagId) {
            List<String> rows = rows("SELECT c.source_code FROM dag d JOIN dag_code c ON c.fileloc = d.fileloc "
                    + "WHERE d.dag_id = ?", dagId);
            return rows.isEmpty() ? null : rows.get(0);
        }

        @Override
        public List<String> importErrors(String dagId) {
            return rows("SELECT filename || ': ' || stacktrace FROM import_error WHERE filename LIKE ?",
                    "%" + dagId + "%");
        }

        @Override
        public Boolean paused(String dagId) {
            List<String> rows = rows("SELECT is_paused::text FROM dag WHERE dag_id = ?", dagId);
            return rows.isEmpty() ? null : Boolean.valueOf(rows.get(0));
        }

        @Override
        public List<String> active(String dagId) {
            return rows("SELECT task_id || '@' || run_id || ':' || state FROM task_instance "
                    + "WHERE dag_id = ? AND state IN ('queued', 'running') ORDER BY 1", dagId);
        }

        @Override
        public String runState(String dagId, String runId) {
            List<String> rows = rows("SELECT state FROM dag_run WHERE dag_id = ? AND run_id = ?", dagId, runId);
            return rows.isEmpty() ? null : rows.get(0);
        }

        @Override
        public List<String> taskStates(String dagId, String runId) {
            return rows("SELECT task_id || '  ' || state FROM task_instance WHERE dag_id = ? AND run_id = ? "
                    + "ORDER BY 1", dagId, runId);
        }

        private List<String> rows(String sql, Object... params) {
            try (Connection c = connect.get(); PreparedStatement ps = c.prepareStatement(sql)) {
                for (int i = 0; i < params.length; i++) {
                    ps.setObject(i + 1, params[i]);
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

    // ------------------------------------------------------------------ the REST API

    /**
     * Airflow's stable REST API. {@code base} is the web server's URL (on Composer, the
     * environment's {@code airflow_uri}); the paths are those of Airflow 2.9.3's
     * {@code api_connexion/openapi/v1.yaml}.
     */
    final class Rest implements AirflowState {
        private static final Duration TIMEOUT = Duration.ofSeconds(30);

        private final String base;
        private final Supplier<String> authorization;
        private final HttpClient http = HttpClient.newBuilder().connectTimeout(TIMEOUT).build();

        /**
         * @param authorization the {@code Authorization} header's value for each request: Basic for a
         *     local Airflow, {@code Bearer <token>} for Composer. Called per request, so a token
         *     source can refresh.
         */
        Rest(String base, Supplier<String> authorization) {
            this.base = base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
            this.authorization = authorization;
        }

        static Supplier<String> basic(String user, String password) {
            String value = "Basic " + Base64.getEncoder()
                    .encodeToString((user + ":" + password).getBytes(StandardCharsets.UTF_8));
            return () -> value;
        }

        /**
         * {@code Bearer <token>}: the last line {@code command} prints on standard output (its
         * standard error is discarded, so a warning there is never taken for the token), fetched
         * again every 10 minutes.
         */
        static Supplier<String> bearerFrom(List<String> command) {
            return new Supplier<>() {
                private String token;
                private long fetchedAt;

                @Override
                public synchronized String get() {
                    if (token == null || System.nanoTime() - fetchedAt > Duration.ofMinutes(10).toNanos()) {
                        String out;
                        int exit;
                        try {
                            Process p = new ProcessBuilder(command)
                                    .redirectError(ProcessBuilder.Redirect.DISCARD).start();
                            out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8).strip();
                            if (!p.waitFor(120, java.util.concurrent.TimeUnit.SECONDS)) {
                                p.destroyForcibly();
                                throw new IllegalStateException("the token command " + command + " did not finish");
                            }
                            exit = p.exitValue();
                        } catch (IOException e) {
                            throw new IllegalStateException("could not run the token command " + command, e);
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            throw new IllegalStateException(e);
                        }
                        String last = out.isEmpty() ? "" : out.lines().reduce((a, b) -> b).orElse("").strip();
                        if (exit != 0 || last.isEmpty()) {
                            // Its output is not printed: on success it would be the token.
                            throw new IllegalStateException("the token command " + command + " failed (exit "
                                    + exit + ", " + (last.isEmpty() ? "no output" : "output withheld") + ")");
                        }
                        token = last;
                        fetchedAt = System.nanoTime();
                    }
                    return "Bearer " + token;
                }
            };
        }

        @Override
        public String describe() {
            return "Airflow's REST API, " + base + "/api/v1";
        }

        @Override
        public String source(String dagId) {
            JsonObject dag = get("/dags/" + enc(dagId));
            if (dag == null || text(dag, "file_token").isEmpty()) {
                return null;
            }
            // The file token names the file the DAG was parsed from; the server resolves it.
            JsonObject source = get("/dagSources/" + enc(text(dag, "file_token")));
            return source == null ? null : text(source, "content");
        }

        @Override
        public List<String> importErrors(String dagId) {
            JsonObject body = get("/importErrors?limit=100");
            List<String> out = new ArrayList<>();
            if (body == null) {
                return out;
            }
            for (JsonElement e : body.getAsJsonArray("import_errors")) {
                JsonObject o = e.getAsJsonObject();
                String filename = text(o, "filename");
                if (filename.contains(dagId)) {
                    out.add(filename + ": " + text(o, "stack_trace"));
                }
            }
            return out;
        }

        @Override
        public Boolean paused(String dagId) {
            JsonObject dag = get("/dags/" + enc(dagId));
            JsonElement paused = dag == null ? null : dag.get("is_paused");
            return paused == null || paused.isJsonNull() ? null : paused.getAsBoolean();
        }

        @Override
        public List<String> active(String dagId) {
            // "~" is every run of the DAG; the cap is per DAG, so every run's tasks count.
            JsonObject body = get("/dags/" + enc(dagId) + "/dagRuns/~/taskInstances?state=queued&state=running&limit=100");
            List<String> out = new ArrayList<>();
            if (body != null) {
                for (JsonElement e : body.getAsJsonArray("task_instances")) {
                    JsonObject o = e.getAsJsonObject();
                    out.add(text(o, "task_id") + "@" + text(o, "dag_run_id") + ":" + text(o, "state"));
                }
            }
            out.sort(null);
            return out;
        }

        @Override
        public String runState(String dagId, String runId) {
            JsonObject run = get("/dags/" + enc(dagId) + "/dagRuns/" + enc(runId));
            return run == null ? null : text(run, "state");
        }

        @Override
        public List<String> taskStates(String dagId, String runId) {
            JsonObject body = get("/dags/" + enc(dagId) + "/dagRuns/" + enc(runId) + "/taskInstances?limit=100");
            List<String> out = new ArrayList<>();
            if (body != null) {
                JsonArray all = body.getAsJsonArray("task_instances");
                for (JsonElement e : all) {
                    JsonObject o = e.getAsJsonObject();
                    out.add(text(o, "task_id") + "  " + text(o, "state"));
                }
            }
            out.sort(null);
            return out;
        }

        /** The response body, or null on 404. Any other status than 200 fails the call. */
        JsonObject get(String path) {
            HttpRequest request = HttpRequest.newBuilder(URI.create(base + "/api/v1" + path))
                    .timeout(TIMEOUT)
                    .header("Accept", "application/json")
                    .header("Authorization", authorization.get())
                    .GET().build();
            try {
                HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() == 404) {
                    return null;
                }
                if (response.statusCode() != 200) {
                    throw new IllegalStateException("GET " + request.uri() + " -> " + response.statusCode() + ": "
                            + abbreviate(response.body()));
                }
                return JsonParser.parseString(response.body()).getAsJsonObject();
            } catch (IOException e) {
                throw new IllegalStateException("GET " + request.uri() + ": " + e, e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException(e);
            }
        }

        private static String text(JsonObject o, String field) {
            JsonElement e = o.get(field);
            return e == null || e.isJsonNull() ? "" : e.getAsString();
        }

        private static String enc(String segment) {
            return URLEncoder.encode(segment, StandardCharsets.UTF_8).replace("+", "%20");
        }

        private static String abbreviate(String s) {
            return s.length() > 300 ? s.substring(0, 300) + "..." : s;
        }
    }
}
