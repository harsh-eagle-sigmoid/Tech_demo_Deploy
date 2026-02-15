
from typing import Dict, List
from loguru import logger

class IntentLayer:
    """
    Layer 2: Intent Matching (Weight: 25%)
    Checks if the generated SQL contains logical operations requested in the user query.
    Uses synonym mapping to handle variations (e.g., "highest" -> MAX).
    """
    
    def __init__(self):
        # Synonym Map: Intent Name -> {keywords: [], sql_op: []}
        self.intent_patterns = {
            "aggregation": {
                "keywords": ["average", "mean", "avg"],
                "sql_op": ["AVG"]
            },
            "summation": {
                "keywords": ["total", "sum", "spend", "volume", "amount", "revenue", "sales", "qty", "quantity"],
                "sql_op": ["SUM", "COUNT"]
            },
            "maximization": {
                "keywords": ["highest", "maximum", "max", "peak", "top", "most", "best", "fastest", "expensive"],
                "sql_op": ["MAX", "DESC"] # MAX() function OR ORDER BY DESC
            },
            "minimization": {
                "keywords": ["lowest", "minimum", "min", "bottom", "least", "worst", "slowest", "cheapest"],
                "sql_op": ["MIN", "ASC"] # MIN() function OR ORDER BY ASC
            },
            "grouping": {
                "keywords": ["per", "each", "group by", "breakdown", "by", "split"],
                "sql_op": ["GROUP BY"]
            },
            "filtering": {
                "keywords": ["where", "filter", "only", "exclude", "not", "priority", "status", "category", "segment", "region", "country"],
                "sql_op": ["WHERE"]
            }
        }

    def evaluate(self, user_query: str, sql: str) -> float:
        """
        Calculates the Intent Match Score with penalties for unrequested complexity.
        """
        query_lower = user_query.lower()
        sql_upper = sql.upper()
        
        matches = 0
        total_checks = 0
        unrequested_penalty = 0.0
        
        # Check for each intent type
        for intent, config in self.intent_patterns.items():
            # Does the query ask for this?
            requested = any(k in query_lower for k in config["keywords"])
            
            # Does the SQL contain it?
            fulfilled = any(op in sql_upper for op in config["sql_op"])
            
            # Special handling for Implicit ASC (Minimization)
            # If user asked for 'least'/'min' (Minimization):
            # 1. SQL uses 'ORDER BY' without 'DESC' -> Implies ASC (Fulfilled)
            # 2. SQL uses 'WHERE' with 'LOW' or 'MIN' -> Implies filtering for lowest value (Fulfilled)
            if not fulfilled and intent == "minimization":
                if "ORDER BY" in sql_upper and "DESC" not in sql_upper:
                    fulfilled = True
                    logger.debug(f"Intent Fulfilled: Implicit ASC detected (ORDER BY without DESC) for {intent}")
                elif "WHERE" in sql_upper and ("LOW" in sql_upper or "MIN" in sql_upper):
                    fulfilled = True
                    logger.debug(f"Intent Fulfilled: Contextual Minimization via WHERE clause for {intent}")
            
            if requested:
                total_checks += 1
                if fulfilled:
                    matches += 1
                else:
                    logger.debug(f"Intent Missing: Query asked for {intent} but SQL missing {config['sql_op']}")
            else:
                # Not requested, but SQL has it?
                # Penalize unrequested Aggregation or Grouping as they change result shape
                if fulfilled and intent in ["aggregation", "grouping"]:
                     # Check if it's implicitly required (e.g. 'top' requires ORDER BY, maybe Grouping?)
                     # But 'top' usually maps to 'maximization', not 'grouping'.
                     # If user says "top product", they might mean "product with most sales", requiring SUM+GROUP BY.
                     # This is hard to detect with keywords only.
                     # Let's apply a small penalty for now to show variation.
                     logger.debug(f"Unrequested Complexity: SQL has {intent} but user didn't ask for keywords {config['keywords']}")
                     unrequested_penalty += 0.1

        # Base score logic:
        if total_checks == 0:
            # No explicit keywords found. 
            # If SQL is complex (Aggregation/Grouping), penalize.
            # If SQL is simple (SELECT *), Score 1.0.
            score = 1.0 - unrequested_penalty
        else:
            score = (float(matches) / total_checks) - unrequested_penalty
            
        return max(0.0, score)
