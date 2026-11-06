"""Hito 1: Core Foundation — Lectura/escritura atómica de SPEC.md."""

import os
import tempfile
import frontmatter
from pathlib import Path
from typing import Optional, Tuple

# Regla de separación del archivo SPEC.md (Sección 8.1)
LOG_SECTION_HEADER = "## 💬 Bitácora de Captura (Telegram Log)"
LOG_DELIMITER = f"\n---\n\n{LOG_SECTION_HEADER}\n"


def _ensure_vault_dir(vault_dir: Path, idea_id: str) -> Path:
    """Asegura que el directorio data/vault/{idea_id}-{slug} existe."""
    idea_dir = vault_dir / idea_id
    idea_dir.mkdir(parents=True, exist_ok=True)
    return idea_dir


def parse_spec_file(spec_path: Path) -> Tuple[dict, str, str]:
    """
    Divide el SPEC.md en YAML Frontmatter, spec_body y capture_log.
    
    1. Carga el YAML Frontmatter con frontmatter.load(path).
    2. El contenido Markdown (post.content) se divide por LOG_SECTION_HEADER.
    3. La parte superior es spec_body (editable en la Web o por "Estructurar con IA").
    4. La parte inferior es capture_log (append-only).
    """
    with open(spec_path, "r", encoding="utf-8") as f:
        post = frontmatter.load(spec_path)

    content = post.content
    if LOG_SECTION_HEADER in content:
        parts = content.split(LOG_DELIMITER, 1)
        spec_body = parts[0].rstrip("\n")
        capture_log = parts[1] if len(parts) > 1 else ""
    else:
        spec_body = content.rstrip("\n")
        capture_log = ""

    return post.metadata, spec_body, capture_log


def write_spec_file(
    spec_path: Path,
    metadata: dict,
    spec_body: str,
    capture_log: str = "",
) -> None:
    """
    Escribe el SPEC.md de forma atómica.
    
    1. Se escribe primero en un archivo temporal SPEC.md.tmp.
    2. Se ejecuta os.replace(tmp_path, target_path) para atomicidad en disco.
    """
    tmp_path = spec_path.with_suffix(".tmp")

    content = spec_body
    if capture_log:
        content = f"{content}\n---\n\n{LOG_SECTION_HEADER}\n{capture_log}"

    metadata_str = ""
    for key, value in metadata.items():
        if isinstance(value, list):
            value_str = "\n  - ".join(str(v) for v in value)
            metadata_str += f"  {key}:\n    - {value_str}\n"
        elif isinstance(value, str):
            metadata_str += f"  {key}: {value}\n"
        else:
            metadata_str += f"  {key}: {value}\n"

    yaml_section = f"""\
---
{metadata_str}---

"""
    full_content = f"{yaml_section}{content}"

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    os.replace(tmp_path, spec_path)


def read_spec_file(spec_path: Path) -> dict:
    """Lee y devuelve el documento completo de una idea."""
    if not spec_path.exists():
        raise FileNotFoundError(f"SPEC.md no encontrado: {spec_path}")
    metadata, spec_body, capture_log = parse_spec_file(spec_path)
    return {
        "metadata": metadata,
        "spec_body": spec_body,
        "capture_log": capture_log,
    }


def update_spec_body(spec_path: Path, new_spec_body: str) -> None:
    """Actualiza solo el spec_body preservando la bitácora."""
    metadata, _, capture_log = parse_spec_file(spec_path)
    write_spec_file(spec_path, metadata, new_spec_body, capture_log)


def append_capture_log(spec_path: Path, entry_text: str, timestamp: str = "") -> None:
    """Append-only: agrega una entrada a la bitácora de captura."""
    if not timestamp:
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()

    entry = f"[{timestamp}] {entry_text}\n"
    metadata, spec_body, capture_log = parse_spec_file(spec_path)

    if capture_log and not capture_log.endswith("\n"):
        capture_log += "\n"
    capture_log += entry

    write_spec_file(spec_path, metadata, spec_body, capture_log)


def generate_slug(title: str, idea_id: str) -> str:
    """Genera un slug legible a partir del título."""
    import re
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return f"{idea_id}-{slug}" if slug else idea_id
