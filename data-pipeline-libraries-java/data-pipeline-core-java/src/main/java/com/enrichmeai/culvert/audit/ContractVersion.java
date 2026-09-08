package com.enrichmeai.culvert.audit;

/**
 * The single source of the {@code contract_version} every emitted record
 * carries ({@code docs/CONTRACT.md} §2).
 *
 * <p>One constant, in core, stamped by {@link AuditEvent}'s constructor — never
 * duplicated per adapter and never passed in by a caller. Both alternatives
 * fail the same way: an adapter drifts to a stale value, or forgets the field
 * and the row claims conformance to nothing.
 *
 * <p>§2 is explicit that producers <strong>must not</strong> increment this
 * unilaterally; the version is bumped by a PR to that document and its
 * conformance fixtures. Changing the literal below without doing that is the
 * error this class exists to make obvious.
 *
 * <p>Python mirror: {@code data_pipeline_core.audit.CONTRACT_VERSION}.
 */
public final class ContractVersion {

    /**
     * The contract version this library emits.
     *
     * <p>Still {@code 1.0.0}: §4's schema is unchanged by the 0.2.0 work, which
     * builds the first emitter that actually matches it rather than altering
     * what it says.
     */
    public static final String CURRENT = "1.0.0";

    private ContractVersion() {
        // constant holder
    }
}
