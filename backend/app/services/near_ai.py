from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .art_seed import random_value

class Direction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    theme: str = Field(max_length=300)
    composition: Literal["orbital_network", "fractal_branches", "crystalline", "flow_field", "spiral_constellation", "particle_nebula"]
    palette: list[str] = Field(min_length=3, max_length=5)
    material: str = Field(max_length=100)
    symmetry: int = Field(ge=1, le=12)
    complexity: float = Field(ge=0, le=1)
    description: str = Field(max_length=600)

    @classmethod
    def validate_output(cls, value):
        import re
        d = cls.model_validate(value)
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in d.palette):
            raise ValueError("Invalid palette")
        return d

def fallback(seed, stats):
    families = ["orbital_network", "fractal_branches", "crystalline", "flow_field", "spiral_constellation", "particle_nebula"]
    names = ["The Shape of Elsewhere", "A Thousand Quiet Currents", "Between Two Constellations", "Where the Light Returns"]
    return Direction(title=names[int(random_value(seed, "layout", 0)*len(names))],
                     theme="A field of connected histories", composition=families[int(random_value(seed, "layout", 1)*6)],
                     palette=["#75F0C0", "#9A87F5", "#E9C98B", "#378A91"], material="luminous mineral threads",
                     symmetry=3+int(random_value(seed, "geometry", 0)*5), complexity=stats["chain_diversity_score"],
                     description="Cross-chain journeys accumulate into a luminous topology. Each curve holds a route; each point carries a moment.")

def apply_curatorial_theme(direction,theme):
    # Published bounded style policy. The transaction-derived seed is untouched.
    if theme=="organic":
        direction={**direction,"composition":"fractal_branches","material":"branching luminous fibers"}
    elif theme=="crystalline":
        direction={**direction,"composition":"crystalline","material":"translucent crystalline facets"}
    elif theme!="celestial":
        raise ValueError("Unsupported curatorial theme")
    return Direction.validate_output(direction).model_dump()

async def creative_direction(seed, stats, settings):
    default = fallback(seed, stats)
    if not settings.near_ai_api_key or not settings.near_ai_text_model:
        if not settings.allow_ai_fallback:raise ValueError("NEAR AI is required by the published production policy")
        return default.model_dump(), {"provider": "deterministic_fallback", "reason": "NEAR AI credentials/model not configured", "policy": "first-valid-v1"}
    from openai import AsyncOpenAI
    import json
    client = AsyncOpenAI(api_key=settings.near_ai_api_key, base_url=settings.near_ai_base_url, max_retries=0, timeout=60)
    try:
        models = await client.models.list()
        if settings.near_ai_text_model not in {m.id for m in models.data}:
            raise ValueError("Configured model is absent from current catalog")
        prompt = {"statistics": stats, "art_seed": seed, "schema": Direction.model_json_schema()}
        response = await client.chat.completions.create(model=settings.near_ai_text_model, temperature=0,
            messages=[{"role": "system", "content": "Act as a generative art director. Return only JSON matching the supplied schema. Use only aggregate statistics. Do not add identifiers or financial rules."},
                      {"role": "user", "content": json.dumps(prompt)}])
        value = Direction.validate_output(json.loads(response.choices[0].message.content))
        return value.model_dump(), {"provider": "near_ai_cloud", "model": settings.near_ai_text_model,
            "request_id": response.id, "policy": "first-valid-v1", "temperature": 0, "prompt": prompt,
            "reproducibility": "Replay the persisted response; LLM reruns are not guaranteed identical"}
    except Exception as exc:
        if not settings.allow_ai_fallback:raise RuntimeError("NEAR AI generation failed; edition remains pending") from None
        # Never log SDK errors containing request headers or keys.
        return default.model_dump(), {"provider": "deterministic_fallback", "reason": type(exc).__name__, "policy": "first-valid-v1"}
    finally:
        await client.close()
