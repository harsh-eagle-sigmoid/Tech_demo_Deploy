
import json
import psycopg2
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
from config.settings import settings
from evaluation.validators import StructuralValidator
from evaluation.semantic_checker import SemanticChecker
from evaluation.llm_judge import LLMJudge
from evaluation.semantic_match import get_semantic_matcher
from evaluation.layers.manager import EvaluationManager

from monitoring.drift_detector import DriftDetector


class Evaluator:
    

    def __init__(self, agent_type: str):
        
        self.agent_type = agent_type
        self.schema_name = "spend_data" if agent_type == "spend" else "demand_data"

        
        self.structural_validator = StructuralValidator(self.schema_name)
        self.semantic_checker = SemanticChecker()
        self.llm_judge = LLMJudge()
        
        # New Heuristic Manager
        self.manager = EvaluationManager(self.schema_name, agent_type=self.agent_type)

        logger.info(f"Initialized Evaluator for {agent_type} agent")

    def _get_db_connection(self):
        
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    def preprocess(self, query_text: str, generated_sql: str) -> Dict:
        
        cleaned_sql = generated_sql.strip()

        
        if "```" in cleaned_sql:
            cleaned_sql = cleaned_sql.split("```")[1] if cleaned_sql.count("```") >= 2 else cleaned_sql
            cleaned_sql = cleaned_sql.replace("sql", "").strip()

        return {
            "query_text": query_text.strip(),
            "cleaned_sql": cleaned_sql,
            "original_sql": generated_sql
        }

    def evaluate(
        self,
        query_id: str,
        query_text: str,
        generated_sql: str,
        ground_truth_sql: Optional[str] = None,
        complexity: str = "unknown"
    ) -> Dict:
        
        logger.info(f"Evaluating query {query_id}: {query_text[:50]}...")

        
        if not ground_truth_sql:
            matcher = get_semantic_matcher()
            if not matcher.is_ready:
                
                matcher.load_from_file("data/ground_truth/all_queries.json")
            
            match = matcher.find_match(query_text, threshold=0.85)
            if match:
                ground_truth_sql = match["sql"]
                complexity = match["complexity"]
                logger.info(f"Evaluator found GT: {ground_truth_sql[:30]}...")
            else:
                logger.warning(f"Evaluator could not find Ground Truth for: {query_text}")
                ground_truth_sql = None

        result = {
            "query_id": query_id,
            "query_text": query_text,
            "generated_sql": generated_sql,
            "ground_truth_sql": ground_truth_sql,
            "complexity": complexity,
            "agent_type": self.agent_type,
            "timestamp": datetime.now().isoformat(),
            "steps": {},
            "scores": {},
            "final_result": "FAIL",
            "final_score": 0.0,
            "confidence": 0.0
        }

        
        try:
            
            preprocessed = self.preprocess(query_text, generated_sql)
            result["steps"]["preprocessing"] = preprocessed
            cleaned_sql = preprocessed["cleaned_sql"]

            
            logger.debug(f"Step 2: Structural validation for {query_id}")
            structural_result = self.structural_validator.validate(cleaned_sql)
            result["steps"]["structural_validation"] = structural_result
            result["scores"]["structural"] = structural_result["score"]

            
            if structural_result["score"] == 0.0:
                result["final_result"] = "FAIL"
                result["final_score"] = 0.0
                result["confidence"] = 1.0
                logger.warning(f"Query {query_id} failed structural validation")
                return result

            
            if not ground_truth_sql:
                 logger.info(f"Query {query_id}: No Ground Truth. Switching to Heuristic Evaluation.")
                 
                 # Run Heuristic Evaluation
                 heuristic_res = self.manager.evaluate_heuristic(
                     query_text, 
                     cleaned_sql,
                     query_id=query_id
                 )
                 
                 # Update Result
                 result["final_result"] = heuristic_res["final_result"]
                 result["final_score"] = heuristic_res["final_score"]
                 result["confidence"] = heuristic_res["confidence"]
                 result["scores"] = heuristic_res["components"]
                 result["reasoning"] = "Reference-Free Heuristic Evaluation"
                 
                 # We can return here, or let it fall through? 
                 # The legacy flow continues to Semantic/LLM which require GT.
                 # So we must return.
                 
                 # But wait, structural validation was already done above (Step 2).
                 # The Manager runs structural validation AGAIN. 
                 # Optimization: Pass structural score to manager? 
                 # Or just let manager do it all? 
                 # The Manager is self-contained. 
                 # Let's rely on Manager for consistency.
                 
                 # Important: We must save the result!
                 self.store_result(result) # We need to make sure store_result handles missing GT columns?
                 # store_result takes dictionary.
                 
                 return result

            
            logger.debug(f"Step 3: Semantic check for {query_id}")
            semantic_result = self.semantic_checker.check_semantic_equivalence(
                cleaned_sql,
                ground_truth_sql
            )
            result["steps"]["semantic_check"] = semantic_result
            result["scores"]["semantic"] = semantic_result["similarity_score"]

            
            logger.debug(f"Step 4: LLM evaluation for {query_id}")
            llm_result = self.llm_judge.evaluate(
                query_text,
                cleaned_sql,
                ground_truth_sql,
                self.agent_type
            )
            result["steps"]["llm_judge"] = llm_result

            
            llm_score = 1.0 if llm_result["verdict"] == "PASS" else 0.0
            result["scores"]["llm"] = llm_score

            
            logger.debug(f"Step 5: Final scoring for {query_id}")
            final_score, final_result, confidence = self._calculate_final_score(
                result["scores"]["structural"],
                result["scores"]["semantic"],
                llm_score,
                llm_result["confidence"]
            )

            result["final_score"] = final_score
            result["final_result"] = final_result
            result["confidence"] = confidence

            
            logger.info(f"Query {query_id} evaluation complete: {final_result} (score: {final_score:.2f})")

            return result

        except Exception as e:
            logger.error(f"Error evaluating query {query_id}: {e}")
            result["final_result"] = "ERROR"
            result["error"] = str(e)
            return result

    def _calculate_final_score(
        self,
        structural_score: float,
        semantic_score: float,
        llm_score: float,
        llm_confidence: float
    ) -> tuple:
        
        final_score = (
            0.60 * structural_score +
            0.20 * semantic_score +
            0.20 * llm_score
        )

        
        threshold = settings.EVALUATION_THRESHOLD  # Default: 0.7
        final_result = "PASS" if final_score >= threshold else "FAIL"

        
        score_confidence = final_score  
        confidence = (llm_confidence + score_confidence) / 2.0

        return final_score, final_result, confidence

    def store_result(self, evaluation_result: Dict) -> bool:
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO monitoring.evaluations (
                    query_id, query_text, agent_type, complexity,
                    generated_sql, ground_truth_sql,
                    structural_score, semantic_score, llm_score,
                    final_score, result, confidence,
                    reasoning, evaluation_data, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (query_id) DO UPDATE SET
                    query_text = EXCLUDED.query_text,
                    agent_type = EXCLUDED.agent_type,
                    complexity = EXCLUDED.complexity,
                    generated_sql = EXCLUDED.generated_sql,
                    ground_truth_sql = EXCLUDED.ground_truth_sql,
                    structural_score = EXCLUDED.structural_score,
                    semantic_score = EXCLUDED.semantic_score,
                    llm_score = EXCLUDED.llm_score,
                    final_score = EXCLUDED.final_score,
                    result = EXCLUDED.result,
                    confidence = EXCLUDED.confidence,
                    reasoning = EXCLUDED.reasoning,
                    evaluation_data = EXCLUDED.evaluation_data,
                    created_at = EXCLUDED.created_at
            """, (
                evaluation_result["query_id"],
                evaluation_result["query_text"],
                evaluation_result["agent_type"],
                evaluation_result["complexity"],
                evaluation_result["generated_sql"],
                evaluation_result["ground_truth_sql"],
                evaluation_result["scores"].get("structural", 0.0),
                evaluation_result["scores"].get("semantic", 0.0),
                evaluation_result["scores"].get("llm", 0.0),
                evaluation_result["final_score"],
                evaluation_result["final_result"],
                evaluation_result["confidence"],
                evaluation_result["steps"].get("llm_judge", {}).get("reasoning", ""),
                json.dumps(evaluation_result["steps"]),
                datetime.now()
            ))

            conn.commit()
            cursor.close()
            conn.close()

            logger.debug(f"Stored evaluation result for {evaluation_result['query_id']}")
            return True

        except Exception as e:
            logger.error(f"Error storing evaluation result: {e}")
            print(f"CRITICAL DB ERROR: {e}")  
            return False
