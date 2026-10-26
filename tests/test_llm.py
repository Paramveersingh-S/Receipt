import os
import pytest
from pydantic import BaseModel
from receipt_api.config import Settings
from receipt_api.llm.client import LLMCache, LLMClient


class SampleResponse(BaseModel):
    name: str
    count: int


def test_llm_cache_sqlite(tmp_path):
    cache_file = tmp_path / "test_cache.sqlite"
    cache = LLMCache(str(cache_file))

    cache.set(
        cache_key="key1",
        model="gpt-4o-mini",
        prompt_hash="hash1",
        response_data={"content": "cached output"},
    )
    result = cache.get("key1")
    assert result is not None
    assert result["content"] == "cached output"
    assert cache.get("non_existent") is None


@pytest.mark.asyncio
async def test_llm_replay_mode_cached_hit(tmp_path):
    cache_file = tmp_path / "test_cache.sqlite"
    cache = LLMCache(str(cache_file))

    # Prepopulate cache
    settings = Settings(
        llm_mode="replay",
        data_dir=str(tmp_path),
    )
    client = LLMClient(settings=settings)
    client.cache = cache

    cache_key, prompt_hash = client._compute_cache_key(
        "gpt-4o-mini",
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.0,
        },
    )
    cache.set(
        cache_key=cache_key,
        model="gpt-4o-mini",
        prompt_hash=prompt_hash,
        response_data={"content": "{\"name\": \"test\", \"count\": 42}"},
    )

    res = await client.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-4o-mini",
    )
    assert res.cached is True
    assert "test" in res.content
