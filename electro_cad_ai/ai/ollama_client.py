"""
Клиент для Ollama API
"""

import httpx
import json
import base64
from typing import Optional, Dict, Any, List


class OllamaClient:
    """Клиент для взаимодействия с Ollama API"""

    VISION_MODEL = "qwen3-vl:30b"
    TEXT_MODEL = "qwen3:latest"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def generate_text(self,
                            prompt: str,
                            system_prompt: Optional[str] = None,
                            temperature: float = 0.2,
                            format_json: bool = True) -> Dict[str, Any]:
        """Генерация текста через qwen3:latest"""
        payload = {
            "model": self.TEXT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        if format_json:
            payload["format"] = "json"

        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        text_response = result.get("response", "")

        if format_json:
            try:
                return json.loads(text_response)
            except json.JSONDecodeError:
                return self._extract_json_from_text(text_response)

        return {"response": text_response}

    async def analyze_image(self,
                            image_path: str,
                            prompt: str,
                            system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Анализ изображения через qwen3-vl:30b"""
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            image_base64 = base64.b64encode(image_bytes).decode()

        payload = {
            "model": self.VISION_MODEL,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 4096
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        text_response = result.get("response", "")

        try:
            return json.loads(text_response)
        except json.JSONDecodeError:
            return self._extract_json_from_text(text_response)

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Извлечь JSON из текста"""
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0].strip()
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                json_str = text[start:end + 1]
            else:
                return {"raw_response": text, "error": "No JSON found"}

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            return {"raw_response": text, "error": f"JSON parse error: {e}"}

    async def chat(self,
                   messages: List[Dict[str, str]],
                   model: Optional[str] = None) -> str:
        """Chat API для многоступенчатого диалога"""
        payload = {
            "model": model or self.TEXT_MODEL,
            "messages": messages,
            "stream": False
        }

        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()

        result = response.json()
        return result.get("message", {}).get("content", "")

    async def check_model(self, model_name: str) -> bool:
        """Проверить, загружена ли модель"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return model_name in models
        except:
            return False

    async def pull_model(self, model_name: str) -> bool:
        """Загрузить модель"""
        import subprocess
        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=3600
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error pulling model: {e}")
            return False

    async def close(self):
        """Закрыть соединение"""
        await self.client.aclose()