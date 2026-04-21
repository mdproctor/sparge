package io.sparge.server;

import java.util.Map;

/**
 * A replayable refinement rule stored in state.refinement.accepted.
 * fence_index + fingerprint + contentSample together locate the target
 * fence even when surrounding text changes between MD regenerations.
 */
public record RefinementRule(
    String check,
    int    fenceIndex,
    String fingerprint,
    String contentSample,
    Map<String, String> fix
) {}
