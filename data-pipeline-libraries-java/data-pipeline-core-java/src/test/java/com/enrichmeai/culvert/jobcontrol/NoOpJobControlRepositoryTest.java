package com.enrichmeai.culvert.jobcontrol;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.time.LocalDate;
import java.util.Optional;
import java.util.ServiceLoader;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

class NoOpJobControlRepositoryTest {

    private final NoOpJobControlRepository repository = new NoOpJobControlRepository();

    @Test
    void everyWriteIsAcceptedAndEveryReadAnswersNothing() {
        PipelineJob job = PipelineJob.builder("run-1", "sys", "job", LocalDate.of(2026, 9, 17), JobStatus.CREATED)
                .build();
        assertThatCode(() -> {
            repository.createJob(job);
            repository.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
            repository.markFailed("run-1", "X", "why", FailureStage.LOAD, Optional.empty());
            repository.markRetrying("run-1", 1);
            repository.updateCostMetrics("run-1", 0.01, 1_024L, 512L);
        }).doesNotThrowAnyException();

        // Honest absence, never an invented status: what was "written" cannot be read back.
        assertThat(repository.getJob("run-1")).isEmpty();
        assertThat(repository.getPendingJobs(Optional.empty())).isEmpty();
        assertThat(repository.getEntityStatus("sys", LocalDate.of(2026, 9, 17))).isEmpty();
        assertThat(repository.getFailedJobs("sys", LocalDate.of(2026, 9, 17))).isEmpty();
        assertThat(repository.getFdpJobStatus("sys", LocalDate.of(2026, 9, 17), "m")).isEmpty();
        assertThat(repository.cleanupPartialLoad("run-1", "t")).isZero();
    }

    /**
     * The whole point of the class is that choosing it is a decision a deployment states in its
     * own code. If it were ever discoverable, a deployment with no job control configured would
     * pick it up and run with its state recorded nowhere, reported as fine.
     */
    @Test
    void isNeverDiscoveredAsAServiceLoaderImplementation() {
        for (JobControlRepository discovered : ServiceLoader.load(JobControlRepository.class)) {
            assertThat(discovered).isNotInstanceOf(NoOpJobControlRepository.class);
        }
    }

    /** Beam ships stages to workers by serialisation, and the repository rides inside the stage. */
    @Test
    void isSerializable() throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(repository);
        }
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
            assertThat(in.readObject()).isInstanceOf(NoOpJobControlRepository.class);
        }
    }
}
