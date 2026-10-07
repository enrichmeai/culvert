package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.e2e.ReferenceE2EMain;
import com.enrichmeai.culvert.postgres.PostgresJobControlRepository;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Runs the fan-out on the control plane once, prints one line per stage, and exits with
 * {@link ControlPlaneRun.Report#exitCode()}: 0 done, 1 a stage failed or a gate was closed, 2 a
 * stage was held by another claimant, 64 bad arguments.
 *
 * <pre>
 *   CULVERT_POSTGRES_URL=jdbc:postgresql://localhost:5432/culvert \
 *   java -cp ... com.enrichmeai.culvert.e2e.controlplane.ControlPlaneMain \
 *       --period=2026-10-06 --units=orders,customers,products --max-concurrency=2
 * </pre>
 *
 * <p>Arguments, all optional: {@code --period} (ISO date, default today in UTC), {@code --units}
 * (default {@code orders,customers,products}), {@code --stages} (default all three),
 * {@code --max-concurrency} (default 2), {@code --records} (per stage, default 5),
 * {@code --claimant} (default {@code host:pid}), {@code --apply-ddl} (apply the shipped
 * {@code job_control.sql} first; it is idempotent), and the {@link Faults} switches. A kill
 * ({@code --fault.kill-after}) halts the JVM with exit code 137 and no cleanup, as a killed
 * worker would.
 */
public final class ControlPlaneMain {

    static final List<String> DEFAULT_UNITS = List.of("orders", "customers", "products");

    private ControlPlaneMain() {
    }

    public static void main(String[] args) {
        int code;
        try {
            code = run(ReferenceE2EMain.parseArgs(args));
        } catch (IllegalArgumentException | java.time.format.DateTimeParseException e) {
            System.err.println("reference-e2e-gcp control plane: " + e.getMessage());
            code = 64;
        }
        System.exit(code);
    }

    static int run(Map<String, String> opts) {
        if (Boolean.parseBoolean(opts.getOrDefault("apply-ddl", "false"))) {
            applyDdl();
        }
        ControlPlaneRun run = new ControlPlaneRun(
                ControlPlane.discover(AutoConfig.discover()),
                list(opts.getOrDefault("units", String.join(",", DEFAULT_UNITS))),
                opts.getOrDefault("period", LocalDate.now(ZoneOffset.UTC).toString()),
                list(opts.getOrDefault("stages", String.join(",", ControlPlaneRun.STAGES))),
                integer(opts, "max-concurrency", 2),
                integer(opts, "records", 5),
                Faults.parse(opts),
                () -> {
                    System.out.println("KILLED (fault.kill-after) — halting with no cleanup");
                    System.out.flush();
                    Runtime.getRuntime().halt(137);
                });
        ControlPlaneRun.Report report = run.run(opts.getOrDefault("claimant", defaultClaimant()));
        report.results().forEach(System.out::println);
        System.out.println("exit=" + report.exitCode());
        return report.exitCode();
    }

    /** Apply the {@code job_control.sql} that {@code data-pipeline-postgres} ships. */
    static void applyDdl() {
        String url = setting("CULVERT_POSTGRES_URL", "culvert.postgres.url");
        if (url == null) {
            throw new IllegalArgumentException("--apply-ddl needs CULVERT_POSTGRES_URL");
        }
        try (InputStream in = PostgresJobControlRepository.class.getResourceAsStream("job_control.sql");
             Connection c = DriverManager.getConnection(url,
                     setting("CULVERT_POSTGRES_USER", "culvert.postgres.user"),
                     setting("CULVERT_POSTGRES_PASSWORD", "culvert.postgres.password"));
             Statement s = c.createStatement()) {
            if (in == null) {
                throw new IllegalStateException("job_control.sql is not on the classpath");
            }
            s.execute(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        } catch (SQLException e) {
            throw new IllegalStateException("applying job_control.sql failed: " + e.getMessage(), e);
        }
    }

    private static String setting(String env, String property) {
        String value = System.getenv(env);
        return value != null && !value.isBlank() ? value : System.getProperty(property);
    }

    private static List<String> list(String csv) {
        return Arrays.stream(csv.split(",")).map(String::trim).filter(s -> !s.isEmpty()).toList();
    }

    private static int integer(Map<String, String> opts, String key, int fallback) {
        String value = opts.get(key);
        try {
            return value == null ? fallback : Integer.parseInt(value);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("--" + key + " must be a number, got '" + value + "'");
        }
    }

    private static String defaultClaimant() {
        String host;
        try {
            host = InetAddress.getLocalHost().getHostName();
        } catch (UnknownHostException e) {
            host = "unknown-host";
        }
        return host + ":" + ManagementFactory.getRuntimeMXBean().getPid();
    }
}
