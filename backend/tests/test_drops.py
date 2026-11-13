import json
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.database import Base,Artwork,Epoch,Release,Job
from app.services.drops import drop_feed
from app.services.drop_progress import CollectionProgress,generation_phase

def ts(date):return int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())
FIRST=ts('2026-11-15')
@pytest.fixture
def factory(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'drops.db'}");Base.metadata.create_all(engine)
    yield sessionmaker(engine,expire_on_commit=False)
    engine.dispose()
def settings(mode='live'):
    return Settings(_env_file=None,execution_mode=mode,first_release_sunday='2026-11-15')
def release(db,n,state):
    row=Release(number=n,sunday=FIRST+(n-1)*604800,freeze_at=FIRST+(n-1)*604800+19*3600,state=state,payload={},updated_at=FIRST)
    db.add(row);return row
def artwork(db,n=1,mode='live',sunday=None):
    ident=f'{mode}-{n:06d}';date=sunday if sunday is not None else FIRST+(n-1)*604800
    db.add(Epoch(id=ident,number=n,mode=mode,status='rendered',start=date-604800,end=date,payload={'selection':{'sunday_start':date},'records':[{'private':'must not be returned'}]}));db.flush()
    p={'id':ident,'number':n,'edition':f'ECHO-{n:06d}','mode':mode,'title':f'Echo {n}','description':'Frozen artwork','composition':'crystalline',
        'image':'/api/v1/content/'+f'{n:064x}','thumbnail':'/thumb','image_hash':f'{n:064x}','seed':'a'*64,'start':date-604800,'end':date,
        'stats':{'total_swaps':7,'unique_chains':3},'nft':{'status':'minted' if mode=='live' else 'not_minted'},'auction':{'status':'Active' if mode=='live' else 'not_created'}}
    db.add(Artwork(id=ident,epoch_id=ident,image_hash=p['image_hash'],payload=p));return p

def test_first_drop_schedule_does_not_start_generation_or_pretend_18utc_is_completion(factory):
    d=drop_feed(factory,settings(),now=ts('2026-11-13T12:00:00'))
    assert d['upcoming']['number']==1 and d['upcoming']['sunday']==FIRST
    assert d['upcoming']['beacon_at']==FIRST+18*3600 and d['upcoming']['freeze_at']==FIRST+19*3600
    assert d['upcoming']['delivery']=='creator' and d['active'] is None and d['previous']==[]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Release))==db.scalar(select(func.count()).select_from(Job))==0

def test_old_active_auction_does_not_hide_next_creation_and_artwork_appears_when_saved(factory):
    with factory.begin() as db:
        release(db,1,'auction_active');artwork(db)
    d=drop_feed(factory,settings(),now=ts('2026-11-20'))
    assert d['upcoming']['number']==2 and d['active']['number']==1 and d['active']['phase']=='ready'
    assert d['active']['artwork']['nft_status']=='minted'
    with factory.begin() as db:
        r=release(db,2,'collecting');r.payload={'block':{'height':42,'hash':'public-block','provider_secret':'hidden'}}
    progress=CollectionProgress(factory,2,lambda:ts('2026-11-22T18:10:00'));progress.page(1000)
    d=drop_feed(factory,settings(),now=ts('2026-11-22T18:11:00'))
    assert d['upcoming']['number']==d['active']['number']==2 and d['active']['phase']=='collection'
    assert d['active']['progress']['received_rows']==1000 and d['active']['progress']['total_records'] is None
    assert d['previous'][0]['number']==1 and d['active']['selected_block']=={'height':42,'hash':'public-block'}
    assert 'hidden' not in json.dumps(d) and 'must not be returned' not in json.dumps(d)
    with factory.begin() as db:artwork(db,2);db.get(Release,2).state='awaiting_signer'
    d=drop_feed(factory,settings(),now=ts('2026-11-22T19:10:00'))
    assert d['upcoming']['number']==3 and d['active']['artwork']['number']==2 and d['active']['phase']=='ready'
    assert d['active']['state']=='awaiting_signer' and [a['number'] for a in d['previous']]==[1]

def test_progress_counts_each_pass_and_exposes_only_successful_contribution_count(factory):
    with factory.begin() as db:release(db,1,'collecting')
    p=CollectionProgress(factory,1,lambda:FIRST+18*3600);p.page(1000);p.page(50);p.complete(1040,700)
    d=drop_feed(factory,settings(),now=FIRST+18*3600+300)
    assert d['active']['phase']=='reconciliation' and d['active']['progress']['received_rows']==1050
    assert d['active']['progress']['eligible_records']==700 and d['active']['progress']['total_records']==1040
    p=CollectionProgress(factory,1,lambda:FIRST+18*3600+400);p.page(40)
    d=drop_feed(factory,settings(),now=FIRST+18*3600+410)
    assert d['active']['progress']['pass_number']==2 and d['active']['progress']['received_rows']==40
    assert d['active']['progress']['collection_complete'] is False and d['active']['progress']['eligible_records'] is None

def test_generation_phase_and_delays_are_read_from_the_correct_edition(factory):
    with factory.begin() as db:
        r=release(db,1,'rendering');r.error='RecordedFailureType'
        db.add(Job(key='live-000001:generate-v1',kind='generate_epoch',status='running',payload={}))
    generation_phase(factory,'live-000001:generate-v1','preparing_files')
    d=drop_feed(factory,settings(),now=FIRST+19*3600)
    assert d['active']['phase']=='preparing_files' and d['active']['last_error_type']=='RecordedFailureType'

def test_missed_drop_is_not_silently_skipped_when_worker_has_not_started(factory):
    d=drop_feed(factory,settings(),now=ts('2026-12-15'))
    assert d['upcoming']['number']==1 and d['active']['phase']=='awaiting_worker'
    with factory.begin() as db:release(db,1,'scheduled')
    assert drop_feed(factory,settings(),now=FIRST+18*3600+100)['active']['phase']=='awaiting_worker'

def test_preview_uses_launch_schedule_without_counting_replay_as_a_live_drop(factory):
    with factory.begin() as db:artwork(db,mode='historical_replay',sunday=ts('2026-11-08'))
    s=settings('historical_replay');s.first_release_sunday='2026-11-08'
    d=drop_feed(factory,s,now=ts('2026-11-13'))
    assert d['preview'] and d['upcoming']['number']==1 and d['upcoming']['sunday']==FIRST
    assert d['active'] is None and d['previous'][0]['sunday']==ts('2026-11-08')
    assert d['previous'][0]['mode']=='historical_replay' and d['previous'][0]['nft_status']=='not_minted'

def test_archive_is_paginated_and_switches_to_24h_auctions_in_december(factory):
    with factory.begin() as db:
        for n in range(1,5):release(db,n,'settled');artwork(db,n)
    d=drop_feed(factory,settings(),now=ts('2026-12-10'),offset=1,limit=1)
    assert d['upcoming']['number']==5 and d['upcoming']['delivery']=='auction' and d['upcoming']['auction_hours']==24
    assert d['total_previous']==3 and [a['number'] for a in d['previous']]==[2]

async def test_live_worker_persists_actual_page_counts_and_successful_interval_counts(factory,tmp_path):
    from app.workers.production import Worker
    from test_dataset import raw
    s=settings();s.data_dir=tmp_path
    class Collector:
        async def collect(self,start,end,page_size,on_page):
            records=[raw(1,start+1),raw(2,start+2,status='FAILED')]
            on_page(records);return records,{'complete':True,'pages':1}
    class RPC:
        async def first_block_at(self,target):return {'height':42,'hash':'verified-block','timestamp_ns':str(target*10**9)}
    async def beacon(_):return {'randomness':'01'*32}
    w=Worker(factory,s,clock=lambda:FIRST+18*3600+100,collector=Collector(),rpc=RPC(),beacon_fetch=beacon)
    w.release(1);await w.advance(1)
    d=drop_feed(factory,s,now=FIRST+18*3600+101)
    assert d['active']['state']=='collecting' and d['active']['phase']=='reconciliation'
    p=d['active']['progress'];assert p['received_rows']==2 and p['pages']==1 and p['total_records']==2 and p['eligible_records']==1
    assert 'deposit-' not in json.dumps(d)
