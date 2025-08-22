import streamlit as st
from openai import OpenAI
import time
from datetime import datetime, timedelta
import json
import re
import dns.resolver
import socket
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import random
import string
import uuid
import pytz
from typing import Optional, Dict, List, Any
import pandas as pd
import threading
import concurrent.futures

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API Key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or st.secrets.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or st.secrets.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION") or st.secrets.get("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME") or st.secrets.get("S3_BUCKET_NAME", "anisol-chatbot-data")
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL") or st.secrets.get("SES_FROM_EMAIL")
VERIFICATION_BASE_URL = os.getenv("VERIFICATION_BASE_URL") or st.secrets.get("VERIFICATION_BASE_URL", "http://localhost:8501")

# Email Report Configuration
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL") or st.secrets.get("NOTIFICATION_EMAIL", "as@aniketsolutions.com.sg")

# Timezone Configuration
COMPANY_TIMEZONE = pytz.timezone('Asia/Singapore')
UTC = pytz.UTC

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize AWS clients
s3_client = None
ses_client = None

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    
    ses_client = boto3.client(
        'ses',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

# =============================================================================
# SIMPLIFIED S3 STORAGE FUNCTION
# =============================================================================

def save_conversation_to_s3(conversation_data):
    """Simple function to save conversation transcript to S3"""
    try:
        if not s3_client:
            print("S3 client not configured")
            return False
        
        # Ensure bucket exists
        bucket_name = S3_BUCKET_NAME
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # Create bucket if it doesn't exist
                try:
                    if AWS_REGION == 'us-east-1':
                        s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                        )
                except Exception as create_error:
                    print(f"Failed to create bucket: {create_error}")
                    return False
        
        # Create S3 key with date structure
        current_time = datetime.now(UTC)
        date_str = current_time.strftime('%Y/%m/%d')
        conversation_id = conversation_data.get('conversation_id', str(uuid.uuid4()))
        s3_key = f"conversations/{date_str}/{conversation_id}.json"
        
        # Convert conversation data to JSON
        json_data = json.dumps(conversation_data, default=str, indent=2)
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        print(f"Conversation saved to S3: {s3_key}")
        return True
        
    except Exception as e:
        print(f"Error saving to S3: {e}")
        return False

# =============================================================================
# SIMPLIFIED EMAIL FUNCTION
# =============================================================================

def email_conversation_transcript(conversation_data):
    """Simple function to email conversation transcript"""
    try:
        if not ses_client:
            print("SES client not configured")
            return False
        
        # Get sender email
        sender_email = SES_FROM_EMAIL
        if not sender_email:
            try:
                response = ses_client.list_verified_email_addresses()
                verified_emails = response.get('VerifiedEmailAddresses', [])
                if verified_emails:
                    sender_email = verified_emails[0]
                else:
                    print("No verified email addresses found")
                    return False
            except Exception as e:
                print(f"Error getting verified emails: {e}")
                return False
        
        # Extract conversation details
        user_email = conversation_data.get('user_email', 'Unknown')
        start_time = conversation_data.get('start_time_singapore', 'Unknown')
        messages = conversation_data.get('messages', [])
        conversation_id = conversation_data.get('conversation_id', 'Unknown')
        
        # Calculate duration
        try:
            start_dt = datetime.fromisoformat(conversation_data.get('start_time_utc', '').replace('Z', ''))
            end_dt = datetime.fromisoformat(conversation_data.get('end_time_utc', '').replace('Z', ''))
            duration_seconds = int((end_dt - start_dt).total_seconds())
            duration = f"{duration_seconds // 60}m {duration_seconds % 60}s" if duration_seconds >= 60 else f"{duration_seconds}s"
        except:
            duration = "Unknown"
        
        # Create email subject
        subject = f"AniSol Conversation - {user_email} - {start_time.split('T')[0] if 'T' in start_time else start_time}"
        
        # Create HTML email body
        html_body = create_html_email(user_email, start_time, duration, len(messages), conversation_id, messages)
        
        # Create plain text email body
        text_body = create_text_email(user_email, start_time, duration, len(messages), conversation_id, messages)
        
        # Send email
        response = ses_client.send_email(
            Source=sender_email,
            Destination={'ToAddresses': [NOTIFICATION_EMAIL]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"Email sent successfully to {NOTIFICATION_EMAIL}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def create_html_email(user_email, start_time, duration, total_messages, conversation_id, messages):
    """Create HTML email body"""
    
    # Create messages HTML
    messages_html = ""
    for msg in messages:
        role_display = "🤖 Alex (Assistant)" if msg['role'] == 'assistant' else "👤 User"
        timestamp = msg.get('timestamp_singapore', 'Unknown')
        if 'T' in timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '')).strftime('%H:%M:%S')
        
        # Style based on role
        if msg['role'] == 'assistant':
            style = "background: #f0f8ff; border-left: 4px solid #4285f4; margin: 10px 0; padding: 15px; border-radius: 8px;"
        else:
            style = "background: #f8f9fa; border-left: 4px solid #28a745; margin: 10px 0; padding: 15px; border-radius: 8px;"
        
        messages_html += f"""
        <div style="{style}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="color: #333;">{role_display}</strong>
                <small style="color: #666;">{timestamp}</small>
            </div>
            <div style="line-height: 1.5; color: #444;">
                {msg['content'].replace('\n', '<br>')}
            </div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>AniSol Conversation Report</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">🚢 AniSol Conversation Report</h1>
            <p style="color: #f0f0f0; margin: 8px 0 0 0; font-size: 14px;">Complete Conversation Transcript</p>
        </div>
        
        <div style="background: #ffffff; padding: 25px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            
            <!-- Conversation Summary -->
            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                <h2 style="margin: 0 0 15px 0; color: #1565c0;">📋 Conversation Summary</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div>
                        <strong>User Email:</strong><br>
                        <span style="color: #666;">{user_email}</span>
                    </div>
                    <div>
                        <strong>Start Time:</strong><br>
                        <span style="color: #666;">{start_time}</span>
                    </div>
                    <div>
                        <strong>Duration:</strong><br>
                        <span style="color: #666;">{duration}</span>
                    </div>
                    <div>
                        <strong>Messages:</strong><br>
                        <span style="color: #666;">{total_messages}</span>
                    </div>
                </div>
                <div style="margin-top: 15px;">
                    <strong>Conversation ID:</strong><br>
                    <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-size: 12px;">{conversation_id}</code>
                </div>
            </div>

            <!-- Full Conversation -->
            <div style="margin-bottom: 25px;">
                <h2 style="margin: 0 0 20px 0; color: #333;">💬 Complete Conversation</h2>
                {messages_html}
            </div>

            <!-- Footer -->
            <div style="text-align: center; color: #666; font-size: 14px; border-top: 1px solid #eee; padding-top: 20px;">
                <p><strong>📧 AniSol AI Assistant</strong><br>
                Conversation transcript automatically generated<br>
                <span style="font-size: 12px;">Generated: {datetime.now(COMPANY_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')} SGT</span></p>
                
                <p style="margin: 15px 0 0 0; font-size: 13px;">
                    📞 <strong>Contact:</strong> info@aniketsolutions.com | 
                    🌐 <strong>Website:</strong> https://www.aniketsolutions.com
                </p>
            </div>
        </div>
    </body>
    </html>
    """

def create_text_email(user_email, start_time, duration, total_messages, conversation_id, messages):
    """Create plain text email body"""
    
    # Create messages text
    messages_text = ""
    for msg in messages:
        role_display = "Alex (Assistant)" if msg['role'] == 'assistant' else "User"
        timestamp = msg.get('timestamp_singapore', 'Unknown')
        if 'T' in timestamp:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '')).strftime('%H:%M:%S')
        
        messages_text += f"""
[{timestamp}] {role_display}:
{msg['content']}

{'=' * 60}
"""
    
    return f"""
AniSol Conversation Report

CONVERSATION SUMMARY:
• User Email: {user_email}
• Start Time: {start_time} 
• Duration: {duration}
• Total Messages: {total_messages}
• Conversation ID: {conversation_id}

COMPLETE CONVERSATION:
{'=' * 60}
{messages_text}

Generated automatically by AniSol AI Assistant
Contact: info@aniketsolutions.com | Website: https://www.aniketsolutions.com
    """

# =============================================================================
# SIMPLIFIED CONVERSATION MANAGER
# =============================================================================

class SimpleConversationManager:
    def __init__(self):
        self.conversation_id = str(uuid.uuid4())
        self.user_email = None
        self.messages = []
        self.start_time = datetime.now(UTC)
        
    def add_message(self, role: str, content: str):
        """Add a message to the conversation"""
        current_time = datetime.now(UTC)
        singapore_time = datetime.now(COMPANY_TIMEZONE)
        
        message = {
            'role': role,
            'content': content,
            'timestamp_utc': current_time.isoformat(),
            'timestamp_singapore': singapore_time.isoformat()
        }
        
        self.messages.append(message)
    
    def set_user_email(self, email: str):
        """Set user email"""
        self.user_email = email
    
    def get_conversation_data(self):
        """Get complete conversation data"""
        end_time = datetime.now(UTC)
        singapore_end_time = datetime.now(COMPANY_TIMEZONE)
        
        return {
            'conversation_id': self.conversation_id,
            'user_email': self.user_email,
            'start_time_utc': self.start_time.isoformat(),
            'start_time_singapore': datetime.now(COMPANY_TIMEZONE).replace(
                year=self.start_time.year, month=self.start_time.month, day=self.start_time.day,
                hour=self.start_time.hour, minute=self.start_time.minute, second=self.start_time.second
            ).isoformat(),
            'end_time_utc': end_time.isoformat(),
            'end_time_singapore': singapore_end_time.isoformat(),
            'total_messages': len(self.messages),
            'messages': self.messages,
            'created_at': datetime.now(UTC).isoformat()
        }
    
    def save_and_email_conversation(self):
        """Execute S3 save and email functions in parallel using threading"""
        conversation_data = self.get_conversation_data()
        
        # Results storage
        results = {'s3_success': False, 'email_success': False}
        
        def save_to_s3():
            """Thread function for S3 save"""
            try:
                results['s3_success'] = save_conversation_to_s3(conversation_data)
                print(f"S3 Save Thread: {'Success' if results['s3_success'] else 'Failed'}")
            except Exception as e:
                print(f"S3 Save Thread Error: {e}")
                results['s3_success'] = False
        
        def send_email():
            """Thread function for email sending"""
            try:
                results['email_success'] = email_conversation_transcript(conversation_data)
                print(f"Email Thread: {'Success' if results['email_success'] else 'Failed'}")
            except Exception as e:
                print(f"Email Thread Error: {e}")
                results['email_success'] = False
        
        # Execute both functions simultaneously using threads
        print("Starting parallel S3 save and email operations...")
        
        # Create threads
        s3_thread = threading.Thread(target=save_to_s3, name="S3-Save-Thread")
        email_thread = threading.Thread(target=send_email, name="Email-Send-Thread")
        
        # Start both threads at the same time
        start_time = time.time()
        s3_thread.start()
        email_thread.start()
        
        # Wait for both threads to complete
        s3_thread.join()
        email_thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Parallel operations completed in {total_time:.2f} seconds")
        print(f"Final Results - S3: {'Success' if results['s3_success'] else 'Failed'}, Email: {'Success' if results['email_success'] else 'Failed'}")
        
        return results['s3_success'], results['email_success']
    
    def save_and_email_conversation_async(self):
        """Alternative: Execute S3 save and email using concurrent.futures for better control"""
        conversation_data = self.get_conversation_data()
        
        print("Starting concurrent S3 save and email operations...")
        start_time = time.time()
        
        # Use ThreadPoolExecutor for better thread management
        with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="ChatBot") as executor:
            # Submit both tasks simultaneously
            s3_future = executor.submit(save_conversation_to_s3, conversation_data)
            email_future = executor.submit(email_conversation_transcript, conversation_data)
            
            # Wait for both to complete and get results
            try:
                s3_success = s3_future.result(timeout=30)  # 30 second timeout for S3
                print(f"S3 operation completed: {'Success' if s3_success else 'Failed'}")
            except Exception as e:
                print(f"S3 operation failed: {e}")
                s3_success = False
            
            try:
                email_success = email_future.result(timeout=30)  # 30 second timeout for email
                print(f"Email operation completed: {'Success' if email_success else 'Failed'}")
            except Exception as e:
                print(f"Email operation failed: {e}")
                email_success = False
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"Concurrent operations completed in {total_time:.2f} seconds")
        print(f"Final Results - S3: {'Success' if s3_success else 'Failed'}, Email: {'Success' if email_success else 'Failed'}")
        
        return s3_success, email_success

# =============================================================================
# EMAIL VALIDATION AND OTP FUNCTIONS
# =============================================================================

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp):
    """Send OTP to the provided email address using AWS SES"""
    try:
        if not ses_client:
            return False, "AWS SES not configured."
        
        sender_email = SES_FROM_EMAIL
        
        if not sender_email:
            try:
                response = ses_client.list_verified_email_addresses()
                verified_emails = response.get('VerifiedEmailAddresses', [])
                
                if verified_emails:
                    sender_email = verified_emails[0]
                else:
                    return False, "No verified email addresses found in AWS SES."
            except Exception as e:
                return False, f"Could not retrieve verified email addresses: {str(e)}"
        
        subject = "Aniket Solutions - Email Verification Code"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Email Verification - Aniket Solutions</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">Aniket Solutions</h1>
                <p style="color: #f0f0f0; margin: 10px 0 0 0; font-size: 16px;">Total Solutions Provider</p>
            </div>
            
            <div style="background: #ffffff; padding: 40px; border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h2 style="color: #333; margin-top: 0;">Email Verification Code</h2>
                
                <p>Hello,</p>
                
                <p>Thank you for your interest in Aniket Solutions! We've been providing excellent technology solutions since 2004.</p>
                
                <p>To verify your email address and continue with our consultation, please use the following verification code:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background: #f8f9fa; border: 2px solid #667eea; border-radius: 10px; padding: 20px; display: inline-block;">
                        <p style="margin: 0; color: #666; font-size: 14px;">Your Verification Code</p>
                        <h1 style="margin: 10px 0 0 0; color: #667eea; font-size: 36px; font-weight: bold; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                            {otp}
                        </h1>
                    </div>
                </div>
                
                <p style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #667eea;">
                    <strong>⏰ Important:</strong> This verification code will expire in 10 minutes for security purposes.
                </p>
                
                <p>If you did not request this verification, please ignore this email.</p>
                
                <hr style="border: none; height: 1px; background: #eee; margin: 30px 0;">
                
                <div style="text-align: center; color: #666; font-size: 14px;">
                    <p><strong>Aniket Solutions</strong><br>
                    Website: <a href="https://www.aniketsolutions.com" style="color: #667eea;">www.aniketsolutions.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
Hello,

Thank you for your interest in Aniket Solutions!

To verify your email address and continue with our consultation, please use the following verification code:

Verification Code: {otp}

This verification code will expire in 10 minutes for security purposes.

If you did not request this verification, please ignore this email.

Best regards,
Aniket Solutions Team
Website: https://www.aniketsolutions.com
        """
        
        response = ses_client.send_email(
            Source=sender_email,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        return True, f"OTP sent successfully to {email}!"
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'MessageRejected':
            return False, "Email address not verified in AWS SES."
        else:
            return False, f"AWS SES error: {e.response['Error']['Message']}"
            
    except Exception as e:
        return False, f"Failed to send OTP email: {str(e)}"

def verify_otp(entered_otp, stored_otp_data):
    """Verify OTP and check if it's still valid (10 minutes)"""
    if not stored_otp_data:
        return False, "No OTP found. Please request a new one."
    
    stored_otp = stored_otp_data.get("otp")
    timestamp = stored_otp_data.get("timestamp")
    attempts = stored_otp_data.get("attempts", 0)
    
    if not stored_otp or not timestamp:
        return False, "Invalid OTP data."
    
    if attempts >= 3:
        return False, "Too many failed attempts. Please request a new OTP."
    
    current_time = datetime.now()
    time_diff = (current_time - timestamp).total_seconds()
    
    if time_diff > 600:  # 10 minutes
        return False, "OTP has expired. Please request a new one."
    
    if entered_otp == stored_otp:
        return True, "OTP verified successfully!"
    else:
        return False, "Invalid OTP. Please try again."

def validate_email_format(email):
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.match(pattern, email) is not None

def validate_domain(domain):
    """Validate domain by checking DNS records"""
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            return True, "Domain has valid MX records"
    except dns.resolver.NXDOMAIN:
        return False, "Domain does not exist"
    except dns.resolver.NoAnswer:
        try:
            a_records = dns.resolver.resolve(domain, 'A')
            if a_records:
                return True, "Domain exists but no MX record found"
        except:
            return False, "Domain validation failed"
    except Exception as e:
        return False, f"DNS lookup error: {str(e)}"
    
    return False, "Domain validation failed"

def is_corporate_email(email):
    """Check if email is from a corporate domain (not personal email providers)"""
    personal_domains = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
        'icloud.com', 'me.com', 'mac.com', 'live.com', 'msn.com',
        'yahoo.co.uk', 'yahoo.ca', 'yahoo.com.au', 'googlemail.com',
        'protonmail.com', 'tutanota.com', 'zoho.com', 'yandex.com',
        'mail.com', 'gmx.com', 'inbox.com', 'fastmail.com'
    }
    
    domain = email.split('@')[1].lower()
    
    if domain in personal_domains:
        return False, f"'{domain}' is a personal email provider"
    
    corporate_indicators = ['.edu', '.gov', '.org']
    
    for indicator in corporate_indicators:
        if domain.endswith(indicator):
            return True, f"Domain '{domain}' appears to be institutional/corporate"
    
    if '.' in domain and len(domain.split('.')) >= 2:
        return True, f"Domain '{domain}' appears to be corporate"
    
    return False, "Unable to determine if email is corporate"

def comprehensive_email_validation(email):
    """Perform comprehensive email validation"""
    results = {
        'email': email,
        'is_valid': False,
        'format_valid': False,
        'domain_valid': False,
        'is_corporate': False,
        'messages': []
    }
    
    if not validate_email_format(email):
        results['messages'].append("❌ Invalid email format")
        return results
    
    results['format_valid'] = True
    results['messages'].append("✅ Email format is valid")
    
    try:
        domain = email.split('@')[1].lower()
    except IndexError:
        results['messages'].append("❌ Could not extract domain")
        return results
    
    domain_valid, domain_message = validate_domain(domain)
    results['domain_valid'] = domain_valid
    
    if domain_valid:
        results['messages'].append(f"✅ {domain_message}")
    else:
        results['messages'].append(f"❌ {domain_message}")
        return results
    
    is_corp, corp_message = is_corporate_email(email)
    results['is_corporate'] = is_corp
    
    if is_corp:
        results['messages'].append(f"✅ {corp_message}")
    else:
        results['messages'].append(f"❌ {corp_message}")
    
    results['is_valid'] = results['format_valid'] and results['domain_valid'] and results['is_corporate']
    
    return results

# =============================================================================
# UNIVERSAL KNOWLEDGE AI RESPONSE
# =============================================================================

def generate_smart_response(user_message):
    """Generate smart response using OpenAI with UNIVERSAL knowledge of ALL products and services."""
    try:
        if st.session_state.get("openai_client"):
            system_prompt = """
You are Alex, a senior technology consultant at Aniket Solutions. You have COMPLETE knowledge of ALL our offerings and can answer ANY question about maritime products OR technology services, regardless of what the user initially selected.

COMPLETE ANIKET SOLUTIONS PORTFOLIO:

🚢 MARITIME SOFTWARE PRODUCTS:

**AniSol TMS (Technical Management System)**
- Comprehensive maintenance scheduling and planning with automated workflows
- Inspection tracking with automated reminders and compliance monitoring
- Certificate management with expiry alerts and renewal tracking
- Regulatory compliance monitoring (ISM, ISO, MLC, SOLAS)
- Work order management and resource allocation
- Technical documentation and drawings management
- Performance analytics and KPI dashboards with real-time reporting
- Integration with classification societies and port state control
- Spare parts integration for maintenance planning
- Crew competency tracking for maintenance tasks

**AniSol Procurement - AI-Powered Maritime Purchasing**
- Intelligent purchase requisition automation with AI-driven recommendations
- Multi-level approval workflows with role-based permissions
- Vendor management with performance scoring and evaluation
- ShipServ marketplace integration for global sourcing
- Price comparison and negotiation tools with market intelligence
- Contract management and compliance tracking
- Spend analytics and cost optimization with predictive insights
- Emergency procurement workflows for port calls
- Integration with inventory management for automated reordering
- Budget management and financial controls

**AniSol Inventory Control - Fleet-Wide Management**
- Real-time inventory tracking across all vessels and locations
- Automated reordering based on consumption patterns and lead times
- Spare parts catalog with detailed technical specifications
- Critical spares monitoring with safety stock alerts
- Multi-location warehouse management with transfer capabilities
- Barcode/RFID integration for efficient tracking
- Comprehensive audit trails and stock reconciliation
- Cost center allocation and detailed reporting
- Integration with procurement and maintenance systems
- Obsolescence management and lifecycle tracking

**AniSol Crewing Module - Complete Crew Management**
- Crew planning and rotation scheduling with optimization algorithms
- Certificate and license tracking with automated expiry alerts
- Medical certificate management and health monitoring
- Training records and competency matrix management
- Performance evaluation and analytics with KPI tracking
- Visa and travel document management with renewal alerts
- Crew welfare programs and family communication systems
- Integration with manning agencies and recruitment partners
- Payroll integration for seamless financial management
- Compliance tracking for MLC, STCW, and flag state requirements

**AniSol Payroll & Master Cash - Crew Financial Management**
- Multi-currency payroll processing with real-time exchange rates
- Allotment management for crew families with bank integration
- Tax compliance across multiple jurisdictions
- Cash advance tracking and reconciliation
- Overtime calculation and approval workflows
- Benefits administration and pension management
- Financial reporting and analytics with cost center allocation
- Bank integration for direct payments and transfers
- Mobile access for crew to view pay statements and balances
- Integration with crewing module for seamless data flow

💻 TECHNOLOGY SERVICES:

**Custom Application Development**
- Enterprise software architecture and development using modern frameworks
- Legacy system modernization and cloud migration strategies
- Cloud-native application development with microservices architecture
- Database design, optimization, and performance tuning
- Security implementation and compliance (SOC 2, ISO 27001)
- Performance optimization and scalability planning
- DevOps and CI/CD pipeline setup with automated testing
- API development and integration services
- Mobile-responsive web applications
- Quality assurance and testing automation

**Mobile Solutions**
- Native iOS and Android development with platform-specific optimizations
- Cross-platform solutions using React Native and Flutter
- Offline-first mobile applications with data synchronization
- Enterprise mobile app management and security
- Mobile device management (MDM) solutions
- App store deployment and maintenance
- Mobile analytics and user experience optimization
- Integration with enterprise backend systems and APIs
- Maritime-specific mobile apps (crew apps, inventory scanning, maintenance reporting)
- Push notifications and real-time communication features

**AI & Machine Learning Services**
- Predictive maintenance algorithms for maritime equipment
- Natural language processing for document automation
- Computer vision and image recognition for inspections
- Intelligent document processing and data extraction
- Chatbots and virtual assistants for customer service
- Machine learning model development and deployment
- AI strategy consulting and implementation roadmaps
- Data science and analytics platforms
- Recommendation engines for procurement and inventory
- Anomaly detection for operational monitoring

**Data Services & Migration**
- Database migration and modernization projects
- Data warehouse design and implementation
- Business intelligence and reporting solutions with interactive dashboards
- ETL/ELT pipeline development and automation
- Data quality management and governance frameworks
- Real-time analytics and operational dashboards
- Big data processing and storage solutions
- Data lake architecture and implementation
- Master data management and data integration
- Compliance reporting and regulatory data management

**System Integration Services**
- Enterprise application integration with seamless data flow
- API development and management platforms
- Hybrid cloud-premise connectivity solutions
- Third-party system integration and middleware
- Workflow automation and business process orchestration
- Event-driven architecture implementation
- Message queuing and real-time processing
- Integration testing and monitoring tools
- Legacy system connectivity and modernization
- B2B integration and electronic data interchange (EDI)

**AI Chatbots & Virtual Assistants**
- Conversational AI development with natural language understanding
- Multi-channel deployment (web, mobile, messaging platforms, voice)
- Intent recognition and response generation with machine learning
- Integration with knowledge bases and enterprise systems
- Analytics and conversation optimization with performance insights
- Voice assistant development and speech recognition
- Multilingual support and localization capabilities
- 24/7 automated customer support and service desk
- Maritime-specific chatbots for crew support and operational queries
- Escalation workflows to human agents when needed

INTEGRATION CAPABILITIES:
- All maritime products integrate seamlessly with each other
- Technology services can enhance and extend maritime product capabilities
- Custom mobile apps can be built to integrate with AniSol maritime systems
- AI services can be integrated into existing maritime workflows
- Chatbots can provide support for maritime operations and crew

CRITICAL INSTRUCTIONS:
1. Answer ANY question about ANY product or service - completely ignore any initial category selection
2. For customer support/chatbot questions → discuss our AI Chatbots & Virtual Assistants service
3. For mobile app questions → discuss our Mobile Solutions service and maritime app integrations
4. For custom software questions → discuss our Custom Development service
5. For maritime operational questions → discuss relevant AniSol products
6. For AI/ML questions → discuss our AI & Machine Learning services
7. ALWAYS cross-reference when relevant (e.g., "We can integrate chatbots with your AniSol maritime systems")
8. Provide specific technical details and business benefits
9. Include contact info@aniketsolutions.com for detailed consultation
10. Be conversational and helpful - address exactly what the user asks
11. If asked about pricing, implementation, or demos, provide helpful guidance and direct to contact for personalized consultation

REMEMBER: You have universal knowledge and can discuss ALL products and services in any conversation!
"""
            
            # Include comprehensive conversation history for better context
            messages_to_send = [{"role": "system", "content": system_prompt}]

            # Get last 10 messages for context
            recent_history = [
                {"role": msg["role"], "content": msg["content"]} 
                for msg in st.session_state.messages[-10:]
            ]
            
            messages_to_send.extend(recent_history)
            
            response = st.session_state.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages_to_send,
                temperature=0.3,
                max_tokens=800,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            return response.choices[0].message.content.strip()
        
        return "I can help you with any questions about our maritime software products or technology services. Contact info@aniketsolutions.com for detailed consultation."
        
    except Exception as e:
        print(f"Error in generate_smart_response: {e}")
        return "For information about any of our maritime products or technology services, contact info@aniketsolutions.com"

# =============================================================================
# SIMPLIFIED HELPER FUNCTIONS
# =============================================================================

def add_message_to_chat(role, content, timestamp=None):
    """Add message to chat and conversation manager"""
    if timestamp is None:
        timestamp = datetime.now(COMPANY_TIMEZONE).strftime("%H:%M")
    
    # Save to session state for display
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })
    
    # Save to conversation manager
    if "conversation_manager" in st.session_state:
        st.session_state.conversation_manager.add_message(role, content)

def update_user_activity():
    """Update the last user activity timestamp"""
    st.session_state.last_user_activity = datetime.now()

def check_conversation_flow():
    """Check conversation flow with proactive engagement and graceful ending"""
    if "last_user_activity" not in st.session_state:
        st.session_state.last_user_activity = datetime.now()
        st.session_state.conversation_ended = False
        st.session_state.asked_for_more_questions = False
        return False
    
    current_time = datetime.now()
    
    # Check if conversation has already ended
    if st.session_state.get("conversation_ended"):
        return True
    
    # Skip inactivity check if still in initial flow
    if (st.session_state.conversation_flow.get("awaiting_email") or 
        st.session_state.conversation_flow.get("awaiting_otp") or 
        st.session_state.conversation_flow.get("awaiting_selection")):
        return False
    
    # Check if we're in the middle of a business conversation
    if st.session_state.conversation_flow.get("otp_verified"):
        time_since_activity = current_time - st.session_state.last_user_activity
        
        # First warning at 3 minutes - ask if they have more questions
        if (time_since_activity.total_seconds() > 180 and  # 3 minutes
            not st.session_state.get("asked_for_more_questions")):
            
            st.session_state.asked_for_more_questions = True
            st.session_state.follow_up_time = current_time
            
            add_message_to_chat("assistant", 
                "Is there anything else I can help you with regarding our maritime products or technology services?")
            
            return False
        
        # Final timeout at 6 minutes total (3 min + 3 min after follow-up)
        elif (st.session_state.get("asked_for_more_questions") and 
              time_since_activity.total_seconds() > 360):  # 6 minutes total
            
            st.session_state.conversation_ended = True
            
            # Add graceful ending message
            add_message_to_chat("assistant", 
                "Thank you for your time! It was great discussing our solutions with you. This conversation has been completed and saved. You'll receive a copy via email shortly. Have a wonderful day!")
            
            # PARALLEL EXECUTION: Save to S3 and email transcript simultaneously
            if "conversation_manager" in st.session_state:
                s3_success, email_success = st.session_state.conversation_manager.save_and_email_conversation()
                print(f"Parallel Operations - S3: {'Success' if s3_success else 'Failed'}, Email: {'Success' if email_success else 'Failed'}")
                
                # Optional: Use the alternative async method
                # s3_success, email_success = st.session_state.conversation_manager.save_and_email_conversation_async()
            
            return True
    
    return False

def auto_restart_conversation():
    """Automatically restart conversation after completion"""
    # Clear all session state and restart
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def add_initial_greeting():
    """Add initial greeting message"""
    greeting_message = """Hi! I'm Alex from Aniket Solutions. I can help you with any questions about our maritime software products OR technology services. Please share your corporate email to get started."""
    
    timestamp = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({
        "role": "assistant",
        "content": greeting_message,
        "timestamp": timestamp
    })

def handle_email_validation_flow(email, validation_result):
    """Handle the flow after email validation"""
    if validation_result['is_valid']:
        validation_response = "✅ Email validated successfully."
        add_message_to_chat("assistant", validation_response)
        
        # Update conversation manager with email
        if "conversation_manager" in st.session_state:
            st.session_state.conversation_manager.set_user_email(email)
        
        otp = generate_otp()
        success, message = send_otp_email(email, otp)
        
        if success:
            st.session_state.otp_data = {
                "otp": otp,
                "email": email,
                "timestamp": datetime.now(),
                "attempts": 0
            }
            
            st.session_state.conversation_flow["email_validated"] = True
            st.session_state.conversation_flow["awaiting_email"] = False
            st.session_state.conversation_flow["awaiting_otp"] = True
            
            add_message_to_chat("assistant", 
                f"I've sent a 6-digit code to {email}. Please enter it below to continue. Code expires in 10 minutes."
            )
            return True
        else:
            add_message_to_chat("assistant", 
                f"Email validation successful, but couldn't send verification code: {message}")
            return False
    else:
        validation_response = f"""Email validation failed:

{chr(10).join(validation_result['messages'])}

Please provide a valid corporate email address."""
        
        add_message_to_chat("assistant", validation_response)
        return False

# =============================================================================
# STREAMLIT APP CONFIGURATION
# =============================================================================

# Configure the page
st.set_page_config(
    page_title="Aniket Solutions - AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    /* Hide sidebar completely */
    .css-1d391kg, .css-1rs6os, .css-17eq0hr, section[data-testid="stSidebar"], div[data-testid="stSidebarNav"] {
        display: none !important;
    }
    
    /* Fix main app container */
    .stApp {
        max-width: 800px;
        margin: 0 auto;
        padding-top: 1rem !important;
    }
    
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 800px;
    }
    
    /* Hide Streamlit header */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* Chat message styling */
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    
    .chat-message.user {
        background-color: #e3f2fd;
        margin-left: 10%;
    }
    
    .chat-message.assistant {
        background-color: #f5f5f5;
        margin-right: 10%;
    }
    
    /* Button styling */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        border: 2px solid #667eea;
        background-color: white;
        color: #667eea;
        font-weight: bold;
        padding: 0.75rem 1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #667eea;
        color: white;
        border-color: #667eea;
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }
    
    /* Conversation ended styling */
    .conversation-ended {
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        border: 2px solid #4caf50;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2);
    }
    
    .conversation-ended h3 {
        color: #2e7d32;
        margin-bottom: 15px;
        font-size: 1.5rem;
    }
    
    .conversation-ended p {
        color: #388e3c;
        margin-bottom: 15px;
        font-size: 1.1rem;
    }

    /* Universal knowledge indicator */
    .universal-indicator {
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        border: 2px solid #4caf50;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
    }
    
    .universal-indicator h4 {
        color: #2e7d32;
        margin: 0 0 5px 0;
    }
    
    .universal-indicator p {
        color: #388e3c;
        margin: 0;
        font-size: 14px;
    }

    /* Auto-restart indicator */
    .auto-restart-indicator {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc02 100%);
        border: 2px solid #ff9800;
        border-radius: 10px;
        padding: 15px;
        margin: 15px 0;
        text-align: center;
        animation: pulse 2s infinite;
    }
    
    .auto-restart-indicator h4 {
        color: #f57c00;
        margin: 0 0 5px 0;
    }
    
    .auto-restart-indicator p {
        color: #ef6c00;
        margin: 0;
        font-size: 14px;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
    }
</style>
""", unsafe_allow_html=True)

# Avatar Configuration
ALEX_AVATAR_URL = "https://raw.githubusercontent.com/AShirsat96/WebsiteChatbot/main/Alex_AI_Avatar.png"
USER_AVATAR_URL = "https://api.dicebear.com/7.x/initials/svg?seed=User&backgroundColor=4f46e5&fontSize=40"

# =============================================================================
# MAIN APP INITIALIZATION
# =============================================================================

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_key" not in st.session_state:
    if OPENAI_API_KEY:
        st.session_state.api_key = OPENAI_API_KEY
    else:
        st.session_state.api_key = ""

if "openai_client" not in st.session_state:
    if OPENAI_API_KEY:
        st.session_state.openai_client = client
    else:
        st.session_state.openai_client = None

# Conversation flow state
if "conversation_flow" not in st.session_state:
    st.session_state.conversation_flow = {
        "email_validated": False,
        "awaiting_email": True,
        "awaiting_otp": False,
        "otp_verified": False,
        "awaiting_selection": False
    }

if "otp_data" not in st.session_state:
    st.session_state.otp_data = None

# Activity tracking
if "last_user_activity" not in st.session_state:
    st.session_state.last_user_activity = datetime.now()

if "conversation_ended" not in st.session_state:
    st.session_state.conversation_ended = False

if "asked_for_more_questions" not in st.session_state:
    st.session_state.asked_for_more_questions = False

# SIMPLIFIED: Initialize conversation manager
if "conversation_manager" not in st.session_state:
    st.session_state.conversation_manager = SimpleConversationManager()

# Check conversation flow
conversation_ended = check_conversation_flow()

# Add initial greeting if messages is empty
if len(st.session_state.messages) == 0:
    add_initial_greeting()

# If conversation has ended, show completion message and auto-restart
if conversation_ended:
    st.markdown("""
    <div class="conversation-ended">
        <h3>✅ Conversation Completed</h3>
        <p>Thank you for your time! Your conversation has been saved and you'll receive a copy via email.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-restart indicator
    st.markdown("""
    <div class="auto-restart-indicator">
        <h4>🔄 Starting New Session</h4>
        <p>Automatically restarting in 3 seconds...</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-restart after 3 seconds
    time.sleep(3)
    auto_restart_conversation()

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Universal Knowledge Indicator
    st.markdown("""
    <div class="universal-indicator">
        <h4>🧠 Universal Knowledge Mode</h4>
        <p>AI can answer questions about ALL products and services</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Conversation status
    if st.session_state.conversation_flow.get("otp_verified"):
        time_since_activity = datetime.now() - st.session_state.last_user_activity
        minutes_inactive = int(time_since_activity.total_seconds() // 60)
        
        if minutes_inactive >= 3 and not st.session_state.get("asked_for_more_questions"):
            st.warning("💬 Just asked if you have more questions!")
        elif st.session_state.get("asked_for_more_questions"):
            st.info("⏰ Conversation will end in ~3 minutes if no response")
        else:
            st.success(f"✅ Active conversation ({minutes_inactive}m inactive)")
    
    st.divider()
    
    # OpenAI Configuration
    if not OPENAI_API_KEY:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.api_key,
            help="Enter your OpenAI API key to enable the chat assistant"
        )
        
        if api_key:
            st.session_state.api_key = api_key
            st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.success("✅ API Key configured")
    
    st.divider()
    
    # AWS Configuration Status
    st.subheader("☁️ AWS Configuration")
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        st.error("❌ AWS credentials not configured")
    else:
        st.success("✅ AWS credentials configured")
        if S3_BUCKET_NAME:
            st.success(f"📦 S3 Bucket: {S3_BUCKET_NAME}")
        if SES_FROM_EMAIL:
            st.success(f"📧 Sender email: {SES_FROM_EMAIL}")
        st.success(f"📬 Notification: {NOTIFICATION_EMAIL}")
    
    st.divider()
    
    st.subheader("🚀 System Status")
    st.success("✅ Simplified S3 & Email functions")
    st.success("✅ Proactive engagement (3min)")
    st.success("✅ Auto-restart after completion")

# Main chat interface
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        message_class = "user" if message["role"] == "user" else "assistant"
        timestamp = message.get("timestamp", "")
        
        if message["role"] == "user":
            sender_name = "You"
            avatar_url = USER_AVATAR_URL
        else:
            sender_name = "Alex"
            avatar_url = ALEX_AVATAR_URL
        
        st.markdown(f"""
        <div class="chat-message {message_class}">
            <div style="display: flex; align-items: flex-start; gap: 12px; margin-bottom: 8px;">
                <img src="{avatar_url}" style="width: 45px; height: 45px; border-radius: 50%; border: 2px solid #e0e0e0; flex-shrink: 0;">
                <div style="flex: 1; min-width: 0;">
                    <div class="sender-name" style="font-weight: bold; color: #333; font-size: 0.9rem; margin-bottom: 2px;">{sender_name}</div>
                    <div class="message-time" style="font-size: 0.8rem; color: #666; margin-bottom: 6px;">{timestamp}</div>
                    <div class="message-content" style="line-height: 1.5; word-wrap: break-word;">{message["content"]}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Handle conversation flow
if st.session_state.conversation_flow["awaiting_email"]:
    st.markdown("---")
    st.markdown("**Please enter your corporate email address:**")
    
    email_input = st.text_input(
        "Email Address",
        placeholder="your.email@company.com",
        key="email_flow_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Submit", key="submit_email_flow"):
            if email_input.strip():
                update_user_activity()
                add_message_to_chat("user", email_input)
                
                with st.spinner("Validating email..."):
                    validation_result = comprehensive_email_validation(email_input.strip())
                    
                    if handle_email_validation_flow(email_input.strip(), validation_result):
                        st.rerun()
                    else:
                        st.rerun()
            else:
                st.warning("Please enter an email address")

elif st.session_state.conversation_flow["awaiting_otp"]:
    st.markdown("---")
    st.markdown("**📧 Verification Code Sent**")
    
    otp_data = st.session_state.otp_data
    if otp_data:
        st.info(f"""
        We've sent a 6-digit verification code to **{otp_data['email']}**
        
        Please check your email and enter the code below.
        """)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            otp_input = st.text_input(
                "Enter 6-digit verification code:",
                placeholder="123456",
                max_chars=6,
                key="otp_input"
            )
        
        with col2:
            if st.button("✅ Verify", key="verify_otp", use_container_width=True):
                if otp_input.strip() and len(otp_input.strip()) == 6:
                    update_user_activity()
                    add_message_to_chat("user", f"Entered verification code: {otp_input}")
                    
                    is_valid, message = verify_otp(otp_input.strip(), st.session_state.otp_data)
                    
                    if is_valid:
                        add_message_to_chat("assistant", "✅ Email verified! What would you like to explore? (I can answer questions about ALL our products and services)")
                        
                        st.session_state.conversation_flow["awaiting_otp"] = False
                        st.session_state.conversation_flow["otp_verified"] = True
                        st.session_state.conversation_flow["awaiting_selection"] = True
                        
                        st.rerun()
                    else:
                        st.session_state.otp_data["attempts"] = st.session_state.otp_data.get("attempts", 0) + 1
                        add_message_to_chat("assistant", f"❌ {message}")
                        
                        if st.session_state.otp_data["attempts"] >= 3:
                            add_message_to_chat("assistant", 
                                "Too many failed attempts. Please request a new verification code.")
                            st.session_state.otp_data = None
                            st.session_state.conversation_flow["awaiting_otp"] = False
                            st.session_state.conversation_flow["awaiting_email"] = True
                        
                        st.rerun()
                else:
                    st.warning("Please enter a valid 6-digit code")
        
        with col3:
            if st.button("📧 Resend", key="resend_otp", use_container_width=True):
                update_user_activity()
                
                otp_data = st.session_state.otp_data
                if otp_data:
                    new_otp = generate_otp()
                    success, message = send_otp_email(otp_data["email"], new_otp)
                    
                    if success:
                        st.session_state.otp_data = {
                            "otp": new_otp,
                            "email": otp_data["email"],
                            "timestamp": datetime.now(),
                            "attempts": 0
                        }
                        add_message_to_chat("assistant", "📧 New verification code sent!")
                        st.success("New code sent!")
                    else:
                        add_message_to_chat("assistant", f"❌ Failed to resend: {message}")
                        st.error(f"Failed to resend: {message}")
                    st.rerun()

elif st.session_state.conversation_flow["awaiting_selection"]:
    st.markdown("---")
    st.markdown("**What would you like to explore first?**")
    
    # Universal knowledge indicator
    st.markdown("""
    <div class="universal-indicator">
        <h4>🧠 Universal Knowledge</h4>
        <p>I can answer questions about ALL our products and services throughout our conversation!</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚢 Start with Maritime Products", key="select_products", use_container_width=True):
            update_user_activity()
            add_message_to_chat("user", "I'd like to learn about your maritime products")
            
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            products_overview = """Perfect! Our AniSol Maritime Software Suite includes:

🚢 **AniSol TMS** - Technical Management System for maintenance, inspections, and compliance
🛒 **AniSol Procurement** - AI-powered purchasing and vendor management  
📦 **AniSol Inventory Control** - Fleet-wide inventory with automated reordering
👥 **AniSol Crewing Module** - Complete crew lifecycle management
💰 **AniSol Payroll & Master Cash** - Multi-currency crew financial management

💡 **Remember**: I can also help with technology services like AI chatbots, mobile apps, custom development, and system integration. What specific area interests you most?"""
            
            add_message_to_chat("assistant", products_overview)
            st.rerun()
    
    with col2:
        if st.button("💻 Start with Technology Services", key="select_services", use_container_width=True):
            update_user_activity()
            add_message_to_chat("user", "I'd like to learn about your technology services")
            
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            services_overview = """Excellent! Our Technology Services include:

💻 **Custom Development** - Enterprise software and legacy modernization
📱 **Mobile Solutions** - Native iOS/Android apps with maritime integration
🤖 **AI & Machine Learning** - Intelligent automation and predictive analytics
🤖 **AI Chatbots & Virtual Assistants** - Customer support automation
📊 **Data Services** - Migration, analytics, and business intelligence
🔗 **System Integration** - API development and enterprise connectivity

💡 **Remember**: I can also discuss our maritime products and how they integrate with our technology services. What challenge can I help you solve?"""
            
            add_message_to_chat("assistant", services_overview)
            st.rerun()

# Chat input (only show after category selection or OTP verification)
if (not st.session_state.conversation_flow["awaiting_email"] and 
    not st.session_state.conversation_flow["awaiting_otp"] and
    not st.session_state.conversation_flow["awaiting_selection"]):
    
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        
        with col1:
            user_input = st.text_input(
                "Message",
                placeholder="Ask about any maritime product or technology service...",
                label_visibility="collapsed"
            )
        
        with col2:
            send_button = st.form_submit_button("Send", use_container_width=True)

    if send_button and user_input.strip():
        if not st.session_state.api_key:
            st.error("Please configure your OpenAI API key to start chatting.")
        else:
            update_user_activity()
            add_message_to_chat("user", user_input)
            
            with st.spinner("Thinking..."):
                try:
                    ai_response = generate_smart_response(user_input)
                    add_message_to_chat("assistant", ai_response)
                    st.rerun()
                    
                except Exception as e:
                    fallback_response = "I can help you with any questions about our maritime products or technology services. Contact info@aniketsolutions.com for detailed consultation."
                    add_message_to_chat("assistant", fallback_response)
                    st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "Powered by Aniket Solutions - Simplified S3 & Email Functions"
    "</div>",
    unsafe_allow_html=True
)
