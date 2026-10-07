package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.autoconfig.DiscoveryFailure;
import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.StageClaim;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * The three control-plane stores this deployment runs on. On PostgreSQL all three come from
 * {@code data-pipeline-postgres}, which reads {@code CULVERT_POSTGRES_URL},
 * {@code CULVERT_POSTGRES_USER} and {@code CULVERT_POSTGRES_PASSWORD}.
 */
public record ControlPlane(JobControlRepository jobControl, StageClaim claims, InputReadiness readiness) {

    public ControlPlane {
        Objects.requireNonNull(jobControl, "jobControl must not be null");
        Objects.requireNonNull(claims, "claims must not be null");
        Objects.requireNonNull(readiness, "readiness must not be null");
    }

    /**
     * The stores {@link AutoConfig} finds. This deployment refuses to run without any of them: a
     * run without claims could double-start a stage, and one without readiness could publish
     * from an input that never validated.
     *
     * @throws IllegalStateException naming each missing store and every discovery failure
     */
    public static ControlPlane discover(AutoConfig config) {
        Optional<JobControlRepository> jobControl = config.jobControl();
        Optional<StageClaim> claims = config.stageClaim();
        Optional<InputReadiness> readiness = config.inputReadiness();
        List<String> missing = new ArrayList<>();
        if (jobControl.isEmpty()) {
            missing.add("JobControlRepository");
        }
        if (claims.isEmpty()) {
            missing.add("StageClaim");
        }
        if (readiness.isEmpty()) {
            missing.add("InputReadiness");
        }
        if (!missing.isEmpty()) {
            StringBuilder why = new StringBuilder("reference-e2e-gcp needs " + String.join(", ", missing)
                    + " on PostgreSQL. Set CULVERT_POSTGRES_URL (and CULVERT_POSTGRES_USER, "
                    + "CULVERT_POSTGRES_PASSWORD).");
            for (DiscoveryFailure failure : config.failures()) {
                why.append(" Discovery failed for ").append(failure.providerClass()).append(": ")
                        .append(failure.cause());
            }
            throw new IllegalStateException(why.toString());
        }
        return new ControlPlane(jobControl.get(), claims.get(), readiness.get());
    }
}
