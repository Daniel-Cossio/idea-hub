"""Hito 2: Tests — Bot Telegram + API REST."""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings
from app.api.auth import AuthMiddleware
from app.api.routes import router as api_router
from app.bot.keyboards import build_action_keyboard, build_status_keyboard
from app.bot.middlewares import UserWhitelistMiddleware, create_whitelist_middleware
from app.bot.router import create_bot_router


# ============================================================
# Tests de Autenticación
# ============================================================
class TestAuth:
    def test_create_session_token(self):
        """Crea un token de sesión válido."""
        auth = AuthMiddleware(web_password="test_secret")
        token = auth.create_session_token("mypassword")
        assert len(token) > 0
        assert isinstance(token, str)

    def test_verify_password(self):
        """Verifica la contraseña y devuelve el token."""
        auth = AuthMiddleware(web_password="test_secret")
        token = auth.verify_password("test_secret")
        assert token is not None

    def test_auth_middleware_no_token(self):
        """Middleware sin token permite el paso en test local."""
        auth = AuthMiddleware()
        assert auth.api_token == ""


# ============================================================
# Tests de Rutas API
# ============================================================
class TestRoutes:
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
        app.state.settings = Settings(api_token="", disable_bot_polling=True)
        app.include_router(api_router)
        return app

    def test_health_endpoint(self, app):
        """El endpoint /api/health responde correctamente."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ideas_count" in data

    def test_list_ideas_empty(self, app):
        """Lista ideas vacías correctamente."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/ideas")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_idea_endpoint(self, app):
        """Crea una idea vía endpoint."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post(
            "/api/ideas",
            json={"raw_input": "Test input", "source_type": "text"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "001"
        assert data["title"] == "Idea 001"

    def test_get_idea_endpoint(self, app):
        """Obtiene una idea por ID."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        # Crear idea primero
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.get("/api/ideas/001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "001"

    def test_update_idea_endpoint(self, app):
        """Actualiza una idea por endpoint."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Original", "source_type": "text"})
        response = client.put(
            "/api/ideas/001",
            json={"title": "Updated", "status": "refining"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"

    def test_append_log_endpoint(self, app):
        """Agrega una nota a la bitácora."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        client.post("/api/ideas", json={"raw_input": "Test", "source_type": "text"})
        response = client.post(
            "/api/ideas/001/log",
            json={"entry_text": "Note text", "source_type": "note"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Note text" in data["capture_log"]

    def test_login_endpoint(self):
        """Endpoint de login responde con token."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.routes import router as routes_router

        app = FastAPI()
        app.include_router(routes_router)
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"password": "test_secret"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "token" in data


# ============================================================
# Tests del Bot
# ============================================================
class TestBot:
    def test_build_action_keyboard(self):
        """Construye el teclado de acciones correctamente."""
        keyboard = build_action_keyboard("001")
        assert keyboard is not None
        # Verificar estructura
        assert len(keyboard.inline_keyboard) == 3
        assert len(keyboard.inline_keyboard[0]) == 2

    def test_build_status_keyboard(self):
        """Construye el teclado de estados correctamente."""
        keyboard = build_status_keyboard("001")
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 3

    def test_whitelist_middleware(self):
        """Middleware filtra correctamente por whitelist."""
        middleware = create_whitelist_middleware("12345,67890")
        assert "12345" in middleware.allowed_user_ids
        assert "67890" in middleware.allowed_user_ids

    def test_whitelist_middleware_blocks_other(self):
        """Middleware bloquea usuarios no autorizados."""
        middleware = create_whitelist_middleware("12345")
        assert "99999" not in middleware.allowed_user_ids


# ============================================================
# Tests de Endpoints con filtros
# ============================================================
class TestEndpointFilters:
    @pytest.fixture
    def app(self, tmp_path):
        from fastapi import FastAPI
        from app.services.idea_service import IdeaService

        app = FastAPI()
        data_dir = str(tmp_path / "data")
        sqlite_path = str(tmp_path / "data" / "index.sqlite")
        service = IdeaService(data_dir=data_dir, sqlite_path=sqlite_path)
        app.state.idea_service = service
        app.state.settings = Settings(api_token="", disable_bot_polling=True)
        app.include_router(api_router)
        return app

    def test_filter_by_status(self, app):
        """Filtra ideas por estado."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/ideas?status=inbox")
        assert response.status_code == 200

    def test_filter_by_tag(self, app):
        """Filtra ideas por tag."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/ideas?tag=test")
        assert response.status_code == 200
