"""
Ground Truth Query Generator - 1000 Queries (Testing Version)
Generates 1,000 query-SQL pairs for initial testing
"""
import json
import random
from typing import List, Dict
from loguru import logger
from agents.spend_agent import SpendAgent
from agents.demand_agent import DemandAgent


class GroundTruthGenerator1000:
    """Generate 1000 ground truth query-SQL pairs for testing"""

    def __init__(self):
        """Initialize generator"""
        self.spend_agent = SpendAgent()
        self.demand_agent = DemandAgent()

        # Query templates by complexity
        self.spend_templates = {
            "simple": [
                "What was total sales in {year}?",
                "How many orders were placed in {year}?",
                "What is the average discount?",
                "Show me all orders from {market} market",
                "What products are in the {category} category?",
                "List all customers from {region} region",
                "What was total profit in {year}?",
                "How many products are in {category}?",
                "What is total shipping cost for {year}?",
                "Show me orders with high priority",
                "What is the average order value?",
                "List all {segment} segment customers",
                "What was total quantity sold in {year}?",
                "Show me all {ship_mode} shipments",
                "What categories do we have?",
            ],
            "medium": [
                "What are the top 5 products by sales?",
                "Which customers spent the most?",
                "What is the average sales by category?",
                "Show me monthly sales trend for {year}",
                "Which region has highest profit?",
                "What is total sales by segment?",
                "Which products have highest profit margin?",
                "What is average discount by category?",
                "Show me top 10 customers by profit",
                "What is sales by market and region?",
                "Which category has most orders?",
                "What is average shipping cost by ship mode?",
                "Show me products with negative profit",
                "What is sales distribution by segment?",
                "Which sub-category has highest sales?",
            ],
            "complex": [
                "Which customers in {market} market had highest spend in {year} with orders above ${amount}?",
                "Show me year-over-year sales growth by category",
                "What is the profit margin by product category for {segment} segment?",
                "Which products have declining sales over time?",
                "What is customer lifetime value by segment?",
                "Show me products with high sales but low profit",
                "Which regions have highest sales per customer?",
                "What is the correlation between discount and profit?",
                "Show me top products by profit margin in each category",
                "What is quarterly sales trend by market?",
                "Which customers have highest order frequency?",
                "What is average order value by customer segment and region?",
                "Show me products that are frequently ordered together",
                "What is the shipping cost as percentage of sales by region?",
                "Which market-category combinations are most profitable?",
            ]
        }

        self.demand_templates = {
            "simple": [
                "Which products have stock below {threshold}?",
                "What is total revenue generated?",
                "How many products are out of stock?",
                "List all {product_type} products",
                "What is average price of products?",
                "Show me products with availability above {percent}%",
                "What is total products sold?",
                "Which supplier is located in {location}?",
                "What is average lead time?",
                "Show me all products with high defect rates",
                "What is total manufacturing cost?",
                "List suppliers by location",
                "What is average shipping cost?",
                "Show me products with price above ${amount}",
                "What is total order quantities?",
            ],
            "medium": [
                "Which products have highest revenue?",
                "What is average stock level by product type?",
                "Which supplier has shortest lead time?",
                "Show me products with low stock and high demand",
                "What is total revenue by product type?",
                "Which products have highest defect rate?",
                "What is average manufacturing cost by supplier?",
                "Show me suppliers ranked by lead time",
                "What is total shipping cost by carrier?",
                "Which products need reordering?",
                "What is stock turnover ratio?",
                "Show me top 10 products by units sold",
                "What is average defect rate by supplier?",
                "Which transportation mode is most cost effective?",
                "What is production volume by supplier?",
            ],
            "complex": [
                "Which products have high demand but low stock from {supplier}?",
                "What is cost breakdown analysis by product?",
                "Show me supplier performance score based on lead time and defect rate",
                "Which products have best revenue per stock unit?",
                "What is optimal reorder quantity for each product?",
                "Show me correlation between manufacturing cost and defect rate",
                "Which supplier-product combinations are most efficient?",
                "What is inventory carrying cost by product type?",
                "Show me products with highest profit margin",
                "What is demand forecast based on historical sales?",
                "Which products have seasonal demand patterns?",
                "What is total cost of ownership by supplier?",
                "Show me products that exceed quality thresholds",
                "What is the relationship between lead time and stock levels?",
                "Which routes have lowest shipping cost per unit?",
            ]
        }

        # Value options for template filling
        self.values = {
            "year": ["2011", "2012", "2013", "2014"],
            "market": ["Africa", "APAC", "Europe", "LATAM", "US"],
            "category": ["Technology", "Furniture", "Office Supplies"],
            "region": ["Central", "East", "South", "West"],
            "segment": ["Consumer", "Corporate", "Home Office"],
            "ship_mode": ["Standard Class", "Second Class", "First Class", "Same Day"],
            "amount": ["100", "500", "1000", "5000"],
            "threshold": ["10", "20", "30", "50"],
            "percent": ["50", "75", "90"],
            "product_type": ["skincare", "haircare", "cosmetics"],
            "location": ["Mumbai", "Delhi", "Bangalore", "Kolkata", "Chennai"],
            "supplier": ["Supplier 1", "Supplier 2", "Supplier 3", "Supplier 4", "Supplier 5"]
        }

    def fill_template(self, template: str) -> str:
        """Fill template with random values"""
        filled = template
        for key, options in self.values.items():
            placeholder = "{" + key + "}"
            if placeholder in filled:
                filled = filled.replace(placeholder, random.choice(options))
        return filled

    def generate_queries(self, agent_type: str, count: int) -> List[Dict]:
        """
        Generate ground truth queries

        Args:
            agent_type: 'spend' or 'demand'
            count: Number of queries to generate

        Returns:
            List of dicts with query, sql, complexity
        """
        logger.info(f"Generating {count} queries for {agent_type} agent...")

        templates = self.spend_templates if agent_type == "spend" else self.demand_templates
        agent = self.spend_agent if agent_type == "spend" else self.demand_agent

        # Distribution: 40% simple, 40% medium, 20% complex
        simple_count = int(count * 0.4)
        medium_count = int(count * 0.4)
        complex_count = count - simple_count - medium_count

        queries = []
        query_id = 1

        # Generate simple queries
        logger.info(f"Generating {simple_count} simple queries...")
        for i in range(simple_count):
            template = random.choice(templates["simple"])
            query_text = self.fill_template(template)

            # Generate SQL using agent
            result = agent.process_query(query_text)

            if result["status"] == "success":
                queries.append({
                    "query_id": f"{agent_type.upper()}-{query_id:04d}",
                    "query_text": query_text,
                    "sql": result["sql"],
                    "complexity": "simple",
                    "agent_type": agent_type
                })
                query_id += 1

                if query_id % 50 == 0:
                    logger.info(f"Generated {query_id} queries...")

        # Generate medium queries
        logger.info(f"Generating {medium_count} medium queries...")
        for i in range(medium_count):
            template = random.choice(templates["medium"])
            query_text = self.fill_template(template)

            result = agent.process_query(query_text)

            if result["status"] == "success":
                queries.append({
                    "query_id": f"{agent_type.upper()}-{query_id:04d}",
                    "query_text": query_text,
                    "sql": result["sql"],
                    "complexity": "medium",
                    "agent_type": agent_type
                })
                query_id += 1

                if query_id % 50 == 0:
                    logger.info(f"Generated {query_id} queries...")

        # Generate complex queries
        logger.info(f"Generating {complex_count} complex queries...")
        for i in range(complex_count):
            template = random.choice(templates["complex"])
            query_text = self.fill_template(template)

            result = agent.process_query(query_text)

            if result["status"] == "success":
                queries.append({
                    "query_id": f"{agent_type.upper()}-{query_id:04d}",
                    "query_text": query_text,
                    "sql": result["sql"],
                    "complexity": "complex",
                    "agent_type": agent_type
                })
                query_id += 1

                if query_id % 50 == 0:
                    logger.info(f"Generated {query_id} queries...")

        logger.info(f"✅ Generated {len(queries)} valid queries for {agent_type} agent")
        return queries

    def save_ground_truth(self, queries: List[Dict], filename: str):
        """Save ground truth to JSON file"""
        with open(filename, 'w') as f:
            json.dump(queries, f, indent=2)
        logger.info(f"Saved {len(queries)} queries to {filename}")

    def split_dataset(self, queries: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Split into train/test/validation sets

        60% training, 30% testing, 10% validation
        """
        random.shuffle(queries)

        total = len(queries)
        train_size = int(total * 0.6)
        test_size = int(total * 0.3)

        return {
            "train": queries[:train_size],
            "test": queries[train_size:train_size + test_size],
            "validation": queries[train_size + test_size:]
        }


if __name__ == "__main__":
    logger.add("logs/ground_truth_generation_1000.log", rotation="10 MB")

    print("🤖 Ground Truth Generator - 1000 Queries (Testing Version)")
    print("=" * 80)
    print("\nGenerating 1,000 query-SQL pairs for testing...")
    print("\nTarget Distribution:")
    print("  - Spend Agent: 600 queries (60%)")
    print("  - Demand Agent: 400 queries (40%)")
    print("\nComplexity Distribution:")
    print("  - Simple: 40% (single table, basic filters)")
    print("  - Medium: 40% (joins, aggregations)")
    print("  - Complex: 20% (multiple joins, subqueries)")
    print("\n" + "=" * 80 + "\n")

    generator = GroundTruthGenerator1000()

    # Generate Spend Agent queries
    print("\n📊 SPEND AGENT (Procurement/Spend Analysis)\n")
    spend_queries = generator.generate_queries("spend", 600)

    # Generate Demand Agent queries
    print("\n📦 DEMAND AGENT (Supply Chain/Demand Forecasting)\n")
    demand_queries = generator.generate_queries("demand", 400)

    # Combine all queries
    all_queries = spend_queries + demand_queries

    print(f"\n✅ Total queries generated: {len(all_queries)}")

    # Split into datasets
    print("\n📂 Splitting into train/test/validation sets...")
    datasets = generator.split_dataset(all_queries)

    print(f"  - Training: {len(datasets['train'])} queries (60%)")
    print(f"  - Testing: {len(datasets['test'])} queries (30%)")
    print(f"  - Validation: {len(datasets['validation'])} queries (10%)")

    # Save to files
    print("\n💾 Saving ground truth files...")
    generator.save_ground_truth(datasets['train'], 'data/ground_truth/train.json')
    generator.save_ground_truth(datasets['test'], 'data/ground_truth/test.json')
    generator.save_ground_truth(datasets['validation'], 'data/ground_truth/validation.json')
    generator.save_ground_truth(all_queries, 'data/ground_truth/all_queries.json')

    print("\n✅ Ground truth generation complete!")
    print(f"\nFiles saved to:")
    print(f"  - data/ground_truth/train.json")
    print(f"  - data/ground_truth/test.json")
    print(f"  - data/ground_truth/validation.json")
    print(f"  - data/ground_truth/all_queries.json")
