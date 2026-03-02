"""
PSI-based Result Distribution Drift Detector.

Detects when the numeric values returned by an agent have shifted
from the baseline distribution built from ground truth expected_output data.

PSI thresholds:
  < 0.10  → normal   (no significant drift)
  0.10-0.20 → medium (moderate drift, monitor)
  > 0.20  → high     (significant drift, trigger alert)
"""
import json
import math
import psycopg2
import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger
from config.settings import settings


class ResultDriftDetector:
    """
    Detects result distribution drift using Population Stability Index (PSI).

    Workflow:
    1. create_baseline(agent_type, gt_queries)  — called once after GT generation
    2. detect_psi(agent_type, query_id, rows, columns) — called per ingest query
    """

    PSI_MEDIUM = 0.10
    PSI_HIGH   = 0.20
    MIN_SAMPLES = 20    # Minimum values per column to create a reliable baseline
    NUM_BUCKETS = 10    # Equal-frequency (quantile) buckets

    # ------------------------------------------------------------------
    # DB connection
    # ------------------------------------------------------------------

    def _conn(self):
        return psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )

    # ------------------------------------------------------------------
    # Baseline Creation
    # ------------------------------------------------------------------

    def create_baseline(self, agent_type: str, gt_queries: list) -> Dict:
        """
        Build quantile bucket distributions from GT expected_output.sample_rows.
        Called once after GT generation completes for an agent.

        Args:
            agent_type:  Normalized agent name (e.g. 'marketing')
            gt_queries:  List of query dicts from the GT JSON file

        Returns:
            {"agent_type": ..., "columns_baselined": [...], "sample_count": ...}
        """
        # Collect all numeric values per column across all GT queries
        column_values: Dict[str, List[float]] = {}

        for query in gt_queries:
            expected = query.get("expected_output")
            if not expected:
                continue

            columns    = expected.get("columns", [])
            sample_rows = expected.get("sample_rows", [])

            if not columns or not sample_rows:
                continue

            for row in sample_rows:
                if len(row) != len(columns):
                    continue
                for col_name, val in zip(columns, row):
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        col_key = col_name.lower()
                        column_values.setdefault(col_key, []).append(float(val))

        if not column_values:
            logger.warning(
                f"No numeric data found in GT for agent '{agent_type}' — result baseline skipped"
            )
            return {"agent_type": agent_type, "columns_baselined": [], "sample_count": 0}

        # Build quantile buckets for each column with enough samples
        columns_baselined = []
        total_samples = 0

        for col_name, values in column_values.items():
            if len(values) < self.MIN_SAMPLES:
                logger.debug(
                    f"Skipping column '{col_name}' — only {len(values)} samples "
                    f"(need {self.MIN_SAMPLES})"
                )
                continue

            try:
                edges, expected_pct = self._build_quantile_buckets(values)
                self._store_baseline(agent_type, col_name, edges, expected_pct, len(values))
                columns_baselined.append(col_name)
                total_samples += len(values)
                logger.info(
                    f"Result baseline created for '{agent_type}.{col_name}' "
                    f"({len(values)} samples, {len(edges)-1} buckets)"
                )
            except Exception as e:
                logger.warning(f"Failed to baseline column '{col_name}': {e}")

        logger.info(
            f"Result baseline complete for '{agent_type}': "
            f"{len(columns_baselined)} columns — {columns_baselined}"
        )
        return {
            "agent_type": agent_type,
            "columns_baselined": columns_baselined,
            "sample_count": total_samples
        }

    def _build_quantile_buckets(
        self, values: List[float]
    ) -> Tuple[List[float], List[float]]:
        """
        Build equal-frequency (quantile) buckets.
        Returns (bucket_edges, expected_pct_per_bucket).
        """
        arr = np.array(values)
        quantiles = np.linspace(0, 100, self.NUM_BUCKETS + 1)
        edges = np.percentile(arr, quantiles).tolist()

        # Deduplicate edges (can happen with highly skewed / constant data)
        edges = sorted(set(edges))
        if len(edges) < 2:
            raise ValueError("Not enough unique values to create buckets")

        # Count values per bucket
        counts = np.zeros(len(edges) - 1)
        for val in values:
            idx = self._find_bucket(val, edges)
            if idx >= 0:
                counts[idx] += 1

        total = counts.sum()
        if total > 0:
            expected_pct = (counts / total).tolist()
        else:
            expected_pct = [1.0 / len(counts)] * len(counts)

        return edges, expected_pct

    def _store_baseline(
        self,
        agent_type: str,
        column_name: str,
        edges: List[float],
        expected_pct: List[float],
        sample_count: int
    ):
        """Store / update baseline in monitoring.result_drift_baseline."""
        conn = self._conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO monitoring.result_drift_baseline
                (agent_type, column_name, bucket_edges, expected_pct, sample_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (agent_type, column_name) DO UPDATE SET
                bucket_edges = EXCLUDED.bucket_edges,
                expected_pct = EXCLUDED.expected_pct,
                sample_count = EXCLUDED.sample_count,
                created_at   = NOW()
        """, (
            agent_type,
            column_name,
            json.dumps(edges),
            json.dumps(expected_pct),
            sample_count
        ))
        conn.commit()
        cur.close()
        conn.close()

    # ------------------------------------------------------------------
    # PSI Detection
    # ------------------------------------------------------------------

    def detect_psi(
        self,
        agent_type: str,
        query_id: str,
        result_rows: List[List],
        columns: List[str]
    ) -> Dict:
        """
        Compute PSI between agent result rows and the stored baseline distribution.

        Args:
            agent_type:  Normalized agent name
            query_id:    Query identifier (for storage)
            result_rows: Agent's actual result rows (list of lists)
            columns:     Column names matching result_rows

        Returns:
            {
              "psi_scores": {"revenue": 0.32, "impressions": 0.08},
              "overall_psi": 0.32,
              "drift_classification": "high",
              "is_anomaly": True,
              "columns_analyzed": 2
            }
        """
        if not result_rows:
            return self._skip("empty_result", query_id, agent_type)

        # Load baseline for this agent
        baseline = self._load_baseline(agent_type)
        if not baseline:
            return self._skip("no_baseline", query_id, agent_type)

        # Extract numeric column values that have a baseline
        col_values: Dict[str, List[float]] = {}
        for row in result_rows:
            if len(row) != len(columns):
                continue
            for col_name, val in zip(columns, row):
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    col_key = col_name.lower()
                    if col_key in baseline:
                        col_values.setdefault(col_key, []).append(float(val))

        if not col_values:
            return self._skip("no_numeric_data", query_id, agent_type)

        # Compute PSI per column
        psi_scores = {}
        for col_name, values in col_values.items():
            if not values:
                continue
            try:
                b = baseline[col_name]
                actual_pct = self._bucket_values(values, b["edges"])
                psi = self._compute_psi(b["expected_pct"], actual_pct)
                psi_scores[col_name] = round(psi, 4)
            except Exception as e:
                logger.warning(f"PSI computation failed for column '{col_name}': {e}")

        if not psi_scores:
            return self._skip("no_numeric_data", query_id, agent_type)

        overall_psi              = max(psi_scores.values())
        classification, is_anomaly = self._classify_psi(overall_psi)

        result = {
            "psi_scores":          psi_scores,
            "overall_psi":         round(overall_psi, 4),
            "drift_classification": classification,
            "is_anomaly":          is_anomaly,
            "columns_analyzed":    len(psi_scores)
        }

        self._store_result(query_id, agent_type, result)

        logger.info(
            f"PSI result drift [{query_id}]: overall={overall_psi:.4f} "
            f"({classification}), columns={list(psi_scores.keys())}"
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_values(self, values: List[float], edges: List[float]) -> List[float]:
        """Bucket actual values using baseline edges, return % per bucket."""
        counts = [0] * (len(edges) - 1)
        for val in values:
            idx = self._find_bucket(val, edges)
            if idx >= 0:
                counts[idx] += 1
        total = sum(counts)
        if total == 0:
            return [1.0 / len(counts)] * len(counts)
        # Replace 0% with small value to avoid ln(0) in PSI formula
        return [max(c / total, 0.0001) for c in counts]

    @staticmethod
    def _find_bucket(val: float, edges: List[float]) -> int:
        """Return the bucket index for a value given bucket edges."""
        n = len(edges) - 1
        for i in range(n):
            is_last = (i == n - 1)
            if is_last:
                if edges[i] <= val <= edges[i + 1]:
                    return i
            else:
                if edges[i] <= val < edges[i + 1]:
                    return i
        return -1  # Out of range

    @staticmethod
    def _compute_psi(expected_pct: List[float], actual_pct: List[float]) -> float:
        """
        PSI = Σ (Actual% - Expected%) × ln(Actual% / Expected%)
        """
        min_len = min(len(expected_pct), len(actual_pct))
        psi = 0.0
        for exp, act in zip(expected_pct[:min_len], actual_pct[:min_len]):
            exp = max(exp, 0.0001)
            act = max(act, 0.0001)
            psi += (act - exp) * math.log(act / exp)
        return psi

    @staticmethod
    def _classify_psi(psi: float) -> Tuple[str, bool]:
        """Return (classification, is_anomaly) for a PSI score."""
        if psi < 0.10:
            return "normal", False
        elif psi < 0.20:
            return "medium", False
        else:
            return "high", True

    def _load_baseline(self, agent_type: str) -> Optional[Dict]:
        """Load all column baselines for an agent_type from the DB."""
        try:
            conn = self._conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT column_name, bucket_edges, expected_pct
                FROM monitoring.result_drift_baseline
                WHERE agent_type = %s
            """, (agent_type,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                return None

            baseline = {}
            for col_name, edges, expected_pct in rows:
                if isinstance(edges, str):
                    edges = json.loads(edges)
                if isinstance(expected_pct, str):
                    expected_pct = json.loads(expected_pct)
                baseline[col_name] = {"edges": edges, "expected_pct": expected_pct}

            return baseline
        except Exception as e:
            logger.error(f"Failed to load result baseline for '{agent_type}': {e}")
            return None

    def _store_result(self, query_id: str, agent_type: str, result: Dict):
        """Persist PSI result in monitoring.result_drift_monitoring."""
        try:
            conn = self._conn()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO monitoring.result_drift_monitoring
                    (query_id, agent_type, psi_scores, overall_psi,
                     drift_classification, is_anomaly, columns_analyzed)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (query_id) DO UPDATE SET
                    psi_scores           = EXCLUDED.psi_scores,
                    overall_psi          = EXCLUDED.overall_psi,
                    drift_classification = EXCLUDED.drift_classification,
                    is_anomaly           = EXCLUDED.is_anomaly,
                    columns_analyzed     = EXCLUDED.columns_analyzed
            """, (
                query_id,
                agent_type,
                json.dumps(result["psi_scores"]),
                result["overall_psi"],
                result["drift_classification"],
                result["is_anomaly"],
                result["columns_analyzed"]
            ))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to store PSI result for {query_id}: {e}")

    def _skip(self, reason: str, query_id: str, agent_type: str) -> Dict:
        """Return a no-op result when PSI cannot be computed."""
        logger.debug(f"PSI result drift skipped for {query_id}: {reason}")
        return {
            "psi_scores":          {},
            "overall_psi":         0.0,
            "drift_classification": reason,
            "is_anomaly":          False,
            "columns_analyzed":    0
        }
