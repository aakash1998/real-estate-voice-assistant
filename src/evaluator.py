import os
import json
import asyncio
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
from .llm import get_llm_response, reset_memory
from .embed_properties import search_properties

load_dotenv()

QUALITY_THRESHOLD = 0.80
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────
# LAYER 1: PRECISION@K
# Industry standard retrieval metric
# Measures how high the correct property ranks
# ─────────────────────────────────────────────

def precision_at_k(retrieved: list, expected: str, k: int, acceptable: list = None) -> float:
    """
    Checks if expected property appears in top K results.
    Also accepts alternative valid answers via acceptable list.
    """
    if expected is None:
        return 1.0

    top_k = [r["name"] for r in retrieved[:k]]
    
    # Check primary expected property
    if expected in top_k:
        return 1.0
    
    # Check acceptable alternatives
    if acceptable:
        if any(prop in top_k for prop in acceptable):
            return 1.0
    
    return 0.0

def mean_reciprocal_rank(retrieved: list, expected: str, acceptable: list = None) -> float:
    """
    MRR — rewards finding correct answer higher up.
    Also accepts alternative valid answers.
    """
    if expected is None:
        return 1.0

    all_valid = [expected]
    if acceptable:
        all_valid.extend(acceptable)

    for i, result in enumerate(retrieved):
        if result["name"] in all_valid:
            return 1.0 / (i + 1)

    return 0.0

# ─────────────────────────────────────────────
# LAYER 2: LLM-AS-JUDGE
# Uses Groq to evaluate answer quality
# Same approach used by Anthropic and OpenAI
# ─────────────────────────────────────────────

def llm_judge(
    question: str,
    context: str,
    answer: str
) -> dict:
    """
    Uses an LLM to evaluate the answer on three dimensions:
    
    Faithfulness: Is every claim in the answer supported by context?
                  Detects hallucinations.
                  
    Relevance:    Does the answer actually address the question?
                  Detects off-topic responses.
                  
    Completeness: Did the answer include all important information
                  from the retrieved context?
    
    Returns structured JSON so scores are parseable and consistent.
    
    Why LLM-as-Judge over keyword matching:
    - Understands meaning not just words
    - Can detect subtle hallucinations
    - Gives human-readable reasoning
    - Scales to any question type
    """
    judge_prompt = f"""You are an expert evaluator for a real estate AI assistant.

RETRIEVED CONTEXT (what the system found in its database):
{context}

USER QUESTION:
{question}

SYSTEM ANSWER:
{answer}

Evaluate the answer on exactly these three dimensions:

1. FAITHFULNESS (0.0 to 1.0)
   Is every single claim in the answer actually supported by the retrieved context?
   1.0 = every claim is grounded in context, nothing made up
   0.5 = some claims supported, some not verifiable
   0.0 = answer contains claims not in context (hallucination)

2. RELEVANCE (0.0 to 1.0)
   Does the answer actually address what the user asked?
   1.0 = directly answers the question
   0.5 = partially answers or asks clarifying question
   0.0 = completely off topic

3. COMPLETENESS (0.0 to 1.0)
   Did the answer include all important details from context?
   1.0 = included all key information
   0.5 = included some but missed important details
   0.0 = missing critical information that was in context

Respond ONLY with valid JSON, no other text:
{{
  "faithfulness": <float>,
  "relevance": <float>,
  "completeness": <float>,
  "reasoning": "<one sentence explaining your scores>"
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise evaluator. Respond only with valid JSON."
                },
                {
                    "role": "user",
                    "content": judge_prompt
                }
            ],
            max_tokens=200,
            temperature=0.0  # deterministic scoring
        )

        raw = response.choices[0].message.content.strip()

        # Clean up JSON if LLM added backticks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        scores = json.loads(raw)
        return scores

    except Exception as e:
        print(f"  [JUDGE ERROR] {e}")
        return {
            "faithfulness": 0.0,
            "relevance": 0.0,
            "completeness": 0.0,
            "reasoning": f"Judge failed: {e}"
        }

# ─────────────────────────────────────────────
# LAYER 3: REGRESSION GATE
# Warns if quality drops below threshold
# This is your safety net when changing prompts or models
# ─────────────────────────────────────────────

def regression_gate(overall_score: float, failing_questions: list):
    """
    Compares overall score against quality threshold.
    
    In production this would fail a CI/CD pipeline build.
    Here it prints a clear warning with actionable details.
    
    Why this matters:
    If you change your system prompt or swap a model,
    running eval tells you immediately if quality dropped.
    That's how teams catch regressions before users feel them.
    """
    print(f"\n{'='*60}")
    print(f"REGRESSION GATE — Threshold: {QUALITY_THRESHOLD*100:.0f}%")
    print(f"{'='*60}")

    if overall_score >= QUALITY_THRESHOLD:
        print(f"✅ PASSED — Score {overall_score*100:.1f}% above threshold")
    else:
        print(f"❌ FAILED — Score {overall_score*100:.1f}% below threshold")
        print(f"\nFailing questions that need attention:")
        for q in failing_questions:
            print(f"  Q{q['id']} [{q['category']}]: {q['question']}")
            print(f"    Score: {q['overall_score']} | Reason: {q.get('reasoning', 'N/A')}")

# ─────────────────────────────────────────────
# MAIN EVALUATION RUNNER
# ─────────────────────────────────────────────

async def run_evaluation():
    """
    Runs all 30 questions through the full evaluation pipeline.
    
    For each question:
    1. Get response from the actual voice agent pipeline
    2. Get retrieved context from ChromaDB
    3. Score retrieval with Precision@K and MRR
    4. Score answer quality with LLM-as-Judge
    5. Aggregate results
    6. Run regression gate
    """
    with open("data/eval_questions.json", "r") as f:
        data = json.load(f)

    questions = data["questions"]
    results = []

    print(f"\n{'='*60}")
    print(f"EVALUATION PIPELINE")
    print(f"Questions: {len(questions)}")
    print(f"Retrieval: Precision@1, Precision@3, MRR")
    print(f"Quality:   LLM-as-Judge (faithfulness, relevance, completeness)")
    print(f"Gate:      Regression check at {QUALITY_THRESHOLD*100:.0f}%")
    print(f"{'='*60}\n")

    for q in questions:
        print(f"[Q{q['id']:02d}] {q['question']}")

        reset_memory()

        try:
            # Step 1 — Get actual pipeline response
            response, latency = await get_llm_response(q["question"])

            # Step 2 — Get retrieved context for this question
            retrieved = search_properties(q["question"], n_results=5)
            context = "\n\n".join([r["document"] for r in retrieved])

            # Step 3 — Retrieval metrics with support for multiple acceptable answers
            acceptable = q.get("acceptable_properties", None)

            p_at_1 = precision_at_k(retrieved, q["expected_property"], k=1, acceptable=acceptable)
            p_at_3 = precision_at_k(retrieved, q["expected_property"], k=3, acceptable=acceptable)
            mrr = mean_reciprocal_rank(retrieved, q["expected_property"], acceptable=acceptable)

            # Step 4 — LLM-as-Judge
            judge_scores = llm_judge(q["question"], context, response)

            # Step 5 — Combined overall score
            retrieval_score = (p_at_1 + p_at_3 + mrr) / 3
            quality_score = (
                judge_scores["faithfulness"] +
                judge_scores["relevance"] +
                judge_scores["completeness"]
            ) / 3
            overall = round((retrieval_score + quality_score) / 2, 3)

            result = {
                "id": q["id"],
                "question": q["question"],
                "category": q["category"],
                "response": response,
                "latency_ms": round(latency),
                "retrieval": {
                    "precision_at_1": p_at_1,
                    "precision_at_3": p_at_3,
                    "mrr": round(mrr, 3),
                    "top_3_retrieved": [r["name"] for r in retrieved[:3]]
                },
                "quality": {
                    "faithfulness": judge_scores["faithfulness"],
                    "relevance": judge_scores["relevance"],
                    "completeness": judge_scores["completeness"],
                    "reasoning": judge_scores["reasoning"]
                },
                "overall_score": overall
            }

            results.append(result)

            print(f"  P@1:{p_at_1} P@3:{p_at_3} MRR:{mrr:.2f} | "
                  f"Faith:{judge_scores['faithfulness']} "
                  f"Rel:{judge_scores['relevance']} "
                  f"Comp:{judge_scores['completeness']}")
            print(f"  Judge: {judge_scores['reasoning']}")
            print()

            await asyncio.sleep(2)

        except Exception as e:
            print(f"  ERROR: {e}\n")
            results.append({
                "id": q["id"],
                "question": q["question"],
                "category": q["category"],
                "error": str(e)
            })

    return results

def print_report(results: list):
    """Prints final evaluation report with all metrics."""

    valid = [r for r in results if "error" not in r]
    total = len(valid)

    if total == 0:
        print("No valid results")
        return

    # Retrieval metrics
    avg_p1 = round(sum(r["retrieval"]["precision_at_1"] for r in valid) / total * 100, 1)
    avg_p3 = round(sum(r["retrieval"]["precision_at_3"] for r in valid) / total * 100, 1)
    avg_mrr = round(sum(r["retrieval"]["mrr"] for r in valid) / total, 3)

    # Quality metrics
    avg_faith = round(sum(r["quality"]["faithfulness"] for r in valid) / total * 100, 1)
    avg_rel = round(sum(r["quality"]["relevance"] for r in valid) / total * 100, 1)
    avg_comp = round(sum(r["quality"]["completeness"] for r in valid) / total * 100, 1)

    # Overall
    avg_overall = round(sum(r["overall_score"] for r in valid) / total, 3)

    # Failing questions
    failing = [r for r in valid if r["overall_score"] < QUALITY_THRESHOLD]

    # Category breakdown
    categories = {}
    for r in valid:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r["overall_score"])

    print(f"\n{'='*60}")
    print(f"EVALUATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Total questions evaluated: {total}")
    print()
    print(f"RETRIEVAL METRICS (ChromaDB + Reranker)")
    print(f"  Precision@1:  {avg_p1}%  (correct answer ranked #1)")
    print(f"  Precision@3:  {avg_p3}%  (correct answer in top 3)")
    print(f"  MRR:          {avg_mrr}   (mean reciprocal rank)")
    print()
    print(f"QUALITY METRICS (LLM-as-Judge via Groq)")
    print(f"  Faithfulness: {avg_faith}%  (no hallucinations)")
    print(f"  Relevance:    {avg_rel}%  (answers the question)")
    print(f"  Completeness: {avg_comp}%  (includes key details)")
    print()
    print(f"OVERALL SCORE: {avg_overall*100:.1f}%")
    print()
    print(f"BY CATEGORY:")
    for cat, scores in sorted(categories.items()):
        avg = round(sum(scores) / len(scores) * 100, 1)
        bar = "█" * int(avg / 10) + "░" * (10 - int(avg / 10))
        print(f"  {cat:<20} {bar} {avg}%")
    print(f"{'='*60}")

    # Save full results
    with open("data/eval_results.json", "w") as f:
        json.dump({
            "summary": {
                "total": total,
                "retrieval": {
                    "precision_at_1": avg_p1,
                    "precision_at_3": avg_p3,
                    "mrr": avg_mrr
                },
                "quality": {
                    "faithfulness": avg_faith,
                    "relevance": avg_rel,
                    "completeness": avg_comp
                },
                "overall_score": round(avg_overall * 100, 1),
                "generated_at": datetime.now().isoformat()
            },
            "results": valid
        }, f, indent=2)

    print(f"\nFull results saved to data/eval_results.json")

    # Run regression gate
    regression_gate(avg_overall, failing)