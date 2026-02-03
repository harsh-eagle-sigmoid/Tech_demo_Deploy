"""
Evaluation Framework — Test Runner
Reads TWO separate files:
  1. data/ground_truth/all_queries.json  → expected SQL (ground truth)
  2. data/agent_outputs.json             → SQL the agents actually produced

Never imports agents. Agents run independently via agents/run_agents.py first.
"""
import json
from loguru import logger
from evaluation.evaluator import Evaluator


def test_evaluation(sample_size: int = 10):
    """
    Evaluate agent outputs against ground truth.

    Args:
        sample_size: Number of queries to evaluate (None = all)
    """
    logger.add("logs/evaluation_test.log", rotation="10 MB")

    print("=" * 80)
    print(" EVALUATION FRAMEWORK — TEST RUNNER")
    print("=" * 80)

    # ── Load ground truth (expected SQL) ──────────────────────────────────
    print("\n📂 Loading ground truth (expected SQL)...")
    try:
        with open("data/ground_truth/all_queries.json", "r") as f:
            ground_truth_list = json.load(f)
        print(f"   Loaded {len(ground_truth_list)} ground truth entries")
    except FileNotFoundError:
        print("   ❌ Ground truth not found. Run: python -m data.ground_truth_generator_1000")
        return

    # Index ground truth by query_id for fast lookup
    ground_truth = {q["query_id"]: q for q in ground_truth_list}

    # ── Load agent outputs (what agents actually generated) ────────────────
    print("\n📂 Loading agent outputs (agent-generated SQL)...")
    try:
        with open("data/agent_outputs.json", "r") as f:
            agent_outputs = json.load(f)
        print(f"   Loaded {len(agent_outputs)} agent outputs")
    except FileNotFoundError:
        print("   ❌ Agent outputs not found.")
        print("      Run agents independently first:")
        print("      python -m agents.run_agents")
        return

    # ── Match agent outputs with ground truth by query_id ─────────────────
    print("\n🔗 Matching agent outputs with ground truth by query_id...")
    paired = []
    for ao in agent_outputs:
        qid = ao["query_id"]
        if qid in ground_truth and ao["status"] == "success":
            paired.append({
                "query_id": qid,
                "query_text": ao["query_text"],
                "agent_type": ao["agent_type"],
                "complexity": ao["complexity"],
                "agent_generated_sql": ao["agent_generated_sql"],   # what agent produced
                "ground_truth_sql": ground_truth[qid]["sql"]        # what was expected
            })

    print(f"   Matched {len(paired)} queries (agent output + ground truth)")

    if sample_size:
        paired = paired[:sample_size]
        print(f"   Evaluating first {sample_size} for this test run")

    # ── Group by agent type ───────────────────────────────────────────────
    spend_paired  = [p for p in paired if p["agent_type"] == "spend"]
    demand_paired = [p for p in paired if p["agent_type"] == "demand"]

    print(f"\n📊 Evaluation breakdown:")
    print(f"   Spend Agent  : {len(spend_paired)} queries")
    print(f"   Demand Agent : {len(demand_paired)} queries")

    # ── Initialize evaluators ─────────────────────────────────────────────
    spend_evaluator  = Evaluator("spend")
    demand_evaluator = Evaluator("demand")

    # ── Evaluate ──────────────────────────────────────────────────────────
    all_results = []

    for label, evaluator, pairs in [
        ("SPEND AGENT",  spend_evaluator,  spend_paired),
        ("DEMAND AGENT", demand_evaluator, demand_paired)
    ]:
        if not pairs:
            continue

        print(f"\n\n{'─' * 80}")
        print(f" {label} EVALUATION")
        print(f"{'─' * 80}")

        results = []
        for i, p in enumerate(pairs, 1):
            print(f"\n  [{i}/{len(pairs)}] {p['query_id']}  {p['query_text'][:55]}...")
            print(f"       Agent SQL  : {(p['agent_generated_sql'] or '')[:70]}...")
            print(f"       Truth SQL  : {p['ground_truth_sql'][:70]}...")

            result = evaluator.evaluate(
                query_id=p["query_id"],
                query_text=p["query_text"],
                generated_sql=p["agent_generated_sql"],   # agent's own output
                ground_truth_sql=p["ground_truth_sql"],   # expected
                complexity=p["complexity"]
            )

            evaluator.store_result(result)

            print(f"       Result     : {result['final_result']}  "
                  f"score={result['final_score']:.2f}  "
                  f"(struct={result['scores'].get('structural',0):.2f} "
                  f"sem={result['scores'].get('semantic',0):.2f} "
                  f"llm={result['scores'].get('llm',0):.2f})")

            results.append(result)

        # Summary
        passed   = sum(1 for r in results if r["final_result"] == "PASS")
        accuracy = passed / len(results) * 100 if results else 0

        print(f"\n  📈 {label} SUMMARY")
        print(f"     Evaluated : {len(results)}")
        print(f"     Passed    : {passed}")
        print(f"     Failed    : {len(results) - passed}")
        print(f"     Accuracy  : {accuracy:.1f}%")

        all_results.extend(results)

    # ── Overall summary ───────────────────────────────────────────────────
    total_passed = sum(1 for r in all_results if r["final_result"] == "PASS")
    total_acc    = total_passed / len(all_results) * 100 if all_results else 0

    print(f"\n\n{'=' * 80}")
    print(f" OVERALL RESULTS")
    print(f"{'=' * 80}")
    print(f"   Total evaluated : {len(all_results)}")
    print(f"   Total passed    : {total_passed}")
    print(f"   Total failed    : {len(all_results) - total_passed}")
    print(f"   Overall accuracy: {total_acc:.1f}%")
    print(f"   Stored in       : monitoring.evaluations")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    test_evaluation(sample_size=10)
