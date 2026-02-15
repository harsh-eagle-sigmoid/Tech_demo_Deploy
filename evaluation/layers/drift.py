
from typing import Dict, Any, Optional
from loguru import logger
from monitoring.drift_detector import DriftDetector

class DriftLayer:
    """
    Layer 4: Drift Analysis (Weight: 20%)
    Checks for semantic drift by comparing the query embedding to the baseline centroid.
    Supports a Hybrid Approach:
    - Reuse existing drift score (if provided)
    - Calculate drift score on-demand (if missing)
    """
    
    def __init__(self, drift_detector: DriftDetector):
        self.detector = drift_detector

    def evaluate(self, query_id: str, query_text: str, sql: str, agent_type: str, existing_drift_score: Optional[float] = None) -> float:
        """
        Calculates the Drift Quality Score (1.0 - Drift Score).
        If existing_drift_score is provided, it reuses it.
        Otherwise, it calculates it using the DriftDetector.
        """
        drift_score = 0.0
        
        if existing_drift_score is not None:
            # Scenario A: Reuse existing calculation (e.g., from API middleware)
            drift_score = existing_drift_score
            logger.debug(f"DriftLayer: Reusing existing drift score: {drift_score}")
        else:
            # Scenario B: Calculate on-demand (e.g., offline batch)
            try:
                # detect() returns {"drift_score": float, "is_drift": bool, ...}
                result = self.detector.detect(query_id=query_id, query_text=query_text, agent_type=agent_type)
                drift_score = result.get("drift_score", 0.0)
                logger.debug(f"DriftLayer: Calculated new drift score: {drift_score}")
            except Exception as e:
                logger.error(f"Error calculating drift in DriftLayer: {e}")
                # If error, assume High Drift (Safe Fallback) or Low Drift?
                # Let's assume Middle Ground or 0.0 (No Drift) to avoid blocking?
                # Actually, 0.0 means Perfect Score (1.0 Quality).
                # Let's return 0.5 penalty if model fails.
                return 0.5

        # Score Logic:
        # Drift Quality = 1.0 - Drift Score
        # (Low Drift = High Quality)
        quality_score = max(0.0, 1.0 - drift_score)
        
        return quality_score
