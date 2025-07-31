"""
Common utilities for invariant checks.
"""


class InvariantViolation(Exception):
    """Custom exception for invariant violations"""

    def __init__(self, invariant_name: str, message: str):
        self.invariant_name = invariant_name
        self.message = message
        super().__init__(f"Invariant '{invariant_name}' violated: {message}")