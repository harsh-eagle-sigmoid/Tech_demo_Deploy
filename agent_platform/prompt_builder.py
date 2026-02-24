"""
Build prompts for ground truth generation
"""
import json
from loguru import logger


class PromptBuilder:
    """Build comprehensive prompts for LLM"""

    @staticmethod
    def build_ground_truth_prompt(agent_name: str, db_type: str,
                                   schemas: list, relationships: list,
                                   sample_data: dict, num_queries: int = 100) -> str:
        """Build the perfect prompt for ground truth generation"""

        prompt = f"""You are an expert SQL query generator for a {db_type.upper()} database.

# SYSTEM CONTEXT
- Agent Name: {agent_name}
- Database Type: {db_type}
- Task: Generate {num_queries} realistic, executable SQL test queries

{PromptBuilder._get_db_syntax_hints(db_type)}

# DATABASE SCHEMA
{PromptBuilder._format_schema(schemas)}

# TABLE RELATIONSHIPS (Foreign Keys for JOINs)
{PromptBuilder._format_relationships(relationships)}

# SAMPLE DATA (Actual values from the database)
{PromptBuilder._format_sample_data(sample_data)}

# GENERATION REQUIREMENTS

## 1. Query Distribution (Exactly {num_queries} queries):
- {int(num_queries * 0.4)} Simple SELECT queries (single table, basic WHERE filters, various conditions)
- {int(num_queries * 0.3)} Aggregation queries (COUNT, SUM, AVG, MAX, MIN with GROUP BY)
- {int(num_queries * 0.2)} JOIN queries (use the relationships above if available, multi-table queries)
- {int(num_queries * 0.1)} Date/Time or Complex queries (subqueries, window functions, complex filters)

Generate diverse queries covering:
- Different tables and columns
- Various filter conditions and operators (=, !=, >, <, >=, <=, LIKE, IN, BETWEEN)
- Multiple aggregation functions
- Different GROUP BY combinations
- Various JOIN types (INNER, LEFT, RIGHT if applicable)
- Date/time operations and filtering
- String operations (CONCAT, SUBSTRING, UPPER, LOWER, etc.)
- Mathematical operations
- HAVING clauses with aggregations
- DISTINCT and LIMIT variations

## 2. Quality Rules (CRITICAL):
- ✓ Use ONLY table names and column names from the schema above
- ✓ Use ONLY values that exist in the sample data
- ✓ For {db_type}, use correct syntax
- ✓ All JOINs must use the relationships listed above
- ✓ Queries must be executable without errors
- ✓ Natural language should be clear and business-oriented

## 3. Avoid These Mistakes:
- ✗ Don't reference tables/columns that don't exist
- ✗ Don't use values that aren't in the sample data
- ✗ Don't create invalid JOINs between unrelated tables
- ✗ Don't use wrong SQL syntax for {db_type}

# OUTPUT FORMAT (STRICT JSON):
Return ONLY a valid JSON array. No extra text, no markdown, no explanations.

[
  {{
    "natural_language": "natural language question here",
    "sql": "SQL query here"
  }},
  ...{num_queries} queries total...
]

Generate {num_queries} high-quality queries now.
"""
        return prompt

    @staticmethod
    def _format_schema(schemas: list) -> str:
        """Format schema with details"""
        if not schemas:
            return "No schema information available"

        output = []

        for schema in schemas:
            output.append(f"\n## Schema: {schema['schema_name']}")

            for table in schema.get('tables', []):
                output.append(f"\n### Table: {table['table_name']}")
                output.append("Columns:")

                for col in table.get('columns', []):
                    col_name = col.get('name', 'unknown')
                    col_type = col.get('type', 'unknown')
                    output.append(f"  - {col_name}: {col_type}")

        return "\n".join(output)

    @staticmethod
    def _format_relationships(relationships: list) -> str:
        """Format relationships clearly"""
        if not relationships:
            return "No foreign key relationships discovered."

        output = ["Available JOINs:"]

        for rel in relationships:
            source_schema = rel.get('source_schema', '')
            source_table = rel.get('source_table', '')
            source_column = rel.get('source_column', '')
            target_schema = rel.get('target_schema', '')
            target_table = rel.get('target_table', '')
            target_column = rel.get('target_column', '')

            source = f"{source_schema}.{source_table}.{source_column}"
            target = f"{target_schema}.{target_table}.{target_column}"
            output.append(f"  - {source} → {target}")

        return "\n".join(output)

    @staticmethod
    def _format_sample_data(sample_data: dict) -> str:
        """Format sample data with value lists"""
        if not sample_data:
            return "No sample data available"

        output = []

        # Limit to first 10 tables to avoid too long prompts
        tables_to_show = list(sample_data.items())[:10]

        for table_name, rows in tables_to_show:
            output.append(f"\n## Table: {table_name}")

            if not rows:
                output.append("  (No data)")
                continue

            # Show first 3 rows
            output.append(f"Sample rows (showing {min(len(rows), 3)} of {len(rows)}):")
            for i, row in enumerate(rows[:3], 1):
                # Convert to string and limit length
                try:
                    row_str = json.dumps(row, default=str)
                    if len(row_str) > 200:
                        row_str = row_str[:200] + "..."
                    output.append(f"  Row {i}: {row_str}")
                except Exception as e:
                    logger.debug(f"Could not serialize row: {e}")
                    continue

            # Extract unique values for categorical columns
            if rows and len(rows) > 0:
                try:
                    categorical = {}
                    first_row = rows[0]
                    if isinstance(first_row, dict):
                        for key in first_row.keys():
                            unique_vals = []
                            for row in rows:
                                if isinstance(row, dict) and key in row and row[key] is not None:
                                    val_str = str(row[key])
                                    if val_str not in unique_vals:
                                        unique_vals.append(val_str)

                            if 1 < len(unique_vals) <= 10:  # Categorical column
                                categorical[key] = unique_vals

                        if categorical:
                            output.append("\nValid values for filtering:")
                            for col_name, values in categorical.items():
                                value_list = ', '.join(repr(v) for v in values[:5])
                                output.append(f"  - {col_name}: {value_list}")
                except Exception as e:
                    logger.debug(f"Could not extract categorical values: {e}")

        return "\n".join(output)

    @staticmethod
    def _get_db_syntax_hints(db_type: str) -> str:
        """Get database-specific syntax hints"""
        hints = {
            'postgresql': """
# PostgreSQL-Specific Syntax:
- Schema qualification: schema_name.table_name
- Date intervals: INTERVAL '30 days', DATE_TRUNC('month', date_column)
- String comparison: use single quotes 'value'
- Casting: column_name::integer or CAST(column_name AS integer)
""",
            'postgres': """
# PostgreSQL-Specific Syntax:
- Schema qualification: schema_name.table_name
- Date intervals: INTERVAL '30 days', DATE_TRUNC('month', date_column)
- String comparison: use single quotes 'value'
- Casting: column_name::integer or CAST(column_name AS integer)
""",
            'mysql': """
# MySQL-Specific Syntax:
- Table names with backticks: `table_name`
- Date intervals: DATE_SUB(NOW(), INTERVAL 30 DAY)
- String comparison: use single quotes 'value'
- Limit: use LIMIT N
""",
            'mongodb': """
# MongoDB Query Language:
- Use aggregation pipeline syntax
- Match stage: {"$match": {"field": "value"}}
- Group stage: {"$group": {"_id": "$field", "count": {"$sum": 1}}}
- Lookup for joins: {"$lookup": {...}}
""",
            'sqlite': """
# SQLite Syntax:
- Simple SQL syntax
- Date functions: date('now'), datetime('now', '-30 days')
- String comparison: use single quotes 'value'
- Limit: use LIMIT N
"""
        }

        return hints.get(db_type.lower(), "")
