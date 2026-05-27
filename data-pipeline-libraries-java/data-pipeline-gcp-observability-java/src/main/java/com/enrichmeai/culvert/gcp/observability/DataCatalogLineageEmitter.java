package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.lineage.LineageDestination;
import com.enrichmeai.culvert.lineage.LineageEvent;
import com.enrichmeai.culvert.lineage.LineagePipeline;
import com.enrichmeai.culvert.lineage.LineageSource;
import com.google.cloud.datacatalog.v1.CreateTagRequest;
import com.google.cloud.datacatalog.v1.DataCatalogClient;
import com.google.cloud.datacatalog.v1.Tag;
import com.google.cloud.datacatalog.v1.TagField;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/**
 * {@link LineageEmitter} implementation that writes lineage events as Data
 * Catalog tags on a configurable entry.
 *
 * <p>Each {@link LineageEvent} becomes one {@link Tag} attached to the
 * configured Data Catalog entry. The tag's fields mirror the four
 * sub-records of {@code LineageEvent} ({@code source}, {@code pipeline},
 * {@code destination}, {@code audit}), flattened to scalar string values.
 *
 * <h2>Why Data Catalog (and not Cloud Data Lineage)?</h2>
 *
 * <p>The newer Cloud Data Lineage API (artifact
 * {@code google-cloud-datalineage}) is not bundled in the GCP
 * {@code libraries-bom} this module pins. To avoid an out-of-BOM version
 * pin for a product still in transition, this Stage-2 implementation uses
 * the stable v1 {@link DataCatalogClient} and stores lineage as tags. A
 * dedicated {@code DataLineagePublisher} backed by the lineage API is
 * deferred to sprint-5 (tracked under the lineage epic).
 *
 * <h2>Construction</h2>
 *
 * <p>{@link #DataCatalogLineageEmitter(DataCatalogClient, String, String)}
 * — caller supplies an already-built client (so credentials, endpoint, and
 * lifecycle stay in the caller's hands), the fully-qualified Data Catalog
 * entry name to tag, and the tag template ID that defines the lineage tag
 * schema. The tag template must exist before {@link #emit(LineageEvent)} is
 * called; pre-provisioning is a Terraform / setup-time concern, not this
 * emitter's responsibility.
 *
 * <p>Implements {@link AutoCloseable}: {@link DataCatalogClient} is itself
 * closeable (extends {@link com.google.api.gax.core.BackgroundResource}),
 * so closing this emitter closes the wrapped client — matching the
 * {@code SecretManagerProvider} / {@code PubSubSource} pilot rule.
 *
 * <p>Sprint-2 deliverable for issue #24.
 */
public final class DataCatalogLineageEmitter implements LineageEmitter, AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(DataCatalogLineageEmitter.class);

    private final DataCatalogClient client;
    private final String entryName;
    private final String tagTemplate;

    /**
     * Primary constructor.
     *
     * @param client      Pre-built Data Catalog client. Required. Ownership
     *                    transfers to this emitter — {@link #close()} will
     *                    close it.
     * @param entryName   Fully-qualified Data Catalog entry name
     *                    ({@code projects/{p}/locations/{l}/entryGroups/{g}/entries/{e}})
     *                    to which lineage tags will be attached. Required.
     * @param tagTemplate Fully-qualified tag template name
     *                    ({@code projects/{p}/locations/{l}/tagTemplates/{t}})
     *                    that defines the lineage tag schema. Required.
     * @throws NullPointerException if any argument is null.
     */
    public DataCatalogLineageEmitter(DataCatalogClient client, String entryName, String tagTemplate) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.entryName = Objects.requireNonNull(entryName, "entryName must not be null");
        this.tagTemplate = Objects.requireNonNull(tagTemplate, "tagTemplate must not be null");
    }

    /**
     * Emit one lineage event as a Data Catalog tag on the configured entry.
     *
     * <p>If the underlying Data Catalog call throws (network, auth, quota,
     * tag template mismatch), the exception is propagated to the caller.
     * Callers that batch their own events for at-least-once semantics
     * should catch and retry as appropriate.
     *
     * @param event The lineage event to emit. Required.
     * @throws NullPointerException if {@code event} is null.
     */
    @Override
    public void emit(LineageEvent event) {
        Objects.requireNonNull(event, "event must not be null");

        Tag.Builder tag = Tag.newBuilder()
                .setTemplate(tagTemplate);

        Map<String, String> fields = flatten(event);
        for (Map.Entry<String, String> e : fields.entrySet()) {
            tag.putFields(e.getKey(), TagField.newBuilder()
                    .setStringValue(e.getValue())
                    .build());
        }

        CreateTagRequest request = CreateTagRequest.newBuilder()
                .setParent(entryName)
                .setTag(tag.build())
                .build();

        client.createTag(request);
        LOG.debug("emitted lineage tag for entry {}", entryName);
    }

    /** The Data Catalog entry name lineage tags are attached to. */
    public String entryName() {
        return entryName;
    }

    /** The tag template the emitted tags reference. */
    public String tagTemplate() {
        return tagTemplate;
    }

    @Override
    public void close() {
        client.close();
    }

    /**
     * Flatten a {@link LineageEvent} into the scalar string-field shape
     * Data Catalog tags require. Empty optional sub-records are skipped so
     * the resulting tag stays compact.
     */
    private static Map<String, String> flatten(LineageEvent event) {
        Map<String, String> out = new HashMap<>();
        event.source().ifPresent(s -> putSource(out, s));
        event.pipeline().ifPresent(p -> putPipeline(out, p));
        event.destination().ifPresent(d -> putDestination(out, d));
        event.audit().ifPresent(a -> out.put("audit", a.toString()));
        return out;
    }

    private static void putSource(Map<String, String> out, LineageSource s) {
        out.put("source_type", s.type());
        out.put("source_uri", s.uri());
    }

    private static void putPipeline(Map<String, String> out, LineagePipeline p) {
        out.put("run_id", p.runId());
        out.put("pipeline_name", p.pipelineName());
        out.put("stage", p.stage());
        p.startedAt().ifPresent(t -> out.put("started_at", t.toString()));
        p.completedAt().ifPresent(t -> out.put("completed_at", t.toString()));
    }

    private static void putDestination(Map<String, String> out, LineageDestination d) {
        out.put("destination_type", d.type());
        out.put("destination_uri", d.uri());
    }
}
