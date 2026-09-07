package com.enrichmeai.culvert.deployments.segmenttransform;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.function.Supplier;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Terminal job-control status: the signal that was missing entirely.
 *
 * <p>Nothing wrote a terminal status for a segment-transform run, so every row
 * {@code fdp-trigger} inserted stayed {@code running} and its dedup gate
 * latched closed against legitimate retries. These tests pin the cases that
 * gate depends on: success, failure, and a terminal write that itself fails.
 */
class MainframeSegmentPipelineTest {

    private static final String RUN_ID = "auto_20260409_123456";

    private RecordingJobControlRepository repository;
    private boolean repositoryOpened;

    @BeforeEach
    void setUp() {
        repository = new RecordingJobControlRepository();
        repositoryOpened = false;
    }

    // ---------------------------------------------------------------- success

    @Test
    void successfulRunIsMarkedSucceeded() {
        MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, PipelineResult.State.DONE, null);

        assertThat(repository.statusUpdates)
                .containsExactly(RUN_ID + "/" + JobStatus.SUCCEEDED);
        assertThat(repository.failures).isEmpty();
        // Record count is deliberately not reported -- see reportTerminalStatus.
        assertThat(repository.lastTotalRecords).isEmpty();
    }

    @Test
    void successUsesCulvertsLowercaseStatusVocabulary() {
        // AD-17: 'succeeded', not 'SUCCESS'. fdp-trigger's dedup filter reads
        // exactly these values, so the two sides must name the same thing.
        assertThat(JobStatus.SUCCEEDED.getValue()).isEqualTo("succeeded");
        assertThat(JobStatus.RUNNING.getValue()).isEqualTo("running");
        assertThat(JobStatus.FAILED.getValue()).isEqualTo("failed");
    }

    // ---------------------------------------------------------------- failure

    @Test
    void thrownExceptionIsMarkedFailed() {
        MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, null, new IllegalStateException("worker died"));

        assertThat(repository.statusUpdates).isEmpty();
        assertThat(repository.failures).hasSize(1);
        RecordedFailure failure = repository.failures.get(0);
        assertThat(failure.runId).isEqualTo(RUN_ID);
        assertThat(failure.errorCode).isEqualTo("SEGMENT_TRANSFORM_EXCEPTION");
        assertThat(failure.errorMessage).contains("worker died");
        assertThat(failure.failureStage).isEqualTo(FailureStage.TRANSFORMATION);
    }

    @Test
    void nonDoneTerminalStateIsMarkedFailed() {
        // The commonest real failure: waitUntilFinish() RETURNS FAILED rather
        // than throwing, so a catch block alone would never see it.
        MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, PipelineResult.State.FAILED, null);

        assertThat(repository.statusUpdates).isEmpty();
        assertThat(repository.failures).hasSize(1);
        assertThat(repository.failures.get(0).errorCode).isEqualTo("SEGMENT_TRANSFORM_FAILED");
    }

    @Test
    void cancelledStateIsMarkedFailed() {
        MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, PipelineResult.State.CANCELLED, null);

        assertThat(repository.failures).hasSize(1);
        assertThat(repository.failures.get(0).errorCode).isEqualTo("SEGMENT_TRANSFORM_CANCELLED");
    }

    // ---------------------------------------------- the write itself failing

    @Test
    void aFailedSuccessWriteIsNotSwallowed() {
        // AD-5. Exiting 0 over a stale 'running' row is the defect class this
        // whole change exists to remove.
        repository.throwOnWrite = new IllegalStateException(
                "updateStatus affected no rows: no job with runId=" + RUN_ID);

        assertThatThrownBy(() -> MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, PipelineResult.State.DONE, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("affected no rows");
    }

    @Test
    void aFailedFailureWriteIsNotSwallowed() {
        repository.throwOnWrite = new IllegalStateException("BigQuery rejected the update");

        assertThatThrownBy(() -> MainframeSegmentPipeline.reportTerminalStatus(
                repository, RUN_ID, PipelineResult.State.FAILED, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("BigQuery rejected the update");
    }

    // --------------------------------------------------- job_control location

    @Test
    void configuredJobControlTableIsSplitIntoItsThreeParts() {
        assertThat(MainframeSegmentPipeline.resolveJobControlTable(
                "proj.job_control.pipeline_jobs", "ignored"))
                .containsExactly("proj", "job_control", "pipeline_jobs");
    }

    @Test
    void absentJobControlTableFallsBackToTheProjectDefault() {
        assertThat(MainframeSegmentPipeline.resolveJobControlTable(null, "my-project"))
                .containsExactly("my-project",
                        MainframeSegmentPipeline.DEFAULT_JOB_CONTROL_DATASET,
                        MainframeSegmentPipeline.DEFAULT_JOB_CONTROL_TABLE);
        assertThat(MainframeSegmentPipeline.resolveJobControlTable("  ", "my-project"))
                .containsExactly("my-project", "job_control", "pipeline_jobs");
    }

    @Test
    void aMalformedJobControlTableIsRejected() {
        assertThatThrownBy(() -> MainframeSegmentPipeline.resolveJobControlTable(
                "job_control.pipeline_jobs", "my-project"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("project.dataset.table");
    }

    @Test
    void withNoTableAndNoProjectThereIsNothingToGuess() {
        assertThatThrownBy(() ->
                MainframeSegmentPipeline.resolveJobControlTable(null, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    // --------------------------------------------------------- options wiring

    @Test
    void jobControlOptionsBindFromTheCommandLine() {
        MainframeSegmentPipeline.SegmentOptions options = PipelineOptionsFactory
                .fromArgs("--templatePath=/tmp/customer.yaml",
                        "--outputBucket=bucket",
                        "--extractDate=20260409",
                        "--runId=" + RUN_ID,
                        "--gcpProjectId=my-project",
                        "--jobControlTable=my-project.job_control.pipeline_jobs")
                .as(MainframeSegmentPipeline.SegmentOptions.class);

        assertThat(options.getRunId()).isEqualTo(RUN_ID);
        assertThat(options.getJobControlTable())
                .isEqualTo("my-project.job_control.pipeline_jobs");
        // Reporting is on unless explicitly disabled -- a scheduled run must
        // never silently skip its terminal write.
        assertThat(options.getReportJobControlStatus()).isTrue();
    }

    @Test
    void optionNamesAreCamelCase() {
        // Beam derives the flag name from the getter, so --run_id does NOT
        // bind to getRunId(). Pinned here because fdp-trigger's launcher.py
        // currently sends snake_case names; see the deployment README.
        assertThatThrownBy(() -> PipelineOptionsFactory
                .fromArgs("--run_id=" + RUN_ID)
                .as(MainframeSegmentPipeline.SegmentOptions.class))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("run_id");
    }

    // ------------------------------------------------- completeRun (run()'s tail)

    private Supplier<JobControlRepository> supplier() {
        return () -> {
            repositoryOpened = true;
            return repository;
        };
    }

    @Test
    void aFinishedRunReachesTheTerminalWrite() {
        // The wiring test. Disabling the reportTerminalStatus call inside
        // completeRun makes this fail -- which the direct reportTerminalStatus
        // tests do not, because they never go through run()'s tail.
        MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, PipelineResult.State.DONE, null);

        assertThat(repositoryOpened).isTrue();
        assertThat(repository.statusUpdates)
                .containsExactly(RUN_ID + "/" + JobStatus.SUCCEEDED);
    }

    @Test
    void aNonDoneStateIsReportedAndThenExitsNonZero() {
        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, PipelineResult.State.FAILED, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected DONE");

        assertThat(repository.failures).hasSize(1);
        assertThat(repository.failures.get(0).errorCode).isEqualTo("SEGMENT_TRANSFORM_FAILED");
    }

    @Test
    void theRunsOwnFailureIsRethrownAfterBeingReported() {
        RuntimeException boom = new IllegalStateException("worker died");

        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, null, boom))
                .isSameAs(boom);

        assertThat(repository.failures).hasSize(1);
    }

    @Test
    void anErrorFromTheRunStillClosesTheRowOutAndPropagates() {
        // P3: catching only RuntimeException would let an OOM or
        // NoClassDefFoundError skip the write and leave the row 'running'.
        Error oom = new NoClassDefFoundError("com/example/Missing");

        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, null, oom))
                .isSameAs(oom);

        assertThat(repository.failures).hasSize(1);
        assertThat(repository.failures.get(0).errorCode).isEqualTo("SEGMENT_TRANSFORM_EXCEPTION");
    }

    @Test
    void whenBothTheRunAndTheWriteFailNeitherCauseIsLost() {
        RuntimeException boom = new IllegalStateException("worker died");
        repository.throwOnWrite = new IllegalStateException("BigQuery rejected the update");

        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, PipelineResult.State.FAILED, boom))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("BigQuery rejected the update")
                .satisfies(thrown -> assertThat(thrown.getSuppressed()).containsExactly(boom));
    }

    @Test
    void aSuccessfulRunThatCannotReportDoesNotExitZero() {
        repository.throwOnWrite = new IllegalStateException("no such run");

        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, PipelineResult.State.DONE, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no such run");
    }

    @Test
    void aNonTerminalStateIsNeverRecordedAsFailed() {
        // P4: RUNNING is not an outcome, and 'SEGMENT_TRANSFORM_null' is not a
        // diagnosis. Refuse rather than invent a result for a live job.
        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, PipelineResult.State.RUNNING, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("non-terminal");
        assertThatThrownBy(() -> MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, true, null, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("non-terminal");

        assertThat(repository.failures).isEmpty();
        assertThat(repository.statusUpdates).isEmpty();
    }

    // ---------------------------------------------------------- the skip path

    @Test
    void aRunWithNoRunIdHasNothingToComplete() {
        // A synthesised "manual-<millis>" run id has no job_control row, so
        // there is nothing to complete: skip, and do not even open a BigQuery
        // client. Declining to write for a run that was never registered is
        // not the same as swallowing a failure.
        MainframeSegmentPipeline.completeRun(
                supplier(), "manual-123", false, true, PipelineResult.State.DONE, null);

        assertThat(repositoryOpened).isFalse();
        assertThat(repository.statusUpdates).isEmpty();
        assertThat(repository.failures).isEmpty();
    }

    @Test
    void reportingCanBeDisabledForLocalRuns() {
        MainframeSegmentPipeline.completeRun(
                supplier(), RUN_ID, true, false, PipelineResult.State.DONE, null);

        assertThat(repositoryOpened).isFalse();
        assertThat(repository.statusUpdates).isEmpty();
    }

    @Test
    void aBlankRunIdCountsAsAbsent() {
        // run() treats null and blank alike; --runId= must not be mistaken for
        // a real run whose row could be completed.
        MainframeSegmentPipeline.SegmentOptions blank = PipelineOptionsFactory
                .fromArgs("--templatePath=/tmp/customer.yaml",
                        "--outputBucket=bucket",
                        "--extractDate=20260409",
                        "--runId=")
                .as(MainframeSegmentPipeline.SegmentOptions.class);
        MainframeSegmentPipeline.SegmentOptions absent = PipelineOptionsFactory
                .fromArgs("--templatePath=/tmp/customer.yaml",
                        "--outputBucket=bucket",
                        "--extractDate=20260409")
                .as(MainframeSegmentPipeline.SegmentOptions.class);

        assertThat(absent.getRunId()).isNull();
        assertThat(MainframeSegmentPipeline.runIdSupplied(blank.getRunId())).isFalse();
        assertThat(MainframeSegmentPipeline.runIdSupplied(absent.getRunId())).isFalse();
        assertThat(MainframeSegmentPipeline.runIdSupplied(RUN_ID)).isTrue();
    }

    // ------------------------------------------------------------- test double

    private record RecordedFailure(String runId, String errorCode, String errorMessage,
                                   FailureStage failureStage, Optional<String> errorFilePath) {
    }

    /**
     * Hand-rolled {@link JobControlRepository} double. Only the two terminal
     * writes are exercised; the rest of the port throws, so a test that starts
     * depending on them fails loudly rather than silently passing on a stub.
     */
    private static final class RecordingJobControlRepository implements JobControlRepository {

        final List<String> statusUpdates = new ArrayList<>();
        final List<RecordedFailure> failures = new ArrayList<>();
        Optional<Long> lastTotalRecords = Optional.empty();
        RuntimeException throwOnWrite;

        @Override
        public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
            if (throwOnWrite != null) {
                throw throwOnWrite;
            }
            statusUpdates.add(runId + "/" + status);
            lastTotalRecords = totalRecords;
        }

        @Override
        public void markFailed(String runId, String errorCode, String errorMessage,
                               FailureStage failureStage, Optional<String> errorFilePath) {
            if (throwOnWrite != null) {
                throw throwOnWrite;
            }
            failures.add(new RecordedFailure(runId, errorCode, errorMessage,
                    failureStage, errorFilePath));
        }

        @Override
        public void createJob(PipelineJob job) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public Optional<PipelineJob> getJob(String runId) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public void markRetrying(String runId, int retryCount) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                      String modelName) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public int cleanupPartialLoad(String runId, String tableId) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }

        @Override
        public void updateCostMetrics(String runId, double estimatedCostUsd,
                                      long billedBytesScanned, long billedBytesWritten) {
            throw new UnsupportedOperationException("not used by reportTerminalStatus");
        }
    }
}
