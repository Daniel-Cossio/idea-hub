"""Hito 1: Core Foundation — Cliente httpx async para Groq Whisper, LLM Structurer y URL scraper."""

import httpx
from typing import Optional, Dict, Any
from app.config import Settings


class AIService:
    """Cliente de servicios de IA: transcripción de voz, estructuración con LLM y scraping de URLs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.ai_base_url
        self.api_key = settings.ai_api_key

    async def transcribe_voice(self, audio_path: str) -> str:
        """Transcribe una nota de voz usando Groq Whisper."""
        if not self.api_key:
            return "[Nota de voz sin transcribir — AI_API_KEY no configurada]"
        try:
            with open(audio_path, "rb") as f:
                content = f.read()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    files={"file": ("audio.ogg", content, "audio/ogg")},
                    data={"model": "whisper-large-v3-turbo"},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("text", "").strip()
                return f"[Error transcripción {response.status_code}: {response.text[:120]}]"
        except Exception as e:
            return f"[Error procesando audio: {e}]"

    async def structure_with_llm(self, spec_body: str, system_prompt: str = "") -> str:
        """Estructura el spec_body usando un LLM (Groq / OpenAI-compatible)."""
        if not self.api_key:
            return spec_body
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": f"Estructura la siguiente especificación en formato Markdown limpio con secciones claras:\n\n{spec_body}",
        })
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": messages,
                        "max_tokens": 4096,
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception:
            pass
        return spec_body

    async def scrape_url(self, url: str) -> Dict[str, Any]:
        """Scrapea una URL y extrae título, descripción y contenido."""
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            return {
                "title": soup.title.string if soup.title else "",
                "description": soup.find("meta", {"name": "description"}).get("content", "") if soup.find("meta", {"name": "description"}) else "",
                "content": soup.get_text()[:2000],
            }
