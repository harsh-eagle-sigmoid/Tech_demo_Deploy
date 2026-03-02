"""
Semantic Matcher for Ground Truth Lookup
Uses shared SentenceTransformer model to find intent-based matches.
"""
import numpy as np
from typing import Dict, Optional
from loguru import logger
from monitoring.model_loader import get_embedding_model
import json

_matcher_instance = None


# Valid Python Reordering
class SemanticMatcher:
    def __init__(self):
        self.model = get_embedding_model()
        self.index = []     # List of (embedding, gt_entry)
        self.is_ready = False

    def load_from_file(self, filepath: str):
        """Load ground truth from JSON and initialize. Handles multiple GT formats."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Handle different GT file formats
            if isinstance(data, dict) and 'queries' in data:
                # Agent-specific format: {agent_id, agent_name, queries: [...]}
                gt_list = data['queries']
            elif isinstance(data, list):
                # Standard format: [...]
                gt_list = data
            else:
                logger.error(f"Unknown GT format in {filepath}")
                return

            # Convert list to dict format expected by initialize
            gt_data = {}
            for q in gt_list:
                # Handle different query text field names
                query_text = (q.get("query_text") or
                             q.get("natural_language") or
                             q.get("query") or "")

                if not query_text:
                    continue

                key = query_text.strip().lower().rstrip("?.!")

                # Normalize to expected format
                gt_data[key] = {
                    "query_text": query_text,
                    "sql": q.get("sql", ""),
                    "complexity": q.get("complexity", "simple"),
                    "query": query_text  # Alias for compatibility
                }

            self.initialize(gt_data)
            logger.info(f"Loaded {len(gt_data)} queries from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load semantic matcher data from {filepath}: {e}")

    def load_from_data(self, data: dict):
        """Load ground truth from a pre-loaded dict (S3/memory friendly alternative to load_from_file)."""
        try:
            if isinstance(data, dict) and 'queries' in data:
                gt_list = data['queries']
            elif isinstance(data, list):
                gt_list = data
            else:
                logger.error("Unknown GT format in data dict")
                return

            gt_data = {}
            for q in gt_list:
                query_text = (q.get("query_text") or q.get("natural_language") or q.get("query") or "")
                if not query_text:
                    continue
                key = query_text.strip().lower().rstrip("?.!")
                gt_data[key] = {
                    "query_text": query_text,
                    "sql": q.get("sql", ""),
                    "complexity": q.get("complexity", "simple"),
                    "query": query_text,
                    "expected_output": q.get("expected_output"),
                }
            self.initialize(gt_data)
            logger.info(f"Loaded {len(gt_data)} queries from data dict")
        except Exception as e:
            logger.error(f"Failed to load semantic matcher from data: {e}")

    def initialize(self, ground_truth_data: Dict[str, Dict]):
        
        logger.info(f"Initializing Semantic Matcher with {len(ground_truth_data)} queries...")
        
        queries = []
        entries = []
        
        for key, entry in ground_truth_data.items():
            # Use the original query text for embedding (better context than normalized key)
            text = entry.get("query_text") or key
            queries.append(text)
            entries.append(entry)

        if not queries:
            logger.warning("No queries to index.")
            return

        # Batch embed
        embeddings = self.model.encode(queries)
        
        # Store as simple list
        self.index = list(zip(embeddings, entries))
        self.is_ready = True
        logger.info("Semantic Matcher initialized successfully.")

    # Polarity word groups — queries with opposite groups are conflicting
    _POLARITY_LESS = frozenset({
        'less than', 'fewer than', 'below', 'under', 'smaller than',
        'at most', 'no more than', 'not more than', 'no greater than'
    })
    _POLARITY_MORE = frozenset({
        'more than', 'greater than', 'above', 'over', 'larger than',
        'at least', 'no less than', 'not less than', 'no fewer than'
    })

    def _has_polarity_conflict(self, query1: str, query2: str) -> bool:
        """Return True if one query says 'less than' while the other says 'more than'."""
        q1 = query1.lower()
        q2 = query2.lower()
        q1_less = any(t in q1 for t in self._POLARITY_LESS)
        q1_more = any(t in q1 for t in self._POLARITY_MORE)
        q2_less = any(t in q2 for t in self._POLARITY_LESS)
        q2_more = any(t in q2 for t in self._POLARITY_MORE)
        return (q1_less and q2_more) or (q1_more and q2_less)

    def find_match(self, query_text: str, threshold: float = 0.70) -> Optional[Dict]:
        """
        Find nearest neighbor in Ground Truth.
        Skips matches with conflicting polarity (e.g. 'less than' vs 'more than').
        """
        if not self.is_ready:
            return None

        query_vec = self.model.encode(query_text)

        best_score = -1.0
        best_entry = None

        # Explicit cosine similarity
        q_norm = np.linalg.norm(query_vec)

        for vec, entry in self.index:
            v_norm = np.linalg.norm(vec)
            if v_norm == 0 or q_norm == 0:
                score = 0.0
            else:
                score = float(np.dot(query_vec, vec) / (q_norm * v_norm))

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= threshold and best_entry is not None:
            gt_query_text = best_entry.get('query_text', '')
            # Reject match if polarity is opposite ("less than" vs "more than")
            if self._has_polarity_conflict(query_text, gt_query_text):
                logger.warning(
                    f"Polarity conflict — rejecting GT match: "
                    f"'{query_text}' vs '{gt_query_text}' (score={best_score:.3f})"
                )
                return None

            logger.info(f"Semantic Match Found: '{query_text}' -> '{gt_query_text}' (Score: {best_score:.3f})")
            result = dict(best_entry)
            result["match_score"] = float(best_score)
            return result

        return None

def get_semantic_matcher():
    """Singleton accessor"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = SemanticMatcher()
    return _matcher_instance