"""Only normalized public features enter the database; deposit identities stay in memory."""
import time
from sqlalchemy import select,insert,update
from ..database import Swap
from .canonical_data import normalize,record_key

def persist_page(factory,page):
    values={record_key(raw):(normalize(raw),raw["status"]) for raw in page}
    if not values:return
    with factory.begin() as db:
        existing={row.key:row for row in db.scalars(select(Swap).where(Swap.key.in_(values)))}
        additions=[];changes=[]
        for key,(record,status) in values.items():
            row=existing.get(key)
            if row and any(row.normalized[field]!=record[field] for field in ("created_at_unix","origin_asset","destination_asset")):
                raise ValueError("Record identity conflict")
            value={"key":key,"created_at_unix":record["created_at_unix"],"status":status,"normalized":record,"last_verified_at":int(time.time())}
            (changes if row else additions).append(value)
        if additions:db.execute(insert(Swap),additions)
        if changes:db.execute(update(Swap),changes)
