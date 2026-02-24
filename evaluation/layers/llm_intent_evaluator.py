"""
LLM-based intent evaluation for accurate query intent matching
Replaces keyword-based matching with contextual understanding
"""
from typing import Dict, List
from dataclasses import dataclass
from loguru import logger
from evaluation.llm_judge import LLMJudge


@dataclass
class IntentAnalysis:
    """Results from LLM intent analysis"""
    requested_intents: List[str]
    fulfilled_intents: List[str]
    missing_intents: List[str]
    unrequested_intents: List[str]
    score: float
    reasoning: str


class LLMIntentEvaluator:
    """
    Uses LLM to evaluate query intent matching.
    More accurate than keyword matching, understands context.
    """

    def __init__(self):
        """Initialize with shared LLM judge"""
        self.llm_judge = LLMJudge()

    def evaluate(self, user_query: str, sql: str) -> IntentAnalysis:
        """
        Evaluate if the SQL fulfills the intents expressed in the user query.

        Args:
            user_query: User's natural language query
            sql: Generated SQL query

        Returns:
            IntentAnalysis with score and breakdown
        """
        logger.debug(f"LLM evaluating intent for: {user_query[:60]}...")

        # Build prompt
        prompt = self._build_intent_prompt(user_query, sql)

        try:
            # Call LLM
            response = self.llm_judge.call_llm(prompt, temperature=0.0, max_tokens=600)

            # Parse response
            analysis = self._parse_response(response)

            logger.debug(
                f"Intent Analysis: score={analysis.score:.2f}, "
                f"requested={analysis.requested_intents}, "
                f"fulfilled={analysis.fulfilled_intents}, "
                f"missing={analysis.missing_intents}"
            )

            return analysis

        except Exception as e:
            logger.error(f"LLM intent evaluation failed: {e}")
            # Return conservative score on error
            return IntentAnalysis(
                requested_intents=[],
                fulfilled_intents=[],
                missing_intents=[],
                unrequested_intents=[],
                score=0.5,
                reasoning=f"Evaluation failed: {str(e)}"
            )

    def _build_intent_prompt(self, user_query: str, sql: str) -> str:
        """Build prompt for LLM intent evaluation"""
        return f"""You are an expert SQL query analyzer. Your task is to identify what the user wants (intent) and verify if the SQL query fulfills those intents.

**User Query:**
{user_query}

**Generated SQL:**
```sql
{sql}
```

**Intent Categories:**

1. **FILTERING**: Narrowing results by conditions (WHERE clauses)
   - Examples: "campaigns with revenue > 100000", "only active users", "products in category X"

2. **AGGREGATION**: Computing summaries (SUM, AVG, COUNT, MIN, MAX)
   - Examples: "total revenue", "average clicks", "count of orders", "maximum spend"

3. **GROUPING**: Breaking down by dimensions (GROUP BY)
   - Examples: "revenue per campaign", "orders by category", "breakdown by region"

4. **SORTING**: Ordering results (ORDER BY)
   - Examples: "highest revenue", "lowest cost", "sorted by date", "top campaigns"

5. **LIMITING**: Restricting number of rows (LIMIT, TOP N)
   - Examples: "top 10", "first 5", "limit to 20"

6. **JOINING**: Combining multiple tables
   - Examples: "campaigns and their categories", "users with orders"

7. **CALCULATION**: Derived metrics or computed fields
   - Examples: "CTR (clicks/impressions)", "profit margin", "percentage"

**Analysis Instructions:**

1. **Identify REQUESTED intents**: What does the user query ask for?
   - Be contextual: "revenue > 100000" is FILTERING, not AGGREGATION
   - "total revenue" is AGGREGATION, "revenue per campaign" is AGGREGATION + GROUPING
   - "list campaigns" with a threshold is FILTERING

2. **Identify FULFILLED intents**: What does the SQL actually do?
   - Check SQL operations: WHERE, SUM/COUNT/AVG/MAX/MIN, GROUP BY, ORDER BY, LIMIT, JOIN

3. **Calculate score**:
   - If ALL requested intents are fulfilled: 1.0
   - For each missing intent: -0.20
   - For unrequested complexity (GROUP BY/JOIN not asked for): -0.10
   - Minimum score: 0.0

**Response Format (REQUIRED):**
REQUESTED: intent1, intent2, intent3
FULFILLED: intent1, intent2
MISSING: intent3
UNREQUESTED:
SCORE: <number between 0.0 and 1.0>
REASONING: <1-2 sentences explaining the score>

**Example 1:**
User: "List campaigns with revenue > 100000"
SQL: SELECT * FROM campaigns WHERE revenue > 100000

REQUESTED: FILTERING
FULFILLED: FILTERING
MISSING:
UNREQUESTED:
SCORE: 1.0
REASONING: The query requests filtering by revenue threshold, and the SQL correctly implements this with a WHERE clause. All intents fulfilled.

**Example 2:**
User: "Show total revenue per campaign"
SQL: SELECT campaign_id, revenue FROM campaigns

REQUESTED: AGGREGATION, GROUPING
FULFILLED:
MISSING: AGGREGATION, GROUPING
UNREQUESTED:
SCORE: 0.6
REASONING: The query asks for aggregated revenue grouped by campaign, but the SQL just selects individual rows without SUM() or GROUP BY. Missing both critical intents (-0.40).

Now analyze the query above:"""

    def _parse_response(self, response: str) -> IntentAnalysis:
        """Parse LLM response to extract intent analysis"""
        try:
            lines = response.strip().split('\n')

            requested = []
            fulfilled = []
            missing = []
            unrequested = []
            score = 0.5
            reasoning = ""

            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().upper()
                    value = value.strip()

                    if 'REQUESTED' in key:
                        requested = [i.strip() for i in value.split(',') if i.strip()]
                    elif 'FULFILLED' in key:
                        fulfilled = [i.strip() for i in value.split(',') if i.strip()]
                    elif 'MISSING' in key:
                        missing = [i.strip() for i in value.split(',') if i.strip()]
                    elif 'UNREQUESTED' in key:
                        unrequested = [i.strip() for i in value.split(',') if i.strip()]
                    elif 'SCORE' in key:
                        try:
                            score = float(value)
                            score = max(0.0, min(1.0, score))
                        except ValueError:
                            score = 0.5
                    elif 'REASONING' in key:
                        reasoning = value

            return IntentAnalysis(
                requested_intents=requested,
                fulfilled_intents=fulfilled,
                missing_intents=missing,
                unrequested_intents=unrequested,
                score=score,
                reasoning=reasoning or "No reasoning provided"
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM intent response: {e}")
            logger.debug(f"Response was: {response}")

            return IntentAnalysis(
                requested_intents=[],
                fulfilled_intents=[],
                missing_intents=[],
                unrequested_intents=[],
                score=0.5,
                reasoning=f"Failed to parse response: {str(e)}"
            )
