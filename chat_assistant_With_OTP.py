import streamlit as st
from openai import OpenAI
import time
from datetime import datetime
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

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API Key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# AWS SES configuration (add these to your .env file)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # Default to us-east-1
SES_FROM_EMAIL = os.getenv("SES_FROM_EMAIL")  # Optional - will auto-detect if not specified
VERIFICATION_BASE_URL = os.getenv("VERIFICATION_BASE_URL", "http://localhost:8501")  # Your app URL

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize AWS SES client
ses_client = None
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    ses_client = boto3.client(
        'ses',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

# Avatar Configuration
ALEX_AVATAR_URL = "https://api.dicebear.com/7.x/avataaars/svg?seed=Alex&backgroundColor=b6e3f4&clothesColor=262e33&eyebrowType=default&eyeType=default&facialHairColor=auburn&facialHairType=default&hairColor=auburn&hatColor=ff5c5c&mouthType=smile&skinColor=light&topType=shortHairShortWaved"
USER_AVATAR_URL = "https://api.dicebear.com/7.x/initials/svg?seed=User&backgroundColor=4f46e5&fontSize=40"

# Alternative avatar options (you can change these URLs)
ALTERNATIVE_AVATARS = {
    "professional": "https://api.dicebear.com/7.x/avataaars/svg?seed=Professional&backgroundColor=e0e7ff&clothesColor=3730a3&eyebrowType=default&eyeType=default&facialHairType=default&hairColor=brown&mouthType=smile&skinColor=light&topType=shortHairShortFlat",
    "friendly": "https://api.dicebear.com/7.x/avataaars/svg?seed=Friendly&backgroundColor=dcfce7&clothesColor=166534&eyebrowType=default&eyeType=happy&facialHairType=default&hairColor=black&mouthType=smile&skinColor=light&topType=shortHairDreads01",
    "tech": "https://api.dicebear.com/7.x/avataaars/svg?seed=Tech&backgroundColor=f3f4f6&clothesColor=1f2937&eyebrowType=default&eyeType=default&facialHairType=default&hairColor=brown&mouthType=smile&skinColor=light&topType=shortHairShortCurly",
    "support_agent": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iMjAwIiBmaWxsPSIjZjBmOWZmIiByeD0iMTAwIi8+CjwhLS0gSGVhZCAtLT4KPGNpcmNsZSBjeD0iMTAwIiBjeT0iODAiIHI9IjM1IiBmaWxsPSIjZmJiZjI0Ii8+CjwhLS0gSGFpciAtLT4KPHBhdGggZD0ibTY1IDYwYzAtMjAgMTUtMzUgMzUtMzVzMzUgMTUgMzUgMzVjMCAxMC01IDIwLTE1IDI1aC00MGMtMTAtNS0xNS0xNS0xNS0yNVoiIGZpbGw9IiM0YTQ3NGQiLz4KPCEtLSBHeWVzIC0tPgo8Y2lyY2xlIGN4PSI5MCIgY3k9Ijc1IiByPSI0IiBmaWxsPSIjMDAwIi8+CjxjaXJjbGUgY3g9IjExMCIgY3k9Ijc1IiByPSI0IiBmaWxsPSIjMDAwIi8+CjwhLS0gR2xhc3NlcyAtLT4KPHJlY3QgeD0iODAiIHk9IjY4IiB3aWR0aD0iNDAiIGhlaWdodD0iMjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMCIgc3Ryb2tlLXdpZHRoPSIyIiByeD0iNSIvPgo8IS0tIE5vc2UgLS0+CjxjaXJjbGUgY3g9IjEwMCIgY3k9Ijg1IiByPSIyIiBmaWxsPSIjZDY5ZTJlIi8+CjwhLS0gTW91dGggLS0+CjxwYXRoIGQ9Im05MCA5NWMwIDUgNSAxMCAxMCAxMHMxMC01IDEwLTEwIiBzdHJva2U9IiMwMDAiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIvPgo8IS0tIEhlYWRzZXQgLS0+CjxwYXRoIGQ9Im03MCA2NWMtMTAgMC0xNSA1LTE1IDE1czUgMTUgMTUgMTVoNjBjMTAgMCAxNS01IDE1LTE1cy01LTE1LTE1LTE1IiBzdHJva2U9IiMzNzM3MzciIHN0cm9rZS13aWR0aD0iMyIgZmlsbD0ibm9uZSIvPgo8Y2lyY2xlIGN4PSI3MCIgY3k9IjgwIiByPSI4IiBmaWxsPSIjMzczNzM3Ii8+CjxjaXJjbGUgY3g9IjEzMCIgY3k9IjgwIiByPSI4IiBmaWxsPSIjMzczNzM3Ii8+CjwhLS0gTWljIC0tPgo8bGluZSB4MT0iMTMwIiB5MT0iODAiIHgyPSIxMjAiIHkyPSIxMDAiIHN0cm9rZT0iIzM3MzczNyIgc3Ryb2tlLXdpZHRoPSIyIi8+CjxyZWN0IHg9IjExNSIgeT0iMTAwIiB3aWR0aD0iMTAiIGhlaWdodD0iOCIgZmlsbD0iIzM3MzczNyIgcng9IjIiLz4KPCEtLSBCb2R5IC0tPgo8cmVjdCB4PSI3NSIgeT0iMTE1IiB3aWR0aD0iNTAiIGhlaWdodD0iNjAiIGZpbGw9IiMyZDM3NDgiIHJ4PSI1Ii8+CjxyZWN0IHg9IjgwIiB5PSIxMjAiIHdpZHRoPSI0MCIgaGVpZ2h0PSIzMCIgZmlsbD0iIzM5OGVkYiIgcng9IjMiLz4KPC9zdmc+",
    "custom": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face&auto=format"  # You can replace with your custom image
}
COMPANY_URL = "https://www.aniketsolutions.com/aspl/index.htm"
COMPANY_INFO = """
Aniket Solutions - TOTAL SOLUTIONS PROVIDER

About Aniket Solutions:
- Commenced operations in February 2004 in Singapore
- Privately held by Technopreneurs with decades of business experience
- Grown quickly providing excellent services to customers worldwide
- Work with customers in different geographical locations including USA, UK, Cyprus, Greece, India, Japan, Singapore and Hong Kong
- Ability to understand diverse work cultures and provide cost effective and efficient solutions
- Specializes in Marine IOT solutions (Coming soon - February 2021)
- Total solutions provider for various technology needs

Services and Expertise:
- Technology solutions across multiple domains
- Cost-effective and efficient solutions
- Global service delivery
- Understanding of diverse work cultures
- Marine IoT solutions development
"""

# Comprehensive Product Knowledge Base
PRODUCT_KNOWLEDGE_BASE = {
    "inventory_control": """
AniSol Inventory Control - Fleet-Wide Inventory Oversight
- Dedicated ship inventory system for spare parts, consumables, and critical store items
- Two Major Inventory Groups: Spares Inventory (linked to machinery/repairs) and Consumable Stores (food, safety, stationery, chemicals)
- Master Store List Management with centrally controlled consumables list
- Controlled Add/Edit Rights for consistency
- Location & ROB (Remaining Onboard) tracking and adjustment
- Store Receipts handling (office-supplied auto-updates, manual cash/local procurement)
- Consumption Logging & Requisition with permission control
- Stock Level Controls with color-coded alerts and dashboards
- Component Mapping linking spare parts to systems/equipment
- Transaction History & Audit Logs with export capability
- Integration with AniSol TMS for auto-consumption updates
- Works with AniSol Procurement for stock shortages and requisitions
- ERP/Accounts Sync Ready for inventory values and asset movement
- Ship & Cloud Ready: sync when connected, operate standalone offline
- Fleet-wide views of slow movers, fast movers, shortages
    """,
    
    "payroll_master_cash": """
AniSol Payroll & Master Cash System
- Crew Payroll: Wages, overtime, bonuses, allowances, and contract-based automation
- Advances & Deductions: Track salary advances, fines, loans with approval workflows
- Multi-Currency Support: Exchange rate handling and split-company settlements
- Portage Bill: Formal payroll and crew sign-off documentation with audit trails
- Master's Cash: Onboard cash advance issuance and petty cash tracking
- Petty Cash Logs: Digital voucher entries with approvals and spend category tagging
- Export-Ready: Seamless sync with shore payroll and accounting systems
- Audit Compliance: Full historical ledger, transaction approvals, and backup archive
- Built for Ship Use: Designed by seafarers, optimized for onboard workflows
- Office Integration: Direct export to shore payroll and accounting systems
- Secure & Compliant: Multi-level approval workflows and audit history
- Works Independently or with Crewing: Modular design
- Cloud or Ship Hosted: Flexible deployment
    """,
    
    "crewing_module": """
AniSol Crewing Module - Complete Crew Management
- Portage Bill & Crew Wages Accounting: Full lifecycle payroll, wages, overtime, bonuses, allowances
- Salary advances, fines, loans tracking with approval workflows
- Multi-currency payments, exchange rates, multi-company/agency setups
- Formal payroll and portage bill reports with audit trails
- Master's Cash & Petty Cash Management: Cash advances, onboard petty cash, crew expenditures
- Provisions & Slop Chest Accounting: Inventory, sales, cost control
- Crew Document & Certification Management: Centralized repository with expiry alerts
- Crew Scheduling & Deployment: Planning, monitoring, contracts, rotations, shore leave
- Crew Appraisals & Performance Analytics: Structured workflows, competency assessments
- Comprehensive Reporting & Compliance: Flag state, STCW, MLC compliance
- Seamless Integration with other AniSol modules
- Cloud-first, scalable infrastructure with secure backups
    """,
    
    "tms": """
AniSol TMS - Technical Management System
- Smart Maintenance & Real Maritime Insight
- Planned & Unplanned Maintenance: Calendar, counter, condition-based scheduling
- One-click reporting of breakdown work
- Work order generation and closure with audit trail
- Inspections & Defect Management: PSC, Class Surveys, Defects tracking
- Certificate & Survey Control: Full lifecycle tracking with automated alerts
- Inventory Integration: Direct link between spares and work orders
- Technical Dashboard & Analytics: Monitor vessel health, drill-down capability
- Ship-Shore Synchronization: Ultra-low bandwidth usage, works over satellite
- Digital Reporting & Forms: Calibration, decarbonisation, bearing measurements
- Designed by Seafarers for ship operations
- Unified UI for most operations from single screen
- No Dedicated Server Needed: Any onboard computer can act as host
- Multi-layer Access Control: Role-based and department-level security
    """,
    
    "procurement": """
AniSol Procurement - AI-Powered Maritime Purchasing
- Supports inventory-linked and non-inventory requisitions
- Requisition Types: Spares & Stores, Repair Jobs, Service Orders, Adhoc Requests, Framework Agreements
- Smart PO Handling: Auto-generate from RFQs, import vendor quotes (CSV, Excel, ShipServ)
- Configurable approval flows by cost, vessel, user role, project
- Delivery & Auto-Matching: Inventory auto-updates, 2-way & 3-way matching
- Vendor Management: Centralized vendor master with performance tracking
- ShipServ Integration for sourcing and catalog sync
- AI-powered procurement analytics and decision-making
- BI & Analytics: Live dashboards, supplier performance analysis
- IHM Export Support: Regulator-ready purchase data
- Full Audit Logging: Complete traceability from requisition to invoice
- Low-Bandwidth Sync: No need to wait for vessel email
- Budget Control: Budget codes link at requisition level
    """
}

# Services Knowledge Base
SERVICES_KNOWLEDGE_BASE = {
    "custom_development": """
Custom Application Development Services
- Enterprise Web Applications: Modern, responsive applications with cutting-edge frameworks
- Custom Software Solutions: Bespoke applications for specific business processes
- Legacy System Modernization: Upgrade outdated systems while preserving functionality
- API Development & Microservices: Flexible, scalable architectures
- Technologies: React, Angular, Vue.js, Node.js, Python, Java, .NET, PostgreSQL, MySQL, MongoDB
- Process: Discovery & Planning, Design & Architecture, Agile Development, Testing & QA, Deployment & Support
- Industries: Manufacturing, Healthcare, Finance, Logistics, Maritime, Retail, Education
    """,
    
    "mobile_solutions": """
Mobile Solutions Services
- Native Mobile Applications: High-performance iOS and Android apps
- Cross-Platform Development: React Native, Flutter for cost-effective solutions
- Progressive Web Apps (PWAs): App-like experiences through browsers
- Tablet Applications: Optimized for field operations and presentations
- Features: Real-Time Data Access, Offline Functionality, Push Notifications, Secure Authentication
- GPS & Location Services, Camera & Scanning Integration
- Benefits: Increased Productivity, Faster Decision Making, Improved Communication
- Perfect for: Field Service Teams, Sales Representatives, Fleet Management, Remote Workers
    """,
    
    "ai_machine_learning": """
AI & Machine Learning Services
- Generative AI Solutions: Custom chatbots, automated content generation, code assistance
- Large Language Model Integration: GPT, Claude, custom-trained models
- AI-Powered Chatbots & Virtual Assistants: Intelligent conversational AI
- Automated Content Generation: High-quality content at scale
- Predictive Analytics & Forecasting: Trend analysis and optimization
- Intelligent Process Automation (IPA): Automated decision-making
- Natural Language Processing: Text analysis and document processing
- Computer Vision & Image AI: Quality control, monitoring, inspection
- Custom Machine Learning Models: Domain-specific AI solutions
- Technologies: Python, TensorFlow, PyTorch, Hugging Face, OpenAI APIs, LangChain
- Applications: Manufacturing (predictive maintenance), Healthcare (medical analysis), Finance (fraud detection)
    """,
    
    "data_services": """
Data Services
- Data Migration & Transfer: Seamless system transitions with zero downtime
- Database Modernization: Upgrade to modern, high-performance platforms
- Data Warehousing: Centralized data from multiple sources
- ETL/ELT Solutions: Automated data movement and transformation
- Data Analytics & Reporting: Transform raw data into insights
- Migration Specialties: Oracle to PostgreSQL, SQL Server to cloud, legacy mainframe
- Cloud Migrations: AWS, Azure, Google Cloud
- Data Quality Assurance: Profiling, cleansing, validation, monitoring
- Compliance: GDPR, HIPAA, SOX, PCI-DSS compliant solutions
    """,
    
    "system_integration": """
System Integration Services
- API Development & Integration: RESTful APIs, GraphQL endpoints
- Third-Party System Integration: CRM, ERP, payment gateways
- Enterprise Application Integration: Unify complex enterprise systems
- Cloud Integration: Bridge on-premise and cloud systems
- Legacy System Connectivity: Connect older systems with modern platforms
- Integration Patterns: Real-Time, Batch, Event-Driven, Message Queue
- Technologies: Apache Kafka, RabbitMQ, REST, GraphQL, Azure Logic Apps
- Benefits: Operational Efficiency, Real-Time Insights, Cost Reduction
- Common Scenarios: CRM-ERP sync, e-commerce integrations, financial system connections
    """,
    
    "ai_chatbots": """
AI Chatbot/Virtual Assistants Services
- 24/7 Customer Service with intelligent conversational AI
- Answer Customer Questions Instantly with accurate, helpful responses
- Guide Customers Through Processes: orders, appointments, tracking
- Collect Important Information and qualify leads
- Schedule and Manage Appointments with availability checking
- Handle Multiple Languages for global customer base
- Learn and Improve Over Time with every interaction
- Benefits: Never Miss a Customer, Reduce Wait Times, Free Up Human Team
- Integration: Website chat, Facebook Messenger, WhatsApp, SMS, phone systems
- Perfect for: Retail, Restaurants, Healthcare, Professional Services, Real Estate
    """
}

def fetch_company_content():
    """Fetch content from company URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(COMPANY_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text content
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Clean up the text
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        cleaned_content = ' '.join(lines)
        
        return cleaned_content[:2000]  # Limit content length
    except Exception as e:
        return f"Error fetching content: {str(e)}"

def search_company_info(query):
    """Search for relevant information in company content and knowledge base"""
    query_lower = query.lower()
    
    # Enhanced keyword matching for products and services
    product_keywords = {
        'inventory': ['inventory', 'stock', 'spare', 'consumable', 'rob', 'stores'],
        'payroll': ['payroll', 'wages', 'salary', 'cash', 'crew payment', 'master cash'],
        'crewing': ['crew', 'crewing', 'staff', 'personnel', 'maritime crew', 'seafarer'],
        'tms': ['tms', 'maintenance', 'technical', 'planned maintenance', 'pms', 'technical management'],
        'procurement': ['procurement', 'purchasing', 'requisition', 'po', 'purchase order', 'supplier', 'vendor'],
        'custom_development': ['custom', 'development', 'software', 'application', 'web app', 'custom software'],
        'mobile': ['mobile', 'app', 'ios', 'android', 'smartphone', 'tablet'],
        'ai': ['ai', 'artificial intelligence', 'machine learning', 'chatbot', 'generative ai', 'gpt'],
        'data': ['data', 'database', 'migration', 'analytics', 'reporting', 'etl'],
        'integration': ['integration', 'api', 'connect', 'sync', 'system integration']
    }
    
    # Check for specific product/service mentions
    for category, keywords in product_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return True
    
    # General company keywords
    general_keywords = [
        'service', 'product', 'solution', 'technology', 'marine', 'iot',
        'singapore', 'global', 'experience', 'cost effective', 'efficient',
        'maritime', 'shipping', 'vessel', 'ship'
    ]
    
    # Check if query contains relevant keywords
    for keyword in general_keywords:
        if keyword in query_lower:
            return True
    
    return False

# Enhanced AI Assistant Configuration
AI_ASSISTANT_PROMPT = """
You are Alex, a professional and knowledgeable AI assistant for Aniket Solutions, a leading technology solutions provider established in 2004. You are here to help potential clients understand our services and guide them toward the right solutions for their business needs.

## About Aniket Solutions:
- Established: February 2004 in Singapore
- Global presence: USA, UK, Cyprus, Greece, India, Japan, Singapore, Hong Kong
- Expertise: Maritime technology solutions and general technology services
- Focus: Cost-effective, efficient solutions with understanding of diverse work cultures

## Your Role:
- Be warm, professional, and consultative (not salesy)
- Ask intelligent follow-up questions to understand client needs
- Provide detailed information about relevant solutions
- Guide conversations toward booking consultations or demos
- Handle technical questions with expertise
- Maintain conversation flow naturally

## Key Services & Products:

### Maritime Solutions:
1. **AniSol TMS** - Technical Management System for vessel maintenance, inspections, certificates
2. **AniSol Procurement** - AI-powered maritime purchasing with vendor management
3. **AniSol Inventory Control** - Fleet-wide spare parts and consumables management
4. **AniSol Crewing Module** - Complete crew management including payroll and compliance
5. **AniSol Payroll & Master Cash** - Crew financial management and petty cash systems

### Technology Services:
1. **Custom Application Development** - Bespoke software solutions for unique business needs
2. **Mobile Solutions** - Native iOS/Android apps and cross-platform development
3. **AI & Machine Learning** - Generative AI, chatbots, predictive analytics, automation
4. **Data Services** - Migration, warehousing, analytics, database modernization
5. **System Integration** - API development, ERP connections, legacy system connectivity
6. **AI Chatbots & Virtual Assistants** - 24/7 customer service automation

## When You Can't Fully Answer:
If you encounter questions about:
- Specific pricing, quotes, or detailed cost estimates
- Complex technical specifications requiring engineering review
- Custom requirements that need detailed analysis
- Implementation timelines for specific projects
- Legal, compliance, or regulatory specifics
- Questions outside your knowledge base
- Requests requiring human expertise or decision-making

ALWAYS gracefully direct them to our contact form by saying something like:
"That's an excellent question that deserves a detailed response from our specialists. I'd recommend filling out our contact form so our team can provide you with specific information tailored to your situation. You can reach us at [CONTACT_FORM_LINK] or email us directly at info@aniketsolutions.com."

## Conversation Guidelines:
- Always acknowledge and validate the user's specific industry or business type
- Ask clarifying questions to understand their current challenges
- Recommend solutions based on their specific needs, not just list features
- Offer to schedule consultations, demos, or provide detailed proposals
- If you don't have specific information, offer to connect them with a specialist
- Keep responses conversational and appropriately detailed
- Suggest next steps (consultation, demo, proposal, contact form)

## Contact Information to Provide:
- Contact Form: [Direct users to fill out contact form for detailed inquiries]
- Email: info@aniketsolutions.com
- Website: www.aniketsolutions.com

## Example Responses Style:
- "That's an interesting challenge in [their industry]. Many of our clients in [similar sector] have found success with..."
- "Based on what you've described, I think our [specific solution] could be particularly valuable because..."
- "Let me ask you a few questions to better understand your current setup..."
- "That's a great question that requires input from our technical team. I'd recommend reaching out through our contact form..."
- "For specific pricing and implementation details, our specialists can provide a customized proposal. Please contact us at..."

Remember: You're not just answering questions - you're having intelligent business conversations that lead to meaningful solutions or appropriate handoffs to human experts.
"""

# Contact form and escalation configuration
CONTACT_FORM_URL = "https://www.aniketsolutions.com/contact"  # Update with actual URL
CONTACT_EMAIL = "info@aniketsolutions.com"

def should_escalate_to_contact_form(user_message):
    """Determine if query should be escalated to contact form - only for very specific cases"""
    escalation_keywords = [
        # Only very specific pricing requests
        'detailed pricing', 'exact cost', 'price quote', 'cost estimate', 'budget proposal',
        
        # Only very specific technical implementation details
        'detailed implementation plan', 'migration timeline', 'deployment schedule',
        
        # Legal and contract specifics
        'contract terms', 'legal agreement', 'sla details', 'service agreement',
        
        # Explicit requests for human contact
        'speak to sales', 'talk to sales team', 'contact sales', 'human sales rep',
        'account manager', 'sales consultant'
    ]
    
    message_lower = user_message.lower()
    # Only escalate if the query contains very specific escalation phrases
    return any(keyword in message_lower for keyword in escalation_keywords)

def generate_ai_response(user_message, conversation_history=None):
    """Generate intelligent AI response with escalation handling"""
    try:
        if not st.session_state.get("openai_client"):
            return generate_contact_form_response("I'm experiencing technical difficulties at the moment.")
        
        # Check if this should be escalated immediately
        if should_escalate_to_contact_form(user_message):
            return generate_contact_form_response(
                f"This requires detailed information from our specialists."
            )
        
        # Prepare conversation context
        messages = [{"role": "system", "content": AI_ASSISTANT_PROMPT.replace("[CONTACT_FORM_LINK]", CONTACT_FORM_URL)}]
        
        # Add conversation history for context (last 6 messages to avoid repetition)
        if conversation_history:
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            for msg in recent_history:
                if msg["role"] in ["user", "assistant"]:
                    # Skip timestamps and clean content
                    content = msg["content"].strip()
                    if content and len(content) > 10:  # Avoid very short or empty messages
                        messages.append({
                            "role": msg["role"], 
                            "content": content
                        })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Generate response with adjusted parameters
        response = st.session_state.openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.8,  # Slightly higher for variety
            max_tokens=200,   # Shorter responses
            presence_penalty=0.3,  # Encourage new topics
            frequency_penalty=0.5  # Reduce repetition significantly
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Check if response is too similar to recent responses
        if conversation_history and len(conversation_history) > 1:
            last_assistant_msg = None
            for msg in reversed(conversation_history):
                if msg["role"] == "assistant":
                    last_assistant_msg = msg["content"]
                    break
            
            if last_assistant_msg and similarity_check(ai_response, last_assistant_msg):
                # Generate a different response if too similar
                follow_up_prompt = f"The user said: {user_message}. Please provide a different, more specific response without repeating previous information. Focus on next steps or ask for more details."
                
                response = st.session_state.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": AI_ASSISTANT_PROMPT.replace("[CONTACT_FORM_LINK]", CONTACT_FORM_URL)},
                        {"role": "user", "content": follow_up_prompt}
                    ],
                    temperature=0.9,
                    max_tokens=150,
                    presence_penalty=0.5,
                    frequency_penalty=0.7
                )
                ai_response = response.choices[0].message.content.strip()
        
        # Check if AI response indicates it can't fully answer
        uncertainty_indicators = [
            "i don't know", "i'm not sure", "i can't provide", "i don't have",
            "that's beyond my knowledge", "i'm unable to", "i cannot determine",
            "that requires", "you should contact", "speak with our team"
        ]
        
        if any(indicator in ai_response.lower() for indicator in uncertainty_indicators):
            return generate_contact_form_response(
                "This requires detailed expertise from our team."
            )
        
        return ai_response
        
    except Exception as e:
        return generate_contact_form_response("I'm experiencing technical difficulties at the moment.")

def similarity_check(text1, text2):
    """Check if two texts are too similar (basic similarity check)"""
    if not text1 or not text2:
        return False
    
    # Simple similarity check based on common words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if len(words1) == 0 or len(words2) == 0:
        return False
    
    common_words = words1.intersection(words2)
    similarity_ratio = len(common_words) / min(len(words1), len(words2))
    
    return similarity_ratio > 0.7  # More than 70% similar words

def generate_contact_form_response(context_message):
    """Generate a professional response directing users to contact form"""
    contact_responses = [
        f"""
{context_message}

I'd be happy to connect you with our specialists who can provide detailed, personalized information for your specific situation. Here are the best ways to reach our team:

**📋 Contact Form:** Please fill out our contact form at {CONTACT_FORM_URL} - this ensures your inquiry reaches the right specialist who can provide comprehensive answers.

**📧 Direct Email:** You can also email us at {CONTACT_EMAIL} with your specific questions and requirements.

**⚡ What to Include:**
- Your specific requirements or challenges
- Industry/business context  
- Timeline considerations
- Any technical specifications needed

Our team typically responds within 24 hours with detailed information, proposals, or to schedule a consultation call.

Is there anything else about our general capabilities I can help clarify while you're here?
        """,
        
        f"""
{context_message}

For the most accurate and detailed response, I'd recommend reaching out to our specialist team who can provide you with comprehensive information tailored to your specific needs.

**🎯 Best Contact Options:**

• **Contact Form:** {CONTACT_FORM_URL} (recommended - gets routed to the right expert)
• **Email:** {CONTACT_EMAIL}
• **Website:** www.aniketsolutions.com

**💡 Pro Tip:** When you contact us, mentioning your industry, current challenges, and specific requirements helps our team provide you with the most relevant solutions and accurate timelines.

Our specialists are experienced in handling complex requirements and can provide detailed proposals, technical specifications, and implementation roadmaps.

What other general questions about our services can I help with in the meantime?
        """
    ]
    
    import random
    return random.choice(contact_responses)

def get_smart_company_response(query):
    """Enhanced company response that uses knowledge base first, then AI"""
    
    query_lower = query.lower()
    
    # For crew management specific queries
    if any(word in query_lower for word in ['crew management', 'crew software', 'maritime crew', 'crewing']):
        return f"""**AniSol Crewing Module - Complete Crew Management Solution**

Our **AniSol Crewing** system handles all aspects of crew management:

**Key Features:**
• **Crew Payroll & Wages**: Full lifecycle payroll, wages, overtime, bonuses, allowances
• **Document Management**: Centralized repository with expiry alerts for certificates
• **Crew Scheduling**: Planning, monitoring, contracts, rotations, shore leave
• **Compliance Tracking**: Flag state, STCW, MLC compliance automation
• **Performance Analytics**: Structured workflows and competency assessments
• **Multi-Currency Support**: Exchange rates, multi-company/agency setups

**Built for Maritime Operations:**
- Cloud-first, scalable infrastructure
- Seamless integration with other AniSol modules
- Secure backups and audit trails
- Designed by seafarers for real maritime workflows

What specific crew management challenges are you facing? I can provide more details on how our system addresses them."""

    # For inventory/stores queries
    elif any(word in query_lower for word in ['inventory', 'stock', 'spare', 'consumable', 'stores']):
        return f"""**AniSol Inventory Control - Fleet-Wide Inventory Management**

Our inventory system is designed specifically for maritime operations:

**Key Features:**
• **Spares & Consumables**: Separate tracking for machinery spares and consumable stores
• **ROB Tracking**: Real-time Remaining Onboard quantities
• **Automated Reordering**: Smart alerts and procurement integration
• **Component Mapping**: Link spare parts to specific systems/equipment
• **Transaction History**: Complete audit trails with export capability
• **Ship-Shore Sync**: Works offline, syncs when connected

**Integration Benefits:**
- Links with AniSol TMS for maintenance-driven consumption
- Connects to AniSol Procurement for automated ordering
- ERP/Accounts ready for inventory valuation

What size fleet are you managing? This helps me recommend the right configuration approach."""

    # For maintenance/TMS queries
    elif any(word in query_lower for word in ['maintenance', 'tms', 'technical management', 'planned maintenance']):
        return f"""**AniSol TMS - Technical Management System**

Built by seafarers for real ship operations:

**Maintenance Management:**
• **Planned Maintenance**: Calendar, counter, and condition-based scheduling
• **Unplanned Maintenance**: One-click breakdown reporting
• **Work Orders**: Complete generation and closure with audit trails
• **Inspections**: PSC, Class Surveys, and defect tracking

**Key Advantages:**
• **Unified Interface**: Most operations from a single screen
• **No Dedicated Server**: Any onboard computer can host
• **Low Bandwidth**: Ultra-efficient ship-shore synchronization
• **Inventory Integration**: Direct links between spares and work orders
• **Offline Capable**: Works independently when internet is unavailable

**Dashboard & Analytics**: Real-time vessel health monitoring with drill-down capabilities

What type of vessels do you operate? Different vessel types benefit from different TMS configurations."""

    # For procurement queries
    elif any(word in query_lower for word in ['procurement', 'purchasing', 'supplier', 'vendor']):
        return f"""**AniSol Procurement - AI-Powered Maritime Purchasing**

Streamline your entire procurement process:

**Smart Features:**
• **AI-Powered Analytics**: Intelligent procurement insights and recommendations
• **Multiple Requisition Types**: Spares, repairs, services, adhoc requests
• **Vendor Management**: Centralized supplier database with performance tracking
• **ShipServ Integration**: Enhanced sourcing and catalog synchronization
• **Automated Approvals**: Configurable workflows by cost, vessel, and user role

**Compliance & Control:**
• **Full Audit Trails**: Complete traceability from requisition to invoice
• **Budget Controls**: Budget codes linked at requisition level
• **2-way & 3-way Matching**: Automated invoice matching
• **Low Bandwidth**: No need to wait for vessel email systems

**Integration Ready**: Works seamlessly with inventory and technical systems

What's your biggest procurement challenge - vendor management, approval workflows, or compliance tracking?"""

    # For AI/technology services
    elif any(word in query_lower for word in ['ai', 'artificial intelligence', 'chatbot', 'automation']):
        return f"""**AI & Machine Learning Services**

We help businesses harness AI for practical results:

**AI Solutions:**
• **Custom Chatbots**: 24/7 customer service automation
• **Generative AI**: Content creation and automated responses
• **Predictive Analytics**: Trend analysis and forecasting
• **Process Automation**: Intelligent workflow automation
• **Computer Vision**: Quality control and monitoring
• **Natural Language Processing**: Document analysis and processing

**Technologies We Use:**
- Python, TensorFlow, PyTorch, Hugging Face
- OpenAI APIs, LangChain, custom models
- Integration with existing business systems

**Industry Applications:**
- Manufacturing: Predictive maintenance
- Healthcare: Medical data analysis  
- Finance: Fraud detection
- Maritime: Operational optimization

What repetitive tasks or decision-making processes in your business could benefit from AI automation?"""

    # For custom development
    elif any(word in query_lower for word in ['custom development', 'software', 'application', 'web app']):
        return f"""**Custom Application Development Services**

We build software solutions tailored to your specific business needs:

**Development Expertise:**
• **Enterprise Web Applications**: Modern, responsive applications
• **Custom Software Solutions**: Bespoke applications for unique processes
• **Legacy Modernization**: Upgrade systems while preserving functionality
• **API Development**: Flexible, scalable microservices architectures

**Technologies:**
- Frontend: React, Angular, Vue.js
- Backend: Node.js, Python, Java, .NET
- Databases: PostgreSQL, MySQL, MongoDB
- Cloud: AWS, Azure, Google Cloud

**Our Process:**
1. Discovery & Planning
2. Design & Architecture  
3. Agile Development
4. Testing & QA
5. Deployment & Support

**Industries We Serve**: Manufacturing, Healthcare, Finance, Logistics, Maritime, Retail, Education

What specific business process needs automation or improvement?"""

    # For mobile app queries
    elif any(word in query_lower for word in ['mobile', 'app', 'ios', 'android', 'smartphone']):
        return f"""**Mobile Solutions Services**

Transform your mobile strategy with professional app development:

**Mobile Development:**
• **Native Apps**: High-performance iOS and Android applications
• **Cross-Platform**: React Native, Flutter for cost-effective solutions
• **Progressive Web Apps**: App-like experiences through browsers
• **Tablet Applications**: Optimized for field operations

**Key Features:**
• **Offline Functionality**: Work without internet connection
• **Real-Time Data Access**: Instant synchronization
• **Push Notifications**: Keep users engaged
• **Secure Authentication**: Enterprise-grade security
• **GPS Integration**: Location-based services
• **Camera & Scanning**: Document capture and QR codes

**Perfect For:**
- Field service teams
- Sales representatives  
- Fleet management
- Remote workers

What type of mobile functionality would help your team work more efficiently?"""

    # For general company/services inquiry
    elif any(word in query_lower for word in ['services', 'company', 'about', 'solutions']):
        return f"""**Aniket Solutions - Your Technology Partner Since 2004**

**Maritime Software Suite:**
🚢 **AniSol TMS** - Technical Management & Maintenance
🚢 **AniSol Procurement** - AI-Powered Purchasing  
🚢 **AniSol Inventory** - Fleet-Wide Inventory Control
🚢 **AniSol Crewing** - Complete Crew Management
🚢 **AniSol Payroll** - Crew Financial Management

**Technology Services:**
💻 **Custom Development** - Bespoke software solutions
📱 **Mobile Applications** - iOS/Android development
🤖 **AI & Machine Learning** - Intelligent automation
📊 **Data Services** - Migration, analytics, warehousing
🔗 **System Integration** - API development and connectivity

**Why Choose Us:**
• **Maritime Expertise**: Built by professionals who understand shipping
• **Global Experience**: Serving clients across USA, UK, Singapore, India, Japan
• **Proven Track Record**: 20+ years of successful implementations
• **Cost-Effective**: Practical solutions that deliver ROI

Which area interests you most - our maritime solutions or general technology services?"""

    # If no specific match, use AI for a knowledgeable response
    else:
        return generate_ai_response(query, st.session_state.messages)

def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))

def send_otp_email(email, otp):
    """Send OTP to the provided email address using AWS SES"""
    try:
        if not ses_client:
            return False, "AWS SES not configured. Please configure AWS credentials in .env file."
        
        # Try to get sender email, with fallback options
        sender_email = SES_FROM_EMAIL
        
        if not sender_email:
            # If no SES_FROM_EMAIL specified, try to get verified identities
            try:
                response = ses_client.list_verified_email_addresses()
                verified_emails = response.get('VerifiedEmailAddresses', [])
                
                if verified_emails:
                    sender_email = verified_emails[0]  # Use first verified email
                else:
                    return False, "No verified email addresses found in AWS SES. Please verify at least one email address."
            except Exception as e:
                return False, f"Could not retrieve verified email addresses: {str(e)}"
        
        # Email subject
        subject = "Aniket Solutions - Email Verification Code"
        
        # HTML email body for better formatting
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
                    <div style="background: #f8f9fa; 
                                border: 2px solid #667eea; 
                                border-radius: 10px; 
                                padding: 20px; 
                                display: inline-block;">
                        <p style="margin: 0; color: #666; font-size: 14px;">Your Verification Code</p>
                        <h1 style="margin: 10px 0 0 0; 
                                   color: #667eea; 
                                   font-size: 36px; 
                                   font-weight: bold; 
                                   letter-spacing: 8px;
                                   font-family: 'Courier New', monospace;">
                            {otp}
                        </h1>
                    </div>
                </div>
                
                <p style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #667eea;">
                    <strong>⏰ Important:</strong> This verification code will expire in 10 minutes for security purposes.
                </p>
                
                <p style="background: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                    <strong>🔒 Security Note:</strong> Never share this code with anyone. Aniket Solutions will never ask for your verification code via phone or other means.
                </p>
                
                <p>If you did not request this verification, please ignore this email.</p>
                
                <hr style="border: none; height: 1px; background: #eee; margin: 30px 0;">
                
                <div style="text-align: center; color: #666; font-size: 14px;">
                    <p><strong>Aniket Solutions</strong><br>
                    Website: <a href="https://www.aniketsolutions.com" style="color: #667eea;">www.aniketsolutions.com</a></p>
                    
                    <p style="font-size: 12px; color: #999;">
                        This is an automated message. Please do not reply to this email.<br>
                        Established 2004 • Singapore • Global Technology Solutions
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        text_body = f"""
Hello,

Thank you for your interest in Aniket Solutions!

To verify your email address and continue with our consultation, please use the following verification code:

Verification Code: {otp}

This verification code will expire in 10 minutes for security purposes.

If you did not request this verification, please ignore this email.

Security Note: Never share this code with anyone. Aniket Solutions will never ask for your verification code via phone or other means.

Best regards,
Aniket Solutions Team
Website: https://www.aniketsolutions.com

---
This is an automated message. Please do not reply to this email.
        """
        
        # Send email using AWS SES
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
        
        return True, f"OTP sent successfully to {email} from {sender_email}! Message ID: {response['MessageId']}"
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'MessageRejected':
            return False, "Email address not verified in AWS SES. Please verify the sender email address."
        elif error_code == 'SendingPausedException':
            return False, "AWS SES sending is paused for your account. Please contact AWS support."
        else:
            return False, f"AWS SES error ({error_code}): {error_message}"
            
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
    
    # Check if too many attempts
    if attempts >= 3:
        return False, "Too many failed attempts. Please request a new OTP."
    
    # Check if OTP has expired (10 minutes = 600 seconds)
    current_time = datetime.now()
    time_diff = (current_time - timestamp).total_seconds()
    
    if time_diff > 600:  # 10 minutes
        return False, "OTP has expired. Please request a new one."
    
    if entered_otp == stored_otp:
        return True, "OTP verified successfully!"
    else:
        return False, "Invalid OTP. Please try again."

def moderate_content(text):
    """Check content using OpenAI Moderation API"""
    try:
        # Check if OpenAI client is available
        if not client:
            return True, "Content moderation unavailable - proceeding"
        
        # Use OpenAI Moderation API
        response = client.moderations.create(input=text)
        
        moderation_result = response.results[0]
        
        if moderation_result.flagged:
            # Get specific violation categories
            flagged_categories = []
            categories = moderation_result.categories
            
            if categories.harassment: flagged_categories.append("harassment")
            if categories.harassment_threatening: flagged_categories.append("threatening content")
            if categories.hate: flagged_categories.append("hate speech")
            if categories.hate_threatening: flagged_categories.append("threatening hate speech")
            if categories.self_harm: flagged_categories.append("self-harm content")
            if categories.self_harm_instructions: flagged_categories.append("self-harm instructions")
            if categories.self_harm_intent: flagged_categories.append("self-harm intent")
            if categories.sexual: flagged_categories.append("sexual content")
            if categories.sexual_minors: flagged_categories.append("sexual content involving minors")
            if categories.violence: flagged_categories.append("violent content")
            if categories.violence_graphic: flagged_categories.append("graphic violence")
            
            violation_text = ", ".join(flagged_categories)
            return False, f"Content flagged for: {violation_text}"
        
        return True, "Content approved"
        
    except Exception as e:
        # Log error but don't block user - moderation failure shouldn't stop legitimate users
        return True, f"Moderation check failed, proceeding: {str(e)}"

def detect_gibberish(text):
    """Detect if text is gibberish or meaningless"""
    
    # Basic gibberish detection patterns
    text_clean = text.lower().strip()
    
    # Check for minimum length
    if len(text_clean) < 2:
        return True, "Message too short"
    
    # Check for excessive repetition of characters
    if len(set(text_clean)) <= 2 and len(text_clean) > 5:
        return True, "Excessive character repetition detected"
    
    # Check for random character sequences
    vowels = set('aeiou')
    consonants = set('bcdfghjklmnpqrstvwxyz')
    
    # Count vowels and consonants
    vowel_count = sum(1 for char in text_clean if char in vowels)
    consonant_count = sum(1 for char in text_clean if char in consonants)
    total_letters = vowel_count + consonant_count
    
    if total_letters > 5:
        vowel_ratio = vowel_count / total_letters
        # If vowel ratio is too low (< 0.1) or too high (> 0.8), likely gibberish
        if vowel_ratio < 0.1 or vowel_ratio > 0.8:
            return True, "Unusual character pattern detected"
    
    # Check for excessive consecutive consonants
    consecutive_consonants = 0
    max_consecutive_consonants = 0
    
    for char in text_clean:
        if char in consonants:
            consecutive_consonants += 1
            max_consecutive_consonants = max(max_consecutive_consonants, consecutive_consonants)
        else:
            consecutive_consonants = 0
    
    if max_consecutive_consonants > 4:
        return True, "Excessive consecutive consonants detected"
    
    # Check for keyboard mashing patterns
    keyboard_rows = [
        'qwertyuiop',
        'asdfghjkl',
        'zxcvbnm'
    ]
    
    for row in keyboard_rows:
        for i in range(len(row) - 3):
            sequence = row[i:i+4]
            if sequence in text_clean or sequence[::-1] in text_clean:
                return True, "Keyboard sequence pattern detected"
    
    # Check for common gibberish patterns
    gibberish_patterns = [
        'aaaa', 'bbbb', 'cccc', 'dddd', 'eeee',
        'asdf', 'qwer', 'zxcv', 'hjkl',
        'test123', 'aaaaa', 'bbbbb'
    ]
    
    for pattern in gibberish_patterns:
        if pattern in text_clean:
            return True, f"Common gibberish pattern detected: {pattern}"
    
    return False, "Text appears valid"

def advanced_gibberish_check_with_openai(text):
    """Use OpenAI to detect more sophisticated gibberish"""
    try:
        if not client:
            return False, "AI gibberish check unavailable"
        
        # Use OpenAI to analyze if text is meaningful
        prompt = f"""
        Analyze the following text and determine if it's meaningful business communication or gibberish/spam.
        
        Text to analyze: "{text}"
        
        Consider:
        1. Is this a legitimate business inquiry or response?
        2. Does it contain meaningful words and sentences?
        3. Is it trying to communicate something specific?
        4. Could this be from someone genuinely interested in business services?
        
        Respond with only one of these options:
        - "VALID" if it's meaningful business communication
        - "GIBBERISH" if it's nonsensical, spam, or not a legitimate business inquiry
        - "UNCLEAR" if you're not sure
        
        Response:
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip().upper()
        
        if result == "GIBBERISH":
            return True, "AI detected non-meaningful content"
        elif result == "VALID":
            return False, "AI confirmed meaningful content"
        else:
            # If unclear, allow but flag for review
            return False, "Content unclear but allowed"
            
    except Exception as e:
        # If AI check fails, fall back to basic check only
        return False, f"AI gibberish check failed: {str(e)}"

def comprehensive_content_filter(text):
    """Comprehensive content filtering combining moderation and gibberish detection"""
    
    # Step 1: OpenAI Moderation API
    is_safe, moderation_message = moderate_content(text)
    if not is_safe:
        return False, f"🚫 Content Moderation: {moderation_message}"
    
    # Step 2: Basic gibberish detection
    is_gibberish, gibberish_message = detect_gibberish(text)
    if is_gibberish:
        return False, f"🤖 Content Quality: {gibberish_message}. Please provide a meaningful business inquiry."
    
    # Step 3: Advanced AI-based gibberish detection for longer texts
    if len(text.strip()) > 20:  # Only for longer messages
        is_ai_gibberish, ai_message = advanced_gibberish_check_with_openai(text)
        if is_ai_gibberish:
            return False, f"🤖 Content Analysis: {ai_message}. Please provide a clear business inquiry."
    
    return True, "Content approved"

# Email validation functions
def validate_email_format(email):
    """Validate email format using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_domain(domain):
    """Validate domain by checking DNS records"""
    try:
        # Check if domain has MX record (mail exchange)
        mx_records = dns.resolver.resolve(domain, 'MX')
        if mx_records:
            return True, "Domain has valid MX records"
    except dns.resolver.NXDOMAIN:
        return False, "Domain does not exist"
    except dns.resolver.NoAnswer:
        try:
            # If no MX record, check if domain exists with A record
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
    
    # Common personal email providers
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
    
    # Additional checks for corporate emails
    corporate_indicators = [
        # Common corporate domain patterns
        '.edu',  # Educational institutions
        '.gov',  # Government
        '.org',  # Organizations (many are corporate)
    ]
    
    # Check if domain ends with corporate indicators
    for indicator in corporate_indicators:
        if domain.endswith(indicator):
            return True, f"Domain '{domain}' appears to be institutional/corporate"
    
    # If not in personal list and not obviously personal, likely corporate
    # Additional validation: check if domain is not a known personal provider
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
    
    # Step 1: Format validation
    if not validate_email_format(email):
        results['messages'].append("❌ Invalid email format")
        return results
    
    results['format_valid'] = True
    results['messages'].append("✅ Email format is valid")
    
    # Step 2: Extract domain and validate
    try:
        domain = email.split('@')[1].lower()
    except IndexError:
        results['messages'].append("❌ Could not extract domain")
        return results
    
    # Step 3: Domain validation
    domain_valid, domain_message = validate_domain(domain)
    results['domain_valid'] = domain_valid
    
    if domain_valid:
        results['messages'].append(f"✅ {domain_message}")
    else:
        results['messages'].append(f"❌ {domain_message}")
        return results
    
    # Step 4: Corporate email check
    is_corp, corp_message = is_corporate_email(email)
    results['is_corporate'] = is_corp
    
    if is_corp:
        results['messages'].append(f"✅ {corp_message}")
    else:
        results['messages'].append(f"❌ {corp_message}")
    
    # Overall validation
    results['is_valid'] = results['format_valid'] and results['domain_valid'] and results['is_corporate']
    
    return results

# Configure the page
st.set_page_config(
    page_title="Aniket Solutions AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stApp {
        max-width: 800px;
        margin: 0 auto;
    }
    
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    
    .chat-message.user {
        background-color: #e3f2fd;
        margin-left: 20%;
    }
    
    .chat-message.assistant {
        background-color: #f5f5f5;
        margin-right: 20%;
    }
    
    .chat-message .message-content {
        margin-top: 0.5rem;
    }
    
    .chat-message .message-time {
        font-size: 0.8rem;
        color: #666;
        margin-bottom: 0.25rem;
    }
    
    .chat-message .sender-name {
        font-weight: bold;
        color: #333;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }
    
    .sidebar .element-container {
        margin-bottom: 1rem;
    }
    
    .main-header {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px solid #f0f0f0;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def add_initial_greeting():
    """Add concise AI-powered greeting message when chat starts"""
    greeting_message = """Hello! I'm Alex from Aniket Solutions. 

I help businesses find the right technology solutions. We specialize in maritime software and custom development services.

To provide relevant information, could you please share your corporate email address?"""
    
    timestamp = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({
        "role": "assistant",
        "content": greeting_message,
        "timestamp": timestamp
    })

def add_message_to_chat(role, content, timestamp=None):
    """Helper function to add messages to chat"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%H:%M")
    
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": timestamp
    })

def show_selection_buttons(question, options, key_prefix):
    """Display selection buttons and handle responses"""
    st.markdown(f"**Assistant:** {question}")
    
    cols = st.columns(len(options))
    for i, option in enumerate(options):
        with cols[i]:
            if st.button(option, key=f"{key_prefix}_{option.lower()}", use_container_width=True):
                return option
    return None

def handle_email_validation_flow(email, validation_result):
    """Handle the flow after email validation with concise AI-powered responses"""
    # Add validation result to chat
    if validation_result['is_valid']:
        validation_response = "✅ Email validated successfully."
        add_message_to_chat("assistant", validation_response)
        
        # Generate and send OTP
        otp = generate_otp()
        success, message = send_otp_email(email, otp)
        
        if success:
            # Store OTP data in session state
            st.session_state.otp_data = {
                "otp": otp,
                "email": email,
                "timestamp": datetime.now(),
                "attempts": 0
            }
            
            st.session_state.conversation_flow["email_validated"] = True
            st.session_state.conversation_flow["awaiting_email"] = False
            st.session_state.conversation_flow["awaiting_otp"] = True
            
            # Concise verification message
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

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_key" not in st.session_state:
    # Use the environment variable API key if available
    if OPENAI_API_KEY:
        st.session_state.api_key = OPENAI_API_KEY
    else:
        st.session_state.api_key = ""

# Initialize OpenAI client in session state
if "openai_client" not in st.session_state:
    if OPENAI_API_KEY:
        st.session_state.openai_client = client
    else:
        st.session_state.openai_client = None

# Initialize selected avatar in session state
if "selected_avatar" not in st.session_state:
    st.session_state.selected_avatar = ALEX_AVATAR_URL

if "conversation_flow" not in st.session_state:
    st.session_state.conversation_flow = {
        "email_validated": False,
        "awaiting_email": True,
        "awaiting_otp": False,
        "otp_verified": False,
        "awaiting_selection": False,
        "selected_category": None,
        "awaiting_specification": False
    }

if "otp_data" not in st.session_state:
    st.session_state.otp_data = None

# Add initial greeting if messages is empty
if len(st.session_state.messages) == 0:
    add_initial_greeting()

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key status (only show if not in environment)
    if not OPENAI_API_KEY:
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.api_key,
            help="Enter your OpenAI API key to enable the chat assistant"
        )
        
        if api_key:
            st.session_state.api_key = api_key
            # Initialize OpenAI client with the new API key
            st.session_state.openai_client = OpenAI(api_key=api_key)
    else:
        st.success("✅ API Key configured from .env file")
        st.session_state.api_key = OPENAI_API_KEY
        if "openai_client" not in st.session_state:
            st.session_state.openai_client = client
    
    # Model selection
    model_options = [
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo-preview"
    ]
    
    selected_model = st.selectbox(
        "Select Model",
        model_options,
        index=0,
        help="Choose the AI model for responses"
    )
    
    # Temperature setting
    temperature = st.slider(
        "Response Creativity",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="Higher values make responses more creative but less focused"
    )
    
    # Max tokens
    max_tokens = st.slider(
        "Max Response Length",
        min_value=50,
        max_value=2000,
        value=500,
        step=50,
        help="Maximum number of tokens in the response"
    )
    
    # System prompt
    system_prompt = st.text_area(
        "System Instructions",
        value="You are a helpful and friendly chat assistant representing Aniket Solutions. Provide clear, accurate, and helpful responses to user questions about our company, services, and products.",
        height=100,
        help="Instructions that define the assistant's behavior"
    )
    
    # Contact Form Integration
    st.subheader("📋 Contact Information")
    st.success("✅ Contact form integration ready")
    st.info(f"📧 Email: {CONTACT_EMAIL}")
    st.info(f"🌐 Contact Form: {CONTACT_FORM_URL}")
    
    if st.button("🔗 Open Contact Form", use_container_width=True):
        st.markdown(f"[Open Contact Form]({CONTACT_FORM_URL})")
    
    # Session Management
    st.subheader("🔄 Session Management")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 Reset Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Session reset!")
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            # Reset conversation flow and add greeting
            st.session_state.conversation_flow = {
                "email_validated": False,
                "awaiting_email": True,
                "awaiting_otp": False,
                "otp_verified": False,
                "awaiting_selection": False,
                "selected_category": None,
                "awaiting_specification": False
            }
            st.session_state.otp_data = None
            add_initial_greeting()
            st.rerun()
    
    st.divider()
    
    # Avatar Customization
    st.subheader("🎭 Avatar Settings")
    
    avatar_choice = st.selectbox(
        "Choose Alex's Avatar Style",
        options=["default", "support_agent", "professional", "friendly", "tech", "custom"],
        format_func=lambda x: {
            "default": "🤖 Default (Friendly Tech)",
            "support_agent": "🎧 Support Agent (Premium)",
            "professional": "💼 Professional",
            "friendly": "😊 Friendly",
            "tech": "👨‍💻 Tech Expert",
            "custom": "🎨 Custom URL"
        }[x],
        key="avatar_selector"
    )
    
    # Update avatar based on selection
    if avatar_choice == "default":
        new_avatar = ALEX_AVATAR_URL
    else:
        new_avatar = ALTERNATIVE_AVATARS[avatar_choice]
    
    if st.session_state.selected_avatar != new_avatar:
        st.session_state.selected_avatar = new_avatar
        st.rerun()
    
    # Preview current avatar
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""
        <div style="text-align: center;">
            <img src="{st.session_state.selected_avatar}" style="width: 60px; height: 60px; border-radius: 50%; border: 2px solid #e0e0e0;">
            <p style="margin-top: 0.5rem; font-size: 0.8rem; color: #666;">Alex's Avatar</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if avatar_choice == "custom":
            custom_url = st.text_input(
                "Custom Avatar URL",
                placeholder="https://example.com/avatar.jpg",
                help="Enter a direct link to an image (JPG, PNG, SVG)"
            )
            if custom_url and st.button("Apply Custom Avatar"):
                st.session_state.selected_avatar = custom_url
                st.success("Custom avatar applied!")
                st.rerun()
    
    st.divider()
    
    # AWS SES status (only show if not configured)
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        st.warning("⚠️ AWS SES not configured. Please add AWS credentials to .env file.")
        with st.expander("AWS SES Configuration Help"):
            st.markdown("""
            **Required .env variables:**
            ```
            AWS_ACCESS_KEY_ID=your-access-key
            AWS_SECRET_ACCESS_KEY=your-secret-key
            AWS_REGION=us-east-1
            SES_FROM_EMAIL=your-verified@email.com  # Optional - will auto-detect
            ```
            
            **Steps to configure:**
            1. Create AWS account and access to SES
            2. Verify your sender email address in SES
            3. Create IAM user with SES permissions
            4. Add credentials to .env file
            """)
    else:
        st.success("✅ AWS SES configured")
        if not SES_FROM_EMAIL:
            st.info("ℹ️ SES_FROM_EMAIL not set - will use first verified email")
        else:
            st.success(f"📧 Sender email: {SES_FROM_EMAIL}")
    
    st.divider()
    
    # Content Moderation Status
    st.subheader("🛡️ Content Moderation")
    if client:
        st.success("✅ Content moderation active")
        st.caption("OpenAI Moderation API + Gibberish Detection")
    else:
        st.warning("⚠️ Content moderation requires OpenAI API")
        st.caption("Basic gibberish detection only")
    
    st.divider()
    
    # Email validation section
    st.subheader("📧 Email Validator")
    
    email_to_validate = st.text_input(
        "Email Address",
        placeholder="Enter email to validate...",
        help="Check if email is valid, domain exists, and is corporate"
    )
    
    if st.button("🔍 Validate Email", use_container_width=True):
        if email_to_validate.strip():
            with st.spinner("Validating email..."):
                # Handle email validation in sidebar
                validation_result = comprehensive_email_validation(email_to_validate.strip())
                
                # Display results
                if validation_result['is_valid']:
                    st.success("✅ Valid Corporate Email!")
                    
                    # Trigger conversation flow
                    handle_email_validation_flow(email_to_validate.strip(), validation_result)
                    st.rerun()
                else:
                    st.error("❌ Email Validation Failed")
                
                # Show detailed results
                with st.expander("Validation Details", expanded=True):
                    for message in validation_result['messages']:
                        st.write(message)
                    
                    # Summary metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Format", "✅" if validation_result['format_valid'] else "❌")
                    with col2:
                        st.metric("Domain", "✅" if validation_result['domain_valid'] else "❌")
                    with col3:
                        st.metric("Corporate", "✅" if validation_result['is_corporate'] else "❌")
        else:
            st.warning("Please enter an email address to validate")
    
    st.divider()
    
    # Export chat button
    if st.session_state.messages and st.button("💾 Export Chat", use_container_width=True):
        chat_data = {
            "timestamp": datetime.now().isoformat(),
            "messages": st.session_state.messages
        }
        st.download_button(
            label="Download Chat History",
            data=json.dumps(chat_data, indent=2),
            file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Main chat interface
st.markdown('<div class="main-header"><h1>🤖 Alex - Aniket Solutions AI Assistant</h1><p>Your intelligent technology consultant</p></div>', unsafe_allow_html=True)

# Display chat messages
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        message_class = "user" if message["role"] == "user" else "assistant"
        timestamp = message.get("timestamp", "")
        
        # Choose sender name based on role
        sender_name = "You" if message["role"] == "user" else "Alex"
        
        st.markdown(f"""
        <div class="chat-message {message_class}">
            <div class="sender-name">{sender_name}</div>
            <div class="message-time">{timestamp}</div>
            <div class="message-content">{message["content"]}</div>
        </div>
        """, unsafe_allow_html=True)

# Handle conversation flow with interactive buttons
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
                add_message_to_chat("user", email_input)
                
                # Validate email
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
        
        Please:
        1. Check your email inbox (and spam folder)
        2. Find the 6-digit verification code
        3. Enter the code below
        
        The verification code will expire in 10 minutes.
        """)
        
        # OTP input
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            otp_input = st.text_input(
                "Enter 6-digit verification code:",
                placeholder="123456",
                max_chars=6,
                key="otp_input",
                help="Enter the 6-digit code sent to your email"
            )
        
        with col2:
            if st.button("✅ Verify Code", key="verify_otp", use_container_width=True):
                if otp_input.strip() and len(otp_input.strip()) == 6:
                    add_message_to_chat("user", f"Entered verification code: {otp_input}")
                    
                    # Verify OTP
                    is_valid, message = verify_otp(otp_input.strip(), st.session_state.otp_data)
                    
                    if is_valid:
                        # Success - concise success message
                        add_message_to_chat("assistant", "✅ Email verified! What business challenges can I help you solve?")
                        
                        st.session_state.conversation_flow["awaiting_otp"] = False
                        st.session_state.conversation_flow["otp_verified"] = True
                        st.session_state.conversation_flow["awaiting_selection"] = False  # Skip rigid selection, go straight to AI conversation
                        
                        st.rerun()
                    else:
                        # Failed verification
                        st.session_state.otp_data["attempts"] = st.session_state.otp_data.get("attempts", 0) + 1
                        add_message_to_chat("assistant", f"❌ {message}")
                        
                        # Check if too many attempts
                        if st.session_state.otp_data["attempts"] >= 3:
                            add_message_to_chat("assistant", 
                                "Too many failed attempts. Please request a new verification code.")
                            # Reset OTP but keep email validated
                            st.session_state.otp_data = None
                            st.session_state.conversation_flow["awaiting_otp"] = False
                            st.session_state.conversation_flow["awaiting_email"] = True
                        
                        st.rerun()
                else:
                    st.warning("Please enter a valid 6-digit code")
        
        with col3:
            if st.button("📧 Resend Code", key="resend_otp", use_container_width=True):
                otp_data = st.session_state.otp_data
                if otp_data:
                    # Generate new OTP
                    new_otp = generate_otp()
                    success, message = send_otp_email(otp_data["email"], new_otp)
                    
                    if success:
                        # Update OTP data
                        st.session_state.otp_data = {
                            "otp": new_otp,
                            "email": otp_data["email"],
                            "timestamp": datetime.now(),
                            "attempts": 0
                        }
                        add_message_to_chat("assistant", "📧 New verification code sent to your email!")
                        st.success("New verification code sent!")
                    else:
                        add_message_to_chat("assistant", f"❌ Failed to resend verification code: {message}")
                        st.error(f"Failed to resend: {message}")
                    st.rerun()

# Chat input functions
def get_ai_response(messages, model, temperature, max_tokens, system_prompt):
    """Get response from OpenAI API using the new v1.0+ interface"""
    try:
        openai_client = st.session_state.get("openai_client")
        if not openai_client:
            return "Error: OpenAI client not initialized. Please check your API key."
        
        # Prepare messages with system prompt
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend([{"role": msg["role"], "content": msg["content"]} 
                           for msg in messages])
        
        # Use the new OpenAI v1.0+ interface
        response = openai_client.chat.completions.create(
            model=model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        
        return response
    except Exception as e:
        return f"Error: {str(e)}"

# Input form (only show if not in flow)
if (not st.session_state.conversation_flow["awaiting_email"] and 
    not st.session_state.conversation_flow["awaiting_otp"]):
    
    with st.form("chat_form", clear_on_submit=True):
        col1, col2 = st.columns([6, 1])
        
        with col1:
            user_input = st.text_input(
                "Message",
                placeholder="Type your message here...",
                label_visibility="collapsed"
            )
        
        with col2:
            send_button = st.form_submit_button("Send", use_container_width=True)

    # Handle user input (only if not in conversation flow)
    if (send_button and user_input.strip() and 
        not st.session_state.conversation_flow["awaiting_email"] and
        not st.session_state.conversation_flow["awaiting_otp"]):
        
        if not st.session_state.api_key:
            st.error("Please configure your OpenAI API key in the .env file to start chatting.")
        else:
            # Content moderation and gibberish detection
            content_is_safe, filter_message = comprehensive_content_filter(user_input)
            
            if not content_is_safe:
                # Add user message first
                add_message_to_chat("user", user_input)
                # Then add moderation response
                add_message_to_chat("assistant", 
                    f"I apologize, but I cannot process your message. {filter_message}\n\n"
                    "Please rephrase your message with a clear business inquiry about our technology solutions or services."
                )
                st.rerun()
            else:
                # Add user message (after passing content filter)
                add_message_to_chat("user", user_input)
                
                # Add special handling for email validation requests in chat
                if any(keyword in user_input.lower() for keyword in ['validate email', 'check email', 'verify email']):
                    # Extract email from user input
                    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    emails_found = re.findall(email_pattern, user_input)
                    
                    if emails_found:
                        email_to_check = emails_found[0]
                        validation_result = comprehensive_email_validation(email_to_check)
                        
                        # Handle email validation and trigger flow
                        if handle_email_validation_flow(email_to_check, validation_result):
                            st.rerun()
                        else:
                            st.rerun()
                    else:
                        add_message_to_chat("assistant", "Please provide an email address to validate.")
                        st.rerun()
                
                # Check if user provided email in regular chat (during email waiting phase)
                elif st.session_state.conversation_flow["awaiting_email"]:
                    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    emails_found = re.findall(email_pattern, user_input)
                    
                    if emails_found:
                        email_to_check = emails_found[0]
                        validation_result = comprehensive_email_validation(email_to_check)
                        
                        if handle_email_validation_flow(email_to_check, validation_result):
                            st.rerun()
                        else:
                            st.rerun()
                    else:
                        add_message_to_chat("assistant", "I need a valid email address to continue. Could you please provide your corporate email?")
                        st.rerun()
                
                # Get AI response for general queries (only after email validation and OTP verification)
                elif (not any(keyword in user_input.lower() for keyword in ['validate email', 'check email', 'verify email']) and 
                      st.session_state.conversation_flow["email_validated"] and 
                      st.session_state.conversation_flow["otp_verified"]):
                    
                    # Use AI-powered response system
                    with st.spinner("Thinking..."):
                        try:
                            # Always check knowledge base first - much more permissive matching
                            if (any(word in user_input.lower() for word in [
                                # Maritime terms
                                'crew', 'ship', 'vessel', 'maritime', 'marine', 'seafarer',
                                'inventory', 'spare', 'maintenance', 'procurement', 'tms',
                                'payroll', 'crewing', 'technical', 'purchasing', 'supplier',
                                # Technology terms  
                                'software', 'app', 'mobile', 'ai', 'development', 'custom',
                                'system', 'integration', 'data', 'analytics', 'automation',
                                'chatbot', 'solution', 'technology', 'service',
                                # Business terms
                                'management', 'control', 'tracking', 'compliance', 'workflow'
                            ]) or search_company_info(user_input)):
                                ai_response = get_smart_company_response(user_input)
                            else:
                                # Use pure AI for general business conversation
                                ai_response = generate_ai_response(user_input, st.session_state.messages)
                            
                            add_message_to_chat("assistant", ai_response)
                            st.rerun()
                            
                        except Exception as e:
                            # Fallback to contact form if there's an error
                            fallback_response = generate_contact_form_response(
                                "I'm experiencing some technical difficulties at the moment."
                            )
                            add_message_to_chat("assistant", fallback_response)
                            st.rerun()
                
                # If user tries to chat before email validation and OTP verification
                elif not (st.session_state.conversation_flow["email_validated"] and st.session_state.conversation_flow["otp_verified"]):
                    if not st.session_state.conversation_flow["email_validated"]:
                        add_message_to_chat("assistant", "I'd be happy to help! But first, I need your corporate email address to continue. Could you please provide it?")
                    elif not st.session_state.conversation_flow["otp_verified"]:
                        add_message_to_chat("assistant", "Please verify your email with the OTP code sent to your email address before we can continue.")
                    st.rerun()

# Show welcome message only if no API key
if not st.session_state.api_key and not st.session_state.messages:
    st.info("Please configure your OpenAI API key in the .env file to start the chat assistant.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "Built with Streamlit • Powered by OpenAI GPT-4 • Alex - Aniket Solutions AI Assistant"
    "</div>",
    unsafe_allow_html=True
)
