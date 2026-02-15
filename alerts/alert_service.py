
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from config.settings import settings

logger = logging.getLogger(__name__)


class AlertType(Enum):
   
    HIGH_DRIFT = "high_drift"
    CRITICAL_ERROR = "critical_error"
    ACCURACY_DROP = "accuracy_drop"
    SYSTEM_DOWN = "system_down"
    ERROR_SPIKE = "error_spike"


class AlertService:
   

    def __init__(self):
        self._ses_client = None
        self._sns_client = None
        self._initialized = False

    def _init_clients(self):
       
        if self._initialized:
            return

        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            logger.warning("AWS credentials not configured, alerts disabled")
            return

        try:
            self._ses_client = boto3.client(
                'ses',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            self._sns_client = boto3.client(
                'sns',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            self._initialized = True
            logger.info("AWS alert clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")

    @property
    def is_enabled(self) -> bool:
       
        return (
            settings.ALERT_EMAIL_ENABLED and
            bool(settings.AWS_ACCESS_KEY_ID) and
            bool(settings.AWS_SECRET_ACCESS_KEY) and
            bool(settings.AWS_SES_SENDER_EMAIL)
        )

    def _get_recipients(self) -> List[str]:
        
        if not settings.ALERT_RECIPIENT_EMAILS:
            return []
        return [email.strip() for email in settings.ALERT_RECIPIENT_EMAILS.split(',') if email.strip()]

    def send_email(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: Optional[List[str]] = None
    ) -> bool:
       
        if not self.is_enabled:
            logger.debug("Email alerts disabled, skipping")
            return False

        self._init_clients()

        if not self._ses_client:
            logger.error("SES client not initialized")
            return False

        recipients = recipients or self._get_recipients()
        if not recipients:
            logger.warning("No recipient emails configured")
            return False

        try:
            response = self._ses_client.send_email(
                Source=settings.AWS_SES_SENDER_EMAIL,
                Destination={'ToAddresses': recipients},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': body_text, 'Charset': 'UTF-8'},
                        'Html': {'Data': body_html, 'Charset': 'UTF-8'}
                    }
                }
            )
            logger.info(f"Email sent successfully: {response['MessageId']}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send email: {e.response['Error']['Message']}")
            return False

    def send_sns_notification(self, message: str, subject: str) -> bool:
        
        if not settings.AWS_SNS_TOPIC_ARN:
            return False

        self._init_clients()

        if not self._sns_client:
            return False

        try:
            response = self._sns_client.publish(
                TopicArn=settings.AWS_SNS_TOPIC_ARN,
                Message=message,
                Subject=subject[:100]  # SNS subject limit
            )
            logger.info(f"SNS notification sent: {response['MessageId']}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send SNS notification: {e}")
            return False

    def send_alert(
        self,
        alert_type: AlertType,
        title: str,
        details: Dict[str, Any],
        severity: str = "high"
    ) -> bool:
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        
        subject = f"[{severity.upper()}] Unilever Procurement GPT - {title}"

      
        details_html = "".join(
            f"<tr><td style='padding:8px;border:1px solid #ddd;font-weight:bold;'>{k}</td>"
            f"<td style='padding:8px;border:1px solid #ddd;'>{v}</td></tr>"
            for k, v in details.items()
        )

        severity_colors = {
            "low": "#28a745",
            "medium": "#ffc107",
            "high": "#fd7e14",
            "critical": "#dc3545"
        }
        color = severity_colors.get(severity, "#6c757d")

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: {color}; color: white; padding: 15px; border-radius: 5px;">
                <h2 style="margin: 0;">{title}</h2>
                <p style="margin: 5px 0 0 0;">Severity: {severity.upper()}</p>
            </div>

            <div style="margin-top: 20px;">
                <p><strong>Alert Type:</strong> {alert_type.value}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
            </div>

            <h3>Details</h3>
            <table style="border-collapse: collapse; width: 100%;">
                {details_html}
            </table>

            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
                <p>This is an automated alert from Unilever Procurement GPT POC.</p>
                <p>Dashboard: <a href="http://localhost:3000">http://localhost:3000</a></p>
            </div>
        </body>
        </html>
        """

        # Plain text body
        details_text = "\n".join(f"  - {k}: {v}" for k, v in details.items())
        body_text = f"""
{title}
{'=' * len(title)}

Alert Type: {alert_type.value}
Severity: {severity.upper()}
Timestamp: {timestamp}

Details:
{details_text}

---
This is an automated alert from Unilever Procurement GPT POC.
Dashboard: http://localhost:3000
        """

        
        email_sent = self.send_email(subject, body_html, body_text)

       
        if settings.AWS_SNS_TOPIC_ARN:
            self.send_sns_notification(body_text, subject)

        return email_sent

    

    def alert_high_drift(
        self,
        query_id: str,
        query_text: str,
        drift_score: float,
        agent_type: str
    ) -> bool:
        
        return self.send_alert(
            alert_type=AlertType.HIGH_DRIFT,
            title="High Query Drift Detected",
            details={
                "Query ID": query_id,
                "Query": query_text[:100] + ("..." if len(query_text) > 100 else ""),
                "Drift Score": f"{drift_score:.3f}",
                "Agent": agent_type,
                "Threshold": f"{settings.DRIFT_HIGH_THRESHOLD}"
            },
            severity="high"
        )

    def alert_critical_error(
        self,
        query_id: str,
        error_category: str,
        error_message: str,
        agent_type: str
    ) -> bool:
        
        return self.send_alert(
            alert_type=AlertType.CRITICAL_ERROR,
            title=f"Critical Error: {error_category}",
            details={
                "Query ID": query_id,
                "Category": error_category,
                "Error": error_message[:200],
                "Agent": agent_type
            },
            severity="critical"
        )

    def alert_accuracy_drop(
        self,
        current_accuracy: float,
        previous_accuracy: float,
        agent_type: str,
        sample_size: int
    ) -> bool:
        
        drop = previous_accuracy - current_accuracy
        return self.send_alert(
            alert_type=AlertType.ACCURACY_DROP,
            title="Accuracy Drop Detected",
            details={
                "Agent": agent_type,
                "Current Accuracy": f"{current_accuracy:.1f}%",
                "Previous Accuracy": f"{previous_accuracy:.1f}%",
                "Drop": f"{drop:.1f}%",
                "Sample Size": sample_size
            },
            severity="high" if drop > 10 else "medium"
        )

    def alert_system_down(self, service: str, error: str) -> bool:
        
        return self.send_alert(
            alert_type=AlertType.SYSTEM_DOWN,
            title=f"Service Down: {service}",
            details={
                "Service": service,
                "Error": error,
                "Action Required": "Check service health and restart if needed"
            },
            severity="critical"
        )

    def alert_error_spike(
        self,
        error_count: int,
        time_window: str,
        top_errors: List[Dict]
    ) -> bool:
        
        top_errors_str = "; ".join(
            f"{e.get('category', 'Unknown')}: {e.get('count', 0)}"
            for e in top_errors[:3]
        )
        return self.send_alert(
            alert_type=AlertType.ERROR_SPIKE,
            title="Error Rate Spike Detected",
            details={
                "Error Count": error_count,
                "Time Window": time_window,
                "Top Errors": top_errors_str
            },
            severity="high"
        )



alert_service = AlertService()
