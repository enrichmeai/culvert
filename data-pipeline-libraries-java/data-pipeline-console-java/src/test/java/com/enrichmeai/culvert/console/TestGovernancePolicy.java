package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.RetentionPolicy;

import java.util.Optional;

/** A provider CulvertCliTest registers on a throwaway class loader, to see a bound contract. */
public final class TestGovernancePolicy implements GovernancePolicy {

    @Override
    public DataClassification classify(String field, String table) {
        return DataClassification.INTERNAL;
    }

    @Override
    public Optional<MaskingPolicy> maskingFor(String field, String table) {
        return Optional.empty();
    }

    @Override
    public Optional<RetentionPolicy> retentionFor(String table) {
        return Optional.empty();
    }
}
