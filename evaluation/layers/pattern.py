
from typing import Dict, Any
from loguru import logger

class PatternLayer:
    """
    Layer 3: SQL Pattern Analysis (Weight: 20%)
    Checks for common SQL logical pitfalls that might not be syntax errors but indicate wrong logic.
    """
    
    def evaluate(self, sql: str) -> float:
        """
        Analyzes SQL for logical patterns.
        Returns a score between 0.0 and 1.0.
        """
        sql_upper = sql.upper()
        score = 1.0
        issues = []
        
        # 1. Aggregation without Group By Detection
        # (Naive check: if aggregate functions exist but GROUP BY is missing)
        # We can't easily parse this without a full parser, so we use heuristics.
        aggregates = ["SUM(", "AVG(", "COUNT(", "MAX(", "MIN("]
        has_agg = any(agg in sql_upper for agg in aggregates)
        has_group = "GROUP BY" in sql_upper
        
        # If we have aggregates and selecting multiple columns, we usually expect GROUP BY
        # But maybe it's a scalar aggregate (SELECT COUNT(*) FROM X). That involves no Group By.
        # So we only penalize if we see non-aggregates? Hard to detect with regex.
        # Instead, let's look for "SELECT *, COUNT..." pattern which is usually bad in standard SQL.
        
        if "SELECT *" in sql_upper and has_agg and not has_group:
             score -= 0.5
             issues.append("Aggregation with SELECT * and no GROUP BY")

        # 2. Cartesian Product Risk
        # If multiple tables in FROM/JOIN but no WHERE or ON?
        # Rough heuristic: count FROM/JOIN. If > 1, check for ON/WHERE.
        tables_count = sql_upper.count(" JOIN ") + sql_upper.count(" FROM ") 
        # Note: FROM a, b is rare in modern SQL (explicit JOINs preferred), but possible.
        # If we see CROSS JOIN, that's intentional.
        
        # 3. Limit without Order By
        # Non-deterministic result
        if "LIMIT" in sql_upper and "ORDER BY" not in sql_upper:
            score -= 0.3
            issues.append("LIMIT used without ORDER BY (Non-deterministic)")

        # 4. Dangerous Filters
        if "WHERE 1=1" in sql_upper and len(sql_upper) < 50:
            pass

        # 5. Missing LIMIT on SELECT *
        # Performance risk on large tables
        # Use regex to handle multiple spaces
        import re
        if re.search(r"SELECT\s+\*", sql_upper) and "LIMIT" not in sql_upper:
            score -= 0.2
            issues.append("SELECT * used without LIMIT (Performance Risk)")

        if issues:
            logger.debug(f"Pattern Analysis Found Issues: {issues}")
            
        return max(0.0, score)
