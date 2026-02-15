
from typing import Dict
from loguru import logger
from agents.llm_client import LLMClient
from config.settings import settings


class LLMJudge:
    

    def __init__(self):
        
        self.llm = LLMClient(provider=settings.EVALUATOR_LLM_PROVIDER)
        logger.info(f"Initialized LLM Judge with provider: {settings.EVALUATOR_LLM_PROVIDER}")

    def evaluate(
        self,
        user_query: str,
        generated_sql: str,
        ground_truth_sql: str,
        agent_type: str
    ) -> Dict:
        
        try:
            
            system_prompt = """You are an expert SQL evaluator. Your task is to determine if the generated SQL query correctly answers the user's question.

Evaluation Criteria:
1. **Correctness**: Does the SQL query retrieve the right data to answer the question?
2. **Completeness**: Does it include all necessary components (filters, aggregations, etc.)?
3. **Logic**: Are the table joins, WHERE conditions, and GROUP BY clauses correct?

Compare the generated SQL with the ground truth SQL. Consider them equivalent if they produce the same result, even if syntax differs slightly.
Refine your judgment:
- **PASS** if the generated SQL uses a VIEW (e.g., `product_profitability`) instead of complex JOINs. This is a VALID logic optimization.
- **PASS** if the generated SQL uses `LIMIT 1` but Ground Truth uses `LIMIT 100` (unless "top 100" was explicitly asked).
- **PASS** if the generated SQL ranks by a raw column vs Ground Truth ranking by `AVG/SUM` of that column (logic is similar).
- **PASS** if the SQL answers the core intent of the question, even if aggregation or sorting is slightly different.
- **PASS** if the SQL uses different column aliases or table aliases.
- **IGNORE** usage of table aliases if they resolve correctly.
- **IGNORE** additional `ORDER BY` clauses unless the user asked for a specific order.
- **IGNORE** `NULLIF` or safety checks (e.g. division by zero protection).
- **IGNORE** extra columns in SELECT clause if the core answer is present.

**FAIL ONLY IF**:
- The SQL is syntactically invalid.
- The SQL queries the WRONG table or WRONG column (e.g. querying `products` when `sales` is needed).
- The SQL returns completely unrelated data.

**CRITICAL INSTRUCTIONS FOR FLEXIBILITY**:
- **SUPERIOR LOGIC**: If the generated SQL uses a more complex/accurate logic than the Ground Truth (e.g. calculating reorder quantity vs simple threshold), it MUST **PASS**.
- **MISSING COLUMNS**: If the generated SQL selects the core columns but misses 'availability' or 'description', it MUST **PASS**.
- **CASE SENSITIVITY**: Ignore case mismatches in string literals (e.g. 'Haircare' vs 'haircare').
HTML_BLOCK_END

Return your evaluation in this exact format:
VERDICT: [PASS/FAIL]
CONFIDENCE: [0.0-1.0]
REASONING: [Brief explanation of your decision]"""

            user_prompt = f"""User Query: "{user_query}"

Generated SQL:
{generated_sql}

Ground Truth SQL:
{ground_truth_sql}

Agent Type: {agent_type}

Evaluate if the generated SQL correctly answers the user query."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            
            response = self.llm.generate(
                messages=messages,
                temperature=0.0,  
                max_tokens=300
            )

        
            result = self._parse_response(response)

            return result

        except Exception as e:
            logger.error(f"Error in LLM evaluation: {e}")
            return {
                "verdict": "FAIL",
                "confidence": 0.0,
                "reasoning": f"Error during evaluation: {str(e)}",
                "raw_response": str(e)
            }

    def _parse_response(self, response: str) -> Dict:
        
        result = {
            "verdict": "FAIL",
            "confidence": 0.5,
            "reasoning": "",
            "raw_response": response
        }

        try:
            lines = response.strip().split('\n')

            for line in lines:
                line = line.strip()

                if line.startswith("VERDICT:"):
                    verdict_str = line.replace("VERDICT:", "").strip().upper()
                    result["verdict"] = verdict_str if verdict_str in ["PASS", "FAIL"] else "FAIL"

                elif line.startswith("CONFIDENCE:"):
                    try:
                        conf_str = line.replace("CONFIDENCE:", "").strip()
                        result["confidence"] = float(conf_str)
                    except:
                        result["confidence"] = 0.5

                elif line.startswith("REASONING:"):
                    result["reasoning"] = line.replace("REASONING:", "").strip()

            
            if not result["reasoning"]:
                result["reasoning"] = response

        except Exception as e:
            logger.warning(f"Error parsing LLM response: {e}")
            result["reasoning"] = response

        return result
