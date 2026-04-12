import asyncio
from src.tts import speak

async def test():
    await speak(
        "The average rent for a one bedroom in Calgary is around 1400 to 1600 dollars per month."
    )

asyncio.run(test())