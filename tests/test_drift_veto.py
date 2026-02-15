
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.layers.manager import EvaluationManager
from unittest.mock import MagicMock

def test_drift_veto():
    print("Testing Drift Veto Logic...")
    
    # Mock DriftDetector to return High Drift (Low Quality)
    # Drift Score 0.97 -> Quality 0.03
    mock_detector = MagicMock()
    mock_detector.detect.return_value = {
        "drift_score": 0.97,
        "is_drift": True
    }
    
    # Initialize Manager with mocked detector
    manager = EvaluationManager("spend_data")
    manager.drift_detector = mock_detector
    manager.drift_layer.detector = mock_detector
    
    # Run Evaluation
    # Query irrelevant
    result = manager.evaluate_heuristic(
        query_text="what is docker ?",
        sql="SELECT * FROM table", # Assume valid SQL but irrelevant
        query_id="test_id"
    )
    
    print(f"Final Score: {result['final_score']}")
    print(f"Result: {result['final_result']}")
    print(f"Drift Quality: {result['components']['drift_quality']}")
    
    if result['final_result'] == "FAIL" and result['final_score'] <= 0.4:
        print("SUCCESS: Drift Veto triggered correctly.")
    else:
        print("FAILURE: Drift Veto did NOT trigger.")

if __name__ == "__main__":
    test_drift_veto()
