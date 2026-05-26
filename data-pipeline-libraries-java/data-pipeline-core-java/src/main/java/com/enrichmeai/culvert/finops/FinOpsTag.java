package com.enrichmeai.culvert.finops;

import java.util.Map;
import java.util.Objects;

/**
 * Cost-attribution metadata attached to every emitted cost metric.
 *
 * <p>The five required fields are the minimum useful tag set. {@code extra}
 * carries arbitrary additional tags the team wants to attribute by (e.g.
 * {@code business_unit}, {@code customer_id}, {@code feature_flag}).
 *
 * <p>Mirrors the Python {@code FinOpsTag} dataclass. Replaces the older
 * {@code FinOpsLabels} class on the Python side; the rename signals the
 * universal vocabulary (AWS tags, Azure tags, GCP labels all map cleanly).
 *
 * @param system      The system identifier (e.g. "retail-fdp").
 * @param environment The deployment environment ("dev", "staging", "prod").
 * @param costCenter  Cost-center attribution string.
 * @param owner       The responsible team or individual.
 * @param runId       The pipeline run that incurred the cost.
 * @param extra       Additional arbitrary tags.
 */
public record FinOpsTag(
        String system,
        String environment,
        String costCenter,
        String owner,
        String runId,
        Map<String, String> extra) {

    public FinOpsTag {
        Objects.requireNonNull(system, "system");
        Objects.requireNonNull(environment, "environment");
        Objects.requireNonNull(costCenter, "costCenter");
        Objects.requireNonNull(owner, "owner");
        Objects.requireNonNull(runId, "runId");
        if (extra == null) {
            extra = Map.of();
        } else {
            extra = Map.copyOf(extra);
        }
    }

    public static FinOpsTag of(String system, String environment, String costCenter,
                               String owner, String runId) {
        return new FinOpsTag(system, environment, costCenter, owner, runId, Map.of());
    }
}
