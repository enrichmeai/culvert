package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.lineage.LineageDestination;
import com.enrichmeai.culvert.lineage.LineageEvent;
import com.enrichmeai.culvert.lineage.LineagePipeline;
import com.enrichmeai.culvert.lineage.LineageSource;
import com.google.cloud.datacatalog.v1.CreateTagRequest;
import com.google.cloud.datacatalog.v1.DataCatalogClient;
import com.google.cloud.datacatalog.v1.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link DataCatalogLineageEmitter}. Mocks
 * {@link DataCatalogClient} so no real Data Catalog endpoint or
 * credentials are required.
 */
@ExtendWith(MockitoExtension.class)
class DataCatalogLineageEmitterTest {

    private static final String ENTRY =
            "projects/p/locations/us/entryGroups/g/entries/e";
    private static final String TEMPLATE =
            "projects/p/locations/us/tagTemplates/lineage";

    @Mock
    private DataCatalogClient client;

    private static LineageEvent fullEvent() {
        return LineageEvent.builder()
                .source(LineageSource.of("table", "bigquery://p.ds.src"))
                .pipeline(new LineagePipeline(
                        "run-1",
                        "demo_pipeline",
                        "transform",
                        Optional.of(Instant.parse("2026-05-27T10:00:00Z")),
                        Optional.of(Instant.parse("2026-05-27T10:05:00Z"))))
                .destination(LineageDestination.of("table", "bigquery://p.ds.tgt"))
                .build();
    }

    // --- happy path --------------------------------------------------------

    @Test
    void emitOneEventCreatesTagWithFlattenedFields() {
        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);

        emitter.emit(fullEvent());

        ArgumentCaptor<CreateTagRequest> captor =
                ArgumentCaptor.forClass(CreateTagRequest.class);
        verify(client).createTag(captor.capture());
        CreateTagRequest req = captor.getValue();

        assertThat(req.getParent()).isEqualTo(ENTRY);
        Tag tag = req.getTag();
        assertThat(tag.getTemplate()).isEqualTo(TEMPLATE);

        // Pipeline + source + destination all rendered as string tag fields.
        assertThat(tag.getFieldsMap()).containsKeys(
                "run_id", "pipeline_name", "stage",
                "started_at", "completed_at",
                "source_type", "source_uri",
                "destination_type", "destination_uri");
        assertThat(tag.getFieldsMap().get("run_id").getStringValue()).isEqualTo("run-1");
        assertThat(tag.getFieldsMap().get("pipeline_name").getStringValue()).isEqualTo("demo_pipeline");
        assertThat(tag.getFieldsMap().get("source_uri").getStringValue()).isEqualTo("bigquery://p.ds.src");
        assertThat(tag.getFieldsMap().get("destination_uri").getStringValue()).isEqualTo("bigquery://p.ds.tgt");
    }

    @Test
    void emitMinimalEventOmitsEmptyOptionalSections() {
        // No source, no destination, no audit — pipeline only.
        LineageEvent event = LineageEvent.builder()
                .pipeline(new LineagePipeline(
                        "run-2", "p2", "validate", Optional.empty(), Optional.empty()))
                .build();

        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);
        emitter.emit(event);

        ArgumentCaptor<CreateTagRequest> captor =
                ArgumentCaptor.forClass(CreateTagRequest.class);
        verify(client).createTag(captor.capture());
        Tag tag = captor.getValue().getTag();

        assertThat(tag.getFieldsMap()).containsKeys("run_id", "pipeline_name", "stage");
        assertThat(tag.getFieldsMap()).doesNotContainKeys(
                "started_at", "completed_at",
                "source_type", "source_uri",
                "destination_type", "destination_uri");
    }

    @Test
    void emitMultipleEventsIssuesOneCreateTagPerEvent() {
        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);

        emitter.emit(fullEvent());
        emitter.emit(fullEvent());
        emitter.emit(fullEvent());

        verify(client, org.mockito.Mockito.times(3))
                .createTag(org.mockito.ArgumentMatchers.any(CreateTagRequest.class));
    }

    // --- error path --------------------------------------------------------

    @Test
    void clientExceptionPropagatesToCaller() {
        when(client.createTag(org.mockito.ArgumentMatchers.any(CreateTagRequest.class)))
                .thenThrow(new RuntimeException("data catalog unavailable"));

        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);

        assertThatThrownBy(() -> emitter.emit(fullEvent()))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("data catalog unavailable");
    }

    // --- construction & lifecycle -----------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new DataCatalogLineageEmitter(null, ENTRY, TEMPLATE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullEntryName() {
        assertThatThrownBy(() -> new DataCatalogLineageEmitter(client, null, TEMPLATE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullTagTemplate() {
        assertThatThrownBy(() -> new DataCatalogLineageEmitter(client, ENTRY, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void emitRejectsNullEvent() {
        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);
        assertThatThrownBy(() -> emitter.emit(null))
                .isInstanceOf(NullPointerException.class);
        verify(client, never()).createTag(org.mockito.ArgumentMatchers.any(CreateTagRequest.class));
    }

    @Test
    void accessorsReturnConfiguredValues() {
        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);
        assertThat(emitter.entryName()).isEqualTo(ENTRY);
        assertThat(emitter.tagTemplate()).isEqualTo(TEMPLATE);
    }

    @Test
    void closeDelegatesToClient() {
        DataCatalogLineageEmitter emitter =
                new DataCatalogLineageEmitter(client, ENTRY, TEMPLATE);
        emitter.close();
        verify(client).close();
    }
}
