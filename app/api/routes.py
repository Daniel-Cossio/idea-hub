"""Hito 2: API — Endpoints REST (/api/health, /api/auth/login, /api/ideas...)."""

import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import Settings
from app.models import (
    IdeaDocument,
    IdeaCreateRequest,
    IdeaUpdateRequest,
    IdeaLogAppendRequest,
    IdeaStatus,
    IdeaPriority,
)
from app.services.idea_service import IdeaService
from app.api.auth import AuthMiddleware

router = APIRouter(prefix="/api", tags=["ideas"])
auth_middleware = AuthMiddleware()


@router.get("/health")
async def healthcheck(request: Request) -> dict:
    """Healthcheck y conteo en SQLite."""
    service = request.app.state.idea_service
    count = len(service.index.list_ideas())
    return {"status": "ok", "ideas_count": count}


@router.post("/auth/login")
async def login(request: Request) -> JSONResponse:
    """
    Valida IDEAHUB_WEB_PASSWORD y devuelve el token y cookie HttpOnly.
    """
    body = await request.json()
    password = body.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="password required")

    token = auth_middleware.create_session_token(password)
    response = JSONResponse(content={"token": token, "ok": True})
    response.set_cookie(
        "ideahub_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 días
    )
    return response


@router.get("/ideas")
async def list_ideas(
    request: Request,
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None, alias="q"),
) -> List[dict]:
    """
    Lista ideas filtrando por estado, tag o consulta FTS5 (q).
    La búsqueda encuentra ideas por palabras clave dentro de la bitácora o del título.
    """
    # Verificar autenticación (excepto health y auth/login)
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = request.app.state.idea_service
    ideas = service.list_ideas(status=status, tag=tag, query=q)
    return [i.model_dump() for i in ideas]


@router.post("/ideas", status_code=201)
async def create_idea(request: Request) -> dict:
    """Genera el siguiente ID correlativo (001, 002...), escribe SPEC.md e indexa."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    create_req = IdeaCreateRequest(**body)
    service = request.app.state.idea_service
    idea = service.create_idea(create_req)
    return idea.model_dump()


@router.get("/ideas/{idea_id}")
async def get_idea(request: Request, idea_id: str) -> dict:
    """Lee y devuelve la idea completa."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = request.app.state.idea_service
    idea = service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} no encontrada")
    return idea.model_dump()


@router.put("/ideas/{idea_id}")
async def update_idea(request: Request, idea_id: str) -> dict:
    """Actualiza una idea existente."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    update_req = IdeaUpdateRequest(**body)
    service = request.app.state.idea_service
    idea = service.update_idea(idea_id, update_req)
    return idea.model_dump()


@router.post("/ideas/{idea_id}/log")
async def append_log(request: Request, idea_id: str) -> dict:
    """Agrega una entrada a la bitácora de captura de una idea."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    log_req = IdeaLogAppendRequest(**body)
    service = request.app.state.idea_service
    idea = service.append_log_entry(idea_id, log_req)
    return idea.model_dump()


@router.patch("/ideas/{idea_id}/status")
async def set_idea_status(request: Request, idea_id: str) -> dict:
    """Actualiza el estado de una idea."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    status = IdeaStatus(body.get("status", "inbox"))
    service = request.app.state.idea_service
    idea = service.set_status(idea_id, status)
    return idea.model_dump()


async def _check_auth(request: Request) -> bool:
    """Verifica Bearer Token o Cookie HttpOnly."""
    if not request.app.state.settings:
        return True  # Entorno de test local sin token

    settings: Settings = request.app.state.settings
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if settings.api_token and token == settings.api_token:
            return True
        if not settings.api_token:  # Test local sin token
            return True

    cookie = request.cookies.get("ideahub_session")
    if cookie:
        return True

    # Sin token y sin cookie → permitir en test local
    if not settings.api_token:
        return True

    return False


# ============================================================
# Endpoints adicionales para callbacks de Telegram
# ============================================================

@router.post("/ideas/{idea_id}/structure")
async def structure_idea(request: Request, idea_id: str) -> dict:
    """Botón 'Estructurar con IA' — procesa el spec_body con LLM."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = request.app.state.idea_service
    idea = service.get_idea(idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} no encontrada")

    # Placeholder: marca como agent_ready
    idea.status = IdeaStatus.AGENT_READY
    idea.updated_at = datetime.now(timezone.utc).isoformat()
    service.index.upsert_idea_index(idea)
    return idea.model_dump()


@router.post("/ideas/{idea_id}/archive")
async def archive_idea(request: Request, idea_id: str) -> dict:
    """Archiva una idea."""
    if not await _check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = request.app.state.idea_service
    idea = service.set_status(idea_id, IdeaStatus.ARCHIVED)
    return idea.model_dump()
