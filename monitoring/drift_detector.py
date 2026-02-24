
import numpy as np
import psycopg2
import psycopg2.extras
from typing import List, Optional, Dict
from loguru import logger
from monitoring.model_loader import get_embedding_model
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "unilever_poc")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DRIFT_HIGH_THRESHOLD   = float(os.getenv("DRIFT_HIGH_THRESHOLD", "0.5"))
DRIFT_MEDIUM_THRESHOLD = float(os.getenv("DRIFT_MEDIUM_THRESHOLD", "0.3"))
EMBEDDING_MODEL        = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIM          = int(os.getenv("EMBEDDING_DIMENSION", "1024"))


class DriftDetector:
    

    def __init__(self):
        logger.info(f"Loading embedding model via ModelLoader (Bedrock/Local)...")
        self.model = get_embedding_model()
        if not self.model:
             logger.error("Failed to load embedding model")
        logger.info("Embedding model loaded")

    
    def _conn(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    
    def embed(self, text: str) -> List[float]:
        
        return self.model.encode(text).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        
        return self.model.encode(texts).tolist()

    
    def create_baseline(self, agent_type: str, queries: List[str]) -> Dict:
        
        logger.info(f"Creating baseline for {agent_type} from {len(queries)} queries")

        embeddings = self.embed_batch(queries)
        centroid   = np.mean(embeddings, axis=0).tolist()

        try:
            conn = self._conn()
            cur  = conn.cursor()

            
            cur.execute("DELETE FROM monitoring.baseline WHERE agent_type = %s", (agent_type,))
            cur.execute("""
                INSERT INTO monitoring.baseline (agent_type, centroid_embedding, num_queries, version)
                VALUES (%s, %s, %s, 1)
            """, (agent_type, centroid, len(queries)))

            conn.commit()
            cur.close()
            conn.close()

            logger.info(f"Baseline saved for {agent_type}: {len(queries)} queries")
            return {"agent_type": agent_type, "num_queries": len(queries), "version": 1}

        except Exception as e:
            logger.error(f"Error saving baseline: {e}")
            return {"error": str(e)}

    def _get_baseline(self, agent_type: str) -> Optional[List[float]]:
        
        try:
            conn = self._conn()
            cur  = conn.cursor()
            cur.execute(
                "SELECT centroid_embedding FROM monitoring.baseline WHERE agent_type = %s ORDER BY version DESC LIMIT 1",
                (agent_type,)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row is None:
                return None
            vec = row[0]
        
            if isinstance(vec, str):
                vec = [float(x) for x in vec.strip("[]").split(",")]
            return vec
        except Exception as e:
            logger.error(f"Error loading baseline: {e}")
            return None

    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        a_np = np.array(a)
        b_np = np.array(b)
        if a_np.shape != b_np.shape:
            logger.warning(f"Dimension mismatch in cosine similarity: {a_np.shape} vs {b_np.shape}. "
                           f"Baseline may need regeneration.")
            return 0.0
        dot  = np.dot(a_np, b_np)
        norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
        return float(dot / norm) if norm != 0 else 0.0

    def detect(self, query_id: str, query_text: str, agent_type: str) -> Dict:
        
        query_embedding = self.embed(query_text)

       
        baseline = self._get_baseline(agent_type)

        if baseline is None:
            logger.warning(f"No baseline for {agent_type} — cannot detect drift")
            return {
                "query_id": query_id,
                "agent_type": agent_type,
                "drift_score": 0.0,
                "drift_classification": "no_baseline",
                "similarity_to_baseline": 0.0,
                "anomaly_flag": False
            }

        # Dimension guard: if baseline was created with a different model, skip drift
        if len(query_embedding) != len(baseline):
            logger.warning(f"Baseline dimension mismatch for {agent_type}: "
                           f"query={len(query_embedding)}, baseline={len(baseline)}. "
                           f"Regenerate baseline with current embedding model.")
            return {
                "query_id": query_id,
                "agent_type": agent_type,
                "drift_score": 0.0,
                "drift_classification": "dimension_mismatch",
                "similarity_to_baseline": 0.0,
                "anomaly_flag": False
            }

        
        similarity = self._cosine_similarity(query_embedding, baseline)

       
        if similarity >= (1.0 - DRIFT_MEDIUM_THRESHOLD):       # >= 0.7
            classification = "normal"
            anomaly        = False
        elif similarity >= (1.0 - DRIFT_HIGH_THRESHOLD):       # >= 0.5
            classification = "medium"
            anomaly        = False
        else:                                                   # < 0.5
            classification = "high"
            anomaly        = True

        drift_score = 1.0 - similarity          

        result = {
            "query_id":              query_id,
            "agent_type":            agent_type,
            "query_embedding":       query_embedding,
            "drift_score":           drift_score,
            "drift_classification":  classification,
            "similarity_to_baseline": similarity,
            "anomaly_flag":          anomaly
        }

        
        self._store_drift(result)

        return result

    def _store_drift(self, result: Dict):
        
        try:
            conn = self._conn()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO monitoring.drift_monitoring
                    (query_id, query_embedding, drift_score, drift_classification,
                     similarity_to_baseline, is_anomaly)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (query_id) DO UPDATE SET
                    query_embedding = EXCLUDED.query_embedding,
                    drift_score = EXCLUDED.drift_score,
                    drift_classification = EXCLUDED.drift_classification,
                    similarity_to_baseline = EXCLUDED.similarity_to_baseline,
                    is_anomaly = EXCLUDED.is_anomaly
            """, (
                result["query_id"],
                result["query_embedding"],
                result["drift_score"],
                result["drift_classification"],
                result["similarity_to_baseline"],
                result["anomaly_flag"]
            ))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing drift: {e}")
