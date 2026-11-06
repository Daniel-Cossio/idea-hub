"""Hito 3: Puente para Agentes — Servidor FastMCP (5 tools) y CLI Typer."""

from mcp.server.fastmcp import FastMCP
from app.services.idea_service import IdeaService, get_default_idea_service
from app.config import Settings
from app.models import IdeaStatus, IdeaPriority


def _get_service() -> IdeaService:
    """Obtiene o crea el servicio de ideas."""
    if not hasattr(_get_service, "_instance"):
        _get_service._instance = IdeaService()
    return _get_service._instance


mcp = FastMCP("ideas-mcp")


@mcp.tool()
def list_ideas(status: str = "", tag: str = "", query: str = "") -> list[dict]:
    """Lista las ideas de proyectos filtradas por estado, etiqueta o búsqueda FTS5."""
    service = get_default_idea_service()
    ideas = service.list_ideas(status=status or None, tag=tag or None, query=query or None)
    return [i.model_dump() for i in ideas]


@mcp.tool()
def get_idea_spec(idea_id: str) -> dict:
    """Obtiene el documento SPEC.md completo (especificación y bitácora) de una idea."""
    service = get_default_idea_service()
    idea = service.get_idea(idea_id)
    if idea is None:
        return {"error": f"Idea {idea_id} no encontrada"}
    return {
        "id": idea.id,
        "slug": idea.slug,
        "title": idea.title,
        "spec_body": idea.spec_body,
        "capture_log": idea.capture_log,
        "status": idea.status.value,
        "priority": idea.priority.value,
        "tags": idea.tags,
    }


@mcp.tool()
def update_idea_spec(idea_id: str, new_spec_markdown: str) -> dict:
    """Actualiza el cuerpo técnico (spec_body) de una idea preservando su bitácora."""
    service = get_default_idea_service()
    from app.models import IdeaUpdateRequest
    idea = service.update_idea(
        idea_id,
        IdeaUpdateRequest(spec_body=new_spec_markdown),
    )
    return idea.model_dump()


@mcp.tool()
def set_idea_status(idea_id: str, status: str, repo_path: str = "") -> dict:
    """Actualiza el estado de una idea (inbox, refining, agent_ready, in_progress, done, archived)."""
    service = get_default_idea_service()
    idea_status = IdeaStatus(status)
    idea = service.set_status(idea_id, idea_status)
    if repo_path:
        idea.repo_path = repo_path
    return idea.model_dump()


@mcp.tool()
def append_idea_note(idea_id: str, note: str) -> dict:
    """Agrega una nota de progreso o diseño a la bitácora de la idea."""
    service = get_default_idea_service()
    from app.models import IdeaLogAppendRequest
    idea = service.append_log_entry(
        idea_id,
        IdeaLogAppendRequest(entry_text=note, source_type="agent"),
    )
    return idea.model_dump()


def main():
    """Entry point para ideas-mcp."""
    mcp.run()


if __name__ == "__main__":
    main()
