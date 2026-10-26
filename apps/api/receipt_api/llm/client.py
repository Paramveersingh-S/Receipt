import hashlib
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from receipt_api.config import Settings, get_settings

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMChatResult(BaseModel):
    content: str
    usage: LLMUsage
    cached: bool = False


class LLMCache:
    """Persistent SQLite cache for deterministic LLM calls and replay mode."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    model TEXT,
                    prompt_hash TEXT,
                    response_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT response_json FROM llm_cache WHERE cache_key = ?", (cache_key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def set(self, cache_key: str, model: str, prompt_hash: str, response_data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (cache_key, model, prompt_hash, response_json)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, model, prompt_hash, json.dumps(response_data)),
            )
            conn.commit()


class LLMClient:
    """OpenAI-compatible client with caching, structured outputs, and retry-with-repair."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        cache_path = os.path.join(self.settings.data_dir, "llm_cache.sqlite")
        self.cache = LLMCache(cache_path)
        self.http_client = httpx.AsyncClient(
            base_url=self.settings.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=20.0, pool=30.0),
        )

    def _compute_cache_key(self, model: str, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        prompt_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{model}:{prompt_hash}", prompt_hash

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        # Default pricing estimates per 1k tokens
        pricing = {
            "gpt-4o": (0.0025, 0.010),
            "gpt-4o-mini": (0.00015, 0.0006),
        }
        p_in, p_out = pricing.get(model, (0.001, 0.002))
        return (prompt_tokens / 1000.0) * p_in + (completion_tokens / 1000.0) * p_out

    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMChatResult:
        selected_model = model or self.settings.llm_model_fast
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        cache_key, prompt_hash = self._compute_cache_key(selected_model, payload)

        # 1. Check cache in replay or live mode
        if self.settings.llm_mode in ("record", "replay"):
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                return LLMChatResult(
                    content=cached_data["content"],
                    usage=LLMUsage(**cached_data.get("usage", {})),
                    cached=True,
                )
            if self.settings.llm_mode == "replay":
                raise RuntimeError(f"LLM replay mode requested but no cache entry for key: {cache_key}")

        # 2. Execute live network call
        response = await self.http_client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("prompt_tokens", 0)
        completion_tokens = raw_usage.get("completion_tokens", 0)
        total_tokens = raw_usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost = self._estimate_cost(selected_model, prompt_tokens, completion_tokens)

        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
        )

        # 3. Store into cache
        if self.settings.llm_mode in ("live", "record"):
            self.cache.set(
                cache_key=cache_key,
                model=selected_model,
                prompt_hash=prompt_hash,
                response_data={"content": content, "usage": usage.model_dump()},
            )

        return LLMChatResult(content=content, usage=usage, cached=False)

    async def chat_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        model: Optional[str] = None,
        max_repairs: int = 2,
    ) -> T:
        """Call LLM with structured output, automatically repairing schema errors up to max_repairs."""
        current_messages = list(messages)
        schema = response_model.model_json_schema()
        system_instruction = (
            f"You MUST respond ONLY with a valid JSON object strictly complying with this JSON Schema:\n"
            f"{json.dumps(schema, indent=2)}\nDo not wrap in Markdown codeblocks unless necessary."
        )

        # Insert schema instruction into messages
        if current_messages and current_messages[0]["role"] == "system":
            current_messages[0] = {
                "role": "system",
                "content": f"{current_messages[0]['content']}\n\n{system_instruction}",
            }
        else:
            current_messages.insert(0, {"role": "system", "content": system_instruction})

        for attempt in range(max_repairs + 1):
            res = await self.chat(
                messages=current_messages,
                model=model,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            raw_text = res.content.strip()
            # Clean possible markdown fence
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            try:
                return response_model.model_validate_json(raw_text)
            except Exception as e:
                logger.warning(
                    "Structured LLM parsing error, attempting repair",
                    attempt=attempt,
                    error=str(e),
                )
                if attempt == max_repairs:
                    raise ValueError(
                        f"Failed to obtain valid {response_model.__name__} after {max_repairs} repair attempts: {e}"
                    )
                current_messages.append({"role": "assistant", "content": raw_text})
                current_messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"The output failed validation against {response_model.__name__} schema.\n"
                            f"Error details: {e}\n"
                            f"Please provide ONLY the corrected, valid JSON object."
                        ),
                    }
                )

        raise RuntimeError("Unreachable repair loop termination")

    async def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Fetch vector embeddings for a list of input texts."""
        selected_model = model or self.settings.embed_model
        payload = {"model": selected_model, "input": texts}
        cache_key, prompt_hash = self._compute_cache_key(selected_model, payload)

        if self.settings.llm_mode in ("record", "replay"):
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                return cached_data["embeddings"]
            if self.settings.llm_mode == "replay":
                raise RuntimeError(f"LLM replay mode requested but no cache entry for key: {cache_key}")

        response = await self.http_client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]

        if self.settings.llm_mode in ("live", "record"):
            self.cache.set(
                cache_key=cache_key,
                model=selected_model,
                prompt_hash=prompt_hash,
                response_data={"embeddings": embeddings},
            )

        return embeddings


_global_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _global_llm_client
    if _global_llm_client is None:
        _global_llm_client = LLMClient()
    return _global_llm_client
