
import re
from typing import Optional
from loguru import logger


class SemanticChecker:
    """Schema-aware SQL semantic comparison.
    Normalizes table/column aliases before comparing components so that
    'c.region' and 'region', or 'AVG(o.profit) as avg_profit' and 'AVG(profit)',
    are recognized as equivalent.
    """

    def __init__(self, schema_info: Optional[dict] = None):
        # Build lookup sets from schema metadata for alias resolution
        self.all_columns = set()
        self.all_tables = set()

        if schema_info:
            for table, columns in schema_info.items():
                self.all_tables.add(table.lower())
                for col_name in columns.keys():
                    self.all_columns.add(col_name.lower())

            logger.info(f"SemanticChecker schema-aware: {len(self.all_tables)} tables, {len(self.all_columns)} columns")

    def _normalize_column_ref(self, item: str) -> str:
        """Normalize a single column reference by stripping aliases and table prefixes.
        Examples:
          'c.region'                     → 'region'
          'AVG(o.profit) as avg_profit'  → 'avg(profit)'
          'spend_data.orders o'          → 'orders'
          'SUM(o.sales) as total'        → 'sum(sales)'
        """
        item = item.strip().lower()

        # Step 1: Strip column alias (AS alias_name)
        item = re.sub(r'\s+as\s+\w+', '', item)

        # Step 2: Strip table alias suffix on table references ('orders o' → 'orders')
        item = re.sub(r'^([\w\.]+)\s+\w+$', r'\1', item)

        # Step 3: Strip schema prefix ('spend_data.orders' → 'orders')
        item = re.sub(r'^\w+\.(\w+)$', r'\1', item)

        # Step 4: Normalize function arguments — strip table alias inside functions
        # AVG(o.profit) → AVG(profit), SUM(c.sales) → SUM(sales)
        def strip_alias_in_func(match):
            func_name = match.group(1)
            inner = match.group(2)
            # Strip table alias prefix from inner reference
            inner_clean = re.sub(r'\w+\.(\w+)', r'\1', inner)
            return f"{func_name}({inner_clean})"

        item = re.sub(r'(\w+)\(([^)]+)\)', strip_alias_in_func, item)

        # Step 5: Strip remaining table alias prefix on plain columns ('o.profit' → 'profit')
        if '.' in item and '(' not in item:
            parts = item.split('.')
            if len(parts) == 2:
                potential_col = parts[1].strip()
                if potential_col in self.all_columns or not self.all_columns:
                    item = potential_col

        return item.strip()

    def _normalize_component_list(self, items: list) -> list:
        """Apply normalization to every item in a component list."""
        return [self._normalize_column_ref(item) for item in items]

    def normalize_sql(self, sql: str) -> str:
        """Normalize SQL whitespace, case, and trailing semicolons."""
        sql = re.sub(r'\s+', ' ', sql)
        sql = sql.lower()
        sql = sql.rstrip(';')
        sql = sql.strip()
        return sql

    def extract_components(self, sql: str) -> dict:
        """Extract SQL components (SELECT, FROM, WHERE, GROUP BY, ORDER BY, JOINs)."""
        components = {
            "select": [],
            "from": [],
            "where": [],
            "group_by": [],
            "order_by": [],
            "limit": None,
            "joins": []
        }

        sql_normalized = self.normalize_sql(sql)

        # Extract SELECT clause
        select_match = re.search(r'select\s+(.*?)\s+from', sql_normalized, re.IGNORECASE)
        if select_match:
            select_clause = select_match.group(1)
            components["select"] = [col.strip() for col in select_clause.split(',')]

        # Extract FROM clause
        from_match = re.search(r'from\s+([\w\.]+)', sql_normalized, re.IGNORECASE)
        if from_match:
            components["from"] = [from_match.group(1)]

        # Extract WHERE clause
        where_match = re.search(r'where\s+(.*?)(?:\s+group\s+by|\s+order\s+by|\s+limit|$)', sql_normalized, re.IGNORECASE)
        if where_match:
            components["where"] = [where_match.group(1).strip()]

        # Extract GROUP BY
        group_match = re.search(r'group\s+by\s+(.*?)(?:\s+having|\s+order\s+by|\s+limit|$)', sql_normalized, re.IGNORECASE)
        if group_match:
            components["group_by"] = [col.strip() for col in group_match.group(1).split(',')]

        # Extract ORDER BY
        order_match = re.search(r'order\s+by\s+(.*?)(?:\s+limit|$)', sql_normalized, re.IGNORECASE)
        if order_match:
            components["order_by"] = [col.strip() for col in order_match.group(1).split(',')]

        # Extract LIMIT
        limit_match = re.search(r'limit\s+(\d+)', sql_normalized, re.IGNORECASE)
        if limit_match:
            components["limit"] = limit_match.group(1)

        # Extract JOINs
        join_matches = re.findall(r'(inner|left|right|full)?\s*join\s+([\w\.]+)', sql_normalized, re.IGNORECASE)
        if join_matches:
            components["joins"] = [match[1] for match in join_matches]

        return components

    def calculate_similarity(self, sql1: str, sql2: str) -> float:
        """Calculate schema-aware semantic similarity between two SQL queries."""
        norm1 = self.normalize_sql(sql1)
        norm2 = self.normalize_sql(sql2)

        # Exact match after normalization
        if norm1 == norm2:
            return 1.0

        # Extract components
        comp1 = self.extract_components(sql1)
        comp2 = self.extract_components(sql2)

        # Normalize components using schema context before comparison
        comp1_select = self._normalize_component_list(comp1["select"])
        comp2_select = self._normalize_component_list(comp2["select"])

        comp1_from = self._normalize_component_list(comp1["from"])
        comp2_from = self._normalize_component_list(comp2["from"])

        comp1_group = self._normalize_component_list(comp1["group_by"])
        comp2_group = self._normalize_component_list(comp2["group_by"])

        comp1_order = self._normalize_component_list(comp1["order_by"])
        comp2_order = self._normalize_component_list(comp2["order_by"])

        comp1_joins = self._normalize_component_list(comp1["joins"])
        comp2_joins = self._normalize_component_list(comp2["joins"])

        # Calculate component-wise similarity with weights
        scores = []

        select_score = self._list_similarity(comp1_select, comp2_select)
        scores.append(("select", select_score, 0.4))

        from_score = self._list_similarity(comp1_from, comp2_from)
        scores.append(("from", from_score, 0.15))

        # WHERE uses raw comparison (conditions are complex, alias stripping may break logic)
        where_score = self._list_similarity(comp1["where"], comp2["where"])
        scores.append(("where", where_score, 0.2))

        group_score = self._list_similarity(comp1_group, comp2_group)
        scores.append(("group_by", group_score, 0.1))

        order_score = self._list_similarity(comp1_order, comp2_order)
        scores.append(("order_by", order_score, 0.1))

        join_score = self._list_similarity(comp1_joins, comp2_joins)
        scores.append(("joins", join_score, 0.05))

        total_score = sum(score * weight for _, score, weight in scores)

        logger.debug(f"SemanticChecker: {', '.join(f'{name}={score:.2f}' for name, score, _ in scores)} → total={total_score:.3f}")

        return total_score

    def _list_similarity(self, list1: list, list2: list) -> float:
        """Calculate similarity between two lists using Overlap Coefficient."""
        if not list1 and not list2:
            return 1.0

        if not list1 or not list2:
            return 0.0

        set1 = set(item.strip().lower() for item in list1)
        set2 = set(item.strip().lower() for item in list2)

        intersection = len(set1 & set2)
        min_len = min(len(set1), len(set2))
        if min_len == 0:
            return 0.0

        return intersection / min_len

    def check_semantic_equivalence(self, generated_sql: str, ground_truth_sql: str) -> dict:
        """Check semantic equivalence between generated and ground truth SQL."""
        similarity_score = self.calculate_similarity(generated_sql, ground_truth_sql)

        result = {
            "similarity_score": similarity_score,
            "is_equivalent": similarity_score >= 0.6,
            "generated_normalized": self.normalize_sql(generated_sql),
            "ground_truth_normalized": self.normalize_sql(ground_truth_sql),
            "components_match": similarity_score >= 0.7
        }

        return result
