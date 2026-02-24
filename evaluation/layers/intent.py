
from typing import Optional, Set
from loguru import logger
import re

class IntentLayer:
    """
    Layer 2: Intent Matching (Weight: 25%)
    Advanced schema-aware intent detection using:
    1. Phrase pattern detection (context-aware)
    2. SQL structure analysis (WHERE, GROUP BY, aggregation functions)
    3. Schema metadata (dimension vs measure columns)
    4. Contextual keyword matching
    """

    # Data types that indicate dimension columns (GROUP BY candidates)
    DIMENSION_TYPES = {"character varying", "varchar", "text", "character"}
    # Data types that indicate measure columns (aggregation candidates)
    MEASURE_TYPES = {"integer", "numeric", "decimal", "real", "double precision", "bigint", "smallint"}

    def __init__(self, schema_info: Optional[dict] = None):
        # Build dimension/measure column sets from schema metadata
        self.dimension_columns = set()
        self.measure_columns = set()

        if schema_info:
            for table, columns in schema_info.items():
                for col_name, col_type in columns.items():
                    col_type_lower = col_type.lower()
                    if col_type_lower in self.DIMENSION_TYPES:
                        self.dimension_columns.add(col_name.lower())
                    elif col_type_lower in self.MEASURE_TYPES:
                        self.measure_columns.add(col_name.lower())

            logger.info(f"IntentLayer schema-aware: {len(self.dimension_columns)} dimensions, {len(self.measure_columns)} measures")
            logger.debug(f"Dimensions: {self.dimension_columns}")
            logger.debug(f"Measures: {self.measure_columns}")

        # Phrase patterns for intent detection (checked first, before keywords)
        self.phrase_patterns = [
            # Filtering patterns
            (r'\b(list|show|get|find|select)\b.*\b(with|where|having)\b.*[<>=]', 'filtering'),
            (r'\b(campaigns|products|users|customers|orders)\b.*\b(with|where)\b.*\b(greater|less|equal|above|below)\b', 'filtering'),

            # Aggregation patterns
            (r'\b(total|sum|sum of|overall)\b.*\b(' + '|'.join([re.escape(col) for col in list(self.measure_columns)[:20]]) + r')\b', 'summation'),
            (r'\b(average|mean|avg|avg of)\b', 'aggregation'),
            (r'\b(count|number of|how many)\b', 'summation'),

            # Grouping patterns
            (r'\b(' + '|'.join([re.escape(col) for col in list(self.measure_columns)[:20]]) + r')\b.*\b(per|by|for each)\b.*\b(' + '|'.join([re.escape(col) for col in list(self.dimension_columns)[:20]]) + r')\b', 'grouping'),
            (r'\b(breakdown|break down|group by|split by)\b', 'grouping'),

            # Sorting patterns
            (r'\b(top|highest|maximum|best)\b.*\b(by|in terms of)\b', 'maximization'),
            (r'\b(lowest|minimum|bottom|worst)\b.*\b(by|in terms of)\b', 'minimization'),

            # Limiting patterns
            (r'\b(top|first)\s+\d+', 'limiting'),
        ]

    def evaluate(self, user_query: str, sql: str) -> float:
        """
        Calculates Intent Match Score using:
        1. Phrase pattern detection
        2. SQL structure analysis
        3. Schema-aware inference
        4. Contextual keyword matching
        """
        query_lower = user_query.lower()
        sql_upper = sql.upper()

        # Step 1: Detect intents from query using phrase patterns + schema
        requested_intents = self._detect_query_intents(query_lower)

        # Step 2: Analyze SQL to see what operations it actually performs
        fulfilled_intents = self._analyze_sql_operations(sql_upper)

        # Step 3: Calculate match score
        score = self._calculate_intent_score(requested_intents, fulfilled_intents, sql_upper)

        logger.debug(
            f"Intent Analysis: requested={requested_intents}, fulfilled={fulfilled_intents}, score={score:.3f}"
        )

        return score

    def _detect_query_intents(self, query_lower: str) -> Set[str]:
        """Detect what intents the user is requesting"""
        intents = set()

        # Check phrase patterns first (highest priority)
        for pattern, intent in self.phrase_patterns:
            if re.search(pattern, query_lower):
                intents.add(intent)
                logger.debug(f"Phrase pattern matched: {intent} via pattern")

        # Check for comparison operators indicating filtering
        if self._has_comparison_context(query_lower):
            intents.add('filtering')

        # Check for "per" or "by" with dimension columns (grouping)
        if self._has_grouping_context(query_lower):
            intents.add('grouping')

        # Check for aggregation keywords with measure columns
        if self._has_aggregation_context(query_lower):
            if any(kw in query_lower for kw in ["total", "sum", "count", "number of"]):
                intents.add('summation')
            elif any(kw in query_lower for kw in ["average", "mean", "avg"]):
                intents.add('aggregation')
            elif any(kw in query_lower for kw in ["highest", "maximum", "max", "top", "most"]):
                intents.add('maximization')
            elif any(kw in query_lower for kw in ["lowest", "minimum", "min", "bottom", "least"]):
                intents.add('minimization')

        # Check for sorting keywords
        if any(kw in query_lower for kw in ["sort", "order", "rank"]):
            intents.add('sorting')

        # Check for limiting keywords with numbers
        if re.search(r'\b(top|first|limit)\s+\d+', query_lower):
            intents.add('limiting')

        return intents

    def _has_comparison_context(self, query_lower: str) -> bool:
        """Check if query has comparison operators indicating filtering intent"""
        # Look for patterns like "revenue > 100000", "with X greater than Y"
        comparison_patterns = [
            r'\b\w+\s*[<>=]+\s*\d+',  # column > 100
            r'\b(greater|less|equal|above|below|between)\s+(than|to)\b',
            r'\b(with|where|having)\b.*\b(greater|less|above|below|equal)\b',
        ]

        for pattern in comparison_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def _has_grouping_context(self, query_lower: str) -> bool:
        """Check if query implies grouping (measure per dimension)"""
        # Pattern: "revenue per campaign", "clicks by category"
        query_words = query_lower.split()

        for i, word in enumerate(query_words):
            # Check for "per" or "by" pattern
            if word in ["per", "by"] and i > 0 and i < len(query_words) - 1:
                before_word = query_words[i - 1]
                after_word = query_words[i + 1]

                # Check if it's measure + per/by + dimension
                if before_word in self.measure_columns and after_word in self.dimension_columns:
                    return True

        # Also check for explicit grouping keywords
        if any(phrase in query_lower for phrase in ["group by", "breakdown", "break down", "split by"]):
            return True

        return False

    def _has_aggregation_context(self, query_lower: str) -> bool:
        """Check if query needs aggregation (but not just filtering)"""
        # If there's a comparison operator with a measure, it's likely filtering not aggregation
        if self._has_comparison_context(query_lower):
            return False

        # Check if aggregation keywords appear before/near measure columns
        agg_keywords = ["total", "sum", "average", "mean", "avg", "count", "max", "min", "highest", "lowest"]

        for measure in self.measure_columns:
            if measure in query_lower:
                # Get the context around the measure column
                idx = query_lower.find(measure)
                context_before = query_lower[max(0, idx - 30):idx]

                # Check if aggregation keyword appears before the measure
                if any(kw in context_before for kw in agg_keywords):
                    return True

        return False

    def _analyze_sql_operations(self, sql_upper: str) -> Set[str]:
        """Analyze SQL to determine what operations it performs"""
        operations = set()

        # Check for WHERE clause (filtering)
        if "WHERE" in sql_upper:
            operations.add('filtering')

        # Check for aggregation functions
        if re.search(r'\b(SUM|COUNT)\s*\(', sql_upper):
            operations.add('summation')
        if re.search(r'\bAVG\s*\(', sql_upper):
            operations.add('aggregation')
        if re.search(r'\bMAX\s*\(', sql_upper):
            operations.add('maximization')
        if re.search(r'\bMIN\s*\(', sql_upper):
            operations.add('minimization')

        # Check for GROUP BY (grouping)
        if "GROUP BY" in sql_upper:
            operations.add('grouping')

        # Check for ORDER BY (sorting)
        if "ORDER BY" in sql_upper:
            operations.add('sorting')

            # Determine if it's maximization or minimization
            if "DESC" in sql_upper:
                operations.add('maximization')
            else:
                operations.add('minimization')

        # Check for LIMIT (limiting)
        if re.search(r'\bLIMIT\s+\d+', sql_upper):
            operations.add('limiting')

        return operations

    def _calculate_intent_score(self, requested: Set[str], fulfilled: Set[str], sql_upper: str) -> float:
        """Calculate final intent score based on requested vs fulfilled intents"""

        # If no specific intents detected, assume it's a basic select
        if not requested:
            # Basic query should have basic SQL
            if "WHERE" not in sql_upper and "GROUP BY" not in sql_upper and "ORDER BY" not in sql_upper:
                return 1.0  # Perfect for simple list query
            else:
                # Unrequested complexity
                return 0.8

        # Calculate matches
        matched = requested & fulfilled
        missing = requested - fulfilled
        unrequested = fulfilled - requested

        # Base score: percentage of requested intents that were fulfilled
        if len(requested) > 0:
            base_score = len(matched) / len(requested)
        else:
            base_score = 1.0

        # Penalties
        miss_penalty = len(missing) * 0.20  # -20% per missing intent
        unrequested_penalty = len(unrequested) * 0.05  # -5% per unrequested operation

        # Bonus for multi-intent queries done correctly
        coverage_bonus = 0.0
        if len(matched) >= 3:
            coverage_bonus = 0.10
        elif len(matched) == 2:
            coverage_bonus = 0.05

        # SQL quality bonuses
        specificity_bonus = 0.0
        if "SELECT *" not in sql_upper:
            specificity_bonus += 0.03
        if " AS " in sql_upper:
            specificity_bonus += 0.02

        final_score = base_score + coverage_bonus + specificity_bonus - miss_penalty - unrequested_penalty

        logger.debug(
            f"Intent Score breakdown: base={base_score:.2f}, matched={len(matched)}, "
            f"missing={len(missing)}, unrequested={len(unrequested)}, "
            f"coverage_bonus={coverage_bonus:.2f}, miss_penalty={miss_penalty:.2f}, "
            f"final={final_score:.2f}"
        )

        return max(0.0, min(1.0, final_score))
