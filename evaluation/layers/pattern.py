
import re
from loguru import logger

class PatternLayer:
    """
    Layer 3: SQL Pattern Analysis (Weight: 20%)
    Analyzes SQL for both anti-patterns (penalties) and good practices (bonuses).
    Produces granular scores that differentiate between different query styles.
    """

    def evaluate(self, sql: str) -> float:
        """
        Analyzes SQL for logical patterns.
        Returns a score between 0.0 and 1.0.
        """
        sql_upper = sql.upper()
        sql_stripped = sql_upper.strip()

        base_score = 0.75
        bonuses = 0.0
        penalties = 0.0
        issues = []
        good_practices = []

        # === PENALTIES (Anti-patterns) ===

        aggregates = ["SUM(", "AVG(", "COUNT(", "MAX(", "MIN("]
        has_agg = any(agg in sql_upper for agg in aggregates)
        has_group = "GROUP BY" in sql_upper

        # 1. Aggregation with SELECT * and no GROUP BY
        if "SELECT *" in sql_upper and has_agg and not has_group:
             penalties += 0.30
             issues.append("Aggregation with SELECT * and no GROUP BY")

        # 2. Limit without Order By (non-deterministic result)
        if "LIMIT" in sql_upper and "ORDER BY" not in sql_upper:
            penalties += 0.15
            issues.append("LIMIT used without ORDER BY")

        # 3. Missing LIMIT on SELECT *
        if re.search(r"SELECT\s+\*", sql_upper) and "LIMIT" not in sql_upper:
            penalties += 0.10
            issues.append("SELECT * used without LIMIT")

        # 4. Cartesian product risk (multiple tables without JOIN or WHERE)
        from_parts = sql_upper.split("FROM")
        if len(from_parts) > 1:
            after_from = from_parts[1].split("WHERE")[0].split("GROUP")[0]
            comma_tables = after_from.count(",")
            if comma_tables > 0 and "JOIN" not in sql_upper and "WHERE" not in sql_upper:
                penalties += 0.20
                issues.append("Multiple tables without JOIN or WHERE condition")

        # === BONUSES (Good practices) ===

        # 1. Specific column selection (not SELECT *) (+0.05)
        if not re.search(r"SELECT\s+\*", sql_upper) and "SELECT" in sql_upper:
            bonuses += 0.05
            good_practices.append("Specific column selection")

        # 2. Column aliasing with AS (+0.04)
        alias_count = len(re.findall(r'\bAS\s+\w+', sql_upper))
        if alias_count >= 1:
            bonuses += 0.04
            good_practices.append(f"Column aliasing ({alias_count} alias(es))")

        # 3. Proper JOIN usage (+0.05)
        join_count = sql_upper.count("JOIN")
        if join_count >= 1:
            bonuses += 0.05
            good_practices.append(f"Proper JOIN usage ({join_count} join(s))")

        # 4. WHERE clause for filtering (+0.04)
        if "WHERE" in sql_upper:
            bonuses += 0.04
            good_practices.append("WHERE clause for filtering")

        # 5. GROUP BY with aggregation (+0.04)
        if has_group and has_agg:
            bonuses += 0.04
            good_practices.append("Proper GROUP BY with aggregation")

        # 6. ORDER BY for deterministic results (+0.03)
        if "ORDER BY" in sql_upper:
            bonuses += 0.03
            good_practices.append("ORDER BY for deterministic results")

        # 7. LIMIT clause for bounded results (+0.02)
        if "LIMIT" in sql_upper:
            bonuses += 0.02
            good_practices.append("LIMIT for bounded results")

        # 8. Subquery usage (+0.02)
        subquery_count = sql_upper.count("SELECT") - 1
        if subquery_count > 0:
            bonuses += 0.02
            good_practices.append(f"Subquery usage ({subquery_count} subquery)")

        # 9. HAVING clause (+0.02)
        if "HAVING" in sql_upper:
            bonuses += 0.02
            good_practices.append("HAVING clause for aggregate filtering")

        final_score = base_score + bonuses - penalties

        if issues:
            logger.debug(f"Pattern Issues: {issues}")
        if good_practices:
            logger.debug(f"Pattern Good Practices: {good_practices}")
        logger.debug(f"Pattern Score: base={base_score:.2f}, bonuses={bonuses:.3f}, "
                     f"penalties={penalties:.3f}, final={final_score:.3f}")

        return max(0.0, min(1.0, final_score))
