package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.JobControlRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Read-only operator views over {@link JobControlRepository}.
 *
 * <p>It calls the five read methods and nothing else. It never calls a writing method, and in
 * particular never {@code cleanupPartialLoad}, which deletes data. It binds only to the contract,
 * so the same views work on any backend {@link AutoConfig} discovers.
 */
public final class ConsoleReadService {

    private final JobControlRepository jobControl;

    /** A service over {@code jobControl}. */
    public ConsoleReadService(JobControlRepository jobControl) {
        this.jobControl = Objects.requireNonNull(jobControl, "jobControl");
    }

    /**
     * A service over the {@link JobControlRepository} that {@code autoConfig} discovered.
     *
     * @throws IllegalStateException if none is installed
     */
    public static ConsoleReadService from(AutoConfig autoConfig) {
        Objects.requireNonNull(autoConfig, "autoConfig");
        return new ConsoleReadService(autoConfig.jobControl().orElseThrow(() ->
                new IllegalStateException("No JobControlRepository is installed: add an adapter "
                        + "that provides one (for example data-pipeline-gcp-bigquery or "
                        + "data-pipeline-aws-dynamodb) to the classpath.")));
    }

    /** The run with this id, or empty. */
    public Optional<RunView> run(String runId) {
        Objects.requireNonNull(runId, "runId");
        return jobControl.getJob(runId).map(RunView::of);
    }

    /** Runs that are created or running, for one system or for all. */
    public List<RunView> pendingRuns(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId");
        return jobControl.getPendingJobs(systemId).stream().map(RunView::of).toList();
    }

    /** Each entity's latest status for a system and extract date. */
    public List<EntityStatusView> entityStatus(String systemId, LocalDate extractDate) {
        requireKey(systemId, extractDate);
        return jobControl.getEntityStatus(systemId, extractDate).stream()
                .map(EntityStatusView::of).toList();
    }

    /** The failed runs for a system and extract date. */
    public List<FailureView> failures(String systemId, LocalDate extractDate) {
        requireKey(systemId, extractDate);
        return jobControl.getFailedJobs(systemId, extractDate).stream()
                .map(FailureView::of).toList();
    }

    /** An FDP model's run status for a system and extract date, or empty. */
    public Optional<FdpRunView> fdpStatus(String systemId, LocalDate extractDate, String modelName) {
        requireKey(systemId, extractDate);
        Objects.requireNonNull(modelName, "modelName");
        return jobControl.getFdpJobStatus(systemId, extractDate, modelName).map(FdpRunView::of);
    }

    private static void requireKey(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId");
        Objects.requireNonNull(extractDate, "extractDate");
    }
}
