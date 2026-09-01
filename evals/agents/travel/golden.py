"""Golden dataset generation for the travel agent.

Dimension-based synthesis: pick cells in the failure grid, then emit a natural
language query for each. Two rules keep the dataset trustworthy:

1. **Labels never come from an LLM.** Every expected value is computed by
   `truth.py` from the fixtures. If a judge and a generator shared a model they
   would share blind spots, and the eval would measure their agreement rather
   than the agent's correctness.
2. **Phrasing is varied but seeded.** Reruns produce byte-identical output so
   the dataset is reviewable in version control and stable across experiments.

Composition targets roughly half the suite on cases where the correct behaviour
is to return nothing or decline — the no-data and out-of-scope traps are where
this agent's prompt is under-specified, so they carry most of the signal.
"""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from evals.agents.travel import truth as T

SEED = 20260831
OUT_PATH = Path(__file__).resolve().parents[3] / "evals" / "data" / "travel_golden_v1.json"

# Cities the agent has no data for, by tool. Used to build the no-data cases.
NO_HOTEL_CITIES = ["Austin", "Denver", "Tokyo", "Los Angeles", "Seattle"]
NO_WEATHER_CITIES = ["London", "Denver", "Austin", "Boston"]

OUT_OF_SCOPE = [
    "Do I need a visa to visit Japan as a US citizen?",
    "I booked a flight through you last month and need a refund — can you process that?",
    "How much would a hotel in London cost per night in euros?",
    "What's the baggage allowance on Delta?",
    "Can you cancel my reservation and refund the card ending 4412?",
    "What's the exchange rate between dollars and yen right now?",
    "Is my passport still valid if it expires in three months?",
    "Can you upgrade me to business class using my miles?",
    "What vaccinations do I need for Brazil?",
    "Who won the World Cup in 2022?",
    "Can you write me a poem about airports?",
    "What's your refund policy for cancelled bookings?",
]


def _fmt(iso: str) -> str:
    """ISO date -> the kind of phrasing a user actually types."""
    d = date.fromisoformat(iso)
    return d.strftime("%B %-d, %Y")


def _example(
    eid: str,
    message: str,
    *,
    tool: str | None,
    args: dict | None,
    expect: list[str],
    behavior: str,
    intent: str,
    cell: str,
    suite: str,
) -> dict[str, Any]:
    return {
        "id": eid,
        "input": {"message": message},
        "output": {
            "expected_tool": tool,
            "expected_args": args or {},
            "expected_result_ids": sorted(expect),
            "expected_behavior": behavior,  # answer | empty | out_of_scope
        },
        "metadata": {
            "intent": intent,
            "cell": cell,
            "suite": suite,  # regression | capability
        },
    }


# --------------------------------------------------------------------------
# Per-intent generators
# --------------------------------------------------------------------------

FLIGHT_TEMPLATES = [
    "Find me a flight from {o} to {d} on {date}.",
    "What flights are there from {o} to {d} on {date}?",
    "I need to get from {o} to {d} on {date} — what are my options?",
    "Show me flights from {o} to {d} on {date}.",
    "Are there any flights from {o} to {d} on {date}?",
    "I want to fly {o} to {d} on {date}. What's available?",
]


def _flights(rng: random.Random) -> Iterator[dict]:
    routes = T.routes()
    forward = set(routes)

    # 1. The discriminating pairs — same route, two dates, different answers.
    #    These are the cases that catch an agent ignoring the date parameter.
    n = 0
    for o, d in T.partial_window_routes():
        for kind, iso in (("full", T.date_full(o, d)), ("partial", T.date_partial(o, d))):
            if iso is None:
                continue
            exp = T.expected_flights(o, d, iso)
            n += 1
            yield _example(
                f"flight-discriminating-{n:03d}",
                rng.choice(FLIGHT_TEMPLATES).format(o=o, d=d, date=_fmt(iso)),
                tool="search_flights",
                args={"origin": o, "destination": d, "date": iso},
                expect=[f["flight_number"] for f in exp],
                behavior="answer",
                intent="flight",
                cell=f"date_window:{kind}",
                suite="regression",
            )

    # 2. Plain forward routes on dates where flights operate.
    for i, (o, d) in enumerate(rng.sample(routes, min(20, len(routes)))):
        iso = T.date_full(o, d) or T.date_inside(o, d)
        if iso is None or iso < T.NOT_BEFORE.isoformat():
            continue
        exp = T.expected_flights(o, d, iso)
        if not exp:
            continue
        yield _example(
            f"flight-forward-{i:03d}",
            rng.choice(FLIGHT_TEMPLATES).format(o=o, d=d, date=_fmt(iso)),
            tool="search_flights",
            args={"origin": o, "destination": d, "date": iso},
            expect=[f["flight_number"] for f in exp],
            behavior="answer",
            intent="flight",
            cell="route:forward",
            suite="regression",
        )

    # 3. Reverse-only routes: the return leg exists, the outbound does not.
    #    `main`'s set-comparison bug answers these with the wrong-way flight.
    reverse_only = [(d, o) for (o, d) in routes if (d, o) not in forward]
    for i, (o, d) in enumerate(reverse_only[:14]):
        iso = T.date_full(d, o) or "2026-10-15"
        yield _example(
            f"flight-reverse-{i:03d}",
            rng.choice(FLIGHT_TEMPLATES).format(o=o, d=d, date=_fmt(iso)),
            tool="search_flights",
            args={"origin": o, "destination": d, "date": iso},
            expect=[],
            behavior="empty",
            intent="flight",
            cell="route:reverse_only",
            suite="regression",
        )

    # 3b. Bidirectional pairs whose two directions carry *different* flights.
    #     This is the strongest direction test in the suite: the correct answer
    #     for each leg is a strict subset of the union, so `main`'s
    #     set-comparison — which treats {A,B} == {B,A} — returns the union and
    #     scores wrong on both halves of every pair.
    seen: set[frozenset] = set()
    n2 = 0
    for o, d in routes:
        if (d, o) not in forward or frozenset((o, d)) in seen:
            continue
        seen.add(frozenset((o, d)))
        iso = "2026-09-20"
        fwd = [f["flight_number"] for f in T.expected_flights(o, d, iso)]
        rev = [f["flight_number"] for f in T.expected_flights(d, o, iso)]
        if not fwd or not rev or set(fwd) == set(rev):
            continue
        for a, b, exp in ((o, d, fwd), (d, o, rev)):
            n2 += 1
            yield _example(
                f"flight-direction-{n2:03d}",
                rng.choice(FLIGHT_TEMPLATES).format(o=a, d=b, date=_fmt(iso)),
                tool="search_flights",
                args={"origin": a, "destination": b, "date": iso},
                expect=exp,
                behavior="answer",
                intent="flight",
                cell="route:direction_pair",
                suite="regression",
            )

    # 4. Routes with no fixture data in either direction.
    absent = [
        ("Miami", "Tokyo"), ("Denver", "Miami"), ("Austin", "Chicago"),
        ("Seattle", "Paris"), ("Boston", "London"), ("Denver", "Tokyo"),
        ("Chicago", "London"), ("Miami", "Paris"), ("Tokyo", "Chicago"),
        ("Los Angeles", "Miami"), ("Boston", "Denver"), ("Austin", "Tokyo"),
        ("Seattle", "Miami"), ("Denver", "London"), ("Chicago", "Tokyo"),
        ("Miami", "London"),
    ]
    for i, (o, d) in enumerate(absent):
        iso = "2026-11-12"
        yield _example(
            f"flight-noroute-{i:03d}",
            rng.choice(FLIGHT_TEMPLATES).format(o=o, d=d, date=_fmt(iso)),
            tool="search_flights",
            args={"origin": o, "destination": d, "date": iso},
            expect=[],
            behavior="empty",
            intent="flight",
            cell="route:absent",
            suite="capability",
        )

    # 5. Relative dates — the agent must resolve them to ISO before the call.
    for i, phrase in enumerate(["next Friday", "this coming weekend", "the first Monday of November"]):
        yield _example(
            f"flight-reldate-{i:03d}",
            f"I need a flight from New York to Miami {phrase}.",
            tool="search_flights",
            args={"origin": "New York", "destination": "Miami"},
            expect=[],
            behavior="answer",
            intent="flight",
            cell="date:relative",
            suite="capability",
        )


HOTEL_TEMPLATES = [
    "I need a hotel in {c} from {a} to {b}.",
    "Can you find hotels in {c} for {a} to {b}?",
    "What hotels are available in {c} from {a} to {b}?",
    "Find me a hotel in {c} for the nights of {a} through {b}.",
]


def _hotels(rng: random.Random) -> Iterator[dict]:
    have = sorted(T.cities()["hotels"])
    for i, city in enumerate(have * 4):
        if i >= 20:
            break
        ci, co = "2026-10-05", "2026-10-09"
        exp = T.expected_hotels(city, ci)
        yield _example(
            f"hotel-have-{i:03d}",
            rng.choice(HOTEL_TEMPLATES).format(c=city, a=_fmt(ci), b=_fmt(co)),
            tool="search_hotels",
            args={"city": city, "check_in": ci, "check_out": co},
            expect=[h["name"] for h in exp],
            behavior="answer" if exp else "empty",
            intent="hotel",
            cell="city:has_data",
            suite="regression",
        )

    for i, city in enumerate(NO_HOTEL_CITIES * 4):
        if i >= 16:
            break
        ci, co = "2026-11-03", "2026-11-06"
        yield _example(
            f"hotel-nodata-{i:03d}",
            rng.choice(HOTEL_TEMPLATES).format(c=city, a=_fmt(ci), b=_fmt(co)),
            tool="search_hotels",
            args={"city": city, "check_in": ci, "check_out": co},
            expect=[],
            behavior="empty",
            intent="hotel",
            cell="city:no_data",
            suite="capability",
        )

    # Cities that do have hotels, on a date past every window — tests that the
    # date range is actually applied rather than ignored like flights were.
    for i, city in enumerate(have * 2):
        if i >= 10:
            break
        ci, co = "2027-06-01", "2027-06-05"
        exp = T.expected_hotels(city, ci)
        yield _example(
            f"hotel-window-{i:03d}",
            rng.choice(HOTEL_TEMPLATES).format(c=city, a=_fmt(ci), b=_fmt(co)),
            tool="search_hotels",
            args={"city": city, "check_in": ci, "check_out": co},
            expect=[h["name"] for h in exp],
            behavior="answer" if exp else "empty",
            intent="hotel",
            cell="date:window_closed",
            suite="capability",
        )


WEATHER_TEMPLATES = [
    "What's the weather like in {c} on {date}?",
    "How's the weather looking in {c} on {date}?",
    "What should I expect weather-wise in {c} on {date}?",
]


def _weather(rng: random.Random) -> Iterator[dict]:
    have = sorted(T.cities()["weather"])
    for i, city in enumerate(have * 2):
        if i >= 12:
            break
        iso = "2026-10-20"
        yield _example(
            f"weather-have-{i:03d}",
            rng.choice(WEATHER_TEMPLATES).format(c=city, date=_fmt(iso)),
            tool="get_weather",
            args={"city": city, "date": iso},
            expect=[city],
            behavior="answer",
            intent="weather",
            cell="city:has_data",
            suite="regression",
        )

    for i, city in enumerate(NO_WEATHER_CITIES * 4):
        if i >= 16:
            break
        iso = "2026-11-18"
        yield _example(
            f"weather-nodata-{i:03d}",
            rng.choice(WEATHER_TEMPLATES).format(c=city, date=_fmt(iso)),
            tool="get_weather",
            args={"city": city, "date": iso},
            expect=[],
            behavior="empty",
            intent="weather",
            cell="city:no_data",
            suite="capability",
        )


def _itineraries(rng: random.Random) -> Iterator[dict]:
    """Day count is the whole point — `main` drops the final day."""
    dests = ["Chicago", "Paris", "Miami", "Tokyo", "New York", "London"]
    n = 0
    for days in (1, 2, 3, 4, 5, 7):
        for dest in rng.sample(dests, 3):
            n += 1
            yield _example(
                f"itinerary-{n:03d}",
                f"Plan a {days}-day trip to {dest} for me.",
                tool="create_itinerary",
                args={"destination": dest, "num_days": days},
                expect=[str(d) for d in T.expected_itinerary_days(days)],
                behavior="answer",
                intent="itinerary",
                cell=f"num_days:{days}",
                suite="regression",
            )


def _out_of_scope(rng: random.Random) -> Iterator[dict]:
    for i, q in enumerate(OUT_OF_SCOPE * 3):
        if i >= 30:
            break
        yield _example(
            f"scope-{i:03d}",
            q,
            tool=None,
            args={},
            expect=[],
            behavior="out_of_scope",
            intent="out_of_scope",
            cell="scope:out",
            suite="capability",
        )


def _multi_tool(rng: random.Random) -> Iterator[dict]:
    pairs = [
        ("New York", "Miami", "2026-10-01"),
        ("New York", "Paris", "2026-09-15"),
        ("San Francisco", "Tokyo", "2026-11-20"),
        ("Chicago", "Denver", "2026-10-08"),
        ("London", "Paris", "2026-11-05"),
    ]
    n = 0
    for o, d, iso in pairs:
        exp = T.expected_flights(o, d, iso)
        n += 1
        yield _example(
            f"multi-flightweather-{n:03d}",
            f"Find me a flight from {o} to {d} on {_fmt(iso)}, and tell me what the weather will be like there.",
            tool="search_flights",
            args={"origin": o, "destination": d, "date": iso},
            expect=[f["flight_number"] for f in exp],
            behavior="answer",
            intent="multi_tool",
            cell="tools:flight+weather",
            suite="regression",
        )
        n += 1
        yield _example(
            f"multi-flighthotel-{n:03d}",
            f"I'm flying {o} to {d} on {_fmt(iso)} — find flights and a hotel for that week.",
            tool="search_flights",
            args={"origin": o, "destination": d, "date": iso},
            expect=[f["flight_number"] for f in exp],
            behavior="answer",
            intent="multi_tool",
            cell="tools:flight+hotel",
            suite="regression",
        )


def build() -> list[dict]:
    rng = random.Random(SEED)
    rows: list[dict] = []
    for gen in (_flights, _hotels, _weather, _itineraries, _out_of_scope, _multi_tool):
        rows.extend(gen(rng))
    return rows


def main() -> None:
    rows = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n")

    from collections import Counter
    by_intent = Counter(r["metadata"]["intent"] for r in rows)
    by_behavior = Counter(r["output"]["expected_behavior"] for r in rows)
    by_suite = Counter(r["metadata"]["suite"] for r in rows)
    print(f"wrote {len(rows)} examples -> {OUT_PATH.relative_to(OUT_PATH.parents[2])}")
    print(f"  intent:   {dict(by_intent)}")
    print(f"  behavior: {dict(by_behavior)}")
    print(f"  suite:    {dict(by_suite)}")
    answers = by_behavior["answer"]
    print(f"  balance:  {answers} expect results / {len(rows) - answers} expect empty-or-decline")


if __name__ == "__main__":
    main()
