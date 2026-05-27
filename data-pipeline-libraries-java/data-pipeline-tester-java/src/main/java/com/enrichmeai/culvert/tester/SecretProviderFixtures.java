package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.SecretProvider;
import org.mockito.Mockito;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.Set;

/**
 * Mockito-mock fixture builders for {@link SecretProvider}.
 *
 * <p>Each method returns a Mockito mock pre-wired with {@code when(...)}
 * stubs that match the documented {@link SecretProvider} contract. Consumers
 * use these to skip the {@code Mockito.mock(SecretProvider.class)} +
 * {@code when(...).thenReturn(...)} boilerplate in their own tests.
 *
 * <p>This class is non-instantiable.
 */
public final class SecretProviderFixtures {

    private SecretProviderFixtures() {
        throw new AssertionError("no instances");
    }

    /**
     * Mock {@link SecretProvider} backed by a static map.
     *
     * <p>{@code get(name, version)} and {@code get(name)} both look up
     * {@code name} in {@code secrets} (version is ignored — fixtures don't
     * model version history). Missing names raise
     * {@link NoSuchElementException}, matching the contract.
     *
     * @param secrets Secret name -> value map. Must not be null.
     * @return a Mockito mock of {@link SecretProvider}.
     */
    public static SecretProvider staticSecretProvider(Map<String, String> secrets) {
        Objects.requireNonNull(secrets, "secrets must not be null");
        SecretProvider mock = Mockito.mock(SecretProvider.class);
        // Two-arg get(name, version): look up name, ignore version.
        Mockito.when(mock.get(Mockito.anyString(), Mockito.anyString()))
                .thenAnswer(invocation -> {
                    String name = invocation.getArgument(0);
                    String value = secrets.get(name);
                    if (value == null) {
                        throw new NoSuchElementException("Secret not found: " + name);
                    }
                    return value;
                });
        // Single-arg get(name): delegate to the two-arg form via the real
        // default method. Mockito mocks default methods to return null
        // unless we tell it to call the real method.
        Mockito.when(mock.get(Mockito.anyString())).thenCallRealMethod();
        return mock;
    }

    /**
     * Mock {@link SecretProvider} that throws {@code error} on every
     * {@code get} call. Use to simulate a misconfigured Secret Manager or
     * an IAM-denied lookup.
     *
     * @param error The exception to throw. Must not be null.
     * @return a Mockito mock of {@link SecretProvider}.
     */
    public static SecretProvider failingSecretProvider(RuntimeException error) {
        Objects.requireNonNull(error, "error must not be null");
        SecretProvider mock = Mockito.mock(SecretProvider.class);
        Mockito.when(mock.get(Mockito.anyString(), Mockito.anyString())).thenThrow(error);
        Mockito.when(mock.get(Mockito.anyString())).thenThrow(error);
        return mock;
    }

    /**
     * Mock {@link SecretProvider} that returns successfully for every secret
     * EXCEPT the names in {@code notFound} — those raise
     * {@link NoSuchElementException}, matching the contract for missing
     * secrets.
     *
     * <p>Use to test "what happens if exactly secret X is missing" without
     * having to populate a full secret map.
     *
     * @param names Secret names that should raise {@link NoSuchElementException}.
     * @return a Mockito mock of {@link SecretProvider}.
     */
    public static SecretProvider notFoundFor(String... names) {
        Objects.requireNonNull(names, "names must not be null");
        Set<String> missing = new HashSet<>(Arrays.asList(names));
        SecretProvider mock = Mockito.mock(SecretProvider.class);
        Mockito.when(mock.get(Mockito.anyString(), Mockito.anyString()))
                .thenAnswer(invocation -> {
                    String name = invocation.getArgument(0);
                    if (missing.contains(name)) {
                        throw new NoSuchElementException("Secret not found: " + name);
                    }
                    return "fixture-value-for-" + name;
                });
        Mockito.when(mock.get(Mockito.anyString())).thenCallRealMethod();
        return mock;
    }
}
