"""Automatic Lumen Condensor rules engine.

The package deliberately has no dependency on HTTP or browser code.  Humans,
tests, and a future AI all consume the same observation/legal-action contract.
"""

from .engine import AutomaticGameEngine, EngineError, IllegalAction, StaleState

__all__ = [
    'AutomaticGameEngine',
    'EngineError',
    'IllegalAction',
    'StaleState',
]
