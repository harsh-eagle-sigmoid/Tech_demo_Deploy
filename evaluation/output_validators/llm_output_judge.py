"""
LLM-based output validator for queries without ground truth
Uses LLM to evaluate if query output correctly answers the user's question
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
from evaluation.llm_judge import LLMJudge


@dataclass
class LLMOutputScore:
    """Scores from LLM output evaluation"""
    correctness: float  # 0.0-1.0
    completeness: float  # 0.0-1.0
    quality: float  # 0.0-1.0
    overall: float  # weighted average
    reasoning: str


class LLMOutputJudge:
    """
    Uses LLM to evaluate query output quality and correctness.
    Replaces heuristic sanity checks with intelligent reasoning.
    """

    def __init__(self):
        """Initialize with shared LLM judge"""
        self.llm_judge = LLMJudge()

    def evaluate_output(
        self,
        query_text: str,
        sql: str,
        columns: List[str],
        rows: List[Tuple],
        row_count: int,
        execution_time_ms: float,
        schema_info: Optional[dict] = None
    ) -> LLMOutputScore:
        """
        Evaluate query output using LLM reasoning.

        Args:
            query_text: User's natural language query
            sql: Generated SQL query
            columns: Column names from output
            rows: Sample rows (first 5) from output
            row_count: Total number of rows returned
            execution_time_ms: Query execution time

        Returns:
            LLMOutputScore with detailed evaluation
        """
        logger.info(f"LLM evaluating output for: {query_text[:60]}...")

        # Format output as table
        output_table = self._format_output_table(columns, rows)

        # Build LLM prompt
        prompt = self._build_evaluation_prompt(
            query_text=query_text,
            sql=sql,
            output_table=output_table,
            row_count=row_count,
            columns=columns,
            execution_time_ms=execution_time_ms,
            schema_info=schema_info
        )

        # Call LLM
        try:
            response = self.llm_judge.call_llm(prompt)
            scores = self._parse_llm_response(response)

            logger.info(
                f"LLM output evaluation: correctness={scores.correctness:.2f}, "
                f"completeness={scores.completeness:.2f}, overall={scores.overall:.2f}"
            )

            return scores

        except Exception as e:
            logger.error(f"LLM output evaluation failed: {e}")
            # Return conservative scores on error
            return LLMOutputScore(
                correctness=0.5,
                completeness=0.5,
                quality=0.5,
                overall=0.5,
                reasoning=f"Evaluation failed: {str(e)}"
            )

    def _format_output_table(self, columns: List[str], rows: List[Tuple], max_rows: int = 5) -> str:
        """Format output as markdown table for LLM"""
        if not rows:
            return "No rows returned"

        # Header
        table = "| " + " | ".join(columns) + " |\n"
        table += "|" + "|".join(["---" for _ in columns]) + "|\n"

        # Rows (limited to max_rows)
        for row in rows[:max_rows]:
            formatted_row = [str(val) if val is not None else "NULL" for val in row]
            table += "| " + " | ".join(formatted_row) + " |\n"

        if len(rows) > max_rows:
            table += f"\n... and {len(rows) - max_rows} more rows"

        return table

    def _build_evaluation_prompt(
        self,
        query_text: str,
        sql: str,
        output_table: str,
        row_count: int,
        columns: List[str],
        execution_time_ms: float,
        schema_info: Optional[dict] = None
    ) -> str:
        """Build structured prompt for LLM output evaluation"""

        # Build schema context so LLM can map column names to natural language
        schema_context = ""
        if schema_info:
            lines = []
            for table, cols in schema_info.items():
                col_names = [c if isinstance(c, str) else c.get("column_name", str(c)) for c in cols]
                lines.append(f"  - {table}: {', '.join(col_names)}")
            if lines:
                schema_context = "\n**Database Schema (for reference):**\n" + "\n".join(lines) + "\n"

        return f"""You are an expert SQL query evaluator. Analyze whether the query output correctly answers the user's question.{schema_context}

**User Question:**
{query_text}

**Generated SQL:**
```sql
{sql}
```

**Query Output (Sample):**
{output_table}

**Execution Details:**
- Total rows returned: {row_count}
- Columns: {', '.join(columns)}
- Execution time: {execution_time_ms:.1f}ms

**Evaluation Criteria:**

**Important:** A NULL or empty result is CORRECT and VALID if the SQL is logically correct but the requested data simply does not exist in the database (e.g., filtering by a year/date range not present in the data). Judge the SQL logic, not whether the data exists.

1. **CORRECTNESS (50%)**: Does the SQL correctly answer the user's question?
   - Is the SQL logic correct for the question asked?
   - Are the returned values reasonable (NULL is valid if data doesn't exist)?
   - Is the data structure appropriate for the question?
   - Are column names meaningful and relevant?

2. **COMPLETENESS (30%)**: Is the output complete?
   - Did it return the expected structure (even if 0 rows or NULL)?
   - Are all requested fields present?
   - Is any critical data missing from the SQL logic?
   - Does the SQL fully address the question?

3. **QUALITY (20%)**: Is the output high quality?
   - Are values within reasonable ranges?
   - No obvious errors (negative counts, impossible dates, etc.)?
   - Proper data types and formatting?
   - Professional presentation?

**Response Format (REQUIRED):**
CORRECTNESS_SCORE: <number between 0.0 and 1.0>
COMPLETENESS_SCORE: <number between 0.0 and 1.0>
QUALITY_SCORE: <number between 0.0 and 1.0>
OVERALL_SCORE: <weighted average: 0.5*correctness + 0.3*completeness + 0.2*quality>
REASONING: <2-3 sentences explaining your evaluation>

**Example Response:**
CORRECTNESS_SCORE: 0.9
COMPLETENESS_SCORE: 1.0
QUALITY_SCORE: 0.85
OVERALL_SCORE: 0.92
REASONING: The output correctly identifies the maximum clicks value and returns it with a clear column name. The result is complete with exactly one row as expected for a MAX() query. Minor quality improvement would be to format large numbers with commas for readability.

Now evaluate the query output above:"""

    def _parse_llm_response(self, response: str) -> LLMOutputScore:
        """Parse LLM response to extract scores"""
        try:
            lines = response.strip().split('\n')
            scores = {}
            reasoning = ""

            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().upper()
                    value = value.strip()

                    if 'CORRECTNESS_SCORE' in key:
                        scores['correctness'] = float(value)
                    elif 'COMPLETENESS_SCORE' in key:
                        scores['completeness'] = float(value)
                    elif 'QUALITY_SCORE' in key:
                        scores['quality'] = float(value)
                    elif 'OVERALL_SCORE' in key:
                        scores['overall'] = float(value)
                    elif 'REASONING' in key:
                        reasoning = value

            # Validate scores exist
            if not all(k in scores for k in ['correctness', 'completeness', 'quality']):
                raise ValueError("Missing required scores in LLM response")

            # Calculate overall if not provided
            if 'overall' not in scores:
                scores['overall'] = (
                    0.5 * scores['correctness'] +
                    0.3 * scores['completeness'] +
                    0.2 * scores['quality']
                )

            # Clamp scores to 0-1 range
            for key in scores:
                scores[key] = max(0.0, min(1.0, scores[key]))

            return LLMOutputScore(
                correctness=scores['correctness'],
                completeness=scores['completeness'],
                quality=scores['quality'],
                overall=scores['overall'],
                reasoning=reasoning or "No reasoning provided"
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"LLM response was: {response}")

            # Return middle-ground scores on parse error
            return LLMOutputScore(
                correctness=0.5,
                completeness=0.5,
                quality=0.5,
                overall=0.5,
                reasoning=f"Failed to parse LLM response: {str(e)}"
            )
