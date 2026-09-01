"""Send a batch of sample user queries to the travel agent API.

Usage:
    python scripts/generate_traffic.py [base_url]

The API server must be running first:
    uv run fastapi dev backend/main.py
"""

import os
import sys
import time

import httpx

BASE_URL = (
    sys.argv[1] if len(sys.argv) > 1 else os.getenv("TRAVEL_AGENT_URL", "http://localhost:8000")
)

# Each entry is a conversation: a list of one or more user messages sent in order.
CONVERSATIONS = [
    ["Find me a flight from New York to Miami on March 12, 2026."],
    ["What flights are there from San Francisco to Tokyo on April 20, 2026?"],
    ["I need a hotel in Paris from June 10 to June 14, 2026."],
    ["Can you find hotels in Chicago for May 5 to May 8, 2026?"],
    ["What's the weather like in Miami on July 15, 2026?"],
    ["How's the weather looking in Tokyo on April 22, 2026?"],
    ["Plan a 3-day trip to Chicago for me."],
    [
        "I'm thinking about a weekend in Miami in early August. Any flights from New York on August 7, 2026?",
        "Great, can you add a hotel for that weekend too?",
    ],
    ["Show me flights from London to Paris on September 3, 2026."],
    ["I need to get from Tokyo to Los Angeles on May 2, 2026 — what flights are there?"],
    ["Put together a 5-day itinerary for Paris, arriving June 10, 2026."],
    ["I want to fly from Chicago to Denver on October 2, 2026 — what are my options?"],
    ["Find me a hotel in New York for the nights of March 20 to 23, 2026."],
    ["I need a flight from Miami to Tokyo next Friday."],
    ["Can you get me a hotel in Denver for this weekend?"],
    ["What hotels are available in Paris from April 3 to April 7, 2026?"],
    ["Are there any flights from Denver to Miami on August 14, 2026?"],
    ["Do I need a visa to visit Japan as a US citizen?"],
    ["I booked a flight through you last month and need a refund — can you process that?"],
    ["How much would a hotel in London cost per night in euros?"],
    ["What's the weather going to be in London next Tuesday?"],
    ["Find me a hotel in Austin for South by Southwest."],
]


def main():
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        health = client.get("/health")
        health.raise_for_status()

        total = sum(len(c) for c in CONVERSATIONS)
        sent = 0
        for conversation in CONVERSATIONS:
            conversation_id = None
            for message in conversation:
                sent += 1
                print(f"[{sent}/{total}] you> {message}")
                resp = client.post(
                    "/chat",
                    json={"message": message, "conversation_id": conversation_id},
                )
                resp.raise_for_status()
                body = resp.json()
                conversation_id = body["conversation_id"]
                print(f"agent> {body['reply']}\n")
                time.sleep(0.5)

    print(f"Done — sent {sent} messages across {len(CONVERSATIONS)} conversations.")


if __name__ == "__main__":
    main()
