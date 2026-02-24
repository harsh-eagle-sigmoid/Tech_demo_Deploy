"""
Test ground truth generation
"""
import sys
sys.path.insert(0, '/home/lenovo/New_tech_demo')

from agent_platform.agent_manager import AgentManager
from loguru import logger
import os

def test_ground_truth(agent_id: int):
    """Test ground truth generation for an agent"""
    mgr = AgentManager()

    print(f"\n{'='*60}")
    print(f"Testing Ground Truth Generation for Agent {agent_id}")
    print(f"{'='*60}\n")

    try:
        # Get agent info
        agent = mgr.get_agent(agent_id)
        if not agent:
            print(f"❌ Agent {agent_id} not found")
            return

        print(f"Agent: {agent['agent_name']}")
        print(f"Database URL: {agent['db_url']}\n")

        # Trigger discovery and ground truth generation
        print("Starting discovery and ground truth generation...")
        mgr.discover_and_configure(agent_id)

        # Check if file was created
        agent_name = agent['agent_name'].lower().replace(' ', '_')
        filepath = f"data/ground_truth/{agent_name}_queries.json"

        if os.path.exists(filepath):
            import json
            with open(filepath, 'r') as f:
                data = json.load(f)

            print(f"\n{'='*60}")
            print("✅ Ground Truth Generation Successful!")
            print(f"{'='*60}\n")
            print(f"Generated {data['total_queries']} queries")
            print(f"Saved to: {filepath}\n")

            # Show first 3 queries
            print("Sample queries:")
            for i, query in enumerate(data['queries'][:3], 1):
                print(f"\n{i}. {query['natural_language']}")
                print(f"   SQL: {query['sql'][:100]}...")
        else:
            print(f"\n{'='*60}")
            print("⚠️ Ground Truth file not created")
            print(f"{'='*60}\n")
            print(f"Expected file: {filepath}")

    except Exception as e:
        print(f"\n{'='*60}")
        print("❌ Ground Truth Generation Failed!")
        print(f"{'='*60}\n")
        print(f"Error: {e}")
        logger.exception(e)

if __name__ == "__main__":
    # Test with marketing agent
    test_ground_truth(39)
