package com.enrichmeai.culvert.e2e.proof;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The REST reader (#234) against a stand-in for Airflow 2.9.3's /api/v1. */
class AirflowStateRestTest {

    private static final String DAG = "reference_e2e_control_plane";

    private HttpServer server;
    private final Map<String, String> bodies = new ConcurrentHashMap<>();
    private final List<String> requests = new CopyOnWriteArrayList<>();
    private final List<String> authorizations = new CopyOnWriteArrayList<>();
    private AirflowState.Rest rest;

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String target = exchange.getRequestURI().getRawPath()
                    + (exchange.getRequestURI().getRawQuery() == null ? "" : "?" + exchange.getRequestURI().getRawQuery());
            requests.add(target);
            authorizations.add(exchange.getRequestHeaders().getFirst("Authorization"));
            String body = bodies.get(target);
            int status = body == null ? 404 : body.startsWith("!") ? 403 : 200;
            byte[] bytes = (body == null ? "{\"title\":\"not found\"}" : body.replaceFirst("^!", ""))
                    .getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(status, bytes.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(bytes);
            }
        });
        server.start();
        rest = new AirflowState.Rest("http://127.0.0.1:" + server.getAddress().getPort() + "/",
                AirflowState.Rest.basic("admin", "pw"));
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    @Test
    void theDagsParsedSourceIsReadThroughItsFileTokenAndWhetherItIsPaused() {
        assertThat(rest.source(DAG)).isNull();
        assertThat(rest.paused(DAG)).isNull();

        bodies.put("/api/v1/dags/" + DAG, "{\"dag_id\":\"" + DAG + "\",\"is_paused\":false,\"file_token\":\"Ii9k.x\"}");
        bodies.put("/api/v1/dagSources/Ii9k.x", "{\"content\":\"from airflow import DAG\\n\"}");
        assertThat(rest.source(DAG)).isEqualTo("from airflow import DAG\n");
        assertThat(rest.paused(DAG)).isFalse();
        assertThat(authorizations).allMatch(a -> a.equals("Basic YWRtaW46cHc="));
    }

    @Test
    void activeTasksAreTheQueuedAndRunningOnesOfEveryRunOfTheDag() {
        bodies.put("/api/v1/dags/" + DAG + "/dagRuns/~/taskInstances?state=queued&state=running&limit=100",
                "{\"task_instances\":["
                        + "{\"task_id\":\"products__load\",\"dag_run_id\":\"r2\",\"state\":\"queued\"},"
                        + "{\"task_id\":\"orders__load\",\"dag_run_id\":\"r1\",\"state\":\"running\"}"
                        + "],\"total_entries\":2}");
        assertThat(rest.active(DAG)).containsExactly("orders__load@r1:running", "products__load@r2:queued");
    }

    @Test
    void aRunsStateAndItsTaskStatesAreRead() {
        bodies.put("/api/v1/dags/" + DAG + "/dagRuns/proof6%3A1", "{\"dag_run_id\":\"proof6:1\",\"state\":\"running\"}");
        bodies.put("/api/v1/dags/" + DAG + "/dagRuns/proof6%3A1/taskInstances?limit=100",
                "{\"task_instances\":[{\"task_id\":\"b\",\"state\":\"success\"},{\"task_id\":\"a\",\"state\":null}]}");
        assertThat(rest.runState(DAG, "proof6:1")).isEqualTo("running");
        assertThat(rest.runState(DAG, "missing")).isNull();
        assertThat(rest.taskStates(DAG, "proof6:1")).containsExactly("a  ", "b  success");
    }

    @Test
    void onlyTheDagsOwnImportErrorsAreReported() {
        bodies.put("/api/v1/importErrors?limit=100", "{\"import_errors\":["
                + "{\"filename\":\"/home/airflow/gcs/dags/" + DAG + ".py\",\"stack_trace\":\"ModuleNotFoundError\"},"
                + "{\"filename\":\"/home/airflow/gcs/dags/other.py\",\"stack_trace\":\"SyntaxError\"}]}");
        assertThat(rest.importErrors(DAG)).containsExactly("/home/airflow/gcs/dags/" + DAG + ".py: ModuleNotFoundError");
    }

    @Test
    void aRefusedCallFailsWithTheStatusRatherThanReadingAsAbsent() {
        bodies.put("/api/v1/dags/" + DAG, "!{\"title\":\"Forbidden\"}");
        assertThatThrownBy(() -> rest.source(DAG)).hasMessageContaining("-> 403").hasMessageContaining("Forbidden");
    }

    @Test
    void aBearerTokenIsTheLastLineTheTokenCommandPrints() {
        assertThat(AirflowState.Rest.bearerFrom(List.of("sh", "-c", "echo a warning; echo tok-123")).get())
                .isEqualTo("Bearer tok-123");
        assertThat(AirflowState.Rest.bearerFrom(List.of("sh", "-c", "echo tok-456; echo a warning >&2")).get())
                .as("standard error is never taken for the token").isEqualTo("Bearer tok-456");
        // What it prints is withheld (on success it would be the token); the command itself is named.
        assertThatThrownBy(() -> AirflowState.Rest.bearerFrom(List.of("sh", "-c", "printf 'tok%s' -leak; exit 1")).get())
                .hasMessageContaining("exit 1").hasMessageContaining("output withheld").hasMessageNotContaining("tok-leak");
    }
}
