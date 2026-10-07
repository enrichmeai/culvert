package com.enrichmeai.culvert.e2e.proof;

import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** A child process whose combined output is captured as it arrives. */
final class Proc {

    private final String label;
    private final Process process;
    private final StringBuffer out = new StringBuffer();
    private final Thread reader;

    private Proc(String label, Process process) {
        this.label = label;
        this.process = process;
        this.reader = new Thread(() -> {
            try (java.io.Reader in = new java.io.InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8)) {
                char[] buf = new char[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    out.append(buf, 0, n);
                }
            } catch (IOException ignored) {
                // the process went away; what was read is kept
            }
        }, "proc-" + label);
        reader.setDaemon(true);
        reader.start();
    }

    static Proc start(String label, List<String> command, Map<String, String> env, File dir) {
        ProcessBuilder pb = new ProcessBuilder(command).redirectErrorStream(true);
        pb.environment().putAll(env);
        if (dir != null) {
            pb.directory(dir);
        }
        try {
            return new Proc(label, pb.start());
        } catch (IOException e) {
            throw new UncheckedIOException("could not start " + label + ": " + command.get(0), e);
        }
    }

    /** Wait for the process to exit; its exit code. Fails the harness if it outlives {@code seconds}. */
    int waitFor(long seconds) {
        try {
            if (!process.waitFor(seconds, TimeUnit.SECONDS)) {
                destroyTree();
                throw new IllegalStateException(label + " did not finish within " + seconds + "s:\n" + out());
            }
            reader.join(TimeUnit.SECONDS.toMillis(10));
            return process.exitValue();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
    }

    /** Wait until the output contains {@code text}; false if the process exits or time runs out first. */
    boolean awaitOutput(String text, long seconds) {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(seconds);
        while (System.nanoTime() < deadline) {
            if (out().contains(text)) {
                return true;
            }
            if (!process.isAlive()) {
                return out().contains(text);
            }
            sleep(100);
        }
        return false;
    }

    boolean alive() {
        return process.isAlive();
    }

    String out() {
        return out.toString();
    }

    List<String> lines() {
        return out().lines().toList();
    }

    /** Kill the process and everything it started (an Airflow scheduler forks its executors). */
    void destroyTree() {
        // Parent first, so a forking scheduler cannot replace a child it has already lost.
        List<ProcessHandle> children = process.descendants().toList();
        process.destroyForcibly();
        children.forEach(ProcessHandle::destroyForcibly);
        try {
            process.waitFor(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        }
    }

    static File dir(String path) {
        return path == null ? null : new File(path);
    }
}
