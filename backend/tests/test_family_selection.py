import json
from types import SimpleNamespace
import pytest
from app.config import Settings
from app.services import family_selection
from app.services.family_selection import select_family,FAMILIES
from app.services.near_ai import creative_direction,apply_curatorial_theme,fallback,direction_statistics


def test_fixed_family_vector_and_rejection_proof(monkeypatch):
    proof=select_family('01'*32)
    assert proof=={'policy':'seed-rejection-six-v1','family':'flow_field','index':3,'counter':0,
        'digest':'8e4824dbd6908f216c056899dcf46616ee5c0424ebafd37b37b1a824db0544d9'}
    calls=[]
    def digest(key,message,algorithm):
        calls.append(int.from_bytes(message[-8:],'big'))
        return b'\xff'*32 if len(calls)==1 else b'\0'*32
    monkeypatch.setattr(family_selection.hmac,'digest',digest)
    selected=select_family('01'*32)
    assert selected['counter']==1 and selected['family']=='orbital_network' and calls==[0,1]


async def test_fallback_and_curator_styling_preserve_selected_family():
    settings=Settings(_env_file=None,near_ai_api_key='',near_ai_text_model='',allow_ai_fallback=True)
    direction,_=await creative_direction('01'*32,{'chain_diversity_score':.5},settings,'flow_field')
    for theme in ('organic','crystalline','celestial'):
        assert apply_curatorial_theme(direction,theme,preserve_family=True)['composition']=='flow_field'


@pytest.mark.parametrize('mismatch',[False,True])
async def test_ai_is_constrained_to_fixed_family_and_mismatches_fail(monkeypatch,mismatch):
    import openai
    captured={}
    class Client:
        def __init__(self,**kwargs):
            self.models=SimpleNamespace(list=self.list_models)
            self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.complete))
        async def list_models(self):return SimpleNamespace(data=[SimpleNamespace(id='unit-test')])
        async def complete(self,**kwargs):
            captured.update(kwargs)
            direction=fallback('01'*32,{'chain_diversity_score':.5}).model_dump()
            direction['composition']='crystalline' if mismatch else 'flow_field'
            return SimpleNamespace(id='mock-request',choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(direction)))])
        async def close(self):captured['closed']=True
    monkeypatch.setattr(openai,'AsyncOpenAI',Client)
    settings=Settings(_env_file=None,near_ai_api_key='unit-test',near_ai_text_model='unit-test',allow_ai_fallback=False)
    if mismatch:
        with pytest.raises(RuntimeError,match='NEAR AI generation failed'):
            await creative_direction('01'*32,{'chain_diversity_score':.5,'visual_features':{}},settings,'flow_field')
    else:
        result,_=await creative_direction('01'*32,{'chain_diversity_score':.5,'visual_features':{}},settings,'flow_field')
        assert result['composition']=='flow_field'
    prompt=json.loads(captured['messages'][1]['content'])
    assert prompt['schema']['properties']['composition']['const']=='flow_field' and captured['closed']


def test_ai_context_is_bounded_without_discarding_full_renderer_features():
    features={'route_count':100,'nodes':[{'network':str(i),'hub':i/100} for i in range(100)],
              'routes':[{'origin':str(i),'destination':'NEAR','count':i} for i in range(100)]}
    original={'visual_features':features}
    bounded=direction_statistics(original)
    assert len(bounded['visual_features']['routes'])==len(bounded['visual_features']['nodes'])==16
    assert len(original['visual_features']['routes'])==100 and bounded['visual_features']['route_count']==100
