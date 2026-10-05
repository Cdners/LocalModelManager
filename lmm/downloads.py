from __future__ import annotations

import uuid

from .config import atomic_json, read_json


class Downloads:
    """Persist only descriptions and receipts; credentials and executable callbacks are never serialized."""
    def __init__(self, store):
        self.path=store.config/"downloads.json"
        self.records=read_json(self.path,[])
        for item in self.records:
            if item["state"] in {"Running","Queued","Pausing"}:item["state"]="Paused"
        self.save()

    def save(self):atomic_json(self.path,self.records)

    def add(self, kind, title, payload):
        existing=next((r for r in self.records if r["kind"]==kind and r["payload"]==payload and r["state"]!="Completed"),None)
        if existing:return existing
        record={"id":uuid.uuid4().hex,"kind":kind,"title":title,"payload":payload,"state":"Queued"}
        self.records.append(record); self.save(); return record

    def update(self, identity, info):
        record=next(r for r in self.records if r["id"]==identity)
        record.update({key:value for key,value in info.items() if key in {"state","downloaded","total","speed","eta","file","detail","error"}})
        self.save()
