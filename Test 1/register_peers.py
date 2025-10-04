#!/usr/bin/env python3
import sys, requests

NODES = [
    "http://nodeA:5000",
    "http://nodeB:5001",
    "http://nodeC:5002",
    "http://nodeD:5003",
    "http://nodeE:5004",
]

def main():
    # Register every other node on each node
    for a in NODES:
        others = [b for b in NODES if b != a]
        try:
            r = requests.post(f"{a}/nodes/register", json={"nodes": others}, timeout=5)
            print("[register]", a, r.status_code, r.text[:200])
        except Exception as e:
            print("[register error]", a, e)

    # Kick consensus on all nodes
    for a in NODES:
        try:
            r = requests.get(f"{a}/nodes/resolve", timeout=5)
            print("[consensus]", a, r.status_code, r.text[:200])
        except Exception as e:
            print("[consensus error]", a, e)

if __name__ == "__main__":
    sys.exit(main() or 0)
