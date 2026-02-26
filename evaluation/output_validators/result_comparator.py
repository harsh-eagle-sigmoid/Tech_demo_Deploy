"""
Result set comparator with ordering normalization and fuzzy matching
"""
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, date
import re
from loguru import logger


@dataclass
class ComparisonResult:
    """Result of comparing two query result sets"""
    match: bool
    score: float  # 0.0 to 1.0
    schema_match: bool
    row_count_match: bool
    content_match_rate: float
    details: Dict[str, Any]


class ResultComparator:
    """
    Compare two SQL query result sets with intelligent normalization.
    Handles ordering, data types, nulls, and fuzzy matching.
    """

    def __init__(self, epsilon: float = 0.0001):
        """
        Args:
            epsilon: Tolerance for floating point comparison
        """
        self.epsilon = epsilon

    def compare(
        self,
        result1_columns: List[str],
        result1_rows: List[Tuple],
        result2_columns: List[str],
        result2_rows: List[Tuple],
        sql1: str = "",
        sql2: str = ""
    ) -> ComparisonResult:
        """
        Compare two result sets and return detailed comparison.

        Args:
            result1_columns: Column names from query 1
            result1_rows: Rows from query 1
            result2_columns: Column names from query 2
            result2_rows: Rows from query 2
            sql1: Original SQL 1 (for ordering detection)
            sql2: Original SQL 2 (for ordering detection)

        Returns:
            ComparisonResult with match status and details
        """
        details = {}

        # Step 1: Schema comparison (column names)
        schema_match = self._compare_schemas(result1_columns, result2_columns)
        details['schema_match'] = schema_match

        if not schema_match:
            return ComparisonResult(
                match=False,
                score=0.1,  # Small credit for trying
                schema_match=False,
                row_count_match=False,
                content_match_rate=0.0,
                details=details
            )

        # Step 2: Row count comparison
        row_count_match = len(result1_rows) == len(result2_rows)
        details['row_count_1'] = len(result1_rows)
        details['row_count_2'] = len(result2_rows)
        details['row_count_match'] = row_count_match

        if not row_count_match:
            return ComparisonResult(
                match=False,
                score=0.3,  # Schema correct, but wrong row count
                schema_match=True,
                row_count_match=False,
                content_match_rate=0.0,
                details=details
            )

        # Step 3: Detect if ordering matters
        ordering_matters = self._detect_ordering(sql1) or self._detect_ordering(sql2)
        details['ordering_matters'] = ordering_matters

        # Step 4: Normalize and compare content
        if ordering_matters:
            # Compare directly (order matters)
            content_match_rate = self._compare_ordered(result1_rows, result2_rows)
        else:
            # Sort before comparing (order doesn't matter)
            content_match_rate = self._compare_unordered(
                result1_rows, result2_rows, result1_columns
            )

        details['content_match_rate'] = content_match_rate

        # Step 5: Calculate final score
        if content_match_rate >= 0.99:
            score = 1.0  # Perfect match
            match = True
        elif content_match_rate >= 0.95:
            score = 0.95  # Near perfect
            match = True
        elif content_match_rate >= 0.80:
            score = 0.80  # Good match
            match = False
        else:
            score = content_match_rate  # Proportional
            match = False

        return ComparisonResult(
            match=match,
            score=score,
            schema_match=True,
            row_count_match=True,
            content_match_rate=content_match_rate,
            details=details
        )

    def _compare_schemas(self, cols1: List[str], cols2: List[str]) -> bool:
        """Compare column names (order-insensitive)"""
        # Normalize column names (lowercase, strip)
        norm1 = {col.lower().strip() for col in cols1}
        norm2 = {col.lower().strip() for col in cols2}
        return norm1 == norm2

    def _detect_ordering(self, sql: str) -> bool:
        """Detect if SQL has ORDER BY clause"""
        if not sql:
            return False

        sql_upper = sql.upper()
        # Check for ORDER BY (but not in subqueries)
        # Simple heuristic: if ORDER BY appears after last closing paren
        last_paren = sql_upper.rfind(')')
        if last_paren == -1:
            # No subquery
            return 'ORDER BY' in sql_upper
        else:
            # Check ORDER BY after last subquery
            remaining = sql_upper[last_paren:]
            return 'ORDER BY' in remaining

    def _compare_ordered(self, rows1: List[Tuple], rows2: List[Tuple]) -> float:
        """Compare rows maintaining order (for ORDER BY queries)"""
        if len(rows1) != len(rows2):
            return 0.0

        matched = 0
        for r1, r2 in zip(rows1, rows2):
            if self._rows_equal(r1, r2):
                matched += 1

        return matched / len(rows1) if rows1 else 1.0

    def _compare_unordered(
        self,
        rows1: List[Tuple],
        rows2: List[Tuple],
        columns: List[str]
    ) -> float:
        """Compare rows ignoring order (sort first)"""
        if len(rows1) != len(rows2):
            return 0.0

        # Sort both result sets by all columns
        try:
            sorted1 = sorted(rows1, key=lambda r: self._make_sortable(r))
            sorted2 = sorted(rows2, key=lambda r: self._make_sortable(r))

            matched = 0
            for r1, r2 in zip(sorted1, sorted2):
                if self._rows_equal(r1, r2):
                    matched += 1

            return matched / len(rows1) if rows1 else 1.0

        except TypeError as e:
            # Sorting failed (mixed types) - fall back to set comparison
            logger.warning(f"Failed to sort results, using set comparison: {e}")
            return self._compare_as_sets(rows1, rows2)

    def _compare_as_sets(self, rows1: List[Tuple], rows2: List[Tuple]) -> float:
        """Compare rows as sets (when sorting fails)"""
        # Convert to hashable tuples with normalized values
        set1 = {self._normalize_row(r) for r in rows1}
        set2 = {self._normalize_row(r) for r in rows2}

        if not set1 and not set2:
            return 1.0

        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 1.0

    def _rows_equal(self, row1: Tuple, row2: Tuple) -> bool:
        """Check if two rows are equal with normalization"""
        if len(row1) != len(row2):
            return False

        for v1, v2 in zip(row1, row2):
            if not self._values_equal(v1, v2):
                return False

        return True

    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """Compare two values with type normalization"""
        # Handle None/NULL
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False

        # Handle numeric types
        if isinstance(val1, (int, float, Decimal)) and isinstance(val2, (int, float, Decimal)):
            return abs(float(val1) - float(val2)) < self.epsilon

        # Handle datetime types
        if isinstance(val1, (datetime, date)) and isinstance(val2, (datetime, date)):
            return val1 == val2

        # Handle datetime/date vs string (GT JSON stores dates as ISO strings like "2021-02-01")
        if isinstance(val1, (datetime, date)) and isinstance(val2, str):
            try:
                return val1.isoformat() == val2.strip()
            except Exception:
                return False
        if isinstance(val1, str) and isinstance(val2, (datetime, date)):
            try:
                return val1.strip() == val2.isoformat()
            except Exception:
                return False

        # Handle strings
        if isinstance(val1, str) and isinstance(val2, str):
            return val1.strip() == val2.strip()

        # Handle bytes
        if isinstance(val1, bytes) and isinstance(val2, bytes):
            return val1 == val2

        # Fallback: direct comparison
        try:
            return val1 == val2
        except Exception:
            return False

    def _make_sortable(self, row: Tuple) -> Tuple:
        """Convert row to sortable tuple (handle mixed types)"""
        sortable = []
        for val in row:
            if val is None:
                sortable.append((0, None))  # Sort None first
            elif isinstance(val, (int, float, Decimal)):
                sortable.append((1, float(val)))
            elif isinstance(val, str):
                sortable.append((2, val))
            elif isinstance(val, (datetime, date)):
                sortable.append((3, val))
            elif isinstance(val, bytes):
                sortable.append((4, val))
            else:
                sortable.append((5, str(val)))
        return tuple(sortable)

    def _normalize_row(self, row: Tuple) -> Tuple:
        """Normalize row for set comparison (hashable)"""
        normalized = []
        for val in row:
            if val is None:
                normalized.append(None)
            elif isinstance(val, (int, float, Decimal)):
                # Round floats to handle precision
                normalized.append(round(float(val), 6))
            elif isinstance(val, str):
                normalized.append(val.strip())
            elif isinstance(val, (datetime, date)):
                normalized.append(val.isoformat())
            elif isinstance(val, bytes):
                normalized.append(val.hex())
            else:
                normalized.append(str(val))
        return tuple(normalized)
