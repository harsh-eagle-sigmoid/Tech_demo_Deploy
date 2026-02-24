
import json
import psycopg2
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
from config.settings import settings


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")
from evaluation.validators import StructuralValidator
from evaluation.output_validators.result_validator import ResultValidator
from evaluation.semantic_checker import SemanticChecker
from evaluation.llm_judge import LLMJudge
from evaluation.semantic_match import get_semantic_matcher
from evaluation.layers.manager import EvaluationManager

from monitoring.drift_detector import DriftDetector
from monitoring.error_classifier import ErrorClassifier


class Evaluator:
    """Main evaluator that orchestrates SQL quality assessment via two paths:
    - 3-Step LLM Path: Structural → Semantic → LLM Judge (when ground truth found)
    - 4-Layer Heuristic Path: Structural → Intent → Pattern → Drift (no ground truth)
    """

    def __init__(self, agent_type: str):
        """Initialize evaluator with all validators for the given agent type."""
        self.agent_type = agent_type

        # Try platform registry first for dynamic agents
        schema_info_override = None
        agent_db_url = None
        try:
            from agent_platform.agent_manager import AgentManager
            mgr = AgentManager()
            agent_record = mgr.get_agent_by_name(agent_type)
            if agent_record:
                schema_info_override = mgr.get_agent_schema_info(agent_record["agent_id"])
                agent_db_url = agent_record["db_url"]
                self.schema_name = None  # not needed — schema_info takes precedence
            else:
                # Legacy fallback
                self.schema_name = "spend_data" if agent_type == "spend" else "demand_data"
        except Exception:
            self.schema_name = "spend_data" if agent_type == "spend" else "demand_data"
            schema_info_override = None
            agent_db_url = None

        # 3-Step evaluation components
        self.structural_validator = StructuralValidator(
            schema_name=self.schema_name,
            schema_info=schema_info_override,
            db_url=agent_db_url
        )
        # Pass schema_info so SemanticChecker can normalize column/table aliases
        self.semantic_checker = SemanticChecker(schema_info=self.structural_validator.schema_info)
        self.llm_judge = LLMJudge()

        # NEW: Result validator for output comparison
        self.result_validator = ResultValidator(
            timeout_seconds=10,
            max_rows=10000,
            epsilon=0.0001
        )
        self.agent_db_url = agent_db_url  # Store for result validation

        # 4-Layer heuristic evaluation manager
        self.manager = EvaluationManager(
            schema_name=self.schema_name,
            agent_type=self.agent_type,
            schema_info=schema_info_override,
            db_url=agent_db_url
        )

        logger.info(f"Initialized Evaluator for {agent_type} agent")

    def _get_db_connection(self):
        """Create a direct DB connection for storing evaluation results."""
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    def _get_ground_truth_file(self) -> str:
        """
        Dynamically select ground truth file based on agent type.
        Each agent has its own GT file: {agent_type}_agent_queries.json
        Falls back to all_queries.json if agent-specific file doesn't exist.
        """
        import os

        # Normalize agent_type: lowercase, remove spaces, remove '_agent' suffix
        normalized_type = self.agent_type.lower().replace(' ', '_').replace('_agent', '')

        # Try agent-specific GT file first
        agent_gt_file = f"data/ground_truth/{normalized_type}_agent_queries.json"
        if os.path.exists(agent_gt_file):
            logger.info(f"Using agent-specific GT file: {agent_gt_file}")
            return agent_gt_file

        # Fallback to all_queries.json
        default_file = "data/ground_truth/all_queries.json"
        logger.warning(f"Agent-specific GT file not found, using default: {default_file}")
        return default_file

    def preprocess(self, query_text: str, generated_sql: str) -> Dict:
        """Clean SQL by stripping whitespace and removing markdown code fences."""
        cleaned_sql = generated_sql.strip()

        # Remove markdown code blocks (```sql ... ```)
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
        """
        Main evaluation entry point — decides which path to use:
        - If ground truth found → 3-Step LLM evaluation (Structural 60% + Semantic 20% + LLM 20%)
        - If no ground truth   → 4-Layer Heuristic evaluation (Structural 35% + Intent 25% + Pattern 20% + Drift 20%)
        """
        logger.info(f"Evaluating query {query_id}: {query_text[:50]}...")

        # Try to find ground truth SQL via semantic matching if not provided
        gt_expected_output = None  # Initialize GT expected output
        if not ground_truth_sql:
            try:
                matcher = get_semantic_matcher()
                # Always reload GT file for current agent type (don't rely on is_ready)
                gt_file = self._get_ground_truth_file()
                matcher.load_from_file(gt_file)

                # Find closest matching ground truth query (threshold: 0.95 similarity)
                match = matcher.find_match(query_text, threshold=0.95)
                if match:
                    ground_truth_sql = match["sql"]
                    complexity = match["complexity"]
                    # NEW: Store expected_output if available in GT
                    gt_expected_output = match.get("expected_output")
                    logger.info(f"Evaluator found GT: {ground_truth_sql[:30]}...")
                    if gt_expected_output:
                        logger.info("GT includes expected output for validation")
                else:
                    logger.warning(f"Evaluator could not find Ground Truth for: {query_text}")
                    ground_truth_sql = None
                    gt_expected_output = None
            except Exception as e:
                logger.error(f"Semantic matcher failed for {query_id}: {e}")
                ground_truth_sql = None

        # Initialize result dict with default FAIL state
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
            # Step 1: Preprocess — clean SQL, remove markdown fences
            preprocessed = self.preprocess(query_text, generated_sql)
            result["steps"]["preprocessing"] = preprocessed
            cleaned_sql = preprocessed["cleaned_sql"]

            # Step 2: Structural validation — check syntax, table/column existence via EXPLAIN
            structural_result = self.structural_validator.validate(cleaned_sql)
            result["steps"]["structural_validation"] = structural_result
            result["scores"]["structural"] = structural_result["score"]

            # If structural error is classifiable (syntax/table/column), store FAIL + classify error
            if structural_result.get("requires_classification", False):
                logger.warning(f"Structural validation failed with classifiable error: {structural_result.get('error_type')}")
                result["final_result"] = "FAIL"
                result["final_score"] = 0.0
                result["confidence"] = 0.0
                result["error_message"] = "; ".join(structural_result.get("errors", []))

                # Store failed evaluation to get evaluation_id for error linking
                evaluation_id = self.store_result(result)

                # Classify the error (SQL_GENERATION, CONTEXT_RETRIEVAL, etc.)
                if evaluation_id:
                    try:
                        error_classifier = ErrorClassifier()
                        classification_result = error_classifier.classify(
                            error_message=result["error_message"],
                            query_id=query_id,
                            evaluation_id=evaluation_id
                        )
                        logger.info(f"Error classified as {classification_result['error_category']} (severity: {classification_result['severity']})")
                        result["error_classification"] = classification_result
                    except Exception as e:
                        logger.error(f"Error classification failed for {query_id}: {e}")

                return result

            # If structural score is 0 but not classifiable, just fail without error classification
            if structural_result["score"] == 0.0:
                result["final_result"] = "FAIL"
                result["final_score"] = 0.0
                result["confidence"] = 0.0
                return result

            # === PATH A: No Ground Truth → Heuristic + LLM Output Validation ===
            if not ground_truth_sql:
                 logger.info(f"Query {query_id}: No Ground Truth. Switching to Heuristic + LLM Output Evaluation.")

                 # Run all 4 heuristic layers: Structural(35%) + Intent(25%) + Pattern(20%) + Drift(20%)
                 heuristic_res = self.manager.evaluate_heuristic(
                     query_text,
                     cleaned_sql,
                     query_id=query_id
                 )

                 # Copy heuristic results into evaluation result
                 result["final_result"] = heuristic_res["final_result"]
                 result["final_score"] = heuristic_res["final_score"]
                 result["confidence"] = heuristic_res["confidence"]
                 result["scores"] = heuristic_res["components"]
                 result["reasoning"] = "Reference-Free Heuristic Evaluation"

                 # Add LLM-based output validation if DB URL available
                 if self.agent_db_url:
                     try:
                         logger.info("Adding LLM-based output validation (no GT)...")
                         llm_validation_result = self.result_validator.validate_with_llm(
                             query_text=query_text,
                             generated_sql=cleaned_sql,
                             db_url=self.agent_db_url
                         )

                         # Store LLM output validation results
                         result["result_validation"] = {
                             "score": llm_validation_result.score,
                             "confidence": llm_validation_result.confidence,
                             "execution_success": llm_validation_result.execution_success,
                             "validation_type": llm_validation_result.details.get("validation_type"),
                             "llm_correctness": llm_validation_result.details.get("llm_correctness"),
                             "llm_completeness": llm_validation_result.details.get("llm_completeness"),
                             "llm_quality": llm_validation_result.details.get("llm_quality"),
                             "llm_reasoning": llm_validation_result.details.get("llm_reasoning"),
                             "generated_time_ms": llm_validation_result.generated_execution_time_ms,
                             "error": llm_validation_result.error,
                             "details": llm_validation_result.details
                         }
                         result["scores"]["result_validation"] = llm_validation_result.score

                         logger.info(f"LLM output validation complete: score={llm_validation_result.score:.2f}")

                     except Exception as e:
                         logger.error(f"LLM output validation failed: {e}")
                         result["result_validation"] = {
                             "error": str(e),
                             "score": 0.0
                         }
                         result["scores"]["result_validation"] = None
                 else:
                     logger.warning("No agent DB URL available - skipping LLM output validation")
                     result["scores"]["result_validation"] = None

                 # Store heuristic evaluation result to DB
                 self.store_result(result)
                 return result

            # === PATH B: Ground Truth Found → 3-Step LLM Evaluation ===

            # Step 3: Semantic check — compare SQL structure component-by-component
            semantic_result = self.semantic_checker.check_semantic_equivalence(
                cleaned_sql,
                ground_truth_sql
            )
            result["steps"]["semantic_check"] = semantic_result
            result["scores"]["semantic"] = semantic_result["similarity_score"]

            # Step 4: LLM Judge — Azure OpenAI evaluates correctness with reasoning
            llm_result = self.llm_judge.evaluate(
                query_text,
                cleaned_sql,
                ground_truth_sql,
                self.agent_type
            )
            result["steps"]["llm_judge"] = llm_result
            llm_score = 1.0 if llm_result["verdict"] == "PASS" else 0.0
            result["scores"]["llm"] = llm_score

            # Step 5: Result Validation — Execute and compare actual query outputs
            result_validation_score = 0.0
            gt_match_confidence = "HIGH"  # Default confidence

            if self.agent_db_url:
                try:
                    # NEW: Check if GT has expected_output for direct comparison
                    if gt_expected_output:
                        logger.info("Using GT expected output validation (more accurate)")
                        validation_result = self.result_validator.validate_with_gt_output(
                            query_text=query_text,
                            generated_sql=cleaned_sql,
                            gt_expected_output=gt_expected_output,
                            db_url=self.agent_db_url
                        )
                    else:
                        # Fallback to SQL execution comparison
                        # Determine GT match confidence from semantic score
                        sem_score = result["scores"]["semantic"]
                        if sem_score >= 0.90:
                            gt_match_confidence = "HIGH"
                        elif sem_score >= 0.75:
                            gt_match_confidence = "MEDIUM"
                        else:
                            gt_match_confidence = "LOW"

                        logger.info(f"Running SQL execution validation (confidence: {gt_match_confidence})...")
                        validation_result = self.result_validator.validate(
                            generated_sql=cleaned_sql,
                            ground_truth_sql=ground_truth_sql,
                            db_url=self.agent_db_url,
                            gt_match_confidence=gt_match_confidence
                        )

                    result["steps"]["result_validation"] = {
                        "score": validation_result.score,
                        "confidence": validation_result.confidence,
                        "execution_success": validation_result.execution_success,
                        "schema_match": validation_result.schema_match,
                        "row_count_match": validation_result.row_count_match,
                        "content_match_rate": validation_result.content_match_rate,
                        "generated_time_ms": validation_result.generated_execution_time_ms,
                        "gt_time_ms": validation_result.gt_execution_time_ms,
                        "error": validation_result.error,
                        "details": validation_result.details
                    }
                    result_validation_score = validation_result.score
                    result["scores"]["result_validation"] = result_validation_score

                    logger.info(f"Result validation complete: score={result_validation_score:.2f}")

                except Exception as e:
                    logger.error(f"Result validation failed: {e}")
                    result["steps"]["result_validation"] = {
                        "error": str(e),
                        "score": 0.0
                    }
                    result_validation_score = 0.0
                    result["scores"]["result_validation"] = 0.0
            else:
                logger.warning("No agent DB URL available - skipping result validation")
                result["scores"]["result_validation"] = None

            # Step 6: Calculate weighted final score (Structural 40% + Semantic 15% + LLM 15% + Result 30%)
            final_score, final_result, confidence = self._calculate_final_score(
                result["scores"]["structural"],
                result["scores"]["semantic"],
                llm_score,
                llm_result["confidence"],
                result_validation_score
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
        llm_confidence: float,
        result_validation_score: float = 0.0
    ) -> tuple:
        """
        Calculate weighted final score for evaluation with ground truth.

        Weighting:
        - Structural: 40% (syntax, schema validity)
        - Semantic: 15% (SQL component similarity)
        - LLM Judge: 15% (AI reasoning about correctness)
        - Result Validation: 30% (actual output comparison - MOST IMPORTANT)
        """
        # Check if result validation was performed
        if result_validation_score is None or result_validation_score == 0.0:
            # Fallback to old weighting if result validation not available
            final_score = (
                0.60 * structural_score +
                0.10 * semantic_score +
                0.30 * llm_score
            )
            logger.info("Using legacy scoring (no result validation)")
        else:
            # NEW: Include result validation in score
            final_score = (
                0.40 * structural_score +
                0.15 * semantic_score +
                0.15 * llm_score +
                0.30 * result_validation_score
            )
            logger.info(f"Using enhanced scoring with result validation: "
                       f"struct={structural_score:.2f}, sem={semantic_score:.2f}, "
                       f"llm={llm_score:.2f}, result={result_validation_score:.2f}")

        # PASS if score meets threshold (default 0.7)
        threshold = settings.EVALUATION_THRESHOLD
        final_result = "PASS" if final_score >= threshold else "FAIL"

        # Confidence = average of LLM confidence and final score
        score_confidence = final_score
        confidence = (llm_confidence + score_confidence) / 2.0

        return final_score, final_result, confidence

    def store_result(self, evaluation_result: Dict) -> Optional[int]:
        """Store evaluation result to monitoring.evaluations table, return evaluation_id."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Upsert evaluation — insert or update if query_id already exists
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
                RETURNING evaluation_id
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
                # Store steps, scores, and result_validation in evaluation_data JSONB for dashboard retrieval
                json.dumps({
                    **evaluation_result["steps"],
                    "scores": evaluation_result.get("scores", {}),
                    "result_validation": evaluation_result.get("steps", {}).get("result_validation")
                }, default=json_serial),
                datetime.now()
            ))

            row = cursor.fetchone()
            evaluation_id = row[0] if row else None

            conn.commit()
            cursor.close()
            conn.close()

            logger.debug(f"Stored evaluation result for {evaluation_result['query_id']} with id={evaluation_id}")
            return evaluation_id

        except Exception as e:
            import traceback
            logger.error(f"Error storing evaluation result: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
