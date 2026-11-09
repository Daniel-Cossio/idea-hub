"""Hito 1: Tests — Core Foundation (config, models, storage, services)."""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Asegurar que el paquete app sea importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.models import (
    IdeaDocument,
    IdeaCreateRequest,
    IdeaUpdateRequest,
    IdeaLogAppendRequest,
    IdeaStatus,
    IdeaPriority,
)
from app.storage.markdown_vault import (
    LOG_SECTION_HEADER,
    LOG_DELIMITER,
    parse_spec_file,
    write_spec_file,
    read_spec_file,
    update_spec_body,
    append_capture_log,
    generate_slug,
)
from app.storage.sqlite_index import SQLiteIndex
from app.services.idea_service import IdeaService


# ============================================================
# Tests de Configuración
# ============================================================
class TestConfig:
    def test_settings_loads_from_env(self):
        """La configuración carga desde variables de entorno."""
        s = Settings()
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 8090

    def test_settings_default_values(self):
        """Los valores por defecto son correctos."""
        s = Settings()
        assert s.ai_base_url == "https://api.groq.com/openai/v1"
        assert s.disable_bot_polling is False


# ============================================================
# Tests de Modelos
# ============================================================
class TestModels:
    def test_idea_status_enum(self):
        """IdeaStatus tiene todos los valores esperados."""
        assert IdeaStatus.INBOX.value == "inbox"
        assert IdeaStatus.REFINING.value == "refining"
        assert IdeaStatus.AGENT_READY.value == "agent_ready"
        assert IdeaStatus.IN_PROGRESS.value == "in_progress"
        assert IdeaStatus.DONE.value == "done"
        assert IdeaStatus.ARCHIVED.value == "archived"

    def test_idea_priority_enum(self):
        """IdeaPriority tiene todos los valores esperados."""
        assert IdeaPriority.LOW.value == "low"
        assert IdeaPriority.MEDIUM.value == "medium"
        assert IdeaPriority.HIGH.value == "high"
        assert IdeaPriority.CRITICAL.value == "critical"

    def test_idea_document_creation(self):
        """Se puede crear un IdeaDocument."""
        doc = IdeaDocument(
            id="001",
            slug="001-test-idea",
            title="Test Idea",
            status=IdeaStatus.INBOX,
            priority=IdeaPriority.HIGH,
            tags=["test"],
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )
        assert doc.id == "001"
        assert len(doc.tags) == 1

    def test_idea_create_request(self):
        """IdeaCreateRequest valida correctamente."""
        req = IdeaCreateRequest(raw_input="Test input", source_type="text")
        assert req.title is None
        assert req.source_type == "text"

    def test_idea_update_request(self):
        """IdeaUpdateRequest acepta campos opcionales."""
        req = IdeaUpdateRequest(title="New Title", status=IdeaStatus.REFINING)
        assert req.title == "New Title"
        assert req.status == IdeaStatus.REFINING


# ============================================================
# Tests de Markdown Vault
# ============================================================
class TestMarkdownVault:
    @pytest.fixture
    def tmp_spec_dir(self, tmp_path):
        """Directorio temporal para SPEC.md."""
        spec_dir = tmp_path / "vault" / "001-test-idea"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "SPEC.md"
        return spec_dir, spec_file

    def test_log_delimiter_format(self):
        """El delimitador de bitácora tiene el formato esperado."""
        assert LOG_SECTION_HEADER == "## 💬 Bitácora de Captura (Telegram Log)"
        assert "\n---\n\n" in LOG_DELIMITER

    def test_parse_spec_file_no_log(self, tmp_spec_dir):
        """Parsea un SPEC.md sin bitácora."""
        spec_dir, spec_file = tmp_spec_dir
        metadata = {
            "id": "001",
            "slug": "001-test",
            "title": "Test",
            "status": "inbox",
            "priority": "medium",
        }
        spec_content = "# Test Spec\n\nBody content here."
        tmp = spec_file.with_suffix(".tmp")
        yaml_section = "---\n  id: 001\n  slug: 001-test\n  title: Test\n  status: inbox\n  priority: medium\n---\n\n"
        with open(spec_file, "w") as f:
            f.write(yaml_section + spec_content)
        meta, body, log = parse_spec_file(spec_file)
        assert "Test Spec" in body
        assert log == ""

    def test_parse_spec_file_with_log(self, tmp_spec_dir):
        """Parsea un SPEC.md con bitácora."""
        spec_dir, spec_file = tmp_spec_dir
        metadata = {"id": "001", "slug": "001-test", "title": "Test", "status": "inbox", "priority": "medium"}
        spec_content = "Spec body\n"
        capture_log = "[2024-01-01T00:00:00+00:00] text: Hello\n"
        tmp = spec_file.with_suffix(".tmp")
        full = yaml_section = f"---\n  id: 001\n  slug: 001-test\n  title: Test\n  status: inbox\n  priority: medium\n---\n\n{spec_content}\n---\n\n{LOG_SECTION_HEADER}\n{capture_log}"
        with open(spec_file, "w") as f:
            f.write(full)
        meta, body, log = parse_spec_file(spec_file)
        assert body == "Spec body"
        assert "Hello" in log

    def test_write_spec_file_atomic(self, tmp_spec_dir):
        """Escribe SPEC.md de forma atómica."""
        spec_dir, spec_file = tmp_spec_dir
        metadata = {"id": "001", "slug": "001-test", "title": "Test", "status": "inbox"}
        spec_content = "New content"
        capture_log = "[2024-01-01] note: test entry\n"
        write_spec_file(spec_file, metadata, spec_content, capture_log)
        assert spec_file.exists()
        content = spec_file.read_text()
        assert "New content" in content

    def test_generate_slug(self):
        """Genera slugs correctos."""
        assert "001-my-awesome-idea" == generate_slug("My Awesome Idea", "001")
        slug = generate_slug("Simple", "002")
        assert "002-simple" == slug

    def test_read_spec_file_not_found(self, tmp_spec_dir):
        """Lanza FileNotFoundError si el archivo no existe."""
        spec_dir, spec_file = tmp_spec_dir
        with pytest.raises(FileNotFoundError):
            read_spec_file(spec_file)


# ============================================================
# Tests de SQLite Index
# ============================================================
class TestSQLiteIndex:
    @pytest.fixture
    def index(self, tmp_path):
        """Índice SQLite temporal."""
        db_path = str(tmp_path / "test.sqlite")
        idx = SQLiteIndex(db_path)
        yield idx
        idx.close()

    def test_create_index(self, index):
        """El índice se crea correctamente."""
        assert index.db_path.exists()

    def test_upsert_and_get(self, index):
        """Inserta y recupera una idea."""
        from datetime import datetime, timezone
        idea = IdeaDocument(
            id="001",
            slug="001-test",
            title="Test Idea",
            status=IdeaStatus.INBOX,
            priority=IdeaPriority.MEDIUM,
            tags=["test", "web"],
            target_stack=["React", "FastAPI"],
            repo_path="",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            spec_body="Test spec",
            capture_log="",
        )
        index.upsert_idea_index(idea)
        result = index.get_idea_by_id("001")
        assert result is not None
        assert result.title == "Test Idea"
        assert len(result.tags) == 2

    def test_next_id_generation(self, index):
        """Genera IDs correlativos correctamente."""
        id1 = index.get_next_id()
        id2 = index.get_next_id()
        assert id1 == "001"
        assert id2 == "002"

    def test_list_ideas_empty(self, index):
        """Lista ideas vacías correctamente."""
        ideas = index.list_ideas()
        assert ideas == []

    def test_filter_by_status(self, index):
        """Filtra por estado."""
        from datetime import datetime, timezone
        idea1 = IdeaDocument(
            id="001", slug="001-a", title="A", status=IdeaStatus.INBOX,
            priority=IdeaPriority.MEDIUM, tags=[], target_stack=[],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            spec_body="", capture_log="",
        )
        idea2 = IdeaDocument(
            id="002", slug="002-b", title="B", status=IdeaStatus.REFINING,
            priority=IdeaPriority.HIGH, tags=[], target_stack=[],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            spec_body="", capture_log="",
        )
        index.upsert_idea_index(idea1)
        index.upsert_idea_index(idea2)
        inbox_ideas = index.list_ideas(status="inbox")
        assert len(inbox_ideas) == 1
        assert inbox_ideas[0].id == "001"

    def test_save_and_get_message_mapping(self, index):
        """Guarda y recupera mapeos de mensajes de Telegram."""
        index.save_message_mapping(telegram_msg_id=12345, idea_id="001", bot_reply_msg_id=12346)
        idea_id = index.get_idea_id_by_message(12345)
        assert idea_id == "001"
        bot_id = index.get_bot_reply_msg_id(12345)
        assert bot_id == 12346


# ============================================================
# Tests de IdeaService
# ============================================================
class TestIdeaService:
    @pytest.fixture
    def service(self, tmp_path):
        """Servicio de ideas con directorio temporal."""
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        svc = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        yield svc
        svc.index.close()

    def test_create_idea(self, service):
        """Crea una idea correctamente."""
        req = IdeaCreateRequest(raw_input="Test input", source_type="text")
        idea = service.create_idea(req)
        assert idea.id == "001"
        assert idea.title == "Idea 001"
        assert idea.status == IdeaStatus.INBOX

    def test_get_idea(self, service):
        """Recupera una idea por ID."""
        req = IdeaCreateRequest(raw_input="Test", source_type="text")
        service.create_idea(req)
        idea = service.get_idea("001")
        assert idea is not None
        assert idea.id == "001"

    def test_get_idea_not_found(self, service):
        """Devuelve None si la idea no existe."""
        idea = service.get_idea("999")
        assert idea is None

    def test_update_idea(self, service):
        """Actualiza una idea existente."""
        req = IdeaCreateRequest(raw_input="Test", source_type="text")
        service.create_idea(req)
        update = IdeaUpdateRequest(title="Updated Title", status=IdeaStatus.REFINING)
        updated = service.update_idea("001", update)
        assert updated.title == "Updated Title"
        assert updated.status == IdeaStatus.REFINING

    def test_append_log_entry(self, service):
        """Agrega una entrada a la bitácora."""
        req = IdeaCreateRequest(raw_input="Test", source_type="text")
        service.create_idea(req)
        log_req = IdeaLogAppendRequest(entry_text="New note", source_type="note")
        updated = service.append_log_entry("001", log_req)
        assert "New note" in updated.capture_log

    def test_update_idea_app_url(self, service):
        """Actualiza y persiste app_url de una idea desplegada."""
        req = IdeaCreateRequest(raw_input="Panel test", source_type="text")
        service.create_idea(req)
        update = IdeaUpdateRequest(app_url="http://localhost:8085")
        updated = service.update_idea("001", update)
        assert updated.app_url == "http://localhost:8085"

        retrieved = service.get_idea("001")
        assert retrieved is not None
        assert retrieved.app_url == "http://localhost:8085"
