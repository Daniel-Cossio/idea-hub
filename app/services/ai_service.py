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

    async def transcribe_voice(self, audio_url: str) -> str:
        """Transcribe una nota de voz usando Groq Whisper."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/audio/transcriptions",
                files={"file": open(audio_url, "rb")},
                data={"model": "whisper-large-v3-turbo"},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.text

    async def structure_with_llm(self, spec_body: str, system_prompt: str = "") -> str:
        """Estructura el spec_body usando un LLM (Groq / OpenAI-compatible)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": f"Estructura la siguiente especificación en formato Markdown limpio:\n\n{spec_body}",
        })
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
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def scrape_url(self, url: str) -> Dict[str, Any]:
        """Scrapea una URL y extrae título, descripción y contenido."""
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            return {
                "title": soup.title.string if soup.title else "",
                "description": soup.find("meta", {"name": "description"})?.get("content", ""),
                "content": soup.get_text()[:2000],
            }
