# Marker PDF Parse Follow-Up

Status: implemented and archived on 2026-03-22.

## Outcome

The prototype no longer uses the older PDF parsing pipeline. Agent PDF and image uploads now use Docling standard mode with EasyOCR, readable dated upload bundles, and text-first attachment injection.

Implemented behavior:

- uploaded files are stored under `uploads/YYYY-MM-DD/<readable bundle>/`
- the primary uploaded file is renamed to `raw.<ext>`
- Docling writes `parsed.md` plus readable sibling image files beside the primary file
- the initial agent turn receives the full `parsed.md` inline plus absolute `/workspace/uploads/...` paths
- attachment images are no longer eagerly attached on the first turn
- the runtime exposes `read_image` so the agent can load specific `/workspace/...` images on demand when visual evidence is needed
- the workspace contract is `/workspace/uploads` for read-only uploads and `/workspace/scratch` for writable work

## Notes

- Opaque hex filenames and workspace mirror paths were removed from the agent-visible contract.
- Legacy artifact storage and the old workspace mirror layer were removed instead of preserved.
- Existing upload bundles can be migrated to the readable layout with `scripts/migrate_agent_upload_bundle_paths.py`.
