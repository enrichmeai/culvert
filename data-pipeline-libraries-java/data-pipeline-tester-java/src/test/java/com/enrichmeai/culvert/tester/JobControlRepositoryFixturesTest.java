package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class JobControlRepositoryFixturesTest {

    @Test
    void emptyRepoReturnsEmptyForEveryLookup() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();

        assertThat(repo.getJob("any")).isEmpty();
        assertThat(repo.getPendingJobs(Optional.empty())).isEmpty();
        assertThat(repo.getEntityStatus("sys", LocalDate.of(2026, 1, 1))).isEmpty();
        assertThat(repo.getFailedJobs("sys", LocalDate.of(2026, 1, 1))).isEmpty();
        assertThat(repo.getFdpJobStatus("sys", LocalDate.of(2026, 1, 1), "model")).isEmpty();
        assertThat(repo.cleanupPartialLoad("run-1", "tbl")).isZero();
    }

    @Test
    void repoWithReturnsSeededJobByRunId() {
        PipelineJob j1 = PipelineJob.builder("run-1", "sys", "pipe", LocalDate.of(2026, 1, 1),
                JobStatus.CREATED).build();
        PipelineJob j2 = PipelineJob.builder("run-2", "sys", "pipe", LocalDate.of(2026, 1, 1),
                JobStatus.RUNNING).build();
        JobControlRepository repo = JobControlRepositoryFixtures.repoWith(j1, j2);

        assertThat(repo.getJob("run-1")).contains(j1);
        assertThat(repo.getJob("run-2")).contains(j2);
        assertThat(repo.getJob("missing")).isEmpty();
        assertThat(repo.getPendingJobs(Optional.empty())).containsExactly(j1, j2);
    }
}
