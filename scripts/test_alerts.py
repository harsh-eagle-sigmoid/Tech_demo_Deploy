import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from alerts.alert_service import alert_service

print("Testing Alert System...")
print(f"EMAIL_ENABLED: {os.getenv('ALERT_EMAIL_ENABLED')}")
print(f"SLACK_ENABLED: {os.getenv('ALERT_SLACK_ENABLED')}")

try:
    alert_service.alert_system_down(
        service="Test Service",
        error="This is a TEST ALERT to verify system is disabled."
    )
    print("Alert Triggered (Check logs if it was sent).")
except Exception as e:
    print(f"Error triggering alert: {e}")
