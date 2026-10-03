package com.enrichmeai.culvert.readiness;

/** Where one expected input stands for a unit and period. Only {@link #READY} opens a gate. */
public enum InputState {

    /** An attempt validated it, and no failure that a retry has not answered stands against it. */
    READY,

    /** No attempt has been recorded for this period. */
    MISSING,

    /** An attempt is under way or produced it without validation yet. */
    PENDING,

    /** An attempt failed and no retry of it has been recorded. A failed input is not a missing one. */
    FAILED
}
