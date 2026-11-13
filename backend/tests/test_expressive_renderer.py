import copy
import math
from io import BytesIO
import pytest
from PIL import Image
from app.services.asset_networks import build_asset_mapping
from app.services.canonical_data import snapshot,canonical,sha
from app.services.art_seed import GENESIS_HASH
from app.services.near_ai import fallback
from app.services.visual_features import visual_features,expressive_statistics
from app.services.expressive_renderer import scene_v4,render_v4,family_controls
from test_dataset import raw

FAMILIES=('orbital_network','fractal_branches','crystalline','flow_field','spiral_constellation','particle_nebula')
TOKENS=[{'assetId':f'asset-{i}','blockchain':network} for i,network in enumerate(('eth','sol','btc','near'))]


def data(bursty=False,unequal=False,reverse=False):
    rows=[raw(i,101+(i%3 if bursty else i*3),originAsset=f'asset-{i%4}',
              destinationAsset=f'asset-{(i+(-1 if reverse else 1))%4}',
              amountInUsd=str(10000 if unequal and i==0 else 2)) for i in range(100)]
    records=snapshot(rows,100,500)
    mapping=build_asset_mapping(TOKENS,records,observed_at=1)
    return records,mapping


def test_measurements_respond_to_bursts_size_distribution_and_route_direction():
    records,mapping=data();normal=visual_features(records,100,500,mapping)
    burst,bm=data(bursty=True);unequal,um=data(unequal=True)
    assert visual_features(burst,100,500,bm)['burstiness']>normal['burstiness']
    assert visual_features(unequal,100,500,um)['size_inequality']>normal['size_inequality']
    assert normal['reciprocity']==0 and normal['cross_network_share']==1
    back,backmap=data(reverse=True)
    assert visual_features(back,100,500,backmap)['routes']!=normal['routes']
    assert sum(node['outgoing'] for node in normal['nodes'])==len(records)
    assert all(0<=value<=1 for value in normal['activity_profile'])


@pytest.mark.parametrize('family',FAMILIES)
def test_each_family_is_deterministic_bounded_and_renders_new_primitives(family):
    records,mapping=data();stats=expressive_statistics(records,100,500,mapping)
    direction={**fallback('01'*32,stats).model_dump(),'composition':family,'material':'glass','complexity':.65}
    manifest=scene_v4('01'*32,records,stats,direction,100,500,GENESIS_HASH,1,mapping)
    assert manifest==scene_v4('01'*32,records,stats,direction,100,500,GENESIS_HASH,1,mapping)
    assert manifest['version']=='echo-renderer-4'
    assert manifest['controls']['family']==family_controls(stats['visual_features'],direction)
    assert 0<len(manifest['shapes'])<12000
    assert any(shape['kind']=='curve' for shape in manifest['shapes'])
    assert any(shape['kind']=='polygon' for shape in manifest['shapes'])
    assert manifest['animation']['pulse_hz']>0
    if family=='fractal_branches':
        roots=[shape for shape in manifest['shapes'] if shape['kind']=='curve' and shape['layer']=='geometry' and shape['points'][0]==[720,1200]]
        assert len(roots)==manifest['controls']['family']['arms']
    for shape in manifest['shapes']:
        points=shape.get('points',[shape['center']] if 'center' in shape else [])
        assert all(math.isfinite(value) and 0<=value<=1440 for point in points for value in point)
        assert 0<=shape['alpha']<=255
    files=render_v4(manifest)
    assert Image.open(BytesIO(files['artwork.png'])).size==(1440,1440)
    assert b'<path' in files['artwork.svg'] and b'<polygon' in files['artwork.svg']
    assert files['artwork.png']==render_v4(manifest)['artwork.png']


def test_family_shapes_materials_theme_and_complexity_have_visible_effects():
    records,mapping=data();stats=expressive_statistics(records,100,500,mapping)
    base={**fallback('02'*32,stats).model_dump(),'composition':'crystalline','complexity':.5,'theme':'celestial'}
    hashes=set()
    for material in ('glass','ink','grain','iridescent','luminous'):
        scene=scene_v4('02'*32,records,stats,{**base,'material':material},100,500,GENESIS_HASH,1,mapping)
        hashes.add(sha(render_v4(scene)['artwork.png']))
    assert len(hashes)==5
    dim=scene_v4('02'*32,records,stats,{**base,'material':'glass','complexity':0},100,500,GENESIS_HASH,1,mapping)
    detailed=scene_v4('02'*32,records,stats,{**base,'material':'glass','complexity':1},100,500,GENESIS_HASH,1,mapping)
    assert len(detailed['shapes'])>len(dim['shapes'])
    tidal=scene_v4('02'*32,records,stats,{**base,'material':'glass','theme':'tidal'},100,500,GENESIS_HASH,1,mapping)
    assert tidal['background_style']!=dim['background_style']
    assert sha(canonical(tidal['shapes']))!=sha(canonical(dim['shapes']))


def test_network_identity_colors_do_not_shift_when_a_network_is_added():
    records,mapping=data();stats=expressive_statistics(records,100,500,mapping)
    direction={**fallback('03'*32,stats).model_dump(),'composition':'orbital_network'}
    one=scene_v4('03'*32,records,stats,direction,100,500,GENESIS_HASH,1,mapping)
    more=copy.deepcopy(stats);more['visual_features']['nodes'].append({'network':'Added','outgoing':1,'incoming':1,'flow':0,'hub':.1,'community':50})
    two=scene_v4('03'*32,records,more,direction,100,500,GENESIS_HASH,1,mapping)
    assert all(one['network_colors'][name]==two['network_colors'][name] for name in one['network_colors'])
