#!/usr/bin/env python3
"""Quick latency / concurrency smoke test against a running interview-api."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def one_interview(base: str, *, answer: str) -> tuple[float, bool]:
    async with httpx.AsyncClient(base_url=base, timeout=120.0) as client:
        t0 = time.perf_counter()
        start = await client.post(
            "/interview/start",
            json={
                "job_description": "Backend engineer for payments.",
                "resume": "Python, FastAPI, Redis.",
                "evaluation_policy": {"max_main_questions": 1},
            },
        )
        start.raise_for_status()
        sid = start.json()["session_id"]
        ask = await client.post(
            "/interview/ask",
            json={"session_id": sid, "answer": answer},
        )
        ask.raise_for_status()
        return (time.perf_counter() - t0) * 1000, ask.json().get("finalized", False)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark interview API")
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.base, timeout=10.0) as client:
        m = await client.get("/metrics")
        m.raise_for_status()
        print("metrics (before):", m.json())

    tasks = [
        one_interview(args.base, answer=f"benchmark answer {i} with some detail.")
        for i in range(args.concurrency)
    ]
    wall_start = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    wall_ms = (time.perf_counter() - wall_start) * 1000

    ok: list[float] = []
    for r in results:
        if isinstance(r, Exception):
            print("error:", r)
        else:
            ok.append(r[0])
    if ok:
        print(
            f"concurrency={args.concurrency} wall_ms={wall_ms:.0f} "
            f"per_session_ms avg={statistics.mean(ok):.0f} p95={sorted(ok)[int(len(ok)*0.95)-1]:.0f}"
        )

    async with httpx.AsyncClient(base_url=args.base, timeout=10.0) as client:
        m = await client.get("/metrics")
        m.raise_for_status()
        print("metrics (after):", m.json())


if __name__ == "__main__":
    asyncio.run(main())
