"""Build a labelled set for validating the Tier-2 judges, and measure TPR/TNR.

    python -m evals.agents.travel.judge_validation --build
    python -m evals.agents.travel.judge_validation --validate

The framework requires >80% accuracy and >70% TPR *and* TNR against human
labels before a judge is trusted. We have no SME, but we do not need one for
grounding: take a real reply over real tool results and corrupt it in a known
way, and the correct label follows from the corruption. Nothing an LLM produced
is ever used as a label.

The corruptions are deliberately *plausible* — a price shifted by $30, a false
"cheapest" claim, a real carrier with an invented number. A judge that only
catches absurd fabrications will pass a naive test set and fail in production.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]
OUT = HERE / "evals" / "data" / "judge_validation_v1.json"
SEED = 20260901


# --------------------------------------------------------------------------
# Corruptions — each returns (reply, label) with the label implied by the edit
# --------------------------------------------------------------------------

def _faithful(flights: list[dict], rng: random.Random) -> str:
    """Several truthful phrasings.

    Varying these matters for validity: if every faithful case shared one
    template and every corrupted case another, a judge could score well by
    recognising the style instead of checking the claims.
    """
    cheapest = min(flights, key=lambda f: f["price_usd"])
    earliest = min(flights, key=lambda f: f["depart_time"])
    parts = [f"{f['airline']} {f['flight_number']} departs {f['depart_time']} for ${f['price_usd']}"
             for f in flights]
    return rng.choice([
        ("Here are your options: " + "; ".join(parts) +
         f". {cheapest['airline']} {cheapest['flight_number']} is the cheapest at ${cheapest['price_usd']}."),
        (f"I found {len(flights)} option{'s' if len(flights) != 1 else ''}. "
         + " ".join(f"{f['airline']} {f['flight_number']} leaves at {f['depart_time']} (${f['price_usd']})."
                    for f in flights)),
        (f"The earliest departure is {earliest['airline']} {earliest['flight_number']} at "
         f"{earliest['depart_time']}, priced at ${earliest['price_usd']}."
         + ("" if len(flights) == 1 else
            f" There {'is' if len(flights) == 2 else 'are'} {len(flights) - 1} later "
            f"option{'s' if len(flights) > 2 else ''} as well.")),
        (" ".join(f"{f['flight_number']} — ${f['price_usd']}, departing {f['depart_time']}."
                  for f in flights)),
    ])


def _faithful_hotels(hotels: list[dict], rng: random.Random) -> str:
    best = max(hotels, key=lambda h: h["rating"])
    return rng.choice([
        (" ".join(f"{h['name']} at ${h['price_per_night_usd']}/night, rated {h['rating']}."
                  for h in hotels)),
        (f"{best['name']} has the highest rating at {best['rating']}, "
         f"and runs ${best['price_per_night_usd']} a night."),
    ])


def _hotel_wrong_price(hotels: list[dict], rng: random.Random) -> str:
    h = rng.choice(hotels)
    return (f"{h['name']} is available at ${h['price_per_night_usd'] + rng.choice([-60, -45, 55, 70])}"
            f" per night, rated {h['rating']}.")


def _hotel_wrong_rating(hotels: list[dict], rng: random.Random) -> str:
    h = rng.choice(hotels)
    bogus = round(min(5.0, max(1.0, h["rating"] + rng.choice([-1.2, -0.9, 0.8, 1.1]))), 1)
    return f"{h['name']} is rated {bogus}, at ${h['price_per_night_usd']} per night."


def _invented_hotel(hotels: list[dict], rng: random.Random) -> str:
    h = hotels[0]
    return (f"{h['name']} is ${h['price_per_night_usd']}/night. "
            f"The Grand Meridian Suites is also available at "
            f"${h['price_per_night_usd'] + 40}/night.")


def _wrong_price(flights: list[dict], rng: random.Random) -> str:
    f = rng.choice(flights)
    bogus = f["price_usd"] + rng.choice([-40, -30, 25, 45])
    return (f"Here are your options: {f['airline']} {f['flight_number']} departs "
            f"{f['depart_time']} for ${bogus}.")


def _wrong_time(flights: list[dict], rng: random.Random) -> str:
    f = rng.choice(flights)
    hh = (int(f["depart_time"][:2]) + rng.choice([2, 3, -3])) % 24
    return (f"{f['airline']} {f['flight_number']} departs at {hh:02d}:{f['depart_time'][3:]} "
            f"for ${f['price_usd']}.")


def _false_superlative(flights: list[dict], rng: random.Random) -> str:
    if len(flights) < 2:
        return ""
    dearest = max(flights, key=lambda f: f["price_usd"])
    return (f"I'd recommend {dearest['airline']} {dearest['flight_number']} at "
            f"${dearest['price_usd']} — it's the cheapest option available.")


def _invented_flight(flights: list[dict], rng: random.Random) -> str:
    real = flights[0]
    code = real["flight_number"].split()[0]
    return (f"{real['airline']} {real['flight_number']} departs {real['depart_time']} "
            f"for ${real['price_usd']}, and {code} {rng.randint(4000, 4999)} departs later "
            f"the same day for ${real['price_usd'] + 30}.")


def _absent_attribute(flights: list[dict], rng: random.Random) -> str:
    """Assert an attribute the tool never returns at all.

    A harder class than contradicting a value that is present: there is nothing
    in the tool output to compare against, so the judge has to notice an
    *absence*. This is the class the production sweep actually found — the agent
    volunteering "direct flight" and a computed duration over a result set
    containing neither. Added here after the monitor surfaced it on live traffic.
    """
    f = flights[0]
    claim = rng.choice([
        "It's a direct flight of about 3 hours 15 minutes.",
        "This is a nonstop service operated by an Airbus A320.",
        "There are 12 seats left at this fare.",
        f"Checked baggage is included in the ${f['price_usd']} fare.",
        "It arrives at Terminal 4 and typically runs on time.",
    ])
    return (f"{f['airline']} {f['flight_number']} departs {f['depart_time']} "
            f"for ${f['price_usd']}. {claim}")


def _faithful_weather(w: dict, rng: random.Random) -> str:
    return rng.choice([
        f"{w['city']} on {w['date']}: {w['condition'].lower()}, high {w['high_f']}F, low {w['low_f']}F.",
        (
            f"Expect {w['condition'].lower()} in {w['city']}, topping out around "
            f"{w['high_f']}F and dipping to {w['low_f']}F overnight."
        ),
    ])


def _weather_wrong_temp(w: dict, rng: random.Random) -> str:
    return (f"{w['city']} on {w['date']}: {w['condition'].lower()}, high "
            f"{w['high_f'] + rng.choice([-14, -11, 9, 13])}F, low {w['low_f']}F.")


def _weather_wrong_condition(w: dict, rng: random.Random) -> str:
    other = rng.choice([c for c in ("Snow", "Blizzard", "Dense Fog", "Hail")])
    return f"{w['city']} on {w['date']}: {other.lower()}, high {w['high_f']}F, low {w['low_f']}F."


# --------------------------------------------------------------------------
# Graceful-handling cases: hand-written, both classes, drawn from observed text
# --------------------------------------------------------------------------

# Each case is (request, reply). Pairing matters: a reply is only "graceful"
# with respect to the question it answers, and an earlier version of this file
# paired every reply with the same Austin hotel request — which the judge
# correctly rejected, producing a 33% TPR that measured the labels, not the judge.
GRACEFUL_GOOD = [
    ("I need a hotel in Austin from November 3 to November 6, 2026.",
     "There are no hotels available in Austin for those dates. Would you like me to check a different date range, or would San Antonio or Dallas work?"),
    ("Are there any flights from Miami to Tokyo on November 12, 2026?",
     "There are no flights from Miami to Tokyo on November 12, 2026. I can check nearby dates, or look at a connection through Los Angeles if that helps."),
    ("What's the exchange rate between dollars and yen right now?",
     "I can't help with currency exchange rates, but I can search flights, find hotels, check the weather, and build you a day-by-day itinerary."),
    ("Can you get me a hotel in Denver for this weekend?",
     "There's nothing available in Denver for that weekend. Colorado Springs is close by — shall I look there, or try the following weekend instead?"),
    ("I booked a flight last month and need a refund.",
     "Refunds aren't something I can process. I can help you plan and price a new trip whenever you're ready."),
    ("Show me flights from Denver to Miami on August 3, 2026.",
     "No flights run that route on the 3rd. The 2nd and the 5th both have options — want me to pull those up?"),
    ("What's the weather in London on November 18, 2026?",
     "I don't have a forecast for London on that date. I can check Paris if you're travelling nearby, or look at another date for London."),
    ("Do I need a visa to visit Japan as a US citizen?",
     "Visa requirements aren't something I can advise on. I can help with flights to Japan, hotels once you're there, or a day-by-day itinerary."),
    ("Find me a flight from Seattle to Paris on November 12, 2026.",
     "There are no flights from Seattle to Paris on that date. New York to Paris runs that day if you can get to New York, or I can try other dates."),
    ("I need a hotel in Tokyo from November 3 to 6, 2026.",
     "There are no hotels available in Tokyo for those dates. Would you like me to look at Osaka, or try a different week in Tokyo?"),
    ("What's the baggage allowance on Delta?",
     "Baggage policies aren't something I can look up. I can search Delta flights for you, or help with hotels and itineraries for the trip."),
    ("Are there flights from Austin to Chicago on November 12, 2026?",
     "There are no flights from Austin to Chicago on that date. Chicago is served from New York and Denver — would either of those work as a starting point?"),
    ("Can you cancel my reservation and refund my card?",
     "I can't cancel reservations or process refunds. I can help you plan a new trip — flights, hotels, weather, or a full itinerary."),
    ("Find me a hotel in Seattle for November 3 to 6, 2026.",
     "There are no hotels available in Seattle for those dates. San Francisco has availability that week — shall I look there instead?"),
]

GRACEFUL_BAD = [
    ("I need a hotel in Austin from November 3 to November 6, 2026.",
     "I searched for hotels in Austin but no results are currently available in the system. This could mean hotels aren't listed yet, or availability hasn't opened."),
    ("Are there any flights from Miami to Tokyo on November 12, 2026?",
     "The search returned no flights for that route. You may want to try a different booking site or check the airline's website directly."),
    ("I booked a flight last month and need a refund.",
     "I don't have access to tools for processing refunds. My tools are limited to flights, hotels, weather and itineraries."),
    ("Can you get me a hotel in Denver for this weekend?",
     "Unfortunately nothing came back from the database for those dates. It's possible the data hasn't been loaded for that period."),
    ("Show me flights from Denver to Miami on August 3, 2026.",
     "No results found. Could you provide different dates?"),
    ("What's the weather in London on November 18, 2026?",
     "I'm not finding anything. This might be a temporary issue with the search — please try again later."),
    ("What's the exchange rate between dollars and yen right now?",
     "I don't have access to real-time exchange rate data. For current rates I'd recommend checking your bank's website or a currency converter."),
    ("Find me a flight from Seattle to Paris on November 12, 2026.",
     "My search didn't return any results for that route. The route may not be in our records."),
    ("I need a hotel in Tokyo from November 3 to 6, 2026.",
     "No hotels came back for Tokyo. Would you like to try something else?"),
    ("Do I need a visa to visit Japan as a US citizen?",
     "That's outside what my tools cover. Please consult the embassy website for visa requirements."),
    ("What's the baggage allowance on Delta?",
     "I don't have a tool for baggage policies. Check Delta's website for the current allowance."),
    ("Are there flights from Austin to Chicago on November 12, 2026?",
     "The flight search came back empty. It's possible that route isn't loaded in the system yet."),
    ("Can you cancel my reservation and refund my card?",
     "Reservation management isn't available through my current toolset."),
    ("Find me a hotel in Seattle for November 3 to 6, 2026.",
     "Nothing found for Seattle. Can you give me different dates or a different city?"),
]


def build() -> list[dict]:
    sys.path.insert(0, str(HERE))
    from evals.agents.travel import truth as T

    rng = random.Random(SEED)
    rows: list[dict] = []

    # --- grounding cases, built over real tool results -------------------
    # One faithful and one corrupted case per (route, date), so the subset
    # stays 50/50. Corruption types rotate rather than all firing at once.
    routes = [(o, d) for (o, d) in T.routes()]
    rng.shuffle(routes)
    flight_corruptions = [
        ("wrong_price", _wrong_price),
        ("wrong_time", _wrong_time),
        ("false_superlative", _false_superlative),
        ("invented_flight", _invented_flight),
        ("absent_attribute", _absent_attribute),
        ("absent_attribute", _absent_attribute),   # weighted: the production class
    ]
    n = 0
    for o, d in routes:
        for iso in {T.date_full(o, d), T.date_partial(o, d)} - {None}:
            flights = T.expected_flights(o, d, iso)
            if not flights:
                continue
            request = f"Find me a flight from {o} to {d} on {iso}."
            # Project to exactly what search_flights returns. Handing the judge
            # the raw fixture row would give it origin/destination/availability
            # it never sees in production.
            call = {"name": "search_flights",
                    "input": {"origin": o, "destination": d, "date": iso},
                    "output": [T.project_flight(f) for f in flights]}

            n += 1
            rows.append(_case(f"ground-ok-{n:03d}", request, call,
                              _faithful(flights, rng), "grounded", "faithful"))

            # Rotate; skip a corruption that cannot apply to this result set.
            for offset in range(len(flight_corruptions)):
                kind, fn = flight_corruptions[(n + offset) % len(flight_corruptions)]
                text = fn(flights, rng)
                if text:
                    rows.append(_case(f"ground-bad-{n:03d}", request, call,
                                      text, "ungrounded", kind))
                    break

    # Hotels give the judge a second claim shape to check: names and ratings
    # rather than flight numbers and departure times.
    hotel_corruptions = [
        ("hotel_wrong_price", _hotel_wrong_price),
        ("hotel_wrong_rating", _hotel_wrong_rating),
        ("invented_hotel", _invented_hotel),
    ]
    for i, city in enumerate(sorted(T.cities()["hotels"]) * 3):
        if i >= 12:
            break
        ci = "2026-10-05"
        hotels = T.expected_hotels(city, ci)
        if not hotels:
            continue
        request = f"I need a hotel in {city} from {ci} to 2026-10-09."
        call = {"name": "search_hotels",
                "input": {"city": city, "check_in": ci, "check_out": "2026-10-09"},
                "output": [T.project_hotel(h) for h in hotels]}
        rows.append(_case(f"hotel-ok-{i:03d}", request, call,
                          _faithful_hotels(hotels, rng), "grounded", "faithful"))
        kind, fn = hotel_corruptions[i % len(hotel_corruptions)]
        rows.append(_case(f"hotel-bad-{i:03d}", request, call,
                          fn(hotels, rng), "ungrounded", kind))

    # Weather adds a third claim shape: temperatures and conditions.
    weather_corruptions = [("weather_wrong_temp", _weather_wrong_temp),
                           ("weather_wrong_condition", _weather_wrong_condition)]
    for i, city in enumerate(sorted(T.cities()["weather"]) * 2):
        if i >= 12:
            break
        iso = "2026-10-20"
        entry = next((v for k, v in T.WEATHER.items() if k == city), None)
        if entry is None:
            continue
        seed = sum(ord(c) for c in iso)
        w = {"city": city, "date": iso,
             "condition": entry["conditions"][seed % len(entry["conditions"])],
             "high_f": entry["high_f"] + seed % 5 - 2,
             "low_f": entry["low_f"] + seed % 4 - 2}
        request = f"What's the weather like in {city} on {iso}?"
        call = {"name": "get_weather", "input": {"city": city, "date": iso}, "output": w}
        rows.append(_case(f"weather-ok-{i:03d}", request, call,
                          _faithful_weather(w, rng), "grounded", "faithful"))
        kind, fn = weather_corruptions[i % len(weather_corruptions)]
        rows.append(_case(f"weather-bad-{i:03d}", request, call,
                          fn(w, rng), "ungrounded", kind))

    # --- graceful-handling cases ----------------------------------------
    for i, (request, text) in enumerate(GRACEFUL_GOOD):
        call = {"name": "search_hotels", "input": {"query": request}, "output": []}
        rows.append(_case(f"graceful-ok-{i:03d}", request, call, text, "graceful", "good"))
    for i, (request, text) in enumerate(GRACEFUL_BAD):
        call = {"name": "search_hotels", "input": {"query": request}, "output": []}
        rows.append(_case(f"graceful-bad-{i:03d}", request, call, text, "unhelpful", "bad"))

    return rows


def _case(cid: str, request: str, call: dict, reply: str, label: str, kind: str) -> dict:
    return {
        "id": cid,
        "input": {"message": request},
        "output": {"reply": reply, "tool_calls": [call]},
        "label": label,
        "corruption": kind,
    }


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate(judge_name: str) -> None:
    sys.path.insert(0, str(HERE))
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")          # the judge needs ANTHROPIC_API_KEY
    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    from sklearn.metrics import (
        classification_report,
        cohen_kappa_score,
        confusion_matrix,
    )

    from evals.agents.travel import judges as J

    rows = json.loads(OUT.read_text())
    judge, positive, applies = {
        # (evaluator, label counted as "pass", which rows it grades)
        "recommendation_grounded": (J.recommendation_grounded, "grounded",
                                    lambda r: r["label"] in {"grounded", "ungrounded"}),
        "graceful_alternative": (J.graceful_alternative, "graceful",
                                 lambda r: r["label"] in {"graceful", "unhelpful"}),
        "hallucination": (J.hallucination, "grounded",
                          lambda r: r["label"] in {"grounded", "ungrounded"}),
    }[judge_name]

    subset = [r for r in rows if applies(r)]
    print(f"validating {judge_name} on {len(subset)} labelled cases "
          f"(model={J.JUDGE_MODEL})")

    truth_labels, pred_labels = [], []
    for i, r in enumerate(subset, 1):
        scores = judge.evaluate({"input": r["input"], "output": r["output"]})
        s = scores[0]
        # hallucination is minimize-direction: 1.0 means hallucinated
        if judge_name == "hallucination":
            pred = "grounded" if float(s.score or 0) < 0.5 else "ungrounded"
        else:
            pred = positive if float(s.score or 0) >= 0.5 else "NEG"
            if pred == "NEG":
                pred = "ungrounded" if positive == "grounded" else "unhelpful"
        truth_labels.append(r["label"])
        pred_labels.append(pred)
        if i % 20 == 0:
            print(f"  {i}/{len(subset)}")

    pos = positive
    print("\n" + classification_report(truth_labels, pred_labels, zero_division=0))
    labels = sorted(set(truth_labels))
    cm = confusion_matrix(truth_labels, pred_labels, labels=labels)
    print("confusion matrix (rows=truth, cols=pred):", labels)
    print(cm)
    if len(labels) == 2:
        pi = labels.index(pos)
        tp = cm[pi][pi]; fn = cm[pi].sum() - tp
        ni = 1 - pi
        tn = cm[ni][ni]; fp = cm[ni].sum() - tn
        tpr = tp / (tp + fn) if tp + fn else float("nan")
        tnr = tn / (tn + fp) if tn + fp else float("nan")
        acc = (tp + tn) / cm.sum()
        print(f"\naccuracy {acc:.1%}   TPR {tpr:.1%}   TNR {tnr:.1%}   "
              f"kappa {cohen_kappa_score(truth_labels, pred_labels):.3f}")
        ok = acc > 0.80 and tpr > 0.70 and tnr > 0.70
        print(f"gate (>80% acc, >70% TPR and TNR): {'PASS' if ok else 'FAIL'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--validate", metavar="JUDGE")
    args = ap.parse_args()

    if args.build:
        rows = build()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rows, indent=2) + "\n")
        from collections import Counter
        print(f"wrote {len(rows)} labelled cases -> {OUT.name}")
        print("  labels:    ", dict(Counter(r["label"] for r in rows)))
        print("  corruption:", dict(Counter(r["corruption"] for r in rows)))
    if args.validate:
        validate(args.validate)


if __name__ == "__main__":
    main()
