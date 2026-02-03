"""
Spend Agent - Text-to-SQL for Procurement/Spend Analysis
"""
from agents.base_agent import BaseAgent
from loguru import logger


class SpendAgent(BaseAgent):
    """Agent for handling spend/procurement queries"""

    def __init__(self):
        """Initialize Spend Agent"""
        super().__init__(schema_name="spend_data", agent_type="spend")

        # Add spend-specific context
        self.examples = [
            {
                "query": "What was total sales in 2014?",
                "sql": "SELECT SUM(sales) as total_sales FROM spend_data.orders WHERE year = 2014"
            },
            {
                "query": "Show me top 5 products by profit",
                "sql": """SELECT p.product_name, SUM(o.profit) as total_profit
                         FROM spend_data.orders o
                         JOIN spend_data.products p ON o.product_id = p.product_id
                         GROUP BY p.product_name
                         ORDER BY total_profit DESC
                         LIMIT 5"""
            },
            {
                "query": "Which customers have highest spend?",
                "sql": """SELECT c.customer_name, SUM(o.sales) as total_spend
                         FROM spend_data.orders o
                         JOIN spend_data.customers c ON o.customer_id = c.customer_id
                         GROUP BY c.customer_name
                         ORDER BY total_spend DESC
                         LIMIT 10"""
            }
        ]

        logger.info("Spend Agent initialized with example queries")

    def generate_sql(self, user_query: str):
        """Override to add spend-specific examples"""
        try:
            # Build enhanced prompt with examples
            examples_text = "\n\n".join([
                f"Example {i+1}:\nQuestion: {ex['query']}\nSQL: {ex['sql']}"
                for i, ex in enumerate(self.examples[:3])
            ])

            system_prompt = f"""You are an expert SQL query generator for procurement and spend analysis.

Database Schema:
{self.schema_info}

Key Tables:
- orders: Contains order transactions with sales, profit, quantity, discount, shipping_cost
- customers: Customer information with segment, market, region
- products: Product catalog with category and sub_category

Few-Shot Examples:
{examples_text}

Instructions:
1. Generate a valid PostgreSQL SQL query based on the user's question
2. Use proper table references with schema name (e.g., spend_data.orders)
3. For spend/sales analysis, use SUM(sales) or SUM(profit)
4. For customer analysis, JOIN with customers table
5. For product analysis, JOIN with products table
6. Return ONLY the SQL query without markdown formatting
7. Limit results to 100 rows unless specified

Return format:
SQL: <your sql query here>
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]

            response = self.llm.generate(
                messages=messages,
                temperature=0.0,
                max_tokens=1000
            )

            sql = self._extract_sql(response)
            return sql, response

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return "", str(e)


# Test function
if __name__ == "__main__":
    logger.add("logs/spend_agent_test.log")

    print("🤖 Testing Spend Agent...\n")

    agent = SpendAgent()

    # Test queries
    test_queries = [
        "What was total sales in 2014?",
        "Show me top 5 products by profit",
        "Which category has highest sales?",
        "What is the average discount by segment?"
    ]

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print('='*80)

        result = agent.process_query(query)

        if result["status"] == "success":
            print(f"\n✅ SQL Generated:")
            print(result["sql"])

            print(f"\n📊 Results ({len(result['results'])} rows):")
            for i, row in enumerate(result["results"][:5]):  # Show first 5
                print(f"  {i+1}. {row}")

            if len(result["results"]) > 5:
                print(f"  ... and {len(result['results']) - 5} more rows")

        else:
            print(f"\n❌ Error: {result['error']}")
