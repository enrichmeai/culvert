package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.Readiness;
import com.enrichmeai.culvert.readiness.ReadinessResolver;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * The reference: an in-memory {@link InputReadiness} that passes {@link InputReadinessContractTest},
 * so a failure in a backend's run of the suite is the backend's, not the suite's.
 */
class InMemoryInputReadinessContractTest extends InputReadinessContractTest {

    private final InMemoryInputReadiness readiness = new InMemoryInputReadiness();

    @Override
    protected InputReadiness readiness() {
        return readiness;
    }

    static final class InMemoryInputReadiness implements InputReadiness {
        private final Map<String, Set<String>> catalogue = new ConcurrentHashMap<>();
        private final List<InputAttempt> ledger = new ArrayList<>();

        @Override
        public void declareExpected(String unit, Set<String> inputs) {
            requireText(unit, "unit");
            Objects.requireNonNull(inputs, "inputs must not be null");
            if (inputs.isEmpty()) {
                throw new IllegalArgumentException("a unit must expect at least one input");
            }
            inputs.forEach(i -> requireText(i, "input"));
            catalogue.put(unit, Set.copyOf(inputs));
        }

        @Override
        public Set<String> expected(String unit) {
            return catalogue.getOrDefault(requireText(unit, "unit"), Set.of());
        }

        @Override
        public synchronized void publish(InputAttempt attempt) {
            ledger.add(Objects.requireNonNull(attempt, "attempt must not be null"));
        }

        @Override
        public synchronized Readiness readiness(String unit, String period) {
            requireText(period, "period");
            return ReadinessResolver.resolve(unit, period, expected(unit), new ArrayList<>(ledger));
        }

        private static String requireText(String value, String name) {
            Objects.requireNonNull(value, name + " must not be null");
            if (value.isBlank()) {
                throw new IllegalArgumentException(name + " must not be blank");
            }
            return value;
        }
    }
}
