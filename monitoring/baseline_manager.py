from loguru import logger
from monitoring.drift_detector import DriftDetector


def _get_agent_types() -> list:
    """Return list of agent names from platform.agents, fallback to legacy list."""
    try:
        from agent_platform.agent_manager import AgentManager
        mgr = AgentManager()
        registered = [a["agent_name"] for a in mgr.get_all_agents()]
        if registered:
            logger.info(f"baseline_manager: found {len(registered)} registered agents: {registered}")
            return registered
        logger.warning("baseline_manager: platform.agents is empty, falling back to legacy list")
    except Exception as e:
        logger.warning(f"baseline_manager: could not load agents from platform ({e}), falling back to legacy list")
    return ["spend", "demand"]


def initialize_baseline_if_needed():

    try:
        detector = DriftDetector()
        agent_types = _get_agent_types()

        for agent_type in agent_types:
            baseline = detector._get_baseline(agent_type)
            needs_create = False

            if not baseline:
                logger.info(f"📉 No baseline found for '{agent_type}'. Creating one...")
                needs_create = True
            else:
                import numpy as np
                norm = np.linalg.norm(baseline)
                if norm < 0.01:
                    logger.warning(f"⚠️  Baseline for '{agent_type}' is a zero vector (corrupted). Recreating...")
                    needs_create = True
                else:
                    logger.info(f"✅ Baseline exists and is valid for '{agent_type}' (norm={norm:.3f}). Skipping creation.")

            if needs_create:
                _create_baseline_from_file(agent_type, detector)

    except Exception as e:
        logger.error(f"Failed to initialize baseline: {e}")


def _create_baseline_from_file(agent_type: str, detector: DriftDetector):
    try:
        from agent_platform.gt_storage import get_gt_storage
        storage = get_gt_storage()
        queries = []

        # 1. Try agent-specific GT file first: e.g. marketing_agent_queries.json
        normalized = agent_type.lower().replace(' ', '_').replace('_agent', '')
        data = storage.load(f"{normalized}_agent_queries.json")
        if data is not None:
            raw = data.get("queries", [])
            queries = [
                q.get("natural_language") or q.get("query_text", "")
                for q in raw
                if q.get("natural_language") or q.get("query_text")
            ][:50]
            if queries:
                logger.info(f"Using agent-specific GT for baseline: {normalized}_agent_queries.json")

        # 2. Fallback: all_queries.json filtered by agent_type
        if not queries:
            all_data = storage.load("all_queries.json")
            if all_data:
                queries = [
                    q["query_text"] for q in all_data
                    if q.get("agent_type", "").lower() == agent_type.lower()
                ][:50]

        if queries:
            detector.create_baseline(agent_type, queries)
            logger.info(f"✅ Baseline created for '{agent_type}' ({len(queries)} queries)")
        else:
            logger.warning(f"No queries found for '{agent_type}' — baseline skipped")

    except Exception as e:
        logger.error(f"Error creating baseline for {agent_type}: {e}")
