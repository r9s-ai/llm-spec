"""Re-export MockDataLoader from public API for backward compatibility.

New code should use: ``from llm_spec.testing import MockDataLoader``
"""

from llm_spec.testing.mock_loader import MockDataLoader

__all__ = ["MockDataLoader"]
