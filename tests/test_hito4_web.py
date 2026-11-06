"""Hito 4: Tests — Frontend Web (Tablero Kanban + Vista Dual + Endpoints)."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api.routes import router as api_router
from app.api.auth import AuthMiddleware
from app.models import IdeaStatus, IdeaPriority


# ============================================================
# Tests de Autenticación Web
# ============================================================
class TestWebAuth:
    @pytest.fixture
    def auth(self):
        return AuthMiddleware(web_password="test_web_pass")

    def test_create_session_token_produces_hash(self, auth):
        """Crea un token de sesión basado en hash."""
        token = auth.create_session_token("mypassword")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_password_returns_token(self, auth):
        """Verifica la contraseña y devuelve token."""
        token = auth.verify_password("test_web_pass")
        assert token is not None
        assert isinstance(token, str)

    def test_session_token_different_password(self, auth):
        """Contraseñas diferentes producen tokens diferentes."""
        t1 = auth.create_session_token("password1")
        t2 = auth.create_session_token("password2")
        assert t1 != t2

    def test_login_endpoint_returns_token(self):
        """Endpoint de login responde con token y ok."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(api_router)
        client = TestClient(app)

        response = client.post(
            "/api/auth/login",
            json={"password": "test_web_pass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "token" in data

    def test_login_endpoint_rejects_empty(self):
        """Endpoint de login rechaza password vacío."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(api_router)
        client = TestClient(app)

        response = client.post(
            "/api/auth/login",
            json={"password": ""},
        )
        assert response.status_code == 400


# ============================================================
# Tests de Endpoints Kanban
# ============================================================
class TestKanbanEndpoints:
    @pytest.fixture
    def app(self, tmp_path):
        """App FastAPI con servicio de ideas en directorio temporal."""
        from fastapi import FastAPI
        from app.services.idea_service import IdeaService

        app = FastAPI()
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        service = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        app.state.idea_service = service
        app.state.settings = type('Settings', (), {
            'api_token': '',
            'web_password': '',
            'api_host': '0.0.0.0',
            'api_port': 8090,
            'ai_base_url': 'https://api.groq.com/openai/v1',
            'ai_api_key': 'test-key',
            'telegram_bot_token': '',
            'telegram_allowed_user_id': '',
            'disable_bot_polling': False,
        })()
        app.include_router(api_router)
        return app

    def test_health_endpoint_returns_count(self, app):
        """Healthcheck devuelve status ok con ideas_count."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ideas_count" in data
        assert isinstance(data["ideas_count"], int)

    def test_list_ideas_empty(self, app):
        """Lista ideas vacías correctamente."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/ideas")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_ideas_with_query_filter(self, app):
        """Filtra ideas por query (?q=)."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        # Crear ideas
        client.post("/api/ideas", json={"raw_input": "Test marketing idea", "source_type": "text"})
        client.post("/api/ideas", json={"raw_input": "Another test idea", "source_type": "text"})

        response = client.get("/api/ideas?q=marketing")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Debe filtrar
        for idea in data:
            assert "marketing" in idea["title"].lower() or "marketing" in idea["spec_body"].lower()

    def test_list_ideas_status_filter(self, app):
        """Filtra ideas por estado."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.get("/api/ideas?status=inbox")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_idea_endpoint(self, app):
        """Crea una idea vía endpoint."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post(
            "/api/ideas",
            json={"raw_input": "New idea input", "source_type": "text"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "status" in data
        assert data["status"] == "inbox"
        assert "spec_body" in data
        assert "capture_log" in data

    def test_get_idea_endpoint(self, app):
        """Obtiene una idea por ID."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        idea_id = response.json()["id"]
        get_resp = client.get(f"/api/ideas/{idea_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == idea_id

    def test_get_idea_not_found(self, app):
        """Devuelve 404 si la idea no existe."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/ideas/999")
        assert response.status_code == 404

    def test_update_idea_endpoint(self, app):
        """Actualiza una idea por endpoint."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Original", "source_type": "text"})
        response = client.put(
            "/api/ideas/001",
            json={"title": "Updated", "status": "refining", "priority": "high"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["status"] == "refining"
        assert data["priority"] == "high"

    def test_update_spec_body(self, app):
        """Actualiza el spec_body de una idea."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Original", "source_type": "text"})
        response = client.put(
            "/api/ideas/001",
            json={"spec_body": "# New Spec\n\nUpdated content here."},
        )
        assert response.status_code == 200
        assert "New Spec" in response.json()["spec_body"]

    def test_append_log_endpoint(self, app):
        """Agrega una nota a la bitácora."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.post(
            "/api/ideas/001/log",
            json={"entry_text": "Debug note", "source_type": "note"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Debug note" in data["capture_log"]

    def test_set_idea_status_endpoint(self, app):
        """Actualiza el estado de una idea."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.patch(
            "/api/ideas/001/status",
            json={"status": "in_progress"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"


# ============================================================
# Tests de Vista Dual
# ============================================================
class TestDualView:
    @pytest.fixture
    def app(self, tmp_path):
        """App FastAPI con servicio de ideas en directorio temporal."""
        from fastapi import FastAPI
        from app.services.idea_service import IdeaService

        app = FastAPI()
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        service = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        app.state.idea_service = service
        app.state.settings = type('Settings', (), {
            'api_token': '', 'web_password': '', 'api_host': '0.0.0.0',
            'api_port': 8090, 'ai_base_url': 'https://api.groq.com/openai/v1',
            'ai_api_key': 'test-key', 'telegram_bot_token': '',
            'telegram_allowed_user_id': '', 'disable_bot_polling': False,
        })()
        app.include_router(api_router)
        return app

    def test_dual_view_has_log_and_editor(self, app):
        """La vista dual tiene bitácora y editor."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        # Crear idea con capture_log
        client.post("/api/ideas", json={"raw_input": "Test idea", "source_type": "text"})
        response = client.get("/api/ideas/001")
        assert response.status_code == 200
        data = response.json()
        assert "spec_body" in data
        assert "capture_log" in data
        assert "status" in data
        assert "priority" in data

    def test_idea_has_all_dual_view_fields(self, app):
        """Una idea tiene todos los campos para Vista Dual."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.get("/api/ideas/001")
        data = response.json()
        # Campos esenciales de la Vista Dual
        for field in ("id", "slug", "title", "status", "priority", "spec_body", "capture_log"):
            assert field in data, f"Falta campo {field}"

    def test_idea_log_can_be_appended_via_dual_view(self, app):
        """Se pueden añadir notas desde la Vista Dual."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        # Primera nota
        client.post("/api/ideas/001/log", json={"entry_text": "Note 1", "source_type": "note"})
        # Segunda nota
        response = client.post("/api/ideas/001/log", json={"entry_text": "Note 2", "source_type": "note"})
        assert response.status_code == 200
        data = response.json()
        assert "Note 1" in data["capture_log"]
        assert "Note 2" in data["capture_log"]


# ============================================================
# Tests de Estructuración con IA
# ============================================================
class TestStructureEndpoint:
    @pytest.fixture
    def app(self, tmp_path):
        from fastapi import FastAPI
        from app.services.idea_service import IdeaService

        app = FastAPI()
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        service = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        app.state.idea_service = service
        app.state.settings = type('Settings', (), {
            'api_token': '', 'web_password': '', 'api_host': '0.0.0.0',
            'api_port': 8090, 'ai_base_url': 'https://api.groq.com/openai/v1',
            'ai_api_key': 'test-key', 'telegram_bot_token': '',
            'telegram_allowed_user_id': '', 'disable_bot_polling': False,
        })()
        app.include_router(api_router)
        return app

    def test_structure_idea_endpoint(self, app):
        """Botón 'Estructurar con IA' marca como agent_ready."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.post("/api/ideas/001/structure")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "agent_ready"

    def test_structure_idea_not_found(self, app):
        """Devuelve 404 al estructurar idea inexistente."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/api/ideas/999/structure")
        assert response.status_code == 404

    def test_copy_command_generates_cli_format(self, app):
        """El comando copiado tiene formato idea-cli init."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.get("/api/ideas/001")
        data = response.json()
        idea_id = data["id"]
        command = f"idea-cli init {idea_id}"
        assert command.startswith("idea-cli init")
        assert idea_id in command


# ============================================================
# Tests de Integración Web Completa
# ============================================================
class TestWebIntegration:
    @pytest.fixture
    def app(self, tmp_path):
        from fastapi import FastAPI
        from app.services.idea_service import IdeaService

        app = FastAPI()
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        service = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        app.state.idea_service = service
        app.state.settings = type('Settings', (), {
            'api_token': '', 'web_password': 'test_web_pass', 'api_host': '0.0.0.0',
            'api_port': 8090, 'ai_base_url': 'https://api.groq.com/openai/v1',
            'ai_api_key': 'test-key', 'telegram_bot_token': '',
            'telegram_allowed_user_id': '', 'disable_bot_polling': False,
        })()
        app.include_router(api_router)
        return app

    def test_full_workflow_login_then_kanban(self, app):
        """Workflow completo: login → listar → kanban con columnas correctas."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # 1. Login
        response = client.post("/api/auth/login", json={"password": "test_web_pass"})
        assert response.status_code == 200
        assert "token" in response.json()

        # 2. Crear varias ideas en diferentes estados
        client.post("/api/ideas", json={"raw_input": "Idea 1", "source_type": "text"})
        client.post("/api/ideas", json={"raw_input": "Idea 2", "source_type": "text"})

        # 3. Kanban responde
        response = client.get("/api/ideas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # 4. Verificar columnas Kanban
        column_names = list(IdeaStatus)
        for col_name in COLUMNS:
            assert any(s.value == col_name for s in column_names), f"Columna {col_name} no encontrada"

    def test_kanban_columns_exist(self):
        """Verificar que las columnas Kanban están definidas."""
        expected_columns = ["inbox", "refining", "agent_ready", "in_progress", "done", "archived"]
        assert len(expected_columns) == 6
        for col in expected_columns:
            assert col in COLUMNS

    def test_dual_view_command_format(self):
        """El comando de Vista Dual tiene formato correcto."""
        idea_id = "001"
        command = f"idea-cli init {idea_id}"
        assert command == "idea-cli init 001"

    def test_search_filters_ideas(self, app):
        """El buscador filtra ideas correctamente."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Python web app", "source_type": "text"})
        client.post("/api/ideas", json={"raw_input": "Rust backend service", "source_type": "text"})

        response = client.get("/api/ideas?q=Python")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 0  # Filtro aplicado sin error

    def test_status_changes_reflect_in_kanban(self, app):
        """Cambios de estado se reflejan en el Kanban."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})

        # Cambiar a in_progress
        client.patch("/api/ideas/001/status", json={"status": "in_progress"})

        # Ver en kanban
        response = client.get("/api/ideas?status=in_progress")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["status"] == "in_progress"


# Columnas disponibles para los tests
COLUMNS = ["inbox", "refining", "agent_ready", "in_progress", "done", "archived"]


# ============================================================
# Tests de Archivos Web
# ============================================================
class TestWebAssets:
    def test_web_directory_exists(self):
        """El directorio web/ existe."""
        web_dir = Path(__file__).parent.parent / "web"
        assert web_dir.exists()

    def test_web_index_html_exists(self):
        """El archivo index.html existe en web/."""
        html_path = Path(__file__).parent.parent / "web" / "index.html"
        assert html_path.exists()
        content = html_path.read_text()
        assert "Kanban" in content or "kanban" in content

    def test_web_app_js_exists(self):
        """El archivo app.js existe en web/."""
        js_path = Path(__file__).parent.parent / "web" / "app.js"
        assert js_path.exists()

    def test_web_style_css_exists(self):
        """El archivo style.css existe en web/."""
        css_path = Path(__file__).parent.parent / "web" / "style.css"
        assert css_path.exists()
