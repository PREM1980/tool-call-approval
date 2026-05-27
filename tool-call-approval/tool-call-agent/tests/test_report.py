import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_service import _build_pdf, AgentService


# ── PDF generation ────────────────────────────────────────────────────────────

def test_build_pdf_returns_bytes():
    result = _build_pdf("Test Report", "Some content here.")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_pdf_starts_with_pdf_magic_bytes():
    result = _build_pdf("Test Report", "Some content here.")
    assert result[:4] == b"%PDF"


def test_build_pdf_multiline_content():
    content = "\n".join(f"Line {i}" for i in range(50))
    result = _build_pdf("Big Report", content)
    assert isinstance(result, bytes)


# ── AgentService._save_report_local ──────────────────────────────────────────

def _make_service() -> AgentService:
    repo = MagicMock()
    admin_repo = MagicMock()
    return AgentService(repository=repo, admin_repository=admin_repo)


def test_save_report_local_writes_pdf_file():
    service = _make_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        url = service._save_report_local(tmpdir, "sess-1", "My Report", "content")
        report_id = url.split("/")[-1]
        path = Path(tmpdir) / f"{report_id}.pdf"
        assert path.exists()
        assert path.stat().st_size > 0


def test_save_report_local_file_is_valid_pdf():
    service = _make_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        url = service._save_report_local(tmpdir, "sess-1", "My Report", "content")
        report_id = url.split("/")[-1]
        data = (Path(tmpdir) / f"{report_id}.pdf").read_bytes()
        assert data[:4] == b"%PDF"


def test_save_report_local_returns_session_scoped_url():
    service = _make_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        url = service._save_report_local(tmpdir, "sess-abc", "Title", "body")
        assert url.startswith("/sessions/sess-abc/reports/")
        assert url.endswith(url.split("/")[-1])


def test_save_report_local_unique_report_ids():
    service = _make_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        url1 = service._save_report_local(tmpdir, "sess-1", "Title", "body")
        url2 = service._save_report_local(tmpdir, "sess-1", "Title", "body")
        assert url1 != url2


def test_save_report_local_multiple_files_in_tmpdir():
    service = _make_service()
    with tempfile.TemporaryDirectory() as tmpdir:
        service._save_report_local(tmpdir, "sess-1", "Report A", "content a")
        service._save_report_local(tmpdir, "sess-1", "Report B", "content b")
        pdfs = list(Path(tmpdir).glob("*.pdf"))
        assert len(pdfs) == 2


# ── Repository.save_report ────────────────────────────────────────────────────

def test_repository_save_report_inserts_row():
    from repository import PostgresRepository

    repo = PostgresRepository(url="postgresql+psycopg2://localhost:5432/postgres")
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("repository.psycopg2.connect", return_value=mock_conn):
        repo.save_report("r-id", "s-id", "bucket", "reports/s-id/r-id.pdf", "Title")

    mock_cursor.execute.assert_called()
    insert_call = mock_cursor.execute.call_args_list[-1]
    sql = insert_call.args[0]
    params = insert_call.args[1]
    assert "INSERT INTO ai.reports" in sql
    assert params == ("r-id", "s-id", "bucket", "reports/s-id/r-id.pdf", "Title")
    mock_conn.commit.assert_called_once()
