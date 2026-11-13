from typing import Literal,Annotated
from pydantic import BaseModel, ConfigDict, Field,StringConstraints
from .art_seed import random_value

class DirectionGenerationError(RuntimeError):
    def __init__(self,stage,error):
        super().__init__("NEAR AI generation failed; edition remains pending")
        self.safe_reason={"stage":stage,"error_type":type(error).__name__}
        status=getattr(error,"status_code",None)
        if type(status) is int:self.safe_reason["http_status"]=status


def direction_statistics(stats):
    """Keep AI context bounded; the renderer and provenance retain every feature."""
    value={**stats}
    if "visual_features" in stats:
        features=stats["visual_features"]
        value["visual_features"]={**features,
            "nodes":sorted(features.get("nodes",[]),key=lambda row:(-row["hub"],row["network"]))[:16],
            "routes":sorted(features.get("routes",[]),key=lambda row:(-row["count"],row["origin"],row["destination"]))[:16],
            "ai_context_sampling":"Top 16 network hubs and routes; scalar measurements describe the complete capture"}
    return value

class Direction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    theme: str = Field(max_length=300)
    composition: Literal["orbital_network", "fractal_branches", "crystalline", "flow_field", "spiral_constellation", "particle_nebula"]
    palette: list[Annotated[str,StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]] = Field(min_length=3, max_length=5)
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

def apply_curatorial_theme(direction,theme,preserve_family=False):
    # Published bounded style policy. The transaction-derived seed is untouched.
    if theme=="organic":
        direction={**direction,"theme":"botanical growth","material":"grain"} if preserve_family else {**direction,"composition":"fractal_branches","material":"branching luminous fibers"}
    elif theme=="crystalline":
        direction={**direction,"theme":"celestial crystalline light","material":"glass"} if preserve_family else {**direction,"composition":"crystalline","material":"translucent crystalline facets"}
    elif theme!="celestial":
        raise ValueError("Unsupported curatorial theme")
    return Direction.validate_output(direction).model_dump()

async def creative_direction(seed, stats, settings, selected_family=None):
    default = fallback(seed, stats)
    if selected_family is not None:
        from .family_selection import FAMILIES
        if selected_family not in FAMILIES:raise ValueError("Invalid fixed art family")
        default=Direction.validate_output({**default.model_dump(),"composition":selected_family})
    if not settings.near_ai_api_key or not settings.near_ai_text_model:
        if not settings.allow_ai_fallback:raise ValueError("NEAR AI is required by the published production policy")
        return default.model_dump(), {"provider": "deterministic_fallback", "reason": "NEAR AI credentials/model not configured", "policy": "first-valid-v1"}
    from openai import AsyncOpenAI
    import json
    client = AsyncOpenAI(api_key=settings.near_ai_api_key, base_url=settings.near_ai_base_url, max_retries=0, timeout=60)
    stage="catalog"
    try:
        models = await client.models.list()
        if settings.near_ai_text_model not in {m.id for m in models.data}:
            raise ValueError("Configured model is absent from current catalog")
        prompt = {"statistics": direction_statistics(stats), "art_seed": seed, "schema": Direction.model_json_schema()}
        if selected_family is not None:
            prompt["schema"]["properties"]["composition"]={"type":"string","const":selected_family}
            prompt["selected_family"]=selected_family
        instruction="Act as a generative art director. Return only JSON matching the supplied schema. Use only aggregate statistics. Do not add identifiers or financial rules. Palette entries must be literal six-digit RGB hex colors such as #8CB6D8: no color names, gradients, transparency suffixes or descriptions."
        if "visual_features" in stats:
            instruction+=" Material must be one of glass, ink, grain, iridescent, luminous; these are implemented rendering profiles. Theme may describe celestial, tidal, botanical, ember or electric moods. Complexity controls actual detail budgets. Style the fixed selected_family using the measured flows, burstiness, communities and distributions. Do not change its composition. Prefer a coherent palette with deliberate contrast."
        stage="request"
        response = await client.chat.completions.create(model=settings.near_ai_text_model, temperature=0,
            messages=[{"role": "system", "content": instruction},
                      {"role": "user", "content": json.dumps(prompt)}])
        stage="json"
        decoded=json.loads(response.choices[0].message.content)
        stage="validation"
        value = Direction.validate_output(decoded)
        stage="family"
        if selected_family is not None and value.composition!=selected_family:
            raise ValueError("AI changed the verifiably selected family")
        return value.model_dump(), {"provider": "near_ai_cloud", "model": settings.near_ai_text_model,
            "request_id": response.id, "policy": "first-valid-v1", "temperature": 0, "prompt": prompt,
            "reproducibility": "Replay the persisted response; LLM reruns are not guaranteed identical"}
    except Exception as exc:
        if not settings.allow_ai_fallback:raise DirectionGenerationError(stage,exc) from None
        # Never log SDK errors containing request headers or keys.
        return default.model_dump(), {"provider": "deterministic_fallback", "reason": type(exc).__name__, "policy": "first-valid-v1"}
    finally:
        await client.close()
