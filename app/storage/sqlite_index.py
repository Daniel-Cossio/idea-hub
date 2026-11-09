"""Hito 1: Core Foundation — Índice SQLite con FTS5 y mapeo de message_id de Telegram."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Tuple, Any

from app.models import IdeaDocument, IdeaStatus, IdeaPriority


class SQLiteIndex:
    """Índice SQLite con FTS5 para búsqueda instantánea y mapeo de message_id."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
        self._init_db()

    def _init_db(self) -> None:
        """Inicializa las tablas y la FTS5 virtual table."""
        conn = self._conn
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'inbox',
                priority TEXT NOT NULL DEFAULT 'medium',
                tags TEXT DEFAULT '[]',
                target_stack TEXT DEFAULT '[]',
                repo_path TEXT DEFAULT '',
                app_url TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                telegram_root_msg_id INTEGER,
                spec_body TEXT DEFAULT '',
                capture_log TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS ideas_fts USING fts5(
                id,
                title,
                tags,
                spec_body,
                capture_log
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS message_mappings (
                telegram_msg_id INTEGER PRIMARY KEY,
                idea_id TEXT NOT NULL,
                bot_reply_msg_id INTEGER
            )
        """)
        # Migración suave para columnas nuevas
        existing_cols = [c[1] for c in conn.execute("PRAGMA table_info(ideas)").fetchall()]
        if "app_url" not in existing_cols:
            conn.execute("ALTER TABLE ideas ADD COLUMN app_url TEXT DEFAULT ''")
        conn.commit()

    def _upsert_fts(self, idea: IdeaDocument) -> None:
        """Inserta o reemplaza la entrada en ideas_fts."""
        conn = self._conn
        conn.execute("DELETE FROM ideas_fts WHERE id = ?", (idea.id,))
        tags_str = json.dumps(idea.tags)
        conn.execute(
            "INSERT INTO ideas_fts (id, title, tags, spec_body, capture_log) "
            "VALUES (?, ?, ?, ?, ?)",
            (idea.id, idea.title, tags_str, idea.spec_body, idea.capture_log),
        )
        conn.commit()

    def upsert_idea_index(self, idea: IdeaDocument) -> None:
        """
        Actualiza o inserta una idea en el índice.
        Hace INSERT OR REPLACE INTO ideas y actualiza ideas_fts.
        """
        conn = self._conn
        tags_str = json.dumps(idea.tags)
        stacks_str = json.dumps(idea.target_stack)
        conn.execute(
            """INSERT OR REPLACE INTO ideas
               (id, slug, title, status, priority, tags, target_stack,
                repo_path, app_url, created_at, updated_at, telegram_root_msg_id,
                spec_body, capture_log)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                idea.id,
                idea.slug,
                idea.title,
                idea.status.value,
                idea.priority.value,
                tags_str,
                stacks_str,
                idea.repo_path,
                getattr(idea, "app_url", "") or "",
                idea.created_at,
                idea.updated_at,
                idea.telegram_root_msg_id,
                idea.spec_body,
                idea.capture_log,
            ),
        )
        self._upsert_fts(idea)

    def get_idea_by_id(self, idea_id: str) -> Optional[IdeaDocument]:
        """Obtiene una idea por su ID desde SQLite."""
        conn = self._conn
        row = conn.execute(
            "SELECT * FROM ideas WHERE id = ?", (idea_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_idea(row)

    def list_ideas(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[IdeaDocument]:
        """
        Lista ideas filtrando por estado, tag o consulta FTS5 (q).
        La búsqueda encuentra ideas por palabras clave dentro de la bitácora o del título.
        """
        conn = self._conn
        if query:
            rows = conn.execute(
                """SELECT * FROM ideas
                   WHERE title LIKE ? OR spec_body LIKE ? OR capture_log LIKE ?
                   ORDER BY updated_at DESC""",
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            ).fetchall()
        elif status:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()
        elif tag:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE tags LIKE ? ORDER BY updated_at DESC",
                (f"%{tag}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ideas ORDER BY updated_at DESC"
            ).fetchall()

        return [self._row_to_idea(r) for r in rows]

    def get_next_id(self) -> str:
        """Genera el siguiente ID correlativo: 001, 002, ..."""
        conn = self._conn
        row = conn.execute(
            "SELECT MAX(CAST(id AS INTEGER)) FROM ideas"
        ).fetchone()
        max_id = row[0] if row and row[0] else 0
        next_id = f"{max_id + 1:03d}"
        # Inserta un placeholder para que el próximo llamado retorne el siguiente
        conn.execute(
            "INSERT INTO ideas (id, slug, title, status, priority, tags, target_stack, "
            "repo_path, app_url, created_at, updated_at) VALUES (?, 'placeholder', 'placeholder', 'inbox', 'medium', '[]', '[]', '', '', '', '')",
            (next_id,),
        )
        conn.commit()
        return next_id

    def get_idea_by_slug(self, slug: str) -> Optional[IdeaDocument]:
        """Obtiene una idea por su slug."""
        conn = self._conn
        row = conn.execute(
            "SELECT * FROM ideas WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_idea(row)

    def update_idea_fields(self, idea_id: str, **fields) -> IdeaDocument:
        """Actualiza campos específicos de una idea."""
        if not fields:
            return self.get_idea_by_id(idea_id)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [idea_id]
        self._conn.execute(
            f"UPDATE ideas SET {set_clause} WHERE id = ?", values
        )
        self._conn.commit()
        return self.get_idea_by_id(idea_id)

    def set_idea_status(self, idea_id: str, status: IdeaStatus) -> IdeaDocument:
        """Actualiza el estado de una idea."""
        return self.update_idea_fields(idea_id, status=status.value)

    def save_message_mapping(
        self, telegram_msg_id: int, idea_id: str, bot_reply_msg_id: Optional[int] = None
    ) -> None:
        """Guarda el mapeo (message_id -> idea_id) y (bot_reply_message_id -> idea_id)."""
        conn = self._conn
        conn.execute(
            "INSERT OR REPLACE INTO message_mappings (telegram_msg_id, idea_id, bot_reply_msg_id) "
            "VALUES (?, ?, ?)",
            (telegram_msg_id, idea_id, bot_reply_msg_id),
        )
        conn.commit()

    def get_idea_id_by_message(self, telegram_msg_id: int) -> Optional[str]:
        """Busca idea_id por message_id o bot_reply_msg_id de Telegram en el índice."""
        row = self._conn.execute(
            "SELECT idea_id FROM message_mappings WHERE telegram_msg_id = ? OR bot_reply_msg_id = ?",
            (telegram_msg_id, telegram_msg_id),
        ).fetchone()
        return row[0] if row else None

    def get_bot_reply_msg_id(self, telegram_msg_id: int) -> Optional[int]:
        """Obtiene el bot_reply_msg_id para un message_id de Telegram."""
        row = self._conn.execute(
            "SELECT bot_reply_msg_id FROM message_mappings WHERE telegram_msg_id = ?",
            (telegram_msg_id,),
        ).fetchone()
        return row[0] if row and row[0] else None

    def rebuild_index_from_vault(self, vault_dir: Path) -> None:
        """
        Al arrancar, escanea data/vault/*/SPEC.md y sincroniza SQLite.
        Debe completar en < 50 ms.
        """
        conn = self._conn
        conn.execute("DELETE FROM ideas_fts")
        conn.execute("DELETE FROM ideas")
        conn.commit()

        for spec_dir in sorted(vault_dir.glob("*")):
            spec_file = spec_dir / "SPEC.md"
            if not spec_file.exists():
                continue
            from app.storage.markdown_vault import read_spec_file
            data = read_spec_file(spec_file)
            metadata = data["metadata"]

            idea_id = spec_dir.name.split("-")[0] if "-" in spec_dir.name else spec_dir.name
            slug = metadata.get("slug", f"{idea_id}-uncategorized")
            title = str(metadata.get("title") or f"Idea {idea_id}")
            status_val = metadata.get("status", "inbox")
            priority_val = metadata.get("priority", "medium")
            tags = metadata.get("tags", [])
            target_stack = metadata.get("target_stack", [])

            created_raw = metadata.get("created_at")
            if hasattr(created_raw, "isoformat"):
                created_at = created_raw.isoformat()
            else:
                created_at = str(created_raw or "")

            updated_raw = metadata.get("updated_at")
            if hasattr(updated_raw, "isoformat"):
                updated_at = updated_raw.isoformat()
            else:
                updated_at = str(updated_raw or "")

            tg_root = metadata.get("telegram_root_msg_id")
            if tg_root is None or tg_root == "None" or tg_root == "":
                tg_root = None
            else:
                try:
                    tg_root = int(tg_root)
                except (ValueError, TypeError):
                    tg_root = None

            tags_clean = [str(t) for t in tags if t is not None and str(t) != "None"] if isinstance(tags, list) else []
            stack_clean = [str(s) for s in target_stack if s is not None and str(s) != "None"] if isinstance(target_stack, list) else []

            try:
                status_enum = IdeaStatus(status_val)
            except (ValueError, TypeError):
                status_enum = IdeaStatus.INBOX

            try:
                priority_enum = IdeaPriority(priority_val)
            except (ValueError, TypeError):
                priority_enum = IdeaPriority.MEDIUM

            idea = IdeaDocument(
                id=idea_id,
                slug=slug,
                title=title,
                status=status_enum,
                priority=priority_enum,
                tags=tags_clean,
                target_stack=stack_clean,
                repo_path=str(metadata.get("repo_path") or ""),
                app_url=str(metadata.get("app_url") or ""),
                created_at=created_at,
                updated_at=updated_at,
                telegram_root_msg_id=tg_root,
                spec_body=data["spec_body"],
                capture_log=data["capture_log"],
            )
            self.upsert_idea_index(idea)

    def close(self) -> None:
        """Cierra la conexión SQLite."""
        self._conn.close()

    @staticmethod
    def _row_to_idea(row: sqlite3.Row) -> IdeaDocument:
        """Convierte una fila SQLite a IdeaDocument."""
        data = dict(row)
        data["tags"] = json.loads(data["tags"]) if isinstance(data.get("tags"), str) else data.get("tags", [])
        data["target_stack"] = json.loads(data["target_stack"]) if isinstance(data.get("target_stack"), str) else data.get("target_stack", [])
        if "app_url" not in data or data["app_url"] is None:
            data["app_url"] = ""
        return IdeaDocument(**data)
