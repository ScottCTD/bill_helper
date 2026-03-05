"""Compatibility facade for legacy schema imports.

Prefer importing from backend.schemas_agent or backend.schemas_finance directly.
"""

from backend.schemas_agent import *  # noqa: F401,F403
from backend.schemas_finance import *  # noqa: F401,F403

