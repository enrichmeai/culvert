package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.Test;

import java.lang.reflect.RecordComponent;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/** A field added to a contract record fails here until its view carries it too. */
class ViewsMirrorContractsTest {

    private static List<String> names(Class<? extends Record> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }

    @Test
    void runViewCarriesEveryPipelineJobField() {
        assertThat(names(RunView.class)).containsAll(names(PipelineJob.class));
        assertThat(names(RunView.class)).hasSize(names(PipelineJob.class).size() + 1); // + terminal
    }

    @Test
    void theOtherViewsMatchTheirRecordsExactly() {
        assertThat(names(EntityStatusView.class)).isEqualTo(names(EntityStatus.class));
        assertThat(names(FailureView.class)).isEqualTo(names(FailedJob.class));
        assertThat(names(FdpRunView.class)).isEqualTo(names(FdpJobStatus.class));
    }
}
