"""Counters only; raw provider records and cursors never enter public progress."""
import time
from ..database import Job

class CollectionProgress:
    def __init__(self,factory,number,clock=time.time):
        self.factory,self.key,self.clock=factory,f"drop:{number}:collection",clock
        with factory.begin() as db:
            row=db.get(Job,self.key)
            if row is None:row=Job(key=self.key,kind="drop_collection",attempts=0,payload={});db.add(row)
            row.attempts+=1;row.status="running";row.updated_at=int(clock());row.error=None
            row.payload={"received_rows":0,"pages":0,"total_records":None,"eligible_records":None,"collection_complete":False}
    def page(self,count):
        with self.factory.begin() as db:
            row=db.get(Job,self.key);row.payload={**row.payload,"received_rows":row.payload["received_rows"]+count,"pages":row.payload["pages"]+1};row.updated_at=int(self.clock())
    def complete(self,total,eligible):
        with self.factory.begin() as db:
            row=db.get(Job,self.key);row.status="succeeded";row.updated_at=int(self.clock());row.payload={**row.payload,"total_records":total,"eligible_records":eligible,"collection_complete":True}

def generation_phase(factory,key,phase):
    with factory.begin() as db:
        row=db.get(Job,key);row.payload={**row.payload,"phase":phase};row.updated_at=int(time.time())
