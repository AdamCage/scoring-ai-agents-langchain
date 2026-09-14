#!/usr/bin/env python3
from __future__ import annotations

import sys

import httpx


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    health = httpx.get(f"{base}/api/health", timeout=10)
    health.raise_for_status()
    print(health.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
