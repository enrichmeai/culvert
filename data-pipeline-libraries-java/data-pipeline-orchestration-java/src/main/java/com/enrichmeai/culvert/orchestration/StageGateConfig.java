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
 * <p>{@code completion} is the Python side of {@code StageClaim.completion(StageKey)}. Culvert's
 * Python {@code StageClaim} (#196) takes a {@code StageKey}; wrap it for the gate with
 * {@code data_pipeline_core.stage_claim_api.CompletionChecker}, for example
 * {@code CompletionChecker(PostgresStageClaim())}.
 *
 * <p>A task gated on readiness ({@link StageGate#READY}, #230) calls, after any stage check:
 * <pre>{@code
 * _input_readiness.not_ready(unit=<unitExpression>, period=<periodExpression>)
 * }</pre>
 * on the object {@link #readinessVariable()} names, assigned once to a module-level
 * {@code _input_readiness}. It must return a list of strings, one per expected input that is not
 * ready, empty when every input is ready, and a non-empty list when no inputs are declared for the
 * unit and period (an undeclared unit is never ready). The task raises {@code AirflowException}
 * naming itself and each entry. It is the Python side of {@code InputReadiness.readiness(unit, period)};
 * Culvert ships no Python {@code InputReadiness} yet, so the deployment supplies the object.
 *
 * <p>A config needs a checker, a readiness variable, or both; the renderer refuses a DAG with a
 * gate kind the config has no variable for.
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
    private final String readinessVariable;
    private final String unitExpression;
    private final String periodExpression;

    private StageGateConfig(Builder builder) {
        this.checkerVariable = builder.checkerVariable;
        this.readinessVariable = builder.readinessVariable;
        this.unitExpression = builder.unitExpression;
        this.periodExpression = builder.periodExpression;
    }

    /**
     * @param checkerVariable Python expression for the object with {@code completion(unit=, stage=, period=)}
     */
    public static Builder builder(String checkerVariable) {
        Builder builder = new Builder();
        builder.checkerVariable = Builder.requireText(checkerVariable, "checkerVariable");
        return builder;
    }

    /**
     * A builder with no completion checker, for DAGs gated on readiness only. Set
     * {@link Builder#readinessVariable(String)} before {@link Builder#build()}.
     */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Python expression evaluating to the completion checker, or {@code null} if this config
     * re-checks readiness only.
     */
    public String checkerVariable() {
        return checkerVariable;
    }

    /**
     * Python expression evaluating to the readiness checker ({@code not_ready(unit=, period=)}),
     * or {@code null} if this config re-checks stage completions only.
     */
    public String readinessVariable() {
        return readinessVariable;
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

        private String checkerVariable;
        private String readinessVariable;
        private String unitExpression = DEFAULT_UNIT_EXPRESSION;
        private String periodExpression = DEFAULT_PERIOD_EXPRESSION;

        private Builder() {
        }

        /**
         * Python expression for the object with {@code not_ready(unit=, period=)} (#230). Needed
         * when any task carries {@link StageGate#READY}.
         */
        public Builder readinessVariable(String readinessVariable) {
            this.readinessVariable = requireText(readinessVariable, "readinessVariable");
            return this;
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

        /**
         * Build an immutable {@link StageGateConfig}.
         *
         * @throws IllegalStateException if neither a checker nor a readiness variable is set
         */
        public StageGateConfig build() {
            if (checkerVariable == null && readinessVariable == null) {
                throw new IllegalStateException(
                        "A StageGateConfig needs a checkerVariable, a readinessVariable, or both");
            }
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
        return Objects.equals(checkerVariable, that.checkerVariable)
                && Objects.equals(readinessVariable, that.readinessVariable)
                && unitExpression.equals(that.unitExpression)
                && periodExpression.equals(that.periodExpression);
    }

    @Override
    public int hashCode() {
        return Objects.hash(checkerVariable, readinessVariable, unitExpression, periodExpression);
    }

    private static String quoted(String value) {
        return value == null ? "null" : "'" + value + "'";
    }

    @Override
    public String toString() {
        return "StageGateConfig{"
                + "checkerVariable=" + quoted(checkerVariable)
                + ", readinessVariable=" + quoted(readinessVariable)
                + ", unitExpression='" + unitExpression + '\''
                + ", periodExpression='" + periodExpression + '\''
                + '}';
    }
}
