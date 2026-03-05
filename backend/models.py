"""Compatibility facade for legacy ORM model imports.

Prefer importing from backend.models_agent or backend.models_finance directly.
"""

from backend.models_agent import *  # noqa: F401,F403
from backend.models_finance import *  # noqa: F401,F403
from backend.models_shared import *  # noqa: F401,F403

