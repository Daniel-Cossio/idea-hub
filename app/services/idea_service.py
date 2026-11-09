"""Hito 1: Core Foundation — Orquestador de negocio (coordina markdown_vault + sqlite_index)."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

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
    parse_spec_file,
    write_spec_file,
    update_spec_body,
    append_capture_log,
    generate_slug,
    read_spec_file,
)
from app.storage.sqlite_index import SQLiteIndex


# Cache global para el servicio de ideas (usado por MCP)
_default_service_instance = None


def get_default_idea_service() -> "IdeaService":
    """Obtiene o crea la instancia global del servicio de ideas."""
    global _default_service_instance
    if _default_service_instance is None:
        from app.config import Settings
        settings = Settings()
        _default_service_instance = IdeaService(
            data_dir=settings.data_dir,
            sqlite_path=settings.sqlite_path,
        )
    return _default_service_instance


class IdeaService:
    """Orquestador de negocio: coordina markdown_vault y sqlite_index."""

    def __init__(self, data_dir: str = "data", sqlite_path: str = "data/index.sqlite"):
        self.vault_dir = Path(data_dir) / "vault"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.index = SQLiteIndex(sqlite_path)

    def _get_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Creación de ideas
    # ------------------------------------------------------------------
    def create_idea(self, request: IdeaCreateRequest) -> IdeaDocument:
        """Genera el siguiente ID correlativo (001, 002...), escribe SPEC.md e indexa."""
        idea_id = self.index.get_next_id()
        slug = generate_slug(request.title or f"Idea {idea_id}", idea_id)
        now = self._get_now()

        capture_entry = f"[{now}] Captura inicial ({request.source_type}): {request.raw_input}"

        metadata = {
            "id": idea_id,
            "slug": slug,
            "title": request.title or f"Idea {idea_id}",
            "status": IdeaStatus.INBOX.value,
            "priority": request.priority.value if isinstance(request.priority, IdeaPriority) else str(request.priority),
            "tags": request.tags,
            "target_stack": [],
            "created_at": now,
            "updated_at": now,
            "telegram_root_msg_id": request.telegram_msg_id,
        }

        spec_path = self.vault_dir / idea_id / "SPEC.md"
        spec_path.parent.mkdir(parents=True, exist_ok=True)

        write_spec_file(spec_path, metadata, request.raw_input, capture_entry)

        idea = IdeaDocument(
            id=idea_id,
            slug=slug,
            title=metadata["title"],
            status=IdeaStatus.INBOX,
            priority=request.priority,
            tags=request.tags,
            target_stack=[],
            repo_path="",
            created_at=now,
            updated_at=now,
            telegram_root_msg_id=request.telegram_msg_id,
            spec_body=request.raw_input,
            capture_log=capture_entry,
        )
        self.index.upsert_idea_index(idea)
        return idea

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_idea(self, idea_id: str) -> Optional[IdeaDocument]:
        """Lee y devuelve la idea completa."""
        return self.index.get_idea_by_id(idea_id)

    def list_ideas(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[IdeaDocument]:
        """Lista ideas filtrando por estado, tag o consulta FTS5."""
        return self.index.list_ideas(status=status, tag=tag, query=query)

    def get_idea_by_slug(self, slug: str) -> Optional[IdeaDocument]:
        """Obtiene una idea por su slug."""
        return self.index.get_idea_by_slug(slug)

    # ------------------------------------------------------------------
    # Actualización
    # ------------------------------------------------------------------
    def update_idea(self, idea_id: str, request: IdeaUpdateRequest) -> IdeaDocument:
        """Actualiza una idea existente."""
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ValueError(f"Idea {idea_id} no encontrada")

        if request.title is not None:
            idea.title = request.title
            slug = generate_slug(request.title, idea_id)
            idea.slug = slug
        if request.status is not None:
            idea.status = request.status
        if request.priority is not None:
            idea.priority = request.priority
        if request.tags is not None:
            idea.tags = request.tags
        if request.target_stack is not None:
            idea.target_stack = request.target_stack
        if request.repo_path is not None:
            idea.repo_path = request.repo_path
        if request.spec_body is not None:
            idea.spec_body = request.spec_body
            update_spec_body(
                self.vault_dir / idea_id / "SPEC.md",
                request.spec_body,
            )

        idea.updated_at = self._get_now()
        self.index.upsert_idea_index(idea)
        return idea

    # ------------------------------------------------------------------
    # Bitácora (capture_log)
    # ------------------------------------------------------------------
    def append_log_entry(self, idea_id: str, request: IdeaLogAppendRequest) -> IdeaDocument:
        """Agrega una entrada a la bitácora de captura de una idea."""
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ValueError(f"Idea {idea_id} no encontrada")

        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"[{timestamp}] {request.source_type}: {request.entry_text}"

        spec_path = self.vault_dir / idea_id / "SPEC.md"
        append_capture_log(spec_path, entry)

        idea.capture_log += f"\n{entry}"
        idea.updated_at = timestamp
        self.index.upsert_idea_index(idea)
        return idea

    # ------------------------------------------------------------------
    # Callbacks de estado (Telegram inline queries)
    # ------------------------------------------------------------------
    def set_status(self, idea_id: str, status: IdeaStatus) -> IdeaDocument:
        """Actualiza el estado de una idea."""
        idea = self.index.set_idea_status(idea_id, status)
        idea.status = status
        idea.updated_at = self._get_now()
        self.index.upsert_idea_index(idea)
        return idea

    def set_priority(self, idea_id: str, priority: IdeaPriority) -> IdeaDocument:
        """Actualiza la prioridad de una idea."""
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ValueError(f"Idea {idea_id} no encontrada")
        idea.priority = priority
        idea.updated_at = self._get_now()
        spec_path = self.vault_dir / idea_id / "SPEC.md"
        metadata, spec_body, capture_log = parse_spec_file(spec_path)
        metadata["priority"] = priority.value
        write_spec_file(spec_path, metadata, spec_body, capture_log)
        self.index.upsert_idea_index(idea)
        return idea

    # ------------------------------------------------------------------
    # Mapeo de mensajes de Telegram
    # ------------------------------------------------------------------
    def save_message_mapping(
        self, telegram_msg_id: int, idea_id: str, bot_reply_msg_id: Optional[int] = None
    ) -> None:
        """Guarda el mapeo message_id -> idea_id y bot_reply_message_id."""
        self.index.save_message_mapping(telegram_msg_id, idea_id, bot_reply_msg_id)

    def get_idea_id_by_message(self, telegram_msg_id: int) -> Optional[str]:
        """Busca idea_id por message_id de Telegram."""
        return self.index.get_idea_id_by_message(telegram_msg_id)

    def get_bot_reply_msg_id(self, telegram_msg_id: int) -> Optional[int]:
        """Obtiene el bot_reply_msg_id para un message_id de Telegram."""
        return self.index.get_bot_reply_msg_id(telegram_msg_id)

    # ------------------------------------------------------------------
    # Inicialización de proyecto (para idea-cli init)
    # ------------------------------------------------------------------
    def init_project(self, idea_id: str, target_dir: str) -> dict:
        """Inicializa un proyecto a partir de una idea."""
        idea = self.get_idea(idea_id)
        if idea is None:
            raise ValueError(f"Idea {idea_id} no encontrada")

        slug = idea.slug
        project_dir = Path(target_dir) / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        # Actualizar estado
        idea.status = IdeaStatus.IN_PROGRESS
        idea.repo_path = str(project_dir)
        idea.updated_at = self._get_now()
        self.index.upsert_idea_index(idea)

        return {
            "idea_id": idea_id,
            "slug": slug,
            "project_dir": str(project_dir),
            "repo_path": idea.repo_path,
            "status": idea.status.value,
        }
