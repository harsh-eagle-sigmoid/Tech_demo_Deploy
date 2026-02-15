
from typing import Dict, Tuple, Optional, Any
from loguru import logger
from monitoring.drift_detector import DriftDetector
from evaluation.layers.structural import StructuralLayer
from evaluation.layers.intent import IntentLayer
from evaluation.layers.pattern import PatternLayer
from evaluation.layers.drift import DriftLayer

from config.settings import settings

class EvaluationManager:
    """
    Manager for the 4-Layer Heuristic Evaluation System.
    Orchestrates the execution of each layer and computes the final weighted score.
    """
    
    def __init__(self, schema_name: str, agent_type: str = "spend"):
        self.structural_layer = StructuralLayer(schema_name)
        self.intent_layer = IntentLayer()
        self.pattern_layer = PatternLayer()
        self.agent_type = agent_type
        
        # Instantiate Drift Detector and Layer
        # Note: DriftDetector handles DB connection internally
        self.drift_detector = DriftDetector()
        self.drift_layer = DriftLayer(self.drift_detector)
        
        # Weights definition (Total 1.0)
        self.weights = {
            "structural": 0.35,
            "intent": 0.25,
            "pattern": 0.20,
            "drift": 0.20
        }
        
        # Threshold for PASS/FAIL
        self.threshold = settings.EVALUATION_THRESHOLD

    def evaluate_heuristic(
        self, 
        query_text: str, 
        sql: str, 
        query_id: str = "unknown",
        existing_drift_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs the full 4-layer evaluation pipeline.
        Returns a dictionary with scores, final result, and confidence.
        """
        logger.info(f"Starting Heuristic Evaluation for query: {query_text[:50]}...")
        
        # 1. Structural Layer (35%)
        structural_score = self.structural_layer.evaluate(sql)
        
        # 2. Intent Layer (25%)
        intent_score = self.intent_layer.evaluate(query_text, sql)
        
        # 3. Pattern Layer (20%)
        pattern_score = self.pattern_layer.evaluate(sql)
        
        # 4. Drift Layer (20%)
        # Supports reuse of existing score
        drift_quality_score = self.drift_layer.evaluate(
            query_id=query_id,
            query_text=query_text, 
            sql=sql, 
            agent_type=self.agent_type,
            existing_drift_score=existing_drift_score
        )
        
        # Calculate Final Weighted Score
        # Calculate Final Weighted Score
        final_score = (
            (structural_score * self.weights["structural"]) +
            (intent_score * self.weights["intent"]) +
            (pattern_score * self.weights["pattern"]) +
            (drift_quality_score * self.weights["drift"])
        )
        
        # Drift Veto:
        # If Drift Quality is very low (High Drift), we generally shouldn't Pass.
        # If drift_quality < 0.1 (Severe Drift), force FAIL and Governance = 0.0
        # Lowered from previous 0.3 to allow distinct valid queries like "what is average"
        if drift_quality_score < 0.1:
            logger.warning(f"Drift Veto Triggered: Quality {drift_quality_score:.2f} is too low.")
            final_score = 0.0  # Force Absolute Fail
            confidence = 0.0   # Force Zero Confidence (Irrelevant)
            status = "FAIL"
        else:
            # Determine Status
            status = "PASS" if final_score >= self.threshold else "FAIL"
            
            # Calculate Confidence based on Score & Drift
            # DISABLED DRIFT PENALTY FOR TESTING per user request
            confidence = final_score
            # confidence = final_score * drift_quality_score
        
        logger.info(f"Heuristic Evaluation Complete. Status: {status}, Score: {final_score:.2f}, Confidence: {confidence:.2f}")
        
        return {
            "final_score": final_score,
            "final_result": status,
            "confidence": confidence,
            "components": {
                "structural": structural_score,
                "intent": intent_score,
                "pattern": pattern_score,
                "drift_quality": drift_quality_score
            }
        }
