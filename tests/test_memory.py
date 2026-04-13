import asyncio
from src.llm import get_llm_response, reset_memory

async def test():
    print("\n=== CONVERSATION MEMORY TEST ===\n")

    # Simulate a real leasing conversation
    conversation = [
        "Hi, I am looking for an apartment in Calgary",
        "My budget is around $1,500 per month",
        "I have a cat so it needs to be pet friendly",
        "I prefer somewhere near downtown",
        "What options do you have for me?",
        "Tell me more about the first option",
        "Does it have parking?",
        "What about utilities, are they included?",
    ]

    for i, question in enumerate(conversation):
        print(f"\nTurn {i+1}: {question}")
        print("-" * 40)
        response, latency = await get_llm_response(question)
        print(f"Agent: {response}")
        print(f"Latency: {latency:.0f}ms")
        await asyncio.sleep(2)  # avoid rate limiting

    print("\n=== END OF CONVERSATION ===")
    reset_memory()

asyncio.run(test())