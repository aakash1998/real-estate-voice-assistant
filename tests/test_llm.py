import asyncio
from src.llm import get_llm_response

async def test():
    response = await get_llm_response(
        "What is the average rent for a one bedroom in Calgary?"
    )
    print(f"[TEST] Got response: {response}")

asyncio.run(test())