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
ALEX_AVATAR_URL = "https://raw.githubusercontent.com/AShirsat96/WebsiteChatbot/main/Alex_AI_Avatar.png"
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

def get_product_response(query):
    """Get detailed response based on product knowledge base"""
    query_lower = query.lower()
    
    # Product matching with better keyword coverage
    if any(word in query_lower for word in ['inventory', 'stock', 'spare', 'consumable', 'stores', 'rob']):
        return f"""**AniSol Inventory Control - Fleet-Wide Inventory Management**

{PRODUCT_KNOWLEDGE_BASE['inventory_control']}

**Key Benefits:**
• Real-time inventory tracking across your entire fleet
• Automated alerts for low stock levels
• Seamless integration with maintenance and procurement systems
• Works offline on ships, syncs when connected

Would you like to know more about specific features or see a demo? For detailed implementation plans and pricing, please contact our specialists at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['payroll', 'wages', 'salary', 'cash', 'crew payment', 'master cash']):
        return f"""**AniSol Payroll & Master Cash System**

{PRODUCT_KNOWLEDGE_BASE['payroll_master_cash']}

**Key Benefits:**
• Automated payroll calculations with maritime compliance
• Multi-currency support for global operations
• Complete audit trails for all transactions
• Seamless integration with accounting systems

For detailed configuration options and pricing, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['crew', 'crewing', 'staff', 'personnel', 'maritime crew', 'seafarer']):
        return f"""**AniSol Crewing Module - Complete Crew Management**

{PRODUCT_KNOWLEDGE_BASE['crewing_module']}

**Key Benefits:**
• Complete crew lifecycle management
• Automated compliance tracking
• Performance analytics and reporting
• Cloud-first, scalable infrastructure

For specific implementation details and pricing, please contact our specialists at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['tms', 'maintenance', 'technical', 'planned maintenance', 'pms']):
        return f"""**AniSol TMS - Technical Management System**

{PRODUCT_KNOWLEDGE_BASE['tms']}

**Key Benefits:**
• Designed by seafarers for real ship operations
• Ultra-low bandwidth usage for satellite connections
• Complete maintenance history and analytics
• No dedicated server needed

For vessel-specific configuration and implementation, please contact our specialists at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['procurement', 'purchasing', 'supplier', 'vendor', 'po', 'purchase order']):
        return f"""**AniSol Procurement - AI-Powered Maritime Purchasing**

{PRODUCT_KNOWLEDGE_BASE['procurement']}

**Key Benefits:**
• AI-powered procurement analytics
• Complete vendor management system
• Automated approval workflows
• Full audit trails and compliance

For detailed implementation and pricing information, please contact our team at info@aniketsolutions.com"""

    # General product inquiry
    else:
        return f"""**AniSol Maritime Software Suite - Complete Fleet Management**

We offer a comprehensive suite of maritime software products:

🚢 **AniSol TMS** - Technical Management & Maintenance
🚢 **AniSol Procurement** - AI-Powered Purchasing System
🚢 **AniSol Inventory Control** - Fleet-Wide Inventory Management
🚢 **AniSol Crewing Module** - Complete Crew Management
🚢 **AniSol Payroll & Master Cash** - Crew Financial Management

**All Products Feature:**
• Ship & Cloud Ready: Work offline, sync when connected
• Maritime-Specific: Built by seafarers for real operations
• Integrated Suite: All modules work seamlessly together
• Compliance Ready: Flag state, STCW, MLC compliance built-in
• Global Support: Multi-currency, multi-language capabilities

Which specific product area interests you most? I can provide detailed information about any of our solutions.

For comprehensive demos and implementation planning, please contact our team at info@aniketsolutions.com"""

def get_service_response(query):
    """Get detailed response based on services knowledge base"""
    query_lower = query.lower()
    
    # Service matching with comprehensive keywords
    if any(word in query_lower for word in ['custom', 'development', 'software', 'application', 'web app', 'bespoke']):
        return f"""**Custom Application Development Services**

{SERVICES_KNOWLEDGE_BASE['custom_development']}

**Our Development Process:**
• **Discovery & Planning**: Understanding your unique requirements
• **Design & Architecture**: Creating scalable, maintainable solutions
• **Agile Development**: Iterative development with regular feedback
• **Testing & QA**: Comprehensive testing for reliability
• **Deployment & Support**: Ongoing maintenance and updates

**Why Choose Our Custom Development:**
• 20+ years of experience across multiple industries
• Proven track record of successful implementations
• Modern technologies and best practices
• Cost-effective solutions with excellent ROI

For project consultation and development quotes, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['mobile', 'app', 'ios', 'android', 'smartphone', 'tablet', 'pwa']):
        return f"""**Mobile Solutions Services**

{SERVICES_KNOWLEDGE_BASE['mobile_solutions']}

**Mobile Development Approach:**
• **Native Development**: Platform-specific apps for optimal performance
• **Cross-Platform**: Cost-effective solutions using React Native/Flutter
• **Progressive Web Apps**: Browser-based apps with native-like experience
• **Enterprise Integration**: Seamless connection with your existing systems

**Industry Applications:**
• Maritime: Vessel inspections, maintenance tracking, crew management
• Field Services: Work order management, asset tracking
• Logistics: Delivery tracking, inventory management
• Healthcare: Patient management, appointment scheduling

For mobile app development consultation and estimates, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['ai', 'artificial intelligence', 'machine learning', 'chatbot', 'automation', 'ml']):
        return f"""**AI & Machine Learning Services**

{SERVICES_KNOWLEDGE_BASE['ai_machine_learning']}

**AI Implementation Process:**
• **Needs Assessment**: Understanding your automation goals
• **Data Analysis**: Evaluating your data readiness for AI
• **Model Development**: Creating custom AI solutions
• **Integration**: Seamlessly connecting AI with existing systems
• **Training & Support**: Ensuring your team can leverage AI effectively

**Real-World AI Applications:**
• **Maritime**: Predictive maintenance, route optimization, crew scheduling
• **Manufacturing**: Quality control, predictive maintenance, supply chain optimization
• **Healthcare**: Medical image analysis, patient risk assessment
• **Finance**: Fraud detection, risk assessment, automated reporting

For AI project consultation and development timelines, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['data', 'database', 'migration', 'analytics', 'reporting', 'etl', 'warehouse']):
        return f"""**Data Services**

{SERVICES_KNOWLEDGE_BASE['data_services']}

**Data Migration Expertise:**
• **Legacy Modernization**: Moving from outdated systems to modern platforms
• **Cloud Migration**: Transitioning to AWS, Azure, or Google Cloud
• **Database Upgrades**: Oracle to PostgreSQL, SQL Server modernization
• **Zero Downtime**: Seamless transitions without business interruption

**Data Analytics Solutions:**
• **Business Intelligence**: Transform raw data into actionable insights
• **Real-Time Dashboards**: Monitor key metrics and KPIs
• **Predictive Analytics**: Forecast trends and optimize operations
• **Compliance Reporting**: GDPR, HIPAA, SOX compliant solutions

For data migration consultation and analytics implementation, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['integration', 'api', 'connect', 'sync', 'system integration', 'erp', 'crm']):
        return f"""**System Integration Services**

{SERVICES_KNOWLEDGE_BASE['system_integration']}

**Integration Expertise:**
• **Enterprise Systems**: ERP, CRM, HRM, financial systems
• **Cloud & On-Premise**: Hybrid integrations for modern businesses
• **Legacy Connectivity**: Connecting older systems with modern platforms
• **Real-Time Data**: Event-driven integrations for instant updates

**Common Integration Scenarios:**
• **Maritime**: TMS-ERP integration, crew management-payroll sync
• **Manufacturing**: Production systems with inventory management
• **Healthcare**: Patient records with billing systems
• **Retail**: E-commerce platforms with inventory and accounting

For system integration consultation and architecture planning, please contact our team at info@aniketsolutions.com"""

    elif any(word in query_lower for word in ['chatbot', 'virtual assistant', 'customer service', 'conversational ai']):
        return f"""**AI Chatbot & Virtual Assistant Services**

{SERVICES_KNOWLEDGE_BASE['ai_chatbots']}

**Chatbot Implementation Process:**
• **Requirements Analysis**: Understanding your customer service needs
• **Conversation Design**: Creating natural, helpful interactions
• **AI Training**: Teaching the bot about your business and services
• **Integration**: Connecting with your existing systems and channels
• **Optimization**: Continuous improvement based on usage data

**Chatbot Capabilities:**
• **24/7 Availability**: Never miss a customer inquiry
• **Multi-Channel**: Website, WhatsApp, Facebook, SMS integration
• **Intelligent Routing**: Escalate complex issues to human agents
• **Data Collection**: Gather customer insights and preferences

For chatbot consultation and implementation planning, please contact our team at info@aniketsolutions.com"""

    # General services inquiry
    else:
        return f"""**Aniket Solutions Technology Services**

We provide comprehensive technology services to help businesses grow and optimize:

💻 **Custom Development** - Bespoke software solutions for unique business needs
📱 **Mobile Applications** - iOS/Android development and cross-platform solutions
🤖 **AI & Machine Learning** - Intelligent automation and predictive analytics
📊 **Data Services** - Migration, warehousing, analytics, and modernization
🔗 **System Integration** - API development and enterprise connectivity
💬 **AI Chatbots** - 24/7 customer service automation

**Our Service Approach:**
• **Discovery First**: We understand your business before proposing solutions
• **Agile Methodology**: Iterative development with regular feedback
• **Quality Assurance**: Comprehensive testing and validation
• **Ongoing Support**: Long-term partnership beyond project delivery

**Industries We Serve:**
• Maritime & Shipping
• Manufacturing & Logistics
• Healthcare & Finance
• Retail & E-commerce
• Professional Services

Which service area interests you most? I can provide detailed information about our approach and capabilities.

For service consultation and project planning, please contact our team at info@aniketsolutions.com"""

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

# Enhanced AI Assistant Configuration for Product/Service Selection
AI_ASSISTANT_PROMPT = """
You are Alex, a professional and knowledgeable AI assistant for Aniket Solutions, a leading technology solutions provider established in 2004. You help clients understand our products and services in detail.

## About Aniket Solutions:
- Established: February 2004 in Singapore
- Global presence: USA, UK, Cyprus, Greece, India, Japan, Singapore, Hong Kong
- Expertise: Maritime technology solutions and general technology services
- Focus: Cost-effective, efficient solutions with understanding of diverse work cultures

## Your Knowledge Base:
You have access to comprehensive knowledge about:

### Products (Maritime Software):
- AniSol Inventory Control - Fleet-wide inventory management
- AniSol Payroll & Master Cash - Crew financial management
- AniSol Crewing Module - Complete crew management
- AniSol TMS - Technical Management System
- AniSol Procurement - AI-powered maritime purchasing

### Services (Technology Services):
- Custom Application Development - Bespoke software solutions
- Mobile Solutions - iOS/Android development
- AI & Machine Learning - Intelligent automation
- Data Services - Migration, analytics, warehousing
- System Integration - API development, connectivity
- AI Chatbots - Customer service automation

## Your Role:
- Provide detailed, accurate information based strictly on your knowledge base
- Be helpful and professional without being overly sales-focused
- Ask clarifying questions to understand specific needs
- Direct to contact form for complex implementation details or pricing
- Never hallucinate or make up information not in your knowledge base

## Response Guidelines:
- Use the exact information from the knowledge base
- If you don't have specific information, direct them to contact the team
- Provide detailed feature descriptions when available
- Ask follow-up questions to understand their specific requirements
- Suggest appropriate next steps (consultation, demo, contact)

## When You Can't Answer:
For questions about pricing, specific implementation details, custom requirements, or anything not in your knowledge base, respond with:
"That's an excellent question that requires detailed input from our specialists. Please contact our team at info@aniketsolutions.com for specific information tailored to your situation."

## Contact Information:
- Email: info@aniketsolutions.com
- Website: www.aniketsolutions.com

Remember: Stick strictly to the knowledge base information. Never make up features, capabilities, or details that aren't explicitly provided.
"""

def generate_ai_response(user_message, selected_category):
    """Generate AI response based on selected category (products or services)"""
    try:
        if not st.session_state.get("openai_client"):
            return "I'm experiencing technical difficulties. Please contact our team at info@aniketsolutions.com for assistance."
        
        # Use knowledge base first based on category
        if selected_category == "products":
            # Check if we can answer from product knowledge base
            response = get_product_response(user_message)
            if "AniSol" in response:  # If we found a specific product match
                return response
        elif selected_category == "services":
            # Check if we can answer from services knowledge base
            response = get_service_response(user_message)
            if any(service in response for service in ["Custom Application", "Mobile Solutions", "AI &", "Data Services", "System Integration"]):
                return response
        
        # If no specific match in knowledge base, use AI with category context
        category_context = ""
        if selected_category == "products":
            category_context = f"""
The user is interested in our PRODUCTS (Maritime Software). Relevant products include:
{chr(10).join([f"- {key}: {value[:200]}..." for key, value in PRODUCT_KNOWLEDGE_BASE.items()])}
"""
        elif selected_category == "services":
            category_context = f"""
The user is interested in our SERVICES (Technology Services). Relevant services include:
{chr(10).join([f"- {key}: {value[:200]}..." for key, value in SERVICES_KNOWLEDGE_BASE.items()])}
"""
        
        # Prepare messages for AI
        messages = [
            {"role": "system", "content": AI_ASSISTANT_PROMPT + category_context},
            {"role": "user", "content": user_message}
        ]
        
        # Generate response
        response = st.session_state.openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,  # Lower temperature for more focused responses
            max_tokens=300,
            presence_penalty=0.1,
            frequency_penalty=0.1
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Ensure response doesn't hallucinate
        if any(phrase in ai_response.lower() for phrase in [
            "i don't have specific information",
            "i'm not sure about",
            "i don't know",
            "that's not in my knowledge"
        ]):
            return "That's an excellent question that requires detailed input from our specialists. Please contact our team at info@aniketsolutions.com for specific information tailored to your situation."
        
        return ai_response
        
    except Exception as e:
        return "I'm experiencing technical difficulties. Please contact our team at info@aniketsolutions.com for assistance."

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
        margin-left: 10%;
    }
    
    .chat-message.assistant {
        background-color: #f5f5f5;
        margin-right: 10%;
    }
    
    .chat-message img {
        object-fit: cover;
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
    
    /* Ensure images load properly */
    .chat-message img {
        max-width: 45px;
        max-height: 45px;
        width: 45px;
        height: 45px;
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
</style>
""", unsafe_allow_html=True)

def add_initial_greeting():
    """Add initial AI-powered greeting message when chat starts"""
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

def handle_email_validation_flow(email, validation_result):
    """Handle the flow after email validation"""
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
            
            # Verification message
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
    
    # AWS SES status
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        st.warning("⚠️ AWS SES not configured. Please add AWS credentials to .env file.")
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

# Main chat interface
st.markdown('<div class="main-header"><h1>🤖 Alex - Aniket Solutions AI Assistant</h1><p>Your intelligent technology consultant</p></div>', unsafe_allow_html=True)

# Display chat messages
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        message_class = "user" if message["role"] == "user" else "assistant"
        timestamp = message.get("timestamp", "")
        
        # Choose sender name and avatar based on role
        if message["role"] == "user":
            sender_name = "You"
            avatar_url = USER_AVATAR_URL
        else:
            sender_name = "Alex"
            avatar_url = st.session_state.selected_avatar
        
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
                        # Success - move to product/service selection
                        add_message_to_chat("assistant", "✅ Email verified! What would you like to know more about?")
                        
                        st.session_state.conversation_flow["awaiting_otp"] = False
                        st.session_state.conversation_flow["otp_verified"] = True
                        st.session_state.conversation_flow["awaiting_selection"] = True
                        
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

# Product/Service Selection Flow
elif st.session_state.conversation_flow["awaiting_selection"]:
    st.markdown("---")
    st.markdown("**What would you like to know more about?**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚢 Maritime Products", key="select_products", use_container_width=True):
            add_message_to_chat("user", "I'm interested in your maritime products")
            
            # Set category and provide overview
            st.session_state.conversation_flow["selected_category"] = "products"
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            products_overview = """Great choice! Our **AniSol Maritime Software Suite** includes:

🚢 **AniSol TMS** - Technical Management & Maintenance System
🚢 **AniSol Procurement** - AI-Powered Maritime Purchasing 
🚢 **AniSol Inventory Control** - Fleet-Wide Inventory Management
🚢 **AniSol Crewing Module** - Complete Crew Management
🚢 **AniSol Payroll & Master Cash** - Crew Financial Management

All our maritime products are:
• **Ship & Cloud Ready** - Work offline, sync when connected
• **Maritime-Specific** - Built by seafarers for real operations  
• **Integrated Suite** - All modules work seamlessly together
• **Compliance Ready** - Flag state, STCW, MLC compliance built-in

Which specific product interests you most, or do you have questions about any particular area?"""
            
            add_message_to_chat("assistant", products_overview)
            st.rerun()
    
    with col2:
        if st.button("💻 Technology Services", key="select_services", use_container_width=True):
            add_message_to_chat("user", "I'm interested in your technology services")
            
            # Set category and provide overview
            st.session_state.conversation_flow["selected_category"] = "services"
            st.session_state.conversation_flow["awaiting_selection"] = False
            
            services_overview = """Excellent! Our **Technology Services** help businesses innovate and grow:

💻 **Custom Development** - Bespoke software solutions for unique business needs
📱 **Mobile Applications** - iOS/Android development and cross-platform solutions
🤖 **AI & Machine Learning** - Intelligent automation and predictive analytics
📊 **Data Services** - Migration, warehousing, analytics, and modernization
🔗 **System Integration** - API development and enterprise connectivity
💬 **AI Chatbots** - 24/7 customer service automation

**Our Approach:**
• **Discovery First** - We understand your business before proposing solutions
• **Agile Methodology** - Iterative development with regular feedback
• **Quality Assurance** - Comprehensive testing and validation
• **Ongoing Support** - Long-term partnership beyond project delivery

**Industries We Serve:** Maritime, Manufacturing, Healthcare, Finance, Retail, Professional Services

What type of technology challenge are you looking to solve, or which service area interests you most?"""
            
            add_message_to_chat("assistant", services_overview)
            st.rerun()

# Chat input (only show after category selection or during conversation)
if (not st.session_state.conversation_flow["awaiting_email"] and 
    not st.session_state.conversation_flow["awaiting_otp"] and
    not st.session_state.conversation_flow["awaiting_selection"]):
    
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

    # Handle user input
    if send_button and user_input.strip():
        if not st.session_state.api_key:
            st.error("Please configure your OpenAI API key to start chatting.")
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
                
                # Get response based on selected category
                selected_category = st.session_state.conversation_flow.get("selected_category")
                
                if selected_category:
                    with st.spinner("Thinking..."):
                        try:
                            ai_response = generate_ai_response(user_input, selected_category)
                            add_message_to_chat("assistant", ai_response)
                            st.rerun()
                            
                        except Exception as e:
                            # Fallback response
                            fallback_response = "I'm experiencing some technical difficulties. Please contact our team at info@aniketsolutions.com for assistance."
                            add_message_to_chat("assistant", fallback_response)
                            st.rerun()
                else:
                    # If no category selected, prompt for selection
                    add_message_to_chat("assistant", "Please select whether you're interested in our Maritime Products or Technology Services first.")
                    st.session_state.conversation_flow["awaiting_selection"] = True
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
