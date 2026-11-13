from app.services.near_ai import fallback,apply_curatorial_theme
import pytest

def test_bounded_owner_style_policy():
    direction=fallback("01"*32,{"chain_diversity_score":.5}).model_dump()
    assert apply_curatorial_theme(direction,"celestial")==direction
    assert apply_curatorial_theme(direction,"organic")["composition"]=="fractal_branches"
    assert apply_curatorial_theme(direction,"crystalline")["composition"]=="crystalline"
    with pytest.raises(ValueError):apply_curatorial_theme(direction,"change_auction_rules")
