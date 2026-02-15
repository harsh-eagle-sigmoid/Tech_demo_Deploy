
from typing import Dict, Any
from loguru import logger
from evaluation.validators import StructuralValidator

class StructuralLayer:
    """
    Layer 1: Structural Validation (Weight: 35%)
    Wraps StructuralValidator to check syntax and schema compliance.
    """
    def __init__(self, schema_name: str):
        self.validator = StructuralValidator(schema_name)
        logger.info(f"Initialized StructuralLayer for schema: {schema_name}")

    def evaluate(self, sql: str) -> float:
        """
        Validates SQL syntax and schema existence.
        Returns 1.0 if valid, 0.0 if invalid.
        """
        try:
            result = self.validator.validate(sql)
            # StructuralValidator returns a dict with 'score' (0.0 or 1.0)
            score = result.get("score", 0.0)
            if score < 1.0:
                logger.debug(f"Structural Validation Failed: {result.get('errors', [])}")
            return score
        except Exception as e:
            logger.error(f"Error in StructuralLayer: {e}")
            return 0.0
