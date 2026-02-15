import json
import os
from loguru import logger
from monitoring.drift_detector import DriftDetector

def initialize_baseline_if_needed():
   
    try:
        detector = DriftDetector()
        
       
        spend_baseline = detector._get_baseline("spend")
        if not spend_baseline:
            logger.info("📉 No Baseline found for 'spend'. Creating one...")
            _create_baseline_from_file("spend", detector)
        else:
            logger.info("✅ Baseline exists for 'spend'. Skipping creation.")

        
        demand_baseline = detector._get_baseline("demand")
        if not demand_baseline:
            logger.info("📉 No Baseline found for 'demand'. Creating one...")
            _create_baseline_from_file("demand", detector)
        else:
            logger.info("✅ Baseline exists for 'demand'. Skipping creation.")
            
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
