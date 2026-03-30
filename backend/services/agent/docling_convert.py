# CALLING SPEC:
# - Purpose: run Docling standard pipeline (EasyOCR) on a PDF or image and rewrite bundle outputs to readable sibling files.
# - Inputs: existing source file path under an agent upload bundle directory.
# - Outputs: writes `parsed.md` and deterministic image assets beside the source file; raises on failure.
# - Side effects: filesystem writes and file renames; loads Docling/EasyOCR models on first use.
from __future__ import annotations

from functools import lru_cache
import logging
import re
from pathlib import Path

from docling_core.types.doc import ImageRefMode

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

logger = logging.getLogger(__name__)

_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_DOC_IMAGES_SCALE = 1.5
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _rewrite_markdown_image_paths_to_basenames(markdown: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        alt, raw_path = match.group(1), match.group(2).strip()
        basename = Path(raw_path.replace("\\", "/")).name
        return f"![{alt}]({basename})"

    return _MARKDOWN_IMAGE.sub(replacer, markdown)


@lru_cache(maxsize=2)
def _build_converter(*, is_pdf: bool) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.ocr_options = EasyOcrOptions()
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True
    pipeline_options.images_scale = _DOC_IMAGES_SCALE
    pdf_option = PdfFormatOption(pipeline_options=pipeline_options)
    image_option = ImageFormatOption(pipeline_options=pipeline_options)
    if is_pdf:
        return DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: pdf_option},
        )
    return DocumentConverter(
        allowed_formats=[InputFormat.IMAGE],
        format_options={InputFormat.IMAGE: image_option},
    )


def _classified_prefix(raw_name: str) -> str:
    lowered = raw_name.lower()
    if "page" in lowered:
        return "page"
    if "table" in lowered:
        return "table"
    if "fig" in lowered or "picture" in lowered:
        return "figure"
    return "image"


def _replace_markdown_image_names(markdown: str, name_map: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        alt, raw_path = match.group(1), match.group(2).strip()
        basename = Path(raw_path.replace("\\", "/")).name
        replacement = name_map.get(basename, basename)
        return f"![{alt}]({replacement})"

    return _MARKDOWN_IMAGE.sub(replacer, markdown)


def _bundle_image_files(bundle_dir: Path, *, primary_filename: str) -> list[Path]:
    files: list[Path] = []
    for path in sorted(bundle_dir.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        if path.parent == bundle_dir and path.name in {"parsed.md", primary_filename}:
            continue
        if path.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        files.append(path)
    return files


def _prune_empty_dirs(bundle_dir: Path) -> None:
    for directory in sorted(
        [path for path in bundle_dir.rglob("*") if path.is_dir()],
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            continue


def _rename_paths_atomically(name_map: dict[Path, Path]) -> None:
    temp_map: dict[Path, Path] = {}
    for index, source in enumerate(sorted(name_map, key=lambda path: path.name)):
        target = name_map[source]
        if source.resolve() == target.resolve():
            continue
        temp = source.with_name(f".rename-{index}-{source.name}")
        source.rename(temp)
        temp_map[temp] = target
    for temp, target in temp_map.items():
        temp.rename(target)


def normalize_docling_bundle_outputs(
    bundle_dir: Path,
    *,
    primary_filename: str,
) -> Path:
    """Rewrite bundle markdown/image output to deterministic sibling names."""
    md_path = bundle_dir / "parsed.md"
    raw_md = md_path.read_text(encoding="utf-8", errors="replace")
    markdown = _rewrite_markdown_image_paths_to_basenames(raw_md)

    name_map: dict[str, str] = {}
    rename_map: dict[Path, Path] = {}
    counters: dict[str, int] = {}

    all_images = _bundle_image_files(bundle_dir, primary_filename=primary_filename)
    images_by_basename: dict[str, list[Path]] = {}
    for image in all_images:
        images_by_basename.setdefault(image.name, []).append(image)

    referenced_sources: set[Path] = set()
    for _alt, raw_path in _MARKDOWN_IMAGE.findall(markdown):
        basename = Path(raw_path.strip().replace("\\", "/")).name
        matches = images_by_basename.get(basename, [])
        source = matches[0] if matches else bundle_dir / basename
        if (
            basename in name_map
            or not source.is_file()
        ):
            continue
        referenced_sources.add(source.resolve())
        prefix = _classified_prefix(basename)
        counters[prefix] = counters.get(prefix, 0) + 1
        new_name = f"{prefix}-{counters[prefix]}{source.suffix.lower()}"
        name_map[basename] = new_name
        rename_map[source] = bundle_dir / new_name

    for source in all_images:
        if source.resolve() in referenced_sources:
            continue
        prefix = _classified_prefix(source.name)
        counters[prefix] = counters.get(prefix, 0) + 1
        new_name = f"{prefix}-{counters[prefix]}{source.suffix.lower()}"
        name_map[source.name] = new_name
        rename_map[source] = bundle_dir / new_name

    _rename_paths_atomically(rename_map)
    md_path.write_text(_replace_markdown_image_names(markdown, name_map), encoding="utf-8")
    _prune_empty_dirs(bundle_dir)
    return md_path


def convert_upload_bundle_source(source_path: Path, *, is_pdf: bool) -> Path:
    """Run Docling and write ``parsed.md`` with deterministic image siblings into ``source_path.parent``."""
    path = Path(source_path)
    if not path.is_file():
        raise FileNotFoundError(f"Docling source missing: {path}")
    bundle_dir = path.parent
    md_path = bundle_dir / "parsed.md"
    converter = _build_converter(is_pdf=is_pdf)
    try:
        result = converter.convert(path)
    except Exception as exc:
        logger.exception(
            "docling.convert_failed path=%s is_pdf=%s",
            path,
            is_pdf,
        )
        raise RuntimeError("Document conversion failed.") from exc
    try:
        result.document.save_as_markdown(md_path, image_mode=ImageRefMode.REFERENCED)
    except Exception as exc:
        logger.exception(
            "docling.save_markdown_failed path=%s",
            md_path,
        )
        raise RuntimeError("Failed to export converted markdown.") from exc
    if not md_path.is_file():
        raise RuntimeError("Docling did not produce parsed.md.")
    return normalize_docling_bundle_outputs(bundle_dir, primary_filename=path.name)
