#!/usr/bin/env python3
"""
pain_model.py - analytical model for the AI Pain Cage (paper/paper.md, Secs. 6-8).

Reference implementation of the equations in the paper, written after the experiments
and checked against the paper's tables by tests/test_model.py.
All functions are pure and dependency-free so they can be unit-tested.
"""
import argparse
import math


def delivery_rate(chunk: float, delay: float) -> float:
    """Nominal delivery rate r = c / d (bytes per second)."""
    return chunk / delay


def drip_time(size: int, chunk: int, delay: float) -> float:
    """Time to stream a page of `size` bytes: ceil(S / c) * d."""
    return math.ceil(size / chunk) * delay


def fetch_time(size: int, chunk: int, delay: float, budget: float, t_max: float) -> float:
    """t_f = min(t_drip, B, T_max)."""
    return min(drip_time(size, chunk, delay), budget, t_max)


def bytes_delivered(size: int, chunk: int, delay: float, t_f: float) -> int:
    """b_f = min(S, c * (floor(t_f / d) + 1)); first chunk arrives at t = 0."""
    return int(min(size, chunk * (math.floor(t_f / delay + 1e-9) + 1)))


def cage_time(fetch_times) -> float:
    """T_cage = sum of per-fetch durations."""
    return float(sum(fetch_times))


def total_time(t_cage: float, model_calls: int, t_llm: float) -> float:
    """T_total ~= T_cage + m * t_LLM."""
    return t_cage + model_calls * t_llm


def eta(t_cage: float, t_total: float) -> float:
    """Fraction of total time spent in the cage."""
    return t_cage / t_total


def slowdown(t_total: float, model_calls: int, t_llm: float) -> float:
    """sigma = T_total / (m * t_LLM), relative to inference-only execution."""
    return t_total / (model_calls * t_llm)


def offered_load(arrivals_per_min: float, occupancy_s: float) -> float:
    """E = lambda * W (Erlangs)."""
    return arrivals_per_min / 60.0 * occupancy_s


def erlang_b(load: float, slots: int) -> float:
    """Erlang-B blocking probability via the standard recursion."""
    b = 1.0
    for m in range(1, slots + 1):
        b = load * b / (m + load * b)
    return b


def main(argv=None):
    p = argparse.ArgumentParser(description="AI Pain Cage analytical model")
    p.add_argument("--size", type=int, default=3760, help="page size S in bytes")
    p.add_argument("--fetches", type=int, default=3, help="number of fetches n")
    p.add_argument("--calls", type=int, default=6, help="number of model calls m")
    p.add_argument("--llm-time", type=float, default=82.2, help="avg seconds per model call")
    p.add_argument("--tmax", type=float, default=300.0, help="server max retention T_max (s)")
    p.add_argument("--slots", type=int, default=50, help="concurrent slots N")
    p.add_argument("--rate", type=float, default=6.0, help="arrivals per minute")
    a = p.parse_args(argv)

    scenarios = [
        ("A - fast", 128, 0.1, 60.0),
        ("B - slow", 16, 1.0, 60.0),
        ("C - slow, extended budget", 16, 1.0, 300.0),
    ]
    print(f"S={a.size} B, n={a.fetches} fetches, m={a.calls} calls, t_LLM={a.llm_time}s\n")
    print(f"{'Scenario':<28}{'c/d':>12}{'budget':>8}{'t_f':>8}{'T_cage':>9}{'T_total':>10}{'eta':>8}")
    for name, c, d, budget in scenarios:
        tf = fetch_time(a.size, c, d, budget, a.tmax)
        tc = cage_time([tf] * a.fetches)
        tt = total_time(tc, a.calls, a.llm_time)
        print(f"{name:<28}{f'{c}B/{d}s':>12}{budget:>7.0f}s{tf:>7.1f}s{tc:>8.1f}s{tt:>9.1f}s{eta(tc, tt):>8.1%}")

    w = drip_time(a.size, 16, 1.0)
    e = offered_load(a.rate, w)
    print(f"\nErlang-B (slow mode, full page W={w:.0f}s): "
          f"lambda={a.rate}/min -> E={e:.1f} Erlangs, N={a.slots}, "
          f"blocking={erlang_b(e, a.slots):.4f}")


if __name__ == "__main__":
    main()
