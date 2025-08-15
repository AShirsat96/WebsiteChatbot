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
# S3 STORAGE MANAGER
# =============================================================================

class S3StorageManager:
    def __init__(self):
        self.bucket_name = S3_BUCKET_NAME
        self.s3_client = s3_client
        self.bucket_exists = False
        
    def ensure_bucket_exists(self):
        """Ensure S3 bucket exists, create if it doesn't"""
        try:
            if not self.s3_client:
                return False
            
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                self.bucket_exists = True
                return True
            except ClientError as e:
                error_code = int(e.response['Error']['Code'])
                if error_code == 404:
                    # Bucket doesn't exist, create it
                    try:
                        if AWS_REGION == 'us-east-1':
                            self.s3_client.create_bucket(Bucket=self.bucket_name)
                        else:
                            self.s3_client.create_bucket(
                                Bucket=self.bucket_name,
                                CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                            )
                        
                        self.bucket_exists = True
                        return True
                    except Exception as create_error:
                        return False
                else:
                    return False
            
        except Exception as e:
            return False
    
    def save_json(self, key: str, data: dict):
        """Save JSON data to S3"""
        try:
            if not self.s3_client or not self.bucket_exists:
                if not self.ensure_bucket_exists():
                    return False
            
            json_data = json.dumps(data, default=str, indent=2)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_data,
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return True
            
        except Exception as e:
            return False

# =============================================================================
# CONVERSATION STORAGE AND EMAIL MANAGER
# =============================================================================

class ConversationManager:
    def __init__(self):
        self.s3_manager = S3StorageManager()
        self.current_conversation_id = None
        self.conversation_data = {}
        self.messages = []
    
    def get_current_time_utc(self):
        """Get current time in UTC"""
        return datetime.now(UTC)
    
    def get_singapore_time(self):
        """Get current time in Singapore timezone"""
        return datetime.now(COMPANY_TIMEZONE)
    
    def start_new_conversation(self, session_id: str):
        """Start a new conversation record"""
        try:
            self.current_conversation_id = str(uuid.uuid4())
            current_time = self.get_current_time_utc()
            
            self.conversation_data = {
                'conversation_id': self.current_conversation_id,
                'session_id': session_id,
                'start_time_utc': current_time.isoformat(),
                'start_time_singapore': self.get_singapore_time().isoformat(),
                'user_email': None,
                'end_time_utc': None,
                'is_completed': False,
                'messages': [],
                'created_at': current_time.isoformat()
            }
            
            self.messages = []
            return self.current_conversation_id
            
        except Exception as e:
            return None
    
    def add_message(self, role: str, content: str):
        """Add a message to the current conversation"""
        try:
            if not self.current_conversation_id:
                return False
            
            current_time = self.get_current_time_utc()
            
            message = {
                'role': role,
                'content': content,
                'timestamp_utc': current_time.isoformat(),
                'timestamp_singapore': self.get_singapore_time().isoformat()
            }
            
            self.messages.append(message)
            self.conversation_data['messages'] = self.messages
            
            return True
            
        except Exception as e:
            return False
    
    def update_user_email(self, email: str):
        """Update user email for current conversation"""
        try:
            if self.conversation_data:
                self.conversation_data['user_email'] = email
                return True
            return False
        except Exception as e:
            return False
    
    def complete_conversation(self):
        """Complete the conversation: save to S3 and send email"""
        try:
            if not self.current_conversation_id or not self.conversation_data:
                return False
            
            current_time = self.get_current_time_utc()
            
            # Mark conversation as completed
            self.conversation_data.update({
                'end_time_utc': current_time.isoformat(),
                'end_time_singapore': self.get_singapore_time().isoformat(),
                'is_completed': True,
                'total_messages': len(self.messages)
            })
            
            # Save to S3
            date_str = current_time.strftime('%Y/%m/%d')
            s3_key = f"conversations/{date_str}/{self.current_conversation_id}.json"
            s3_saved = self.s3_manager.save_json(s3_key, self.conversation_data)
            
            if s3_saved:
                # Send email with entire conversation
                email_sent = self.send_conversation_email()
                
                # Clear current conversation
                conversation_id = self.current_conversation_id
                self.current_conversation_id = None
                self.conversation_data = {}
                self.messages = []
                
                return email_sent
            
            return False
            
        except Exception as e:
            return False
    
    def send_conversation_email(self):
        """Send email with the complete conversation"""
        try:
            if not ses_client or not self.conversation_data:
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
                        return False
                except Exception as e:
                    return False
            
            # Create email subject
            user_email = self.conversation_data.get('user_email', 'Unknown')
            start_time = datetime.fromisoformat(self.conversation_data['start_time_singapore'].replace('Z', ''))
            subject = f"AniSol Conversation - {user_email} - {start_time.strftime('%Y-%m-%d %H:%M')}"
            
            # Create conversation summary
            total_messages = len(self.messages)
            duration = self.calculate_conversation_duration()
            
            # Create HTML email with full conversation
            html_body = self.create_conversation_email_html(subject, duration, total_messages)
            text_body = self.create_conversation_email_text(subject, duration, total_messages)
            
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
            
            return True
            
        except Exception as e:
            return False
    
    def calculate_conversation_duration(self):
        """Calculate conversation duration"""
        try:
            start_time = datetime.fromisoformat(self.conversation_data['start_time_utc'].replace('Z', ''))
            end_time = datetime.fromisoformat(self.conversation_data['end_time_utc'].replace('Z', ''))
            duration = end_time - start_time
            
            total_seconds = int(duration.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        except:
            return "Unknown"
    
    def create_conversation_email_html(self, subject, duration, total_messages):
        """Create HTML email with full conversation"""
        user_email = self.conversation_data.get('user_email', 'Unknown')
        start_time = self.conversation_data.get('start_time_singapore', '')
        conversation_id = self.conversation_data.get('conversation_id', '')
        
        # Create messages HTML
        messages_html = ""
        for i, msg in enumerate(self.messages, 1):
            role_display = "🤖 Alex (Assistant)" if msg['role'] == 'assistant' else "👤 User"
            timestamp = datetime.fromisoformat(msg['timestamp_singapore'].replace('Z', '')).strftime('%H:%M:%S')
            
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
                <p style="color: #f0f0f0; margin: 8px 0 0 0; font-size: 14px;">Complete Conversation Record</p>
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
                    Conversation automatically saved to S3 and emailed<br>
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
    
    def create_conversation_email_text(self, subject, duration, total_messages):
        """Create plain text email with full conversation"""
        user_email = self.conversation_data.get('user_email', 'Unknown')
        start_time = self.conversation_data.get('start_time_singapore', '')
        conversation_id = self.conversation_data.get('conversation_id', '')
        
        # Create messages text
        messages_text = ""
        for i, msg in enumerate(self.messages, 1):
            role_display = "Alex (Assistant)" if msg['role'] == 'assistant' else "User"
            timestamp = datetime.fromisoformat(msg['timestamp_singapore'].replace('Z', '')).strftime('%H:%M:%S')
            
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
Conversation saved to S3 and emailed automatically
Contact: info@aniketsolutions.com | Website: https://www.aniketsolutions.com
        """

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
# SMART RESPONSE GENERATION
# =============================================================================

def generate_smart_response(user_message):
    """Generate smart response using OpenAI"""
    try:
        if st.session_state.get("openai_client"):
            full_context = f"""
You are Alex, a senior technology consultant at Aniket Solutions. Provide professional responses about our maritime software products and technology services.

AVAILABLE MARITIME PRODUCTS:
- AniSol Inventory Control: Fleet inventory management with spare parts and consumables tracking
- AniSol Payroll & Master Cash: Crew financial management with multi-currency support
- AniSol Crewing Module: Complete crew lifecycle management with compliance tracking
- AniSol TMS: Technical Management System for maintenance and inspections
- AniSol Procurement: AI-powered purchasing platform with vendor management

AVAILABLE TECHNOLOGY SERVICES:
- Custom Application Development: Enterprise software solutions and legacy modernization
- Mobile Solutions: Native iOS/Android apps and cross-platform development
- AI & Machine Learning: Intelligent automation and predictive analytics
- Data Services & Migration: Database migration and business intelligence
- System Integration: API development and enterprise connectivity
- AI Chatbots & Virtual Assistants: Conversational AI for customer service

IMPORTANT INSTRUCTIONS:
- Always respond based on what the user is asking about
- If they ask about products, provide detailed product information
- If they ask about services, provide detailed service information
- Use specific technical details and business benefits
- Always include contact info@aniketsolutions.com for detailed consultation
- Respond professionally without conversational AI language
"""
            
            messages = [
                {"role": "system", "content": full_context},
                {"role": "user", "content": user_message}
            ]
            
            response = st.session_state.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.2,
                max_tokens=600,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            
            return response.choices[0].message.content.strip()
        
        return "For information about our maritime software products and technology services, contact our specialists at info@aniketsolutions.com for detailed consultation."
        
    except Exception as e:
        return "For detailed information about our maritime products and technology services, contact our specialists at info@aniketsolutions.com"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_s3_status():
    """Check if S3 storage is working"""
    try:
        storage = S3StorageManager()
        
        # Test write/read
        test_key = f"test/{datetime.now().isoformat()}.json"
        test_data = {"test": True, "timestamp": datetime.now().isoformat()}
        
        if storage.save_json(test_key, test_data):
            return True, f"S3 bucket '{S3_BUCKET_NAME}' connected successfully"
        else:
            return False, "S3 write operation failed"
            
    except Exception as e:
        return False, f"S3 connection error: {str(e)}"

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

def check_conversation_inactivity():
    """Check for conversation inactivity"""
    if "last_user_activity" not in st.session_state:
        st.session_state.last_user_activity = datetime.now()
        st.session_state.conversation_ended = False
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
        
        # If 5 minutes of inactivity, end conversation
        if time_since_activity.total_seconds() > 300:  # 5 minutes
            st.session_state.conversation_ended = True
            
            # Complete conversation: save to S3 and send email
            if "conversation_manager" in st.session_state:
                success = st.session_state.conversation_manager.complete_conversation()
                if success:
                    add_message_to_chat("assistant", 
                        "Thank you for your time! This conversation has been completed and saved. You'll receive a copy via email shortly.")
                else:
                    add_message_to_chat("assistant", 
                        "Thank you for your time! This conversation has been completed.")
            
            return True
    
    return False

def add_initial_greeting():
    """Add initial greeting message"""
    greeting_message = """Hi! I'm Alex from Aniket Solutions. How can I assist you with maritime software or tech services? Please share your corporate email."""
    
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
            st.session_state.conversation_manager.update_user_email(email)
        
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
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 2px solid #28a745;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.2);
    }
    
    .conversation-ended h3 {
        color: #28a745;
        margin-bottom: 15px;
        font-size: 1.5rem;
    }
    
    .conversation-ended p {
        color: #666;
        margin-bottom: 15px;
        font-size: 1.1rem;
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

if "conversation_flow" not in st.session_state:
    st.session_state.conversation_flow = {
        "email_validated": False,
        "awaiting_email": True,
        "awaiting_otp": False,
        "otp_verified": False,
        "awaiting_selection": False,
        "selected_category": None
    }

if "otp_data" not in st.session_state:
    st.session_state.otp_data = None

# Initialize conversation manager
if "conversation_manager" not in st.session_state:
    st.session_state.conversation_manager = ConversationManager()
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
    st.session_state.conversation_manager.start_new_conversation(session_id)

# Check for conversation inactivity
conversation_ended = check_conversation_inactivity()

# Add initial greeting if messages is empty
if len(st.session_state.messages) == 0:
    add_initial_greeting()

# If conversation has ended, show completion message
if conversation_ended:
    st.markdown("""
    <div class="conversation-ended">
        <h3>✅ Conversation Completed</h3>
        <p>Thank you for your time! Your conversation has been saved to our records and you'll receive a copy via email.</p>
        <p><small>The conversation will restart automatically in a few moments.</small></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-restart after 5 seconds
    st.markdown("""
    <script>
    setTimeout(function() {
        window.location.reload();
    }, 5000);
    </script>
    """, unsafe_allow_html=True)
    
    # Manual restart option
    if st.button("🔄 Start New Conversation", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.stop()

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # S3 Storage Status
    st.subheader("☁️ S3 Storage Status")
    try:
        storage_status, storage_message = check_s3_status()
        if storage_status:
            st.success(f"✅ {storage_message}")
        else:
            st.error(f"❌ {storage_message}")
    except Exception as e:
        st.error(f"❌ S3 error: {str(e)}")
    
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
    
    st.subheader("🔄 Session Management")
    
    if st.button("🔄 Reset Session", use_container_width=True):
        # Complete current conversation before reset
        if "conversation_manager" in st.session_state and not st.session_state.get("conversation_ended"):
            st.session_state.conversation_manager.complete_conversation()
        
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Session reset!")
        st.rerun()
    
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
    st.success("✅ Auto-save & email on completion")

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
                        add_message_to_chat("assistant", "✅ Email verified! What would you like to know more about?")
                        
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
    st.markdown("**What would you like to know more about?**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚢 Maritime Products", key="select_products", use_container_width=True):
            update_user_activity()
            add_message_to_chat("user", "I'm interested in your maritime products")
            
            st.session_state.conversation_flow["selected_category"] = "products"
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            products_overview = """Our AniSol Maritime Software Suite provides integrated operational management for complex fleet requirements and regulatory compliance.

**Product Portfolio:**

**AniSol TMS** - Technical Management System
Comprehensive maintenance scheduling, inspection tracking, and certificate management with maritime-specific workflows.

**AniSol Procurement** - AI-Powered Maritime Purchasing
Advanced procurement automation with vendor management, approval controls, and ShipServ integration.

**AniSol Inventory Control** - Fleet-Wide Inventory Management
Real-time inventory tracking with automated reordering and comprehensive audit capabilities.

**AniSol Crewing Module** - Complete Crew Management
Full crew lifecycle management including compliance tracking, performance analytics, and payroll integration.

**AniSol Payroll & Master Cash** - Crew Financial Management
Maritime-specific payroll processing with multi-currency support and regulatory compliance.

Which specific operational area interests you most?"""
            
            add_message_to_chat("assistant", products_overview)
            st.rerun()
    
    with col2:
        if st.button("💻 Technology Services", key="select_services", use_container_width=True):
            update_user_activity()
            add_message_to_chat("user", "I'm interested in your technology services")
            
            st.session_state.conversation_flow["selected_category"] = "services"
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            services_overview = """Our Technology Services address comprehensive business modernization requirements through specialized expertise and proven implementation methodologies.

**Service Capabilities:**

**Custom Development** - Enterprise software solutions and legacy system modernization using modern architectures and frameworks.

**Mobile Applications** - Native iOS/Android development and cross-platform solutions with offline capabilities and enterprise integration.

**AI & Machine Learning** - Intelligent automation implementation including predictive analytics, natural language processing, and computer vision.

**Data Services** - Database migration, data warehousing, analytics platforms, and business intelligence systems.

**System Integration** - API development, enterprise application connectivity, and hybrid cloud-premise architectures.

**AI Chatbots & Virtual Assistants** - Conversational AI for customer service automation with multi-channel deployment capabilities.

Which technology challenge can we help you solve?"""
            
            add_message_to_chat("assistant", services_overview)
            st.rerun()

# Chat input (only show after category selection)
if (not st.session_state.conversation_flow["awaiting_email"] and 
    not st.session_state.conversation_flow["awaiting_otp"] and
    not st.session_state.conversation_flow["awaiting_selection"]):
    
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        
        with col1:
            user_input = st.text_input(
                "Message",
                placeholder="Ask about our maritime products or technology services...",
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
                    fallback_response = "For detailed information about our maritime products and technology services, contact our specialists at info@aniketsolutions.com"
                    add_message_to_chat("assistant", fallback_response)
                    st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "Powered by Aniket Solutions"
    "</div>",
    unsafe_allow_html=True
)
