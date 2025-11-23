"""
Defines a configuration transition to use exec configuration,
which results in platform-independent output paths.
"""

def _exec_transition_impl(settings, attr):
    """
    Transition to exec configuration which is more stable across platforms.
    This provides more predictable output paths.
    """
    # Return empty dict to use exec configuration
    return {}

# Define the transition object
exec_transition = transition(
    implementation = _exec_transition_impl,
    inputs = [],
    outputs = [],
)
