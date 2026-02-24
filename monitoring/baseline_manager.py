import json
import os
from loguru import logger
from monitoring.drift_detector import DriftDetector


def _get_agent_types() -> list:
    """Return list of agent names from platform.agents, fallback to legacy list."""
    try:
        from agent_platform.agent_manager import AgentManager
        mgr = AgentManager()
        registered = [a["agent_name"] for a in mgr.get_all_agents()]
        if registered:
            return registered
    except Exception as e:
        logger.warning(f"Could not load agents from platform: {e}")
    return ["spend", "demand"]


def initialize_baseline_if_needed():

    try:
        detector = DriftDetector()
        agent_types = _get_agent_types()

        for agent_type in agent_types:
            baseline = detector._get_baseline(agent_type)
            if not baseline:
                logger.info(f"📉 No Baseline found for '{agent_type}'. Creating one...")
                _create_baseline_from_file(agent_type, detector)
            else:
                logger.info(f"✅ Baseline exists for '{agent_type}'. Skipping creation.")

    except Exception as e:
        logger.error(f"Failed to initialize baseline: {e}")


def _create_baseline_from_file(agent_type: str, detector: DriftDetector):
    try:
        filepath = "data/ground_truth/all_queries.json"
        if not os.path.exists(filepath):
             logger.warning(f"Baseline file {filepath} not found. Skipping.")
             return

        with open(filepath, "r") as f:
            data = json.load(f)
            
        queries = [q["query_text"] for q in data if q["agent_type"] == agent_type][:50]
        
        if queries:
            detector.create_baseline(agent_type, queries)
            logger.info(f"✅ Baseline created for {agent_type} ({len(queries)} queries)")
        else:
            logger.warning(f"No queries found for {agent_type} in {filepath}")

    except Exception as e:
        logger.error(f"Error creating baseline for {agent_type}: {e}")
