#!/usr/bin/env python3
import os, itertools
from typing import List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

def env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [p if p.startswith("http") else f"http://{p}" for p in parts]

# Inside the docker network, services resolve by name:
# nodeA:5000, nodeB:5001, ...
NODE_URLS = env_list(
    "NODE_URLS",
    "nodeA:5000,nodeB:5001,nodeC:5002,nodeD:5003,nodeE:5004"
)

TIMEOUT = httpx.Timeout(5.0, read=10.0)
client = httpx.Client(timeout=TIMEOUT)
_rr = itertools.cycle(range(len(NODE_URLS)))

app = FastAPI(title="Blockchain Gateway")

def pick_nodes(order: str = "roundrobin") -> List[str]:
    if order == "roundrobin":
        start = next(_rr)
        return NODE_URLS[start:] + NODE_URLS[:start]
    return NODE_URLS

def try_get(path: str):
    errors = []
    for base in pick_nodes():
        try:
            r = client.get(f"{base}{path}")
            if r.status_code == 200:
                return r.json()
            errors.append((base, r.status_code))
        except Exception as e:
            errors.append((base, str(e)))
    raise HTTPException(status_code=502, detail={"message":"all nodes failed", "errors": errors})

def try_post(path: str, json: Dict[str, Any]):
    errors = []
    for base in pick_nodes():
        try:
            r = client.post(f"{base}{path}", json=json)
            if 200 <= r.status_code < 300:
                return r.json()
            errors.append((base, r.status_code, r.text[:200]))
        except Exception as e:
            errors.append((base, str(e)))
    raise HTTPException(status_code=502, detail={"message":"all nodes failed", "errors": errors})

class Tx(BaseModel):
    sender: str
    recipient: str
    amount: float

@app.get("/health")
def health():
    return try_get("/ping")

@app.get("/chain")
def chain():
    return try_get("/chain")

@app.get("/peers")
def peers():
    return try_get("/nodes")

@app.post("/tx")
def create_tx(tx: Tx):
    # broadcast to all nodes, return first success
    errors = []
    for base in pick_nodes():
        try:
            r = client.post(f"{base}/transactions/new", json=tx.dict())
            if 200 <= r.status_code < 300:
                return {"ok": True, "node": base, "response": r.json()}
            errors.append((base, r.status_code, r.text[:200]))
        except Exception as e:
            errors.append((base, str(e)))
    raise HTTPException(status_code=502, detail={"message":"broadcast failed", "errors": errors})

@app.post("/mine")
def mine_block():
    return try_get("/mine")

@app.post("/consensus")
def consensus_all():
    results = []
    for base in pick_nodes():
        try:
            r = client.get(f"{base}/nodes/resolve")
            results.append({"node": base, "status": r.status_code, "body": r.json() if r.status_code==200 else r.text[:200]})
        except Exception as e:
            results.append({"node": base, "error": str(e)})
    return {"results": results}
