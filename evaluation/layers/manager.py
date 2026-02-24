
from typing import Dict, Optional, Any
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
    
    def __init__(self, schema_name: str = None, agent_type: str = "spend",
                 schema_info: dict = None, db_url: str = None):
        """Initialize all 4 evaluation layers with their weights."""
        from evaluation.validators import StructuralValidator
        if schema_info is not None:
            # Dynamic agent: use pre-loaded schema info
            validator = StructuralValidator(schema_info=schema_info, db_url=db_url)
            self.structural_layer = StructuralLayer(validator=validator)
        else:
            self.structural_layer = StructuralLayer(schema_name)
        # Pass schema_info from StructuralLayer so IntentLayer can detect dimension/measure columns
        self.intent_layer = IntentLayer(schema_info=self.structural_layer.validator.schema_info)
        self.pattern_layer = PatternLayer()
        self.agent_type = agent_type

        # Drift layer uses Bedrock Titan embeddings to compare against baseline
        self.drift_detector = DriftDetector()
        self.drift_layer = DriftLayer(self.drift_detector)

        # Layer weights must sum to 1.0 (drift disabled from scoring)
        self.weights = {
            "structural": 0.45,
            "intent": 0.30,
            "pattern": 0.25
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
        
        # 4. Drift Layer (monitoring only — not included in scoring)
        drift_quality_score = self.drift_layer.evaluate(
            query_id=query_id,
            query_text=query_text,
            sql=sql,
            agent_type=self.agent_type,
            existing_drift_score=existing_drift_score
        )

        # Calculate final weighted score from 3 layers (drift excluded)
        final_score = (
            (structural_score * self.weights["structural"]) +
            (intent_score * self.weights["intent"]) +
            (pattern_score * self.weights["pattern"])
        )

        # Drift Veto: if drift quality is extremely low (junk/irrelevant query), force FAIL
        if drift_quality_score < 0.1:
            logger.warning(f"Drift Veto: quality {drift_quality_score:.2f} — query is irrelevant/junk")
            final_score = 0.0
            confidence = 0.0
            status = "FAIL"
        else:
            status = "PASS" if final_score >= self.threshold else "FAIL"
            confidence = final_score
        
        logger.info(f"Heuristic Evaluation Complete. Status: {status}, Score: {final_score:.2f}, Confidence: {confidence:.2f}")
        
        return {
            "final_score": final_score,
            "final_result": status,
            "confidence": confidence,
            "components": {
                "structural": structural_score,
                "intent": intent_score,
                "pattern": pattern_score,
                "drift": drift_quality_score
            }
        }
