from __future__ import annotations

from types import SimpleNamespace


def test_extract_pdf_text_with_tesseract_uses_subprocess_timeout(monkeypatch, tmp_path):
    from backend.services.agent import attachment_content as attachments

    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    class _FakePixmap:
        def save(self, _path) -> None:
            return

    class _FakePage:
        def get_pixmap(self, **_kwargs):
            return _FakePixmap()

    class _FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> bool:
            return False

        def __iter__(self):
            return iter([_FakePage()])

    class _CompletedProcess:
        stdout = " OCR total CAD 123.45 "

    captured_timeout = {"value": None}

    def _fake_run(*_args, **kwargs):
        captured_timeout["value"] = kwargs.get("timeout")
        return _CompletedProcess()

    monkeypatch.setattr(attachments.shutil, "which", lambda _name: "/usr/bin/tesseract")
    monkeypatch.setattr(attachments.pymupdf, "open", lambda _path: _FakeDoc())
    monkeypatch.setattr(attachments.subprocess, "run", _fake_run)

    parsed = attachments.extract_pdf_text_with_tesseract(str(pdf_path))

    assert parsed == "OCR total CAD 123.45"
    assert captured_timeout["value"] == attachments.PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS


def test_extract_pdf_text_with_tesseract_records_timeout_failure_code(monkeypatch, tmp_path):
    from backend.services.agent import attachment_content as attachments

    pdf_path = tmp_path / "timeout.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    class _FakePixmap:
        def save(self, _path) -> None:
            return

    class _FakePage:
        def get_pixmap(self, **_kwargs):
            return _FakePixmap()

    class _FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> bool:
            return False

        def __iter__(self):
            return iter([_FakePage()])

    captured: dict[str, object] = {}

    def _capture_recoverable(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(value=kwargs.get("fallback"), error=None)

    def _timeout_run(*_args, **_kwargs):
        raise attachments.subprocess.TimeoutExpired(cmd=["tesseract"], timeout=1)

    monkeypatch.setattr(attachments.shutil, "which", lambda _name: "/usr/bin/tesseract")
    monkeypatch.setattr(attachments.pymupdf, "open", lambda _path: _FakeDoc())
    monkeypatch.setattr(attachments.subprocess, "run", _timeout_run)
    monkeypatch.setattr(attachments, "recoverable_result", _capture_recoverable)

    parsed = attachments.extract_pdf_text_with_tesseract(str(pdf_path))

    assert parsed is None
    context = captured.get("context")
    assert isinstance(context, dict)
    assert context.get("failure_code") == "ocr_timeout"
    assert context.get("timeout_seconds") == attachments.PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS
