"""Stage 1 — deterministic checks (free, exact). They gate the LLM judges.

Ground truth = the tool results captured on TOOL spans, plus data/*.json.
Every check fails closed: if it can verify a violation it says "fail"; only
"skip" (nothing to check) or "pass" (checked, clean) let a turn through.

  tool_called     did the agent call a tool when the request needs one (and finish)?
  reply_grounded  do the reply's flights / hotels / prices / temps come from this turn's tool results?
  tool_contract   do the tool results honor the request (route, dates, day count, forecast)?
"""

import json
import re

from agent.config import DATA_DIR

FLIGHTS = {f["flight_number"]: f for f in json.loads((DATA_DIR / "flights.json").read_text(encoding="utf-8"))}
HOTELS = {h["name"]: h for h in json.loads((DATA_DIR / "hotels.json").read_text(encoding="utf-8"))}
WEATHER = {k.lower(): v for k, v in json.loads((DATA_DIR / "weather.json").read_text(encoding="utf-8")).items()}

AIRLINE_CODES = {n.split()[0] for n in FLIGHTS}
FLIGHT_RE = re.compile(r"\b([A-Z][A-Z0-9]) ?(\d{2,4})\b")  # case-sensitive: "DL 883", "B6 1029"
NEEDS_TOOL = ("flight", "hotel", "weather", "forecast", "itinerary", "trip", "plan")
ITINERARY_WORDS = ("itinerary", "trip", "plan")


def _res(label: str, why: str) -> dict:
    return {"label": label, "score": 0 if label == "fail" else 1, "explanation": why}


def is_itinerary(text: str) -> bool:
    return any(w in text.lower() for w in ITINERARY_WORDS)


def _fix(v):
    """Undo mojibake (tools.py reads data/*.json with the OS default encoding on Windows)."""
    if isinstance(v, str):
        try:
            return v.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return v
    if isinstance(v, list):
        return [_fix(x) for x in v]
    if isinstance(v, dict):
        return {k: _fix(x) for k, x in v.items()}
    return v


def _calls(turn: dict) -> list:
    """This turn's tool calls plus earlier turns' in the same session (follow-ups reuse them)."""
    return [{**c, "result": _fix(c["result"])} for c in turn["context_calls"] + turn["tool_calls"]]


def _results(turn: dict, tool: str) -> list:
    """All result payloads of a given tool (lists flattened)."""
    out = []
    for c in _calls(turn):
        if c["name"] == tool and isinstance(c["result"], list):
            out.extend(c["result"])
    return out


def tool_called(turn: dict) -> dict:
    if turn["fallback"]:
        return _res("fail", "Turn ended in the fallback reply (step cap or error) — user got no answer.")
    if any(k in turn["input"].lower() for k in NEEDS_TOOL) and not (turn["tool_calls"] or turn["context_calls"]):
        return _res("fail", "Request needs travel data but no tool was called — answer came from the model alone.")
    return _res("pass", f"{len(turn['tool_calls'])} tool call(s) this turn, {len(turn['context_calls'])} earlier in session.")


def reply_grounded(turn: dict) -> dict:
    if turn["fallback"]:
        return _res("skip", "fallback turn")
    reply = turn["output"]
    flights = {f["flight_number"] for f in _results(turn, "search_flights")}
    hotels = {h["name"] for h in _results(turn, "search_hotels")}

    cited = {f"{p} {n}" for p, n in FLIGHT_RE.findall(reply) if p in AIRLINE_CODES}
    if cited - flights:
        return _res("fail", f"Reply cites flights not in this turn's tool results: {sorted(cited - flights)}")

    stray = {h for h in HOTELS if h in reply} - hotels
    if stray:
        return _res("fail", f"Reply names hotels not in this turn's tool results: {sorted(stray)}")

    # prices: every $N must be a tool price (or a whole-number multiple, e.g. nights x rate)
    prices = [f["price_usd"] for f in _results(turn, "search_flights")]
    prices += [h["price_per_night_usd"] for h in _results(turn, "search_hotels")]
    allowed = {p * k for p in prices for k in range(1, 31)}
    quoted = {int(m.replace(",", "")) for m in re.findall(r"\$\s?(\d[\d,]*)", reply)}
    searches = [c for c in _calls(turn) if c["name"].startswith("search_")]
    if searches and all(c["result"] == [] for c in searches) and quoted:
        return _res("fail", f"Search returned nothing but reply quotes prices {sorted(quoted)} — fabricated specifics.")
    if quoted - allowed and prices:
        return _res("fail", f"Reply quotes prices not in tool results: {sorted(quoted - allowed)}")

    weather = [c["result"] for c in _calls(turn) if c["name"] == "get_weather" and isinstance(c["result"], dict)]
    temps = {w[k] for w in weather for k in ("high_f", "low_f") if k in w}
    said = {int(t) for t in re.findall(r"(\d{2,3})\s?°(?!\s?C)", reply)}  # °F or bare; ignore °C conversions
    if temps and said - temps:
        return _res("fail", f"Reply temps {sorted(said - temps)} differ from tool forecast {sorted(temps)}")

    return _res("pass" if _calls(turn) else "skip", "Reply specifics traceable to tool results.")


def tool_contract(turn: dict) -> dict:
    problems = []
    for c in turn["tool_calls"]:
        args, result = c["args"] if isinstance(c["args"], dict) else {}, _fix(c["result"])
        if c["name"] == "search_flights" and isinstance(result, list):
            for f in result:
                fx = FLIGHTS.get(f["flight_number"])
                if fx and (fx["origin"].lower(), fx["destination"].lower()) != (
                    str(args.get("origin", "")).lower(), str(args.get("destination", "")).lower()
                ):
                    problems.append(f"{f['flight_number']} flies {fx['origin']}->{fx['destination']}, requested {args.get('origin')}->{args.get('destination')}")
        elif c["name"] == "search_hotels" and isinstance(result, list):
            for h in result:
                if (fx := HOTELS.get(h["name"])) and fx["available_to"] < str(args.get("check_out", "")):
                    problems.append(f"{h['name']} unavailable until check-out {args.get('check_out')}")
        elif c["name"] == "get_weather" and isinstance(result, dict) and "high_f" in result:
            base = WEATHER.get(str(args.get("city", "")).lower())
            if base and not (base["high_f"] - 2 <= result["high_f"] <= base["high_f"] + 2
                             and base["low_f"] - 2 <= result["low_f"] <= base["low_f"] + 2):
                problems.append(f"{result['city']} forecast {result['high_f']}/{result['low_f']}F outside fixture {base['high_f']}/{base['low_f']}F")
        elif c["name"] == "create_itinerary" and isinstance(result, dict) and "days" in result:
            want = int(args.get("num_days", 0))
            asked = re.search(r"(\d+)[\s-]?day", turn["input"], re.I)
            if len(result["days"]) != want:
                problems.append(f"itinerary has {len(result['days'])} days, tool was asked for {want}")
            if asked and int(asked.group(1)) != want:
                problems.append(f"user asked {asked.group(1)} days, tool called with {want}")
    if problems:
        return _res("fail", "; ".join(problems))
    return _res("pass" if turn["tool_calls"] else "skip", "Tool results honor the request.")


def run_checks(turn: dict) -> dict[str, dict]:
    return {"tool_called": tool_called(turn), "reply_grounded": reply_grounded(turn), "tool_contract": tool_contract(turn)}


def gate_passed(checks: dict[str, dict]) -> bool:
    return all(r["label"] != "fail" for r in checks.values())
