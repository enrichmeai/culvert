package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.mockito.Mockito;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Mockito-mock fixture builders for {@link JobControlRepository}.
 *
 * <p>Returned mocks expose a read-mostly view of the supplied jobs:
 * {@link JobControlRepository#getJob(String)} returns the matching
 * {@link PipelineJob}; list-style methods return empty lists; write-style
 * methods ({@code createJob}, {@code updateStatus}, {@code markFailed},
 * etc.) are no-ops. Consumers add further stubbing on top when they need
 * to assert against writes or surface specific failed-job lists.
 *
 * <p>This class is non-instantiable.
 */
public final class JobControlRepositoryFixtures {

    private JobControlRepositoryFixtures() {
        throw new AssertionError("no instances");
    }

    /**
     * Mock {@link JobControlRepository} with no jobs. Every lookup returns
     * empty / empty list. Mutating methods are no-ops.
     */
    public static JobControlRepository emptyRepo() {
        return repoWith();
    }

    /**
     * Mock {@link JobControlRepository} pre-populated with {@code jobs}.
     *
     * <p>{@code getJob(runId)} returns the matching {@link PipelineJob} (or
     * empty if no match). {@code getPendingJobs} returns the input list as
     * a snapshot, regardless of the system filter — consumers stub
     * specifically when they care about filter semantics. Other list-style
     * methods return empty lists.
     *
     * @param jobs Jobs to seed. Must not be null.
     */
    public static JobControlRepository repoWith(PipelineJob... jobs) {
        Objects.requireNonNull(jobs, "jobs must not be null");
        Map<String, PipelineJob> byRunId = new HashMap<>();
        for (PipelineJob job : jobs) {
            byRunId.put(job.runId(), job);
        }
        List<PipelineJob> snapshot = List.of(jobs);

        JobControlRepository mock = Mockito.mock(JobControlRepository.class);

        Mockito.when(mock.getJob(Mockito.anyString())).thenAnswer(invocation -> {
            String runId = invocation.getArgument(0);
            return Optional.ofNullable(byRunId.get(runId));
        });

        Mockito.when(mock.getPendingJobs(Mockito.any())).thenReturn(snapshot);
        Mockito.when(mock.getEntityStatus(Mockito.anyString(), Mockito.any()))
                .thenReturn(Collections.emptyList());
        Mockito.when(mock.getFailedJobs(Mockito.anyString(), Mockito.any()))
                .thenReturn(Collections.emptyList());
        Mockito.when(mock.getFdpJobStatus(Mockito.anyString(), Mockito.any(), Mockito.anyString()))
                .thenReturn(Optional.empty());
        Mockito.when(mock.cleanupPartialLoad(Mockito.anyString(), Mockito.anyString()))
                .thenReturn(0);

        // createJob / updateStatus / markFailed / markRetrying /
        // updateCostMetrics default to Mockito no-ops.
        return mock;
    }
}
