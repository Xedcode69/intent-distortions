"""An isolated synthetic regression profile, never the active weekly database."""
from app.config import ROOT,Settings
def fixture_settings():
    directory=ROOT/'data/verification';directory.mkdir(parents=True,exist_ok=True)
    return Settings(_env_file=None,app_env='test',execution_mode='demo',
        database_url=f"sqlite:///{(directory/'fixture.db').as_posix()}",data_dir=directory,
        near_ai_api_key='',near_ai_text_model='',allow_ai_fallback=True,near_intents_partner_jwt='',
        scheduler_enabled=False,enable_chain_writes=False,signer_key_file='',near_nft_contract='',
        near_auction_contract='',near_market_contract='',onchain_art_contract='')
