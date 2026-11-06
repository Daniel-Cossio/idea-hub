"""Hito 3: Puente para Agentes — CLI Typer (idea-cli list, show, init <id>."""

import typer
import sys
from pathlib import Path
from datetime import datetime, timezone

app = typer.Typer(help="IdeaHub CLI — Gestión de ideas y bootstrap de proyectos.")


@app.command()
def list_ideas() -> None:
    """Lista las ideas almacenadas en el vault."""
    from app.services.idea_service import IdeaService
    from app.config import Settings

    settings = Settings()
    service = IdeaService(data_dir=settings.data_dir, sqlite_path=settings.sqlite_path)
    ideas = service.list_ideas()

    if not ideas:
        typer.echo("No hay ideas almacenadas.")
        return

    typer.echo(f"\n📋 Ideas almacenadas ({len(ideas)}):")
    typer.echo(f"{'ID':<6} {'Título':<40} {'Estado':<15} {'Prioridad':<12}")
    typer.echo("-" * 73)
    for idea in ideas:
        typer.echo(
            f"{idea.id:<6} {idea.title:<40} {idea.status.value:<15} {idea.priority.value:<12}"
        )
    typer.echo()


@app.command()
def show(idea_id: str) -> None:
    """Muestra el detalle de una idea específica."""
    from app.services.idea_service import IdeaService
    from app.config import Settings

    settings = Settings()
    service = IdeaService(data_dir=settings.data_dir, sqlite_path=settings.sqlite_path)
    idea = service.get_idea(idea_id)

    if idea is None:
        typer.echo(f"❌ Idea {idea_id} no encontrada.")
        sys.exit(1)

    typer.echo(f"\n📄 Idea {idea_id}: {idea.title}")
    typer.echo(f"   Estado:     {idea.status.value}")
    typer.echo(f"   Prioridad:   {idea.priority.value}")
    typer.echo(f"   Tags:        {', '.join(idea.tags) or 'ninguno'}")
    typer.echo(f"   Stack:       {', '.join(idea.target_stack) or 'ninguno'}")
    typer.echo(f"   Ruta repo:   {idea.repo_path or 'sin ruta'}")
    typer.echo(f"   Creada:      {idea.created_at}")
    typer.echo(f"   Actualizada: {idea.updated_at}")
    typer.echo(f"\n📝 SPEC Body:\n{idea.spec_body}")
    if idea.capture_log:
        typer.echo(f"\n📋 Capture Log:\n{idea.capture_log}")
    typer.echo()


@app.command()
def init(idea_id: str, target_dir: str = "./") -> None:
    """
    Inicializa un proyecto a partir de una idea.

    Ejecuta:
    1. Descarga/sincroniza el SPEC.md de la idea desde el servidor/repo Git.
    2. Crea el directorio /home/dan/Documentos/git/<slug-de-la-idea>/.
    3. Ejecuta git init -b main.
    4. Genera en la raíz del nuevo proyecto:
       - SPEC.md con toda la especificación técnica y contexto.
       - TASKS.md con el checklist extraído de la sección 4 del SPEC.md.
       - .gitignore base acorde al stack detectado.
    5. Actualiza el estado de la idea a in_progress con repo_path actualizado.
    6. Imprime los comandos listos para arrancar.
    """
    from app.services.idea_service import IdeaService
    from app.config import Settings
    import subprocess
    import json

    settings = Settings()
    service = IdeaService(data_dir=settings.data_dir, sqlite_path=settings.sqlite_path)

    result = service.init_project(idea_id, target_dir)
    slug = result["slug"]
    project_dir = Path(target_dir) / slug
    project_dir.mkdir(parents=True, exist_ok=True)

    # Ejecutar git init
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True, capture_output=True)
    except subprocess.SubprocessError:
        typer.echo(f"⚠️ git init omitido (ya inicializado o git no disponible)")

    # Leer idea desde el servicio
    idea = service.get_idea(idea_id)
    if idea is None:
        typer.echo(f"❌ Idea {idea_id} no encontrada.", err=True)
        raise typer.Exit(1)

    spec_content = f"""\
# {idea.title}

## Especificación Técnica

{idea.spec_body}

## Bitácora de Captura

{idea.capture_log or "Sin entradas aún."}

## Tareas

- [ ] Revisar especificación
- [ ] Implementar solución
- [ ] Testing y validación
- [ ] Documentación
"""
    spec_file = project_dir / "SPEC.md"
    spec_file.write_text(spec_content, encoding="utf-8")
    typer.echo(f"✅ SPEC.md escrito en {spec_file}")

    tasks_content = f"""\
# TASKS — {idea_id}

## Checklist de implementación

- [ ] Analizar especificación
- [ ] Diseñar arquitectura
- [ ] Implementar solución
- [ ] Testing
- [ ] Deploy
"""
    tasks_file = project_dir / "TASKS.md"
    tasks_file.write_text(tasks_content, encoding="utf-8")
    typer.echo(f"✅ TASKS.md creado en {tasks_file}")

    gitignore_content = """# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.egg

# Virtualenv
.venv/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log

"""
    gitignore_file = project_dir / ".gitignore"
    gitignore_file.write_text(gitignore_content, encoding="utf-8")
    typer.echo(f"✅ .gitignore creado en {gitignore_file}")

    typer.echo(f"\n🎉 Proyecto inicializado: {result['project_dir']}")
    typer.echo(f"   cd {result['project_dir']} && agy  # o opencode  o claude")
    typer.echo()


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """IdeaHub CLI — Si no se proporciona comando, lista las ideas."""
    if ctx.invoked_subcommand is None:
        list_ideas()


if __name__ == "__main__":
    app()
