"""
Test AWS SES/SNS Alert Configuration
Run this script to verify your AWS setup is working.
"""
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os

load_dotenv("/home/lenovo/Desktop/New_tech_demo/.env")

# Load credentials from environment
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
SENDER_EMAIL = os.getenv("AWS_SES_SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("ALERT_RECIPIENT_EMAILS")
SNS_TOPIC_ARN = os.getenv("AWS_SNS_TOPIC_ARN")

print("=" * 60)
print("AWS Alert Configuration Test")
print("=" * 60)
print(f"Region: {AWS_REGION}")
print(f"Sender Email: {SENDER_EMAIL}")
print(f"Recipient Email: {RECIPIENT_EMAIL}")
print(f"SNS Topic ARN: {SNS_TOPIC_ARN}")
print("=" * 60)

# Initialize clients
ses_client = boto3.client(
    'ses',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

sns_client = boto3.client(
    'sns',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Test 1: Check SES identity verification status
print("\n[TEST 1] Checking SES Email Verification Status...")
try:
    response = ses_client.get_identity_verification_attributes(
        Identities=[SENDER_EMAIL]
    )
    status = response['VerificationAttributes'].get(SENDER_EMAIL, {}).get('VerificationStatus', 'Not Found')
    print(f"  Email: {SENDER_EMAIL}")
    print(f"  Status: {status}")

    if status != 'Success':
        print("\n  [ACTION REQUIRED] Email not verified!")
        print("  Sending verification email...")
        try:
            ses_client.verify_email_identity(EmailAddress=SENDER_EMAIL)
            print(f"  Verification email sent to {SENDER_EMAIL}")
            print("  Please check your inbox and click the verification link.")
        except ClientError as e:
            print(f"  Error sending verification: {e}")
    else:
        print("  Email is verified!")
except ClientError as e:
    print(f"  Error: {e}")

# Test 2: Check SNS Topic
print("\n[TEST 2] Checking SNS Topic...")
try:
    response = sns_client.get_topic_attributes(TopicArn=SNS_TOPIC_ARN)
    print(f"  Topic ARN: {SNS_TOPIC_ARN}")
    print(f"  Topic exists!")

    # List subscriptions
    subs = sns_client.list_subscriptions_by_topic(TopicArn=SNS_TOPIC_ARN)
    print(f"  Subscriptions: {len(subs.get('Subscriptions', []))}")
    for sub in subs.get('Subscriptions', []):
        print(f"    - {sub.get('Protocol')}: {sub.get('Endpoint')} ({sub.get('SubscriptionArn', 'pending')})")
except ClientError as e:
    print(f"  Error: {e}")

# Test 3: Send test SNS notification
print("\n[TEST 3] Sending Test SNS Notification...")
try:
    response = sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Message="This is a test alert from Unilever Procurement GPT POC.\n\nIf you received this, your SNS alerts are working correctly!",
        Subject="[TEST] Unilever Procurement GPT - Alert System Test"
    )
    print(f"  Message sent! MessageId: {response['MessageId']}")
except ClientError as e:
    print(f"  Error: {e}")

# Test 4: Send test SES email (only if verified)
print("\n[TEST 4] Sending Test SES Email...")
try:
    # Check verification status first
    response = ses_client.get_identity_verification_attributes(Identities=[SENDER_EMAIL])
    status = response['VerificationAttributes'].get(SENDER_EMAIL, {}).get('VerificationStatus', 'Not Found')

    if status == 'Success':
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': [RECIPIENT_EMAIL]},
            Message={
                'Subject': {'Data': '[TEST] Unilever Procurement GPT - Email Alert Test', 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {
                        'Data': 'This is a test email from Unilever Procurement GPT POC.\n\nIf you received this, your SES email alerts are working correctly!',
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': '''
                        <html>
                        <body style="font-family: Arial, sans-serif; padding: 20px;">
                            <div style="background: #28a745; color: white; padding: 15px; border-radius: 5px;">
                                <h2 style="margin: 0;">Alert System Test</h2>
                                <p style="margin: 5px 0 0 0;">Severity: TEST</p>
                            </div>
                            <div style="margin-top: 20px;">
                                <p>This is a test email from <strong>Unilever Procurement GPT POC</strong>.</p>
                                <p>If you received this, your SES email alerts are working correctly!</p>
                            </div>
                            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
                                <p>This is an automated test from Unilever Procurement GPT POC.</p>
                            </div>
                        </body>
                        </html>
                        ''',
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print(f"  Email sent! MessageId: {response['MessageId']}")
    else:
        print(f"  Skipped - Email not verified yet (Status: {status})")
        print("  Please verify your email first, then run this test again.")
except ClientError as e:
    error_code = e.response['Error']['Code']
    error_msg = e.response['Error']['Message']
    print(f"  Error [{error_code}]: {error_msg}")

    if 'not verified' in error_msg.lower():
        print("\n  [ACTION REQUIRED] Please verify your sender email in AWS SES:")
        print(f"  1. Check inbox of {SENDER_EMAIL}")
        print("  2. Click the verification link from AWS")
        print("  3. Run this test again")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
