#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/workspace
mkdir -p /workspace/.ide/code-server/User
mkdir -p /workspace/.ide/extensions

PREINSTALLED_PDF_EXTENSION_VSIX=/opt/code-server-preinstalled-vsix/chocolatedesue.modern-pdf-preview-1.5.5.vsix

python - <<'PY'
import json
from pathlib import Path

workspace_root = Path("/workspace")
visible_user_data_root = workspace_root / "user_data"
mounted_user_data_root = Path("/data/user_data")
ide_root = workspace_root / ".ide"
code_server_user_data_root = ide_root / "code-server"
settings_path = code_server_user_data_root / "User" / "settings.json"
if visible_user_data_root.exists() and not visible_user_data_root.is_symlink():
    raise SystemExit("/workspace/user_data must be a symlink to /data/user_data")

if not visible_user_data_root.exists():
    visible_user_data_root.symlink_to(mounted_user_data_root)

settings_data: dict[str, object] = {}

if settings_path.exists():
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            settings_data = loaded
    except json.JSONDecodeError:
        settings_data = {}

settings_data["chat.disableAIFeatures"] = True
settings_data["chat.agent.enabled"] = False
settings_data["workbench.sideBar.location"] = "right"
settings_data["modernPdfViewer.defaultSpreadMode"] = "none"
settings_path.write_text(
    json.dumps(settings_data, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

rm -f /workspace/.ide/extensions/.obsolete
code-server \
  --install-extension "${PREINSTALLED_PDF_EXTENSION_VSIX}" \
  --extensions-dir /workspace/.ide/extensions \
  --user-data-dir /workspace/.ide/code-server \
  --force

exec code-server /workspace \
  --bind-addr 0.0.0.0:13337 \
  --auth none \
  --disable-proxy \
  --user-data-dir /workspace/.ide/code-server \
  --extensions-dir /workspace/.ide/extensions
