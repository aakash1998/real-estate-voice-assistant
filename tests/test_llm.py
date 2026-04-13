import asyncio
from src.llm import get_llm_response

async def test():
    questions = [
        # Budget queries
        "Do you have anything under $1,000 a month?",
        "What is the cheapest apartment available?",
        "I am a student on a tight budget, what can I afford?",

        # Pet queries
        "Do you have any pet friendly apartments?",
        "I have a dog, what options do I have?",
        "Which properties do not allow pets?",

        # Luxury queries
        "Show me your most expensive and luxurious options",
        "I want a penthouse or something premium",
        "Do you have anything with a rooftop pool?",

        # Utilities queries
        "Which apartments include all utilities?",
        "I want heat and water included in my rent",

        # Parking queries
        "I need underground parking, what do you have?",
        "Which properties have free parking included?",

        # Neighborhood queries
        "Do you have anything in Kensington?",
        "What properties are available in Mission?",

        # Availability queries
        "What is available right now today?",
        "Do you have anything available next month?",

        # Unknown questions (should trigger fallback)
        "What are your office hours?",
        "Can I book a viewing for this Saturday?",
        "Do you offer short term rentals?",
    ]

    passed = 0
    failed = 0

    for i, question in enumerate(questions):
        print(f"\n{'='*60}")
        print(f"Test {i+1}/{len(questions)}: {question}")
        print('='*60)
        try:
            response, latency = await get_llm_response(question)
            print(f"[RESPONSE] {response}")
            print(f"[LATENCY] {latency:.0f}ms")
            passed += 1
        except Exception as e:
            print(f"[FAILED] {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(questions)} tests")
    print('='*60)

asyncio.run(test())