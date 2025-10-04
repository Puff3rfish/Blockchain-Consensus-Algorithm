#!/usr/bin/env python3
import os, time, json, sqlite3, hashlib, requests

GATEWAY = os.getenv("GATEWAY", "http://gateway:8080")
DB_PATH = os.getenv("DB_PATH", "/data/chain_index.db")
POLL_SECS = int(os.getenv("POLL_SECS", "3"))

def hash_block(b):
    data = {
        "index": b["index"],
        "timestamp": b["timestamp"],
        "transactions": b["transactions"],
        "proof": b["proof"],
        "previous_hash": b["previous_hash"],
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def ensure_schema(c):
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS blocks (
      index_num INTEGER PRIMARY KEY,
      hash TEXT UNIQUE,
      previous_hash TEXT,
      proof INTEGER,
      timestamp REAL
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      block_index INTEGER,
      sender TEXT,
      recipient TEXT,
      amount REAL
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS balances (
      address TEXT PRIMARY KEY,
      amount REAL
    );""")
    c.commit()

def upsert_block(c, b):
    h = hash_block(b)
    cur = c.cursor()
    cur.execute("INSERT OR IGNORE INTO blocks(index_num, hash, previous_hash, proof, timestamp) VALUES (?, ?, ?, ?, ?)",
                (b["index"], h, b["previous_hash"], b["proof"], b["timestamp"]))
    cur.execute("DELETE FROM transactions WHERE block_index = ?", (b["index"],))
    for tx in b["transactions"]:
        cur.execute("INSERT INTO transactions(block_index, sender, recipient, amount) VALUES (?, ?, ?, ?)",
                    (b["index"], tx["sender"], tx["recipient"], tx["amount"]))
    c.commit()

def rebuild_balances(c):
    cur = c.cursor()
    cur.execute("DELETE FROM balances")
    cur.execute("""
    INSERT INTO balances(address, amount)
    SELECT addr, SUM(amt) FROM (
      SELECT sender AS addr, -amount AS amt FROM transactions WHERE sender <> '0'
      UNION ALL
      SELECT recipient AS addr, amount AS amt FROM transactions
    ) GROUP BY addr;
    """)
    c.commit()

def main():
    c = sqlite3.connect(DB_PATH)
    ensure_schema(c)
    last_len = -1
    while True:
        try:
            r = requests.get(f"{GATEWAY}/chain", timeout=10)
            r.raise_for_status()
            data = r.json()
            chain, length = data["chain"], data["length"]
            if length != last_len:
                for b in chain:
                    upsert_block(c, b)
                rebuild_balances(c)
                last_len = length
        except Exception as e:
            print("[indexer] error:", e)
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()
