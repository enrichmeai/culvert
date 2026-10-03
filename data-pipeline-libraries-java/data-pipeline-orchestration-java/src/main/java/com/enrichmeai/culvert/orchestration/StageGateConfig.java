package com.enrichmeai.culvert.orchestration;

import java.util.Objects;

/**
 * How {@link AirflowDagRenderer} (and {@link ComposerDagRenderer} through it) emits the runtime
 * re-check of a gated task (#197). See {@link StageGate} for the predicate.
 *
 * <p>The rendered DAG assigns {@link #checkerVariable()} to a module-level {@code _stage_gate}
 * once. Each gated task's callable then calls, before doing anything else, for each required stage:
 * <pre>{@code
 * _stage_gate.completion(unit=<unitExpression>, stage="<stage>", period=<periodExpression>)
 * }</pre>
 * and raises {@code AirflowException} naming the task and the stages not completed if any call
 * returns {@code None}. The task fails rather than skips, so its retries re-check the gate and a
 * closed gate never reads as success downstream.
 *
 * <p>{@code completion} is the Python side of {@code StageClaim.completion(StageKey)}. The Python
 * {@code StageClaim} mirror is #196 (waiting on decision A in #188); until it lands, the object the
 * checker expression names must be supplied by the deployment.
 *
 * <p>Both expressions are Python, evaluated inside the task callable, where {@code context} is the
 * Airflow task context.
 */
public final class StageGateConfig {

    /** The default unit: the DAG id. */
    public static final String DEFAULT_UNIT_EXPRESSION = "context[\"dag\"].dag_id";

    /** The default period: the run's logical date, as job-control wiring uses for {@code extract_date}. */
    public static final String DEFAULT_PERIOD_EXPRESSION = "context[\"ds\"]";

    private final String checkerVariable;
    private final String unitExpression;
    private final String periodExpression;

    private StageGateConfig(Builder builder) {
        this.checkerVariable = builder.checkerVariable;
        this.unitExpression = builder.unitExpression;
        this.periodExpression = builder.periodExpression;
    }

    /**
     * @param checkerVariable Python expression for the object with {@code completion(unit=, stage=, period=)}
     */
    public static Builder builder(String checkerVariable) {
        return new Builder(checkerVariable);
    }

    /** Python expression evaluating to the completion checker. */
    public String checkerVariable() {
        return checkerVariable;
    }

    /** Python expression for the unit, evaluated in the task callable. */
    public String unitExpression() {
        return unitExpression;
    }

    /** Python expression for the period, evaluated in the task callable. */
    public String periodExpression() {
        return periodExpression;
    }

    /** Builder for {@link StageGateConfig}. */
    public static final class Builder {

        private final String checkerVariable;
        private String unitExpression = DEFAULT_UNIT_EXPRESSION;
        private String periodExpression = DEFAULT_PERIOD_EXPRESSION;

        private Builder(String checkerVariable) {
            this.checkerVariable = requireText(checkerVariable, "checkerVariable");
        }

        /** Python expression for the unit. Default {@value StageGateConfig#DEFAULT_UNIT_EXPRESSION}. */
        public Builder unitExpression(String unitExpression) {
            this.unitExpression = requireText(unitExpression, "unitExpression");
            return this;
        }

        /** Python expression for the period. Default {@value StageGateConfig#DEFAULT_PERIOD_EXPRESSION}. */
        public Builder periodExpression(String periodExpression) {
            this.periodExpression = requireText(periodExpression, "periodExpression");
            return this;
        }

        /** Build an immutable {@link StageGateConfig}. */
        public StageGateConfig build() {
            return new StageGateConfig(this);
        }

        private static String requireText(String value, String name) {
            Objects.requireNonNull(value, name + " must not be null");
            if (value.isBlank()) {
                throw new IllegalArgumentException(name + " must not be blank");
            }
            return value;
        }
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof StageGateConfig)) return false;
        StageGateConfig that = (StageGateConfig) o;
        return checkerVariable.equals(that.checkerVariable)
                && unitExpression.equals(that.unitExpression)
                && periodExpression.equals(that.periodExpression);
    }

    @Override
    public int hashCode() {
        return Objects.hash(checkerVariable, unitExpression, periodExpression);
    }

    @Override
    public String toString() {
        return "StageGateConfig{"
                + "checkerVariable='" + checkerVariable + '\''
                + ", unitExpression='" + unitExpression + '\''
                + ", periodExpression='" + periodExpression + '\''
                + '}';
    }
}
