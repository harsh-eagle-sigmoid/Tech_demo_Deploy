"""
Trigger a test alert to verify email/SMS notifications
"""
import sys
sys.path.insert(0, '/home/lenovo/Desktop/New_tech_demo')

from dotenv import load_dotenv
load_dotenv("/home/lenovo/Desktop/New_tech_demo/.env")

from alerts.alert_service import alert_service, AlertType

print("=" * 60)
print("Triggering Test Alerts")
print("=" * 60)

# Test 1: High Drift Alert
print("\n[1] Sending HIGH DRIFT Alert...")
result = alert_service.alert_high_drift(
    query_id="TEST-001",
    query_text="This is a test query to check if alerts are working",
    drift_score=0.85,
    agent_type="spend"
)
print(f"    Result: {'Sent!' if result else 'Failed (check if alerts enabled)'}")

# Test 2: Critical Error Alert
print("\n[2] Sending CRITICAL ERROR Alert...")
result = alert_service.alert_critical_error(
    query_id="TEST-002",
    error_category="SYSTEM_FAILURE",
    error_message="Test critical error - please ignore",
    agent_type="demand"
)
print(f"    Result: {'Sent!' if result else 'Failed (check if alerts enabled)'}")

# Test 3: System Down Alert
print("\n[3] Sending SYSTEM DOWN Alert...")
result = alert_service.alert_system_down(
    service="Test Service",
    error="This is a test system down alert - please ignore"
)
print(f"    Result: {'Sent!' if result else 'Failed (check if alerts enabled)'}")

# Test 4: Accuracy Drop Alert
print("\n[4] Sending ACCURACY DROP Alert...")
result = alert_service.alert_accuracy_drop(
    current_accuracy=75.5,
    previous_accuracy=92.3,
    agent_type="spend",
    sample_size=100
)
print(f"    Result: {'Sent!' if result else 'Failed (check if alerts enabled)'}")

print("\n" + "=" * 60)
print("Check your email inbox: h22244080@gmail.com")
print("You should receive 4 alert emails!")
print("=" * 60)
