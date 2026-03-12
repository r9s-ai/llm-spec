"""Re-export MockDataLoader from public API for backward compatibility.

New code should use: ``from llm_spec.mock import MockDataLoader``
"""

from llm_spec.mock.mock_loader import MockDataLoader

__all__ = ["MockDataLoader"]
