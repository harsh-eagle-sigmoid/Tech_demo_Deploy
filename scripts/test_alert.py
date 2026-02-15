utf-8import sys
import os
sys.path.append(os.getcwd())
from alerts.alert_service import alert_service
from config.settings import settings
import logging
logging.basicConfig(level=logging.INFO)
def trigger_manual_alert():
    print("Attempting to trigger manual alerts (Email & SMS)...")
    print(f"Email Enabled: {settings.ALERT_EMAIL_ENABLED}")
    print(f"SNS Topic: {settings.AWS_SNS_TOPIC_ARN}")
    print(f"Recipients: {settings.ALERT_RECIPIENT_EMAILS}")
    success = alert_service.alert_critical_error(
        query_id="MANUAL-TEST-001",
        error_category="TEST_ALERT",
        error_message="This is a manual test of the Alert System requested by the User.",
        agent_type="system"
    )
    if success:
        print("✅ Alert Sent Successfully!")
    else:
        print("❌ Failed to send alert. Check logs/credentials.")
if __name__ == :
    trigger_manual_alert()