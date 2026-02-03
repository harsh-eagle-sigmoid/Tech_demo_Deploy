"""
Demand Agent - Text-to-SQL for Supply Chain/Demand Analysis
"""
from agents.base_agent import BaseAgent
from loguru import logger


class DemandAgent(BaseAgent):
    """Agent for handling demand/supply chain queries"""

    def __init__(self):
        """Initialize Demand Agent"""
        super().__init__(schema_name="demand_data", agent_type="demand")

        # Add demand-specific context
        self.examples = [
            {
                "query": "Which products have low stock?",
                "sql": "SELECT sku, product_type, stock_levels FROM demand_data.products WHERE stock_levels < 20 ORDER BY stock_levels ASC"
            },
            {
                "query": "Show me suppliers with shortest lead time",
                "sql": """SELECT supplier_name, location, AVG(lead_time) as avg_lead_time
                         FROM demand_data.suppliers
                         GROUP BY supplier_name, location
                         ORDER BY avg_lead_time ASC
                         LIMIT 5"""
            },
            {
                "query": "What is total revenue generated?",
                "sql": "SELECT SUM(revenue_generated) as total_revenue FROM demand_data.sales"
            }
        ]

        logger.info("Demand Agent initialized with example queries")

    def generate_sql(self, user_query: str):
        """Override to add demand-specific examples"""
        try:
            # Build enhanced prompt with examples
            examples_text = "\n\n".join([
                f"Example {i+1}:\nQuestion: {ex['query']}\nSQL: {ex['sql']}"
                for i, ex in enumerate(self.examples[:3])
            ])

            system_prompt = f"""You are an expert SQL query generator for supply chain and demand forecasting analysis.

Database Schema:
{self.schema_info}

Key Tables:
- products: Product inventory with SKU, stock_levels, availability, price
- sales: Sales data with products_sold, revenue_generated, order_quantities
- suppliers: Supplier information with lead_time, location, shipping details
- supply_chain: Supply chain metrics with manufacturing costs, defect rates, lead times

Few-Shot Examples:
{examples_text}

Instructions:
1. Generate a valid PostgreSQL SQL query based on the user's question
2. Use proper table references with schema name (e.g., demand_data.products)
3. For inventory queries, focus on stock_levels and availability
4. For demand queries, use products_sold or order_quantities
5. For supplier analysis, JOIN with suppliers table
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
    logger.add("logs/demand_agent_test.log")

    print("🤖 Testing Demand Agent...\n")

    agent = DemandAgent()

    # Test queries
    test_queries = [
        "Which products have low stock?",
        "Show me top 5 products by revenue",
        "Which supplier has shortest lead time?",
        "What is the average defect rate?"
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
