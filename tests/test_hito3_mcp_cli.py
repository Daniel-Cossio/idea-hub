"""Hito 3: Tests — Puente para Agentes (ideas-mcp + idea-cli Bootstrap)."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.mcp_server import (
    list_ideas,
    get_idea_spec,
    update_idea_spec,
    set_idea_status,
    append_idea_note,
)
from app.cli import app as cli_app


# ============================================================
# Tests de MCP Server
# ============================================================
class TestMCP:
    @pytest.fixture
    def service(self, tmp_path):
        """Servicio de ideas con directorio temporal."""
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        from app.services.idea_service import IdeaService
        from app.models import IdeaCreateRequest
        s = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        s.create_idea(IdeaCreateRequest(raw_input="Test spec", source_type="text"))
        return s

    def test_list_ideas(self, service):
        """list_ideas devuelve las ideas del vault."""
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = list_ideas()
            assert isinstance(result, list)
            assert len(result) >= 1

    def test_get_idea_spec(self, service):
        """get_idea_spec devuelve el SPEC.md completo."""
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = get_idea_spec("001")
            assert "id" in result
            assert "spec_body" in result
            assert "capture_log" in result

    def test_update_idea_spec(self, service):
        """update_idea_spec actualiza el spec_body."""
        from app.mcp_server import update_idea_spec as _update
        new_spec = "# Updated Spec\n\nNew content here."
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = _update("001", new_spec)
            assert "001" in str(result.get("id", ""))

    def test_set_idea_status(self, service):
        """set_idea_status actualiza el estado correctamente."""
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = set_idea_status("001", "in_progress")
            assert result is not None

    def test_append_idea_note(self, service):
        """append_idea_note agrega una nota a la bitácora."""
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = append_idea_note("001", "Progress note")
            assert result is not None

    def test_list_ideas_with_filters(self, service):
        """list_ideas filtra correctamente por status, tag y query."""
        with patch("app.mcp_server.get_default_idea_service", return_value=service):
            result = list_ideas(status="inbox", tag="test", query="test")
            assert isinstance(result, list)


# ============================================================
# Tests de CLI
# ============================================================
class TestCLI:
    @pytest.fixture
    def runner(self, tmp_path):
        """Runner de CLI con directorio temporal."""
        from typer.testing import CliRunner
        runner = CliRunner()
        import app.config as config_module
        import app.cli as cli_module

        class FakeSettings:
            data_dir = str(tmp_path / "data")
            sqlite_path = str(tmp_path / "data" / "index.sqlite")
            api_token = ""
            web_password = ""
            ai_base_url = "https://api.groq.com/openai/v1"
            ai_api_key = "test-key"
            telegram_bot_token = ""
            telegram_allowed_user_id = ""
            disable_bot_polling = False

        original = getattr(config_module, 'Settings', None)
        config_module.Settings = FakeSettings  # type: ignore
        cli_module.Settings = FakeSettings

        yield runner

        if original:
            config_module.Settings = original  # type: ignore

    def test_cli_help(self, runner):
        """El CLI muestra ayuda correctamente."""
        result = runner.invoke(cli_app, ["--help"])
        assert result.exit_code == 0
        assert "IdeaHub CLI" in result.stdout

    def test_cli_list_empty(self, runner):
        """El CLI lista ideas (puede estar vacío)."""
        result = runner.invoke(cli_app, ["list"])
        assert result.exit_code == 0

    def test_cli_init_creates_project(self, tmp_path):
        """idea-cli init crea la carpeta y archivos."""
        from typer.testing import CliRunner
        runner = CliRunner()
        import app.config as config_module
        import app.cli as cli_module

        # Crear estructura de vault y datos
        _vault_dir = tmp_path / "vault" / "001-test-idea"
        _vault_dir.mkdir(parents=True)
        _spec_file = _vault_dir / "SPEC.md"
        _spec_file.write_text(
            "---\nid: 001\nslug: 001-test\ntitle: Test Idea\nstatus: inbox\npriority: medium\n---\n\nTest spec body\n",
            encoding="utf-8",
        )

        _data_dir = tmp_path / "data"
        _data_dir.mkdir(exist_ok=True)
        _sqlite_path = _data_dir / "index.sqlite"

        from app.services.idea_service import IdeaService
        from app.models import IdeaCreateRequest

        # Crear idea en el servicio para que exista en el DB
        svc = IdeaService(data_dir=str(_data_dir), sqlite_path=str(_sqlite_path))
        svc.create_idea(IdeaCreateRequest(raw_input="Test spec body", source_type="text"))
        svc.index.close()

        class FakeSettings:
            data_dir = str(_data_dir)
            sqlite_path = str(_sqlite_path)
            api_token = ""
            web_password = ""
            ai_base_url = "https://api.groq.com/openai/v1"
            ai_api_key = "test-key"
            telegram_bot_token = ""
            telegram_allowed_user_id = ""
            disable_bot_polling = False

        original = getattr(config_module, 'Settings', None)
        config_module.Settings = FakeSettings  # type: ignore
        cli_module.Settings = FakeSettings

        _target = str(tmp_path / "projects")
        result = runner.invoke(cli_module.app, ["init", "001", "--target-dir", _target])

        if original:
            config_module.Settings = original  # type: ignore

        assert result.exit_code == 0, f"CLI error: {result.output}\n{result.exception}"
        _project_dir = tmp_path / "projects" / "001-test-idea"
        assert _project_dir.exists(), f"Project dir missing: {_project_dir}"
        assert (_project_dir / "SPEC.md").exists()
        assert (_project_dir / "TASKS.md").exists()
        assert (_project_dir / ".gitignore").exists()


# ============================================================
# Tests de Integration Hito 3
# ============================================================
class TestHito3Integration:
    @pytest.fixture
    def service(self, tmp_path):
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        return IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)

    def test_init_project_updates_state(self, service, tmp_path):
        """init_project actualiza el estado a in_progress con repo_path."""
        from app.models import IdeaCreateRequest
        service.create_idea(IdeaCreateRequest(raw_input="Test", source_type="text"))
        target = str(tmp_path / "output")

        result = service.init_project("001", target)
        assert result["status"] == "in_progress"
        assert "slug" in result
        assert "project_dir" in result
        assert "repo_path" in result
