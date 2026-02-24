"""
Test ground truth generation with 500 queries
"""
import sys
sys.path.insert(0, '/home/lenovo/New_tech_demo')

from agent_platform.ground_truth_generator import GroundTruthGenerator
from agent_platform.schema_discovery import SchemaDiscovery
from agent_platform.agent_manager import AgentManager
from loguru import logger
import os
import json

def test_500_queries():
    """Test generating 500 queries for marketing agent"""
    print(f"\n{'='*60}")
    print(f"Testing 500 Query Generation")
    print(f"{'='*60}\n")
    
    agent_id = 39
    mgr = AgentManager()
    agent = mgr.get_agent(agent_id)
    
    if not agent:
        print("Agent not found")
        return
    
    print(f"Agent: {agent['agent_name']}")
    print("This will take 1-2 minutes...\n")
    
    try:
        # Get schemas
        schemas = SchemaDiscovery.discover_schemas(agent['db_url'])
        
        # Generate ground truth
        generator = GroundTruthGenerator()
        generator.generate_for_agent(
            agent_id=agent_id,
            agent_name=agent['agent_name'],
            db_url=agent['db_url'],
            schemas=schemas
        )
        
        # Check result
        filepath = f"data/ground_truth/{agent['agent_name'].lower().replace(' ', '_')}_queries.json"
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            print(f"\n{'='*60}")
            print(f"✅ SUCCESS! Generated {data['total_queries']} queries")
            print(f"{'='*60}\n")
            print(f"Saved to: {filepath}")
            
            # Show query distribution
            query_types = {}
            for q in data['queries']:
                sql_lower = q['sql'].lower()
                if 'join' in sql_lower:
                    qtype = 'JOIN'
                elif any(agg in sql_lower for agg in ['count', 'sum', 'avg', 'max', 'min', 'group by']):
                    qtype = 'Aggregation'
                elif any(dt in sql_lower for dt in ['date', 'interval', 'now()', 'date_trunc']):
                    qtype = 'Date/Time'
                else:
                    qtype = 'Simple SELECT'
                
                query_types[qtype] = query_types.get(qtype, 0) + 1
            
            print("\nQuery Type Distribution:")
            for qtype, count in sorted(query_types.items()):
                print(f"  - {qtype}: {count} queries")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception(e)

if __name__ == "__main__":
    test_500_queries()
