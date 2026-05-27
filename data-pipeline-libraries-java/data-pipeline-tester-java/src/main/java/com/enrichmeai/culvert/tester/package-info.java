/**
 * Mockito-helper fixture builders for the Culvert framework's contract
 * Protocols.
 *
 * <p>Each public class in this package targets one contract from
 * {@code com.enrichmeai.culvert.contracts} and exposes static factory
 * methods that return a pre-configured Mockito mock (or, in the case of
 * {@link com.enrichmeai.culvert.tester.FinOpsSinkFixtures}, a tiny
 * real implementation). Consumers add further stubbing on top with
 * standard Mockito calls when their tests need behaviour beyond the
 * fixture defaults.
 *
 * <p>Sprint-2 deliverable (issue #26). Sprint-5 will add a full contract
 * test harness on top of these fixtures.
 */
package com.enrichmeai.culvert.tester;
