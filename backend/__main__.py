# CALLING SPEC:
# - Purpose: provide the `__main__` module.
# - Inputs: callers that import `backend/__main__.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `__main__`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from backend.main import main


if __name__ == "__main__":
    main()
