import asyncio
from src.evaluator import run_evaluation, print_report

async def main():
    results = await run_evaluation()
    print_report(results)

asyncio.run(main())