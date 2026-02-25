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

    def find_match(self, query_text: str, threshold: float = 0.70) -> Optional[Dict]:
        """
        Find nearest neighbor in Ground Truth.
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
                score = 0
            else:
                score = np.dot(query_vec, vec) / (q_norm * v_norm)
            
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= threshold:
            logger.info(f"Semantic Match Found: '{query_text}' -> '{best_entry['query_text']}' (Score: {best_score:.3f})")
            return best_entry
        
        return None

def get_semantic_matcher():
    """Singleton accessor"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = SemanticMatcher()
    return _matcher_instance