package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.tester.JobControlRepositoryFixtures;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ConsoleReadServiceTest {

    private static final LocalDate DATE = LocalDate.of(2026, 10, 1);
    private static final Instant T0 = Instant.parse("2026-10-01T06:00:00Z");
    private static final Instant T1 = Instant.parse("2026-10-01T06:05:00Z");

    private static PipelineJob job(String runId, JobStatus status) {
        return PipelineJob.builder(runId, "sys-a", "ingest-orders", DATE, status).build();
    }

    @Test
    void runMapsEveryFieldOfTheJob() {
        PipelineJob failed = new PipelineJob("run-1", "sys-a", "ingest-orders", DATE,
                JobStatus.FAILED, null, Optional.of("orders"), Optional.of("gs://in/orders.csv"),
                Optional.of("ds.orders"), 120, 3, 1, Optional.of(FailureStage.VALIDATION),
                Optional.of("E_SCHEMA"), Optional.of("column 4 is not a date"),
                Optional.of("gs://quarantine/run-1"), 0.25, 1000, 2000, T0, T1,
                Optional.of(T0), Optional.of(T1));
        ConsoleReadService console = new ConsoleReadService(JobControlRepositoryFixtures.repoWith(failed));

        RunView run = console.run("run-1").orElseThrow();

        assertThat(run.runId()).isEqualTo("run-1");
        assertThat(run.systemId()).isEqualTo("sys-a");
        assertThat(run.pipelineName()).isEqualTo("ingest-orders");
        assertThat(run.extractDate()).isEqualTo(DATE);
        assertThat(run.status()).isEqualTo(JobStatus.FAILED);
        assertThat(run.jobType()).isEqualTo("ingestion");
        assertThat(run.entityType()).contains("orders");
        assertThat(run.sourceFile()).contains("gs://in/orders.csv");
        assertThat(run.targetTable()).contains("ds.orders");
        assertThat(run.recordCount()).isEqualTo(120);
        assertThat(run.errorCount()).isEqualTo(3);
        assertThat(run.retryCount()).isEqualTo(1);
        assertThat(run.failureStage()).contains(FailureStage.VALIDATION);
        assertThat(run.errorCode()).contains("E_SCHEMA");
        assertThat(run.errorMessage()).contains("column 4 is not a date");
        assertThat(run.errorFilePath()).contains("gs://quarantine/run-1");
        assertThat(run.estimatedCostUsd()).isEqualTo(0.25);
        assertThat(run.billedBytesScanned()).isEqualTo(1000);
        assertThat(run.billedBytesWritten()).isEqualTo(2000);
        assertThat(run.createdAt()).isEqualTo(T0);
        assertThat(run.updatedAt()).isEqualTo(T1);
        assertThat(run.startedAt()).contains(T0);
        assertThat(run.completedAt()).contains(T1);
    }

    @Test
    void unknownRunIsEmpty() {
        assertThat(new ConsoleReadService(JobControlRepositoryFixtures.emptyRepo()).run("nope")).isEmpty();
    }

    @Test
    void terminalStatesAreFinalAndOnlyThem() {
        for (JobStatus status : JobStatus.values()) {
            RunView run = RunView.of(job("r", status));
            boolean expected = status == JobStatus.SUCCEEDED || status == JobStatus.FAILED
                    || status == JobStatus.CANCELLED;
            assertThat(run.terminal()).as(status.name()).isEqualTo(expected);
        }
    }

    @Test
    void aRetriedFailedRunStaysFailedAndSaysTheRetryIsAnotherRun() {
        PipelineJob failedThenRetried = PipelineJob.builder("run-1", "sys-a", "ingest-orders", DATE,
                JobStatus.FAILED).retryCount(2).build();

        RunView run = RunView.of(failedThenRetried);

        assertThat(run.status()).isEqualTo(JobStatus.FAILED);
        assertThat(run.terminal()).isTrue();
        assertThat(run.summary())
                .contains("failed")
                .contains("a retry runs under a new run id")
                .doesNotContainIgnoringCase("succeeded")
                .doesNotContainIgnoringCase("recovered");
    }

    @Test
    void pendingRunsPassTheSystemFilterThrough() {
        JobControlRepository repo = JobControlRepositoryFixtures.repoWith(job("run-2", JobStatus.RUNNING));
        ConsoleReadService console = new ConsoleReadService(repo);

        assertThat(console.pendingRuns(Optional.of("sys-a"))).extracting(RunView::runId).containsExactly("run-2");
        Mockito.verify(repo).getPendingJobs(Optional.of("sys-a"));
    }

    @Test
    void entityStatusFailuresAndFdpStatusAreMapped() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();
        Mockito.when(repo.getEntityStatus("sys-a", DATE)).thenReturn(List.of(
                new EntityStatus("orders", "failed", "run-1", 120, 3, Optional.of(T0), Optional.of(T1))));
        Mockito.when(repo.getFailedJobs("sys-a", DATE)).thenReturn(List.of(
                new FailedJob("run-1", "orders", "validation", "E_SCHEMA", "bad date",
                        Optional.of("gs://quarantine/run-1"), T1, 1)));
        Mockito.when(repo.getFdpJobStatus("sys-a", DATE, "customer_360")).thenReturn(Optional.of(
                new FdpJobStatus("run-9", "customer_360", "succeeded", 42, Optional.of(T0), Optional.empty())));
        ConsoleReadService console = new ConsoleReadService(repo);

        assertThat(console.entityStatus("sys-a", DATE)).containsExactly(
                new EntityStatusView("orders", "failed", "run-1", 120, 3, Optional.of(T0), Optional.of(T1)));
        assertThat(console.failures("sys-a", DATE)).containsExactly(
                new FailureView("run-1", "orders", "validation", "E_SCHEMA", "bad date",
                        Optional.of("gs://quarantine/run-1"), T1, 1));
        assertThat(console.fdpStatus("sys-a", DATE, "customer_360")).contains(
                new FdpRunView("run-9", "customer_360", "succeeded", 42, Optional.of(T0), Optional.empty()));
        assertThat(console.fdpStatus("sys-a", DATE, "other")).isEmpty();
    }

    @Test
    void theServiceNeverCallsAWritingMethod() {
        JobControlRepository repo = JobControlRepositoryFixtures.repoWith(job("run-1", JobStatus.FAILED));
        ConsoleReadService console = new ConsoleReadService(repo);

        console.run("run-1");
        console.pendingRuns(Optional.empty());
        console.entityStatus("sys-a", DATE);
        console.failures("sys-a", DATE);
        console.fdpStatus("sys-a", DATE, "m");

        Mockito.verify(repo, Mockito.never()).createJob(Mockito.any());
        Mockito.verify(repo, Mockito.never()).updateStatus(Mockito.any(), Mockito.any(), Mockito.any());
        Mockito.verify(repo, Mockito.never()).markFailed(Mockito.any(), Mockito.any(), Mockito.any(),
                Mockito.any(), Mockito.any());
        Mockito.verify(repo, Mockito.never()).markRetrying(Mockito.any(), Mockito.anyInt());
        Mockito.verify(repo, Mockito.never()).cleanupPartialLoad(Mockito.any(), Mockito.any());
        Mockito.verify(repo, Mockito.never()).updateCostMetrics(Mockito.any(), Mockito.anyDouble(),
                Mockito.anyLong(), Mockito.anyLong());
    }

    @Test
    void nullArgumentsAreRejected() {
        ConsoleReadService console = new ConsoleReadService(JobControlRepositoryFixtures.emptyRepo());
        assertThatThrownBy(() -> new ConsoleReadService(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> console.run(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> console.pendingRuns(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> console.entityStatus(null, DATE)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> console.failures("sys-a", null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> console.fdpStatus("sys-a", DATE, null)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void fromAutoConfigNamesTheMissingBinding() {
        // No JobControlRepository is registered on this module's test classpath.
        assertThatThrownBy(() -> ConsoleReadService.from(AutoConfig.discover()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("JobControlRepository");
    }
}
