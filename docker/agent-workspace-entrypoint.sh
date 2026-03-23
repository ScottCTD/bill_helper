#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/scratch
mkdir -p /workspace/.ide/code-server/User
mkdir -p /workspace/.ide/extensions

PREINSTALLED_PDF_EXTENSION_VSIX=/opt/code-server-preinstalled-vsix/chocolatedesue.modern-pdf-preview-1.5.5.vsix

python - <<'PY'
import json
from pathlib import Path
import shutil

workspace_root = Path("/workspace")
ide_root = workspace_root / ".ide"
code_server_user_data_root = ide_root / "code-server"
settings_path = code_server_user_data_root / "User" / "settings.json"
scratch_root = workspace_root / "scratch"
legacy_workspace_root = workspace_root / "workspace"
legacy_user_data_root = workspace_root / "user_data"

scratch_root.mkdir(parents=True, exist_ok=True)
(workspace_root / "uploads").mkdir(parents=True, exist_ok=True)

if legacy_user_data_root.is_symlink() or legacy_user_data_root.is_file():
    legacy_user_data_root.unlink(missing_ok=True)
elif legacy_user_data_root.is_dir():
    shutil.rmtree(legacy_user_data_root, ignore_errors=True)

if legacy_workspace_root.is_dir():
    for entry in sorted(legacy_workspace_root.iterdir(), key=lambda item: item.name):
        target = scratch_root / entry.name
        if target.exists():
            continue
        shutil.move(str(entry), str(target))
    try:
        legacy_workspace_root.rmdir()
    except OSError:
        pass

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
settings_data["workbench.startupEditor"] = "none"
settings_data["workbench.sideBar.location"] = "right"
settings_data["security.workspace.trust.enabled"] = False
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
