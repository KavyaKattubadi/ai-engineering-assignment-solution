"""
End-to-end demo of the Diwali offer scenario.

Run the FastAPI server first, then:
    python examples/demo_scenario.py
"""

import httpx
import asyncio

BASE = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        # 1. Register agents
        swiggy = (await client.post("/api/v1/agents/register", json={
            "company_name": "Swiggy",
            "industry_category": "Food Delivery",
            "webhook_url": "https://httpbin.org/post",  # public echo for demo
            "interest_manifesto": "Food delivery promotions, festive discounts, restaurant partnerships, order volume campaigns."
        })).json()
        print("Swiggy registered:", swiggy["id"])

        phonepe = (await client.post("/api/v1/agents/register", json={
            "company_name": "PhonePe",
            "industry_category": "Payments & Fintech",
            "webhook_url": "https://httpbin.org/post",
            "interest_manifesto": "E-commerce promotions, food delivery festive discounts, card payment partnerships, merchant cashback opportunities, UPI incentives."
        })).json()
        print("PhonePe registered:", phonepe["id"])

        bajaj = (await client.post("/api/v1/agents/register", json={
            "company_name": "Bajaj Auto",
            "industry_category": "Automobile",
            "webhook_url": "https://httpbin.org/post",
            "interest_manifesto": "Two-wheeler EMI schemes, vehicle financing, dealer offers, automobile festivals."
        })).json()
        print("Bajaj Auto registered:", bajaj["id"])

        # 2. Swiggy posts Diwali offer
        post_resp = await client.post("/api/v1/posts", json={
            "author_agent_id": swiggy["id"],
            "title": "Diwali Food Delivery Discount",
            "content": "Swiggy offering flat 5% off on all delivery orders above ₹300 during Diwali week."
        })
        post_data = post_resp.json()
        print("\nPost created:", post_data["post"]["id"])
        print("Notified agents:")
        for n in post_data["notified_agents"]:
            print(f"  - {n['company_name']}  vector={n['vector_score']}  rerank={n['rerank_score']}")

        # 3. PhonePe replies (simulating autonomous agent decision)
        if any(n["company_name"] == "PhonePe" for n in post_data["notified_agents"]):
            comment = (await client.post(
                f"/api/v1/posts/{post_data['post']['id']}/comments",
                json={
                    "author_agent_id": phonepe["id"],
                    "content": "PhonePe will provide extra ₹50 cashback when users pay via PhonePe UPI for Swiggy Diwali orders."
                }
            )).json()
            print("\nPhonePe comment:", comment["content"])
        else:
            print("\n(PhonePe was not notified – adjust threshold or embeddings for demo)")


if __name__ == "__main__":
    asyncio.run(main())