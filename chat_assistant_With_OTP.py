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

# Configure the page
st.set_page_config(
    page_title="Aniket Solutions - AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# ADVANCED KEEP-ALIVE SYSTEM TO PREVENT STREAMLIT SLEEPING
# =============================================================================

def keep_alive_system():
    """Advanced keep-alive system to prevent Streamlit app from sleeping"""
    
    # Initialize session state for activity tracking
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = datetime.now()
        st.session_state.app_start_time = datetime.now()
        st.session_state.interaction_count = 0
        st.session_state.last_message_count = 0
        st.session_state.heartbeat_count = 0
    
    # Update activity timestamp on any interaction
    current_time = datetime.now()
    
    # Track interactions (messages, button clicks, etc.)
    current_message_count = len(st.session_state.get("messages", []))
    if current_message_count > st.session_state.last_message_count:
        st.session_state.last_activity = current_time
        st.session_state.interaction_count += 1
        st.session_state.last_message_count = current_message_count
    
    # Auto-refresh logic - refresh if inactive for 8 minutes
    time_since_activity = current_time - st.session_state.last_activity
    uptime = current_time - st.session_state.app_start_time
    
    # Refresh if inactive too long (but not immediately on first load)
    if time_since_activity.total_seconds() > 480 and uptime.total_seconds() > 60:  # 8 minutes
        st.session_state.last_activity = current_time
        st.session_state.heartbeat_count += 1
        st.rerun()

def add_javascript_keepalive():
    """Add comprehensive JavaScript keep-alive system"""
    js_code = """
    <script>
    // Advanced Keep-alive system for Streamlit
    let keepAliveInterval;
    let activityTimeout;
    let heartbeatCount = 0;
    
    function logActivity(action) {
        console.log(`Keep-alive: ${action} at ${new Date().toLocaleTimeString()}`);
    }
    
    function sendHeartbeat() {
        fetch(window.location.href, {
            method: 'HEAD',
            cache: 'no-cache'
        }).then(() => {
            heartbeatCount++;
            logActivity(`Heartbeat #${heartbeatCount} sent`);
        }).catch(err => {
            console.warn('Heartbeat failed:', err);
        });
    }
    
    function resetActivity() {
        clearTimeout(activityTimeout);
        logActivity('User activity detected');
        
        // Send heartbeat after 7 minutes of inactivity
        activityTimeout = setTimeout(function() {
            logActivity('Inactivity timeout - sending heartbeat');
            sendHeartbeat();
        }, 420000); // 7 minutes
    }
    
    // Monitor user interactions
    const events = ['click', 'keypress', 'scroll', 'mousemove', 'touchstart'];
    events.forEach(event => {
        document.addEventListener(event, resetActivity, { passive: true });
    });
    
    // Initial setup
    resetActivity();
    
    // Regular heartbeat every 4 minutes
    keepAliveInterval = setInterval(function() {
        sendHeartbeat();
    }, 240000); // 4 minutes
    
    // Page visibility change handling
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            logActivity('Page became visible');
            sendHeartbeat();
        }
    });
    
    // Window focus/blur handling
    window.addEventListener('focus', function() {
        logActivity('Window focused');
        resetActivity();
    });
    
    logActivity('Keep-alive system initialized');
    sendHeartbeat(); // Initial heartbeat
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)

def add_auto_refresh():
    """Add emergency auto-refresh to prevent long-term sleeping"""
    refresh_code = """
    <script>
    // Emergency auto-refresh after 20 minutes
    setTimeout(function(){
        console.log('Emergency auto-refresh activated to prevent sleep...');
        // Show user a brief message before refresh
        if (confirm('App refreshing to maintain connection. Continue?')) {
            window.location.reload(1);
        } else {
            window.location.reload(1); // Refresh anyway after 5 seconds
        }
    }, 1200000); // 20 minutes
    </script>
    """
    st.markdown(refresh_code, unsafe_allow_html=True)

def add_service_worker():
    """Add service worker for background keep-alive"""
    sw_code = """
    <script>
    // Register service worker for background activity
    if ('serviceWorker' in navigator) {
        const swCode = `
            self.addEventListener('message', function(event) {
                if (event.data && event.data.type === 'SKIP_WAITING') {
                    self.skipWaiting();
                }
            });
            
            setInterval(() => {
                fetch('/', {method: 'HEAD'}).catch(() => {});
            }, 300000); // 5 minutes
        `;
        
        const blob = new Blob([swCode], {type: 'application/javascript'});
        const swUrl = URL.createObjectURL(blob);
        
        navigator.serviceWorker.register(swUrl).then(function(registration) {
            console.log('Keep-alive service worker registered');
        }).catch(function(error) {
            console.log('Service worker registration failed:', error);
        });
    }
    </script>
    """
    st.markdown(sw_code, unsafe_allow_html=True)

# Avatar Configuration
ALEX_AVATAR_URL = "https://raw.githubusercontent.com/AShirsat96/WebsiteChatbot/main/Alex_AI_Avatar.png"
USER_AVATAR_URL = "https://api.dicebear.com/7.x/initials/svg?seed=User&backgroundColor=4f46e5&fontSize=40"

# Alternative avatar options (you can change these URLs)
ALTERNATIVE_AVATARS = {
    "professional": "https://api.dicebear.com/7.x/avataaars/svg?seed=Professional&backgroundColor=e0e7ff&clothesColor=3730a3&eyebrowType=default&eyeType=default&facialHairType=default&hairColor=brown&mouthType=smile&skinColor=light&topType=shortHairShortFlat",
    "friendly": "https://api.dicebear.com/7.x/avataaars/svg?seed=Friendly&backgroundColor=dcfce7&clothesColor=166534&eyebrowType=default&eyeType=happy&facialHairType=default&hairColor=black&mouthType=smile&skinColor=light&topType=shortHairDreads01",
    "tech": "https://api.dicebear.com/7.x/avataaars/svg?seed=Tech&backgroundColor=f3f4f6&clothesColor=1f2937&eyebrowType=default&eyeType=default&facialHairType=default&hairColor=brown&mouthType=smile&skinColor=light&topType=shortHairShortCurly",
    "support_agent": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDIwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIyMDAiIGhlaWdodD0iMjAwIiBmaWxsPSIjZjBmOWZmIiByeD0iMTAwIi8+CjwhLS0gSGVhZCAtLT4KPGNpcmNsZSBjeD0iMTAwIiBjeT0iODAiIHI9IjM1IiBmaWxsPSIjZmJiZjI0Ii8+CjwhLS0gSGFpciAtLT4KPHBhdGggZD0ibTY1IDYwYzAtMjAgMTUtMzUgMzUtMzVzMzUgMTUgMzUgMzVjMCAxMC01IDIwLTE1IDI1aC00MGMtMTAtNS0xNS0xNS0xNS0yNVoiIGZpbGw9IiM0YTQ3NGQiLz4KPCEtLSBHeWVzIC0tPgo8Y2lyY2xlIGN4PSI5MCIgY3k9Ijc1IiByPSI0IiBmaWxsPSIjMDAwIi8+CjxjaXJjbGUgY3g9IjExMCIgY3k9Ijc1IiByPSI0IiBmaWxsPSIjMDAwIi8+CjwhLS0gR2xhc3NlcyAtLT4KPHJlY3QgeD0iODAiIHk9IjY4IiB3aWR0aD0iNDAiIGhlaWdodD0iMjAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMCIgc3Ryb2tlLXdpZHRoPSIyIiByeD0iNSIvPgo8IS0tIE5vc2UgLS0+CjxjaXJjbGUgY3g9IjEwMCIgY3k9Ijg1IiByPSIyIiBmaWxsPSIjZDY5ZTJlIi8+CjwhLS0gTW91dGggLS0+CjxwYXRoIGQ9Im05MCA5NWMwIDUgNSAxMCAxMCAxMHMxMC01IDEwLTEwIiBzdHJva2U9IiMwMDAiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIvPgo8IS0tIEhlYWRzZXQgLS0+CjxwYXRoIGQ9Im03MCA2NWMtMTAgMC0xNSA1LTE1IDE1czUgMTUgMTUgMTVoNjBjMTAgMCAxNS01IDE1LTE1cy01LTE1LTE1LTE1IiBzdHJva2U9IiMzNzM3MzciIHN0cm9rZS13aWR0aD0iMyIgZmlsbD0ibm9uZSIvPgo8Y2lyY2xlIGN4PSI3MCIgY3k9IjgwIiByPSI4IiBmaWxsPSIjMzczNzM3Ii8+CjxjaXJjbGUgY3g9IjEzMCIgY3k9IjgwIiByPSI4IiBmaWxsPSIjMzczNzM3Ii8+CjwhLS0gTWljIC0tPgo8bGluZSB4MT0iMTMwIiB5MT0iODAiIHgyPSIxMjAiIHkyPSIxMDAiIHN0cm9rZT0iIzM3MzczNyIgc3Ryb2tlLXdpZHRoPSIyIi8+CjxyZWN0IHg9IjExNSIgeT0iMTAwIiB3aWR0aD0iMTAiIGhlaWdodD0iOCIgZmlsbD0iIzM3MzczNyIgcng9IjIiLz4KPCEtLSBCb2R5IC0tPgo8cmVjdCB4PSI3NSIgeT0iMTE1IiB3aWR0aD0iNTAiIGhlaWdodD0iNjAiIGZpbGw9IiMyZDM3NDgiIHJ4PSI1Ii8+CjxyZWN0IHg9IjgwIiB5PSIxMjAiIHdpZHRoPSI0MCIgaGVpZ2h0PSIzMCIgZmlsbD0iIzM5OGVkYiIgcng9IjMiLz4KPC9zdmc+",
    "custom": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face&auto=format"
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

# =============================================================================
# COMPREHENSIVE KEYWORD MAPPING FOR PRODUCTS AND SERVICES
# =============================================================================

INVENTORY_KEYWORDS = [
    # Primary terms
    'inventory', 'stock', 'spare', 'spares', 'consumable', 'consumables', 'stores', 'rob',
    'parts', 'supplies', 'materials', 'warehouse', 'storage', 'stockroom',
    
    # Maritime-specific
    'ship stores', 'vessel inventory', 'marine supplies', 'deck stores', 'engine room stores',
    'provision stores', 'slop chest', 'bond stores', 'ship chandler', 'chandlery',
    
    # Operational terms
    'reorder', 'requisition', 'shortage', 'stock level', 'stock control', 'asset tracking',
    'store keeping', 'storekeeping', 'procurement requisition', 'stock management',
    'remaining onboard', 'onboard inventory', 'ship inventory', 'fleet inventory',
    
    # Technical terms
    'component mapping', 'spare parts management', 'consumable tracking', 'stock alerts',
    'inventory optimization', 'stock rotation', 'expiry tracking', 'shelf life',
    'inventory audit', 'stock count', 'cycle counting', 'stock reconciliation'
]

PAYROLL_KEYWORDS = [
    # Primary terms
    'payroll', 'wages', 'salary', 'cash', 'crew payment', 'master cash', 'pay', 
    'compensation', 'finance', 'money', 'advance', 'payment',
    
    # Maritime-specific
    'crew wages', 'seafarer pay', 'maritime payroll', 'ship payroll', 'vessel payroll',
    'portage bill', 'crew account', 'seaman wages', 'mariner pay', 'sailor wages',
    'crew compensation', 'maritime salary', 'ship crew pay',
    
    # Financial terms
    'overtime', 'bonus', 'allowance', 'deduction', 'allotment', 'tax', 'contribution',
    'salary advance', 'cash advance', 'loan', 'fine', 'penalty', 'reimbursement',
    'petty cash', 'cash management', 'crew cash', 'onboard cash',
    
    # Currency & banking
    'multi currency', 'exchange rate', 'currency conversion', 'foreign exchange',
    'bank transfer', 'wire transfer', 'remittance', 'crew banking',
    
    # Compliance
    'mla compliance', 'flag state requirements', 'crew contract', 'employment agreement'
]

CREWING_KEYWORDS = [
    # Primary terms
    'crew', 'crewing', 'staff', 'personnel', 'maritime crew', 'seafarer', 'seafarers',
    'manning', 'human resources', 'hr', 'employee', 'employees', 'crew management',
    
    # Maritime roles
    'captain', 'master', 'chief officer', 'engineer', 'bosun', 'seaman', 'able seaman',
    'ordinary seaman', 'deck crew', 'engine crew', 'galley crew', 'steward', 'cook',
    'chief engineer', 'second engineer', 'third engineer', 'oiler', 'wiper', 'fitter',
    
    # Crew operations
    'crew scheduling', 'crew rotation', 'crew deployment', 'crew planning', 'shift management',
    'watch keeping', 'duty roster', 'crew roster', 'manning schedule', 'crew assignment',
    'embarkation', 'disembarkation', 'sign on', 'sign off', 'crew change',
    
    # Documentation & compliance
    'crew documents', 'certificates', 'endorsements', 'stcw', 'mlc', 'flag state',
    'medical certificate', 'passport', 'visa', 'seamans book', 'discharge book',
    'coc', 'certificate of competency', 'endorsement', 'training records',
    
    # Performance & development
    'crew appraisal', 'performance review', 'competency assessment', 'training',
    'crew evaluation', 'performance management', 'skill assessment', 'crew development',
    'crew performance', 'crew rating', 'crew feedback'
]

TMS_KEYWORDS = [
    # Primary terms
    'tms', 'maintenance', 'technical', 'planned maintenance', 'pms', 'repair', 'repairs',
    'equipment', 'machinery', 'technical management', 'maintenance management',
    
    # Maintenance types
    'preventive maintenance', 'corrective maintenance', 'predictive maintenance',
    'condition based maintenance', 'routine maintenance', 'scheduled maintenance',
    'unplanned maintenance', 'emergency repair', 'breakdown', 'overhaul',
    
    # Maritime equipment
    'engine', 'main engine', 'auxiliary engine', 'generator', 'pump', 'compressor',
    'boiler', 'heat exchanger', 'separator', 'purifier', 'winch', 'crane', 'hatch cover',
    'steering gear', 'propeller', 'shaft', 'bearing', 'valve', 'pipe', 'tank',
    
    # Inspections & surveys
    'inspection', 'survey', 'class survey', 'dry dock', 'intermediate survey',
    'annual survey', 'special survey', 'psc', 'port state control', 'flag state inspection',
    'vetting inspection', 'internal audit', 'safety inspection',
    
    # Certificates & compliance
    'certificate', 'class certificate', 'safety certificate', 'statutory certificate',
    'renewal', 'extension', 'endorsement', 'survey due', 'certificate expiry',
    
    # Work orders & documentation
    'work order', 'job card', 'maintenance report', 'defect', 'non conformity',
    'finding', 'observation', 'maintenance log', 'engine log', 'technical log',
    
    # Technical systems
    'condition monitoring', 'vibration monitoring', 'oil analysis', 'performance monitoring',
    'alarm system', 'automation', 'control system', 'instrumentation'
]

PROCUREMENT_KEYWORDS = [
    # Primary terms
    'procurement', 'purchasing', 'supplier', 'vendor', 'po', 'purchase order',
    'buying', 'sourcing', 'rfq', 'request for quotation', 'quotation', 'quote',
    
    # Maritime procurement
    'ship supply', 'vessel supply', 'marine supply', 'port supply', 'ship chandler',
    'bunker', 'fuel', 'lubricant', 'provisions', 'fresh water', 'technical supply',
    
    # Procurement processes
    'requisition', 'purchase requisition', 'approval', 'authorization', 'budget approval',
    'vendor selection', 'supplier evaluation', 'price comparison', 'negotiation',
    'contract', 'framework agreement', 'blanket order', 'spot purchase',
    
    # Supply chain
    'delivery', 'shipment', 'logistics', 'freight', 'customs', 'port agent',
    'local agent', 'emergency supply', 'urgent supply', 'stock replenishment',
    
    # Vendor management
    'vendor management', 'supplier management', 'vendor assessment', 'supplier audit',
    'vendor performance', 'supplier rating', 'approved vendor list', 'blacklist',
    
    # Integration platforms
    'shipserv', 'marine marketplace', 'e-procurement', 'digital procurement',
    'procurement portal', 'supplier portal', 'catalog', 'price list',
    
    # Financial terms
    'invoice', 'payment', 'accounts payable', 'cost control', 'budget management',
    'cost analysis', 'spend analysis', 'savings', 'cost reduction'
]

CUSTOM_DEVELOPMENT_KEYWORDS = [
    # Primary terms
    'custom', 'development', 'software', 'application', 'web app', 'webapp',
    'bespoke', 'tailored', 'build', 'create', 'develop', 'programming',
    
    # Development types
    'custom software', 'enterprise software', 'business application', 'web application',
    'desktop application', 'cloud application', 'saas', 'software as a service',
    'enterprise solution', 'business solution', 'digital solution',
    
    # Technologies
    'react', 'angular', 'vue', 'node.js', 'python', 'java', 'dot net', '.net',
    'javascript', 'typescript', 'php', 'ruby', 'c#', 'mysql', 'postgresql',
    'mongodb', 'oracle', 'sql server', 'database', 'api', 'rest api', 'graphql',
    
    # Project types
    'legacy modernization', 'system upgrade', 'digital transformation',
    'business automation', 'workflow automation', 'process automation',
    'enterprise integration', 'system integration', 'platform development',
    
    # Industries
    'maritime software', 'shipping software', 'fleet management software',
    'healthcare software', 'financial software', 'manufacturing software',
    'logistics software', 'supply chain software', 'erp', 'crm', 'hrms'
]

MOBILE_KEYWORDS = [
    # Primary terms
    'mobile', 'app', 'mobile app', 'ios', 'android', 'smartphone', 'tablet',
    'pwa', 'progressive web app', 'react native', 'flutter', 'mobile development',
    
    # Mobile platforms
    'iphone', 'ipad', 'apple', 'google play', 'app store', 'play store',
    'mobile application', 'native app', 'hybrid app', 'cross platform',
    
    # Mobile features
    'offline app', 'push notification', 'gps', 'location', 'camera', 'scanner',
    'qr code', 'barcode', 'biometric', 'fingerprint', 'face id', 'touch id',
    'mobile payments', 'in app purchase', 'mobile commerce', 'm-commerce',
    
    # Business mobile apps
    'field service app', 'sales app', 'crm app', 'inventory app', 'tracking app',
    'delivery app', 'logistics app', 'maintenance app', 'inspection app',
    'workforce app', 'employee app', 'customer app', 'mobile portal',
    
    # Mobile technologies
    'swift', 'kotlin', 'xamarin', 'cordova', 'phonegap', 'ionic', 'unity'
]

AI_ML_KEYWORDS = [
    # Primary terms
    'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
    'neural', 'neural network', 'nlp', 'natural language processing',
    'computer vision', 'automation', 'intelligent automation',
    
    # AI applications
    'chatbot', 'virtual assistant', 'conversational ai', 'voice assistant',
    'recommendation engine', 'recommendation system', 'predictive analytics',
    'fraud detection', 'anomaly detection', 'sentiment analysis', 'text analysis',
    
    # ML techniques
    'supervised learning', 'unsupervised learning', 'reinforcement learning',
    'classification', 'regression', 'clustering', 'decision tree', 'random forest',
    'support vector machine', 'svm', 'neural networks', 'cnn', 'rnn', 'lstm',
    
    # AI technologies
    'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'opencv', 'spacy', 'nltk',
    'hugging face', 'openai', 'gpt', 'bert', 'transformer', 'generative ai',
    
    # Business AI
    'business intelligence', 'predictive maintenance', 'demand forecasting',
    'price optimization', 'customer segmentation', 'lead scoring', 'churn prediction',
    'quality control', 'defect detection', 'process optimization', 'smart automation',
    
    # Industry AI
    'ai for maritime', 'ai for shipping', 'ai for logistics', 'ai for healthcare',
    'ai for finance', 'ai for manufacturing', 'ai for retail', 'fintech ai'
]

DATA_SERVICES_KEYWORDS = [
    # Primary terms
    'data', 'database', 'migration', 'analytics', 'reporting', 'etl', 'elt',
    'warehouse', 'data warehouse', 'data lake', 'bi', 'business intelligence',
    
    # Data operations
    'data migration', 'database migration', 'data transfer', 'data conversion',
    'data transformation', 'data integration', 'data synchronization',
    'data backup', 'data recovery', 'disaster recovery', 'data archiving',
    
    # Analytics & BI
    'dashboard', 'report', 'kpi', 'metrics', 'data visualization', 'charts',
    'graphs', 'tableau', 'power bi', 'qlik', 'looker', 'excel', 'pivot table',
    'data analysis', 'statistical analysis', 'trend analysis', 'forecasting',
    
    # Database technologies
    'sql', 'nosql', 'mysql', 'postgresql', 'oracle', 'sql server', 'mongodb',
    'cassandra', 'redis', 'elasticsearch', 'hadoop', 'spark', 'kafka',
    
    # Cloud data
    'aws', 'azure', 'google cloud', 'cloud migration', 'cloud database',
    's3', 'redshift', 'bigquery', 'azure sql', 'cosmos db', 'dynamodb',
    
    # Data governance
    'data quality', 'data cleansing', 'data validation', 'master data',
    'data governance', 'data lineage', 'metadata', 'data catalog',
    'gdpr', 'data privacy', 'data security', 'compliance'
]

INTEGRATION_KEYWORDS = [
    # Primary terms
    'integration', 'api', 'connect', 'sync', 'synchronization', 'system integration',
    'erp', 'crm', 'middleware', 'interface', 'connector', 'bridge',
    
    # Integration types
    'system integration', 'application integration', 'data integration',
    'enterprise integration', 'cloud integration', 'hybrid integration',
    'real time integration', 'batch integration', 'event driven integration',
    
    # Integration technologies
    'rest', 'soap', 'graphql', 'webhook', 'api gateway', 'message queue',
    'kafka', 'rabbitmq', 'azure service bus', 'aws sqs', 'mule', 'tibco',
    'logic apps', 'azure logic apps', 'aws step functions', 'zapier',
    
    # Business systems
    'erp integration', 'crm integration', 'sap', 'salesforce', 'dynamics',
    'oracle', 'netsuite', 'quickbooks', 'sage', 'workday', 'successfactors',
    'sharepoint', 'office 365', 'google workspace', 'slack integration',
    
    # E-commerce integration
    'shopify', 'magento', 'woocommerce', 'amazon', 'ebay', 'payment gateway',
    'stripe', 'paypal', 'square', 'shipping integration', 'fedex', 'ups', 'dhl',
    
    # Data sync
    'two way sync', 'one way sync', 'real time sync', 'batch sync',
    'data synchronization', 'master data sync', 'customer sync', 'product sync'
]

CHATBOT_KEYWORDS = [
    # Primary terms
    'chatbot', 'chat bot', 'virtual assistant', 'customer service', 'conversational ai',
    'support bot', 'chat', 'assistant', 'ai assistant', 'digital assistant',
    
    # Customer service terms
    'customer support', 'help desk', 'support ticket', 'live chat', 'customer care',
    'customer experience', 'cx', 'customer engagement', 'self service', 'faq bot',
    
    # Communication channels
    'website chat', 'web chat', 'whatsapp bot', 'facebook messenger', 'telegram bot',
    'slack bot', 'discord bot', 'sms bot', 'voice bot', 'phone bot', 'ivr',
    
    # Chatbot features
    'natural language', 'nlp', 'intent recognition', 'entity extraction',
    'conversation flow', 'dialogue management', 'context awareness', 'memory',
    'multilingual', 'sentiment analysis', 'escalation', 'handoff', 'live agent',
    
    # Business applications
    'lead generation', 'lead qualification', 'appointment booking', 'scheduling',
    'order taking', 'product recommendation', 'troubleshooting', 'onboarding',
    'survey bot', 'feedback collection', 'hr bot', 'it support bot',
    
    # Chatbot platforms
    'dialogflow', 'azure bot framework', 'amazon lex', 'rasa', 'botframework',
    'watson assistant', 'chatfuel', 'manychat', 'drift', 'intercom', 'zendesk'
]

# =============================================================================
# COMPREHENSIVE KEYWORD MAPPING
# =============================================================================

COMPREHENSIVE_KEYWORD_MAPPING = {
    'inventory': INVENTORY_KEYWORDS,
    'payroll': PAYROLL_KEYWORDS,
    'crewing': CREWING_KEYWORDS,
    'tms': TMS_KEYWORDS,
    'procurement': PROCUREMENT_KEYWORDS,
    'custom_development': CUSTOM_DEVELOPMENT_KEYWORDS,
    'mobile': MOBILE_KEYWORDS,
    'ai_ml': AI_ML_KEYWORDS,
    'data_services': DATA_SERVICES_KEYWORDS,
    'integration': INTEGRATION_KEYWORDS,
    'chatbot': CHATBOT_KEYWORDS
}

# =============================================================================
# ENHANCED KEYWORD MATCHING FUNCTION
# =============================================================================

def get_best_match_category(query):
    """
    Enhanced keyword matching that finds the best category match for a query
    Returns tuple: (category, confidence_score, matched_keywords)
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    matches = {}
    
    for category, keywords in COMPREHENSIVE_KEYWORD_MAPPING.items():
        matched_keywords = []
        score = 0
        
        for keyword in keywords:
            if keyword in query_lower:
                matched_keywords.append(keyword)
                # Give higher score for exact phrase matches
                if ' ' in keyword:
                    score += 3  # Multi-word phrases get higher weight
                else:
                    score += 1  # Single words get base score
        
        # Additional scoring for word matches
        keyword_words = set()
        for keyword in keywords:
            keyword_words.update(keyword.split())
        
        common_words = query_words.intersection(keyword_words)
        score += len(common_words) * 0.5  # Partial score for individual word matches
        
        if score > 0:
            matches[category] = {
                'score': score,
                'matched_keywords': matched_keywords,
                'confidence': min(score / 10, 1.0)  # Normalize to 0-1
            }
    
    if not matches:
        return None, 0, []
    
    # Get the best match
    best_category = max(matches.keys(), key=lambda k: matches[k]['score'])
    best_match = matches[best_category]
    
    return best_category, best_match['confidence'], best_match['matched_keywords']

# =============================================================================
# ENHANCED PRODUCT AND SERVICE RESPONSE FUNCTIONS
# =============================================================================

def get_product_response_enhanced(query):
    """Enhanced product response using comprehensive keyword matching"""
    
    # Get the best matching category
    category, confidence, matched_keywords = get_best_match_category(query)
    
    # If we have a good match (confidence > 0.3) and it's a product category
    if confidence > 0.3 and category in ['inventory', 'payroll', 'crewing', 'tms', 'procurement']:
        
        if category == 'inventory':
            return f"""**AniSol Inventory Control** - Fleet-Wide Inventory Management System

AniSol Inventory Control provides comprehensive fleet-wide inventory operations across vessels and shore facilities with real-time tracking and automated management capabilities.

**Two Primary Inventory Categories:**
• **Spares Inventory** - Directly linked to machinery maintenance and repair operations
• **Consumable Stores** - Food, safety equipment, stationery, chemicals, and operational supplies

**Core Management Features:**
• Master Store List Management with centralized control and consistency
• Real-time ROB (Remaining Onboard) tracking with location-based adjustments
• Automated store receipts processing for office-supplied items with manual cash/local procurement support
• Consumption logging with permission-based controls and approval workflows
• Color-coded stock level alerts and management dashboards for immediate visibility
• Component mapping system linking spare parts to specific machinery and systems

**Advanced Capabilities:**
• Transaction history and comprehensive audit logging with export functionality
• Fleet-wide visibility enabling identification of slow/fast-moving inventory items
• Automated shortage identification and requisition processing
• Integration with AniSol TMS for maintenance-driven automatic consumption updates
• Seamless connection with AniSol Procurement for stock shortage management

**Technical Integration:**
• ERP/Accounts synchronization for real-time inventory valuation and asset movement tracking
• Ship and cloud deployment options with offline operation capability and automatic synchronization
• Ultra-low bandwidth optimization for satellite communication environments

**Operational Benefits:**
• Reduced stockouts through predictive inventory management
• Lower inventory carrying costs with optimized stock levels
• Complete audit compliance with regulatory requirements
• Streamlined procurement processes with automated requisition generation

For detailed implementation planning and system configuration, contact info@aniketsolutions.com"""

        elif category == 'payroll':
            return f"""**AniSol Payroll & Master Cash System** - Comprehensive Crew Financial Management

AniSol Payroll & Master Cash System handles complete crew financial management with maritime-specific workflows, multi-currency support, and comprehensive compliance requirements.

**Comprehensive Payroll Management:**
• Automated wage calculations including overtime, bonuses, allowances, and contract-based automation
• Integration with crew agreements for seamless payroll processing
• Multi-currency support with real-time exchange rate handling and conversion
• Split-company settlements for complex ownership structures and joint ventures
• Salary advance tracking with configurable approval workflows and repayment schedules

**Advanced Cash Management:**
• Master's cash advance issuance with tracking and reconciliation capabilities
• Digital petty cash voucher system with multi-level approval controls
• Comprehensive spend category tagging for detailed expense analysis and budgeting
• Onboard cash expenditure monitoring with real-time balance tracking

**Compliance & Audit Features:**
• Formal portage bill generation with complete audit trails and crew sign-off documentation
• Export capabilities for shore payroll systems and accounting integration
• Multi-level approval workflows for enhanced financial controls and authorization
• Complete historical ledger with secure backup archiving and disaster recovery
• Regulatory compliance support for maritime labor standards and flag state requirements

**Integration & Deployment:**
• Seamless integration with accounting systems and ERP platforms
• Cloud-hosted or ship-based deployment options with flexible architecture
• Modular design enabling standalone operation or full integration with other AniSol modules
• Designed specifically for maritime operational requirements and constraints

**Security & Access Control:**
• Role-based access controls with department-level security restrictions
• Encrypted data transmission and storage with secure authentication protocols
• Comprehensive audit logging for all financial transactions and system access

For payroll system configuration and maritime compliance setup, contact info@aniketsolutions.com"""

        elif category == 'crewing':
            return f"""**AniSol Crewing Module** - Complete Crew Lifecycle Management System

AniSol Crewing Module provides comprehensive crew management from recruitment through contract completion, designed specifically for maritime operational requirements and international regulatory compliance.

**Comprehensive Crew Administration:**
• Complete payroll and wages accounting with maritime-specific calculations and allowances
• Multi-currency payment processing with automated exchange rate management
• Salary advance and loan tracking with configurable approval workflows
• Formal portage bill generation and crew sign-off documentation with audit compliance

**Document & Certification Management:**
• Centralized repository for crew documents, certifications, and endorsements
• Automated expiry alerts for certificates with configurable notification timelines
• Flag state, STCW, and MLC compliance tracking with regulatory reporting
• Digital document storage with secure access controls and version management
• Integration with training records and competency assessments

**Advanced Operational Management:**
• Crew scheduling and deployment planning with rotation optimization
• Contract monitoring and automated renewal notifications
• Shore leave tracking with approval workflows and compliance monitoring
• Performance appraisals with structured competency assessments and career development
• Crew availability tracking and resource allocation across fleet operations

**Financial Integration Capabilities:**
• Master's cash and petty cash management with reconciliation
• Provisions and slop chest accounting with inventory integration
• Cost control and budget tracking with departmental allocation
• Seamless integration with accounting systems and financial reporting

**Technical Architecture & Compliance:**
• Cloud-first scalable infrastructure with enterprise-grade security
• Integration with other AniSol modules for unified fleet management
• Secure backup and disaster recovery with geo-redundant storage
• Role-based access controls with audit logging for all crew data access
• GDPR compliance and data protection protocols for international operations

**Reporting & Analytics:**
• Comprehensive reporting suite for operational and regulatory requirements
• Performance analytics and crew utilization optimization
• Cost analysis and budget forecasting capabilities
• Custom report generation with automated distribution

For crew management system implementation and regulatory compliance setup, contact info@aniketsolutions.com"""

        elif category == 'tms':
            return f"""**AniSol TMS (Technical Management System)** - Smart Maintenance & Real Maritime Insight

AniSol TMS provides comprehensive maintenance management designed specifically for maritime operations with real-world vessel requirements, bandwidth constraints, and regulatory compliance needs.

**Advanced Maintenance Operations:**
• **Planned Maintenance Scheduling** - Calendar-based, counter-based, and condition-based scheduling with automated work order generation
• **Unplanned Maintenance Management** - One-click breakdown reporting with rapid response workflows
• **Work Order Lifecycle** - Complete generation, assignment, execution, and completion tracking with resource allocation
• **Maintenance History Analysis** - Trend identification, performance analytics, and predictive maintenance insights

**Comprehensive Inspection & Compliance:**
• **PSC (Port State Control)** inspection tracking with deficiency management and resolution monitoring
• **Class Survey Management** - Automated scheduling, preparation checklists, and completion verification
• **Defect Management** - Identification, categorization, tracking, and resolution with priority-based workflows
• **Certificate Lifecycle Management** - Comprehensive tracking with automated renewal alerts and regulatory compliance

**Intelligent System Integration:**
• **Direct Inventory Integration** - Seamless linking of spare parts to maintenance work orders with automatic consumption tracking
• **Technical Dashboard** - Real-time vessel health monitoring with drill-down analytics and performance assessment
• **Digital Reporting Suite** - Calibration management, decarbonization tracking, bearing measurements, and regulatory reporting
• **Performance Analytics** - Equipment reliability analysis, maintenance cost optimization, and operational efficiency metrics

**Maritime-Optimized Design:**
• **Developed by Seafarers** - Practical ship operations focus with real-world workflow optimization
• **Unified Interface** - Most operations accessible from single screen with intuitive navigation
• **No Dedicated Server** - Any onboard computer capable of hosting with minimal hardware requirements
• **Ultra-Low Bandwidth** - Optimized for satellite communications with intelligent data compression

**Security & Access Management:**
• **Multi-Layer Access Control** - Role-based permissions with department-level security restrictions
• **Complete Audit Trails** - All maintenance activities logged with timestamp and user tracking
• **Offline Operation** - Full functionality without internet connection with automatic synchronization when connected
• **Ship-Shore Integration** - Seamless data exchange with shore-based technical management teams

**Regulatory Compliance:**
• **ISM Code Compliance** - Integrated safety management system support
• **Class Society Requirements** - Automated compliance tracking and reporting
• **Flag State Regulations** - Customizable compliance frameworks for different maritime jurisdictions

For vessel-specific TMS configuration and technical implementation, contact info@aniketsolutions.com"""

        elif category == 'procurement':
            return f"""**AniSol Procurement System** - AI-Powered Maritime Purchasing Platform

AniSol Procurement provides comprehensive AI-powered maritime purchasing capabilities with advanced vendor management, automated workflow processing, and intelligent cost optimization.

**Advanced Requisition Management:**
• **Multiple Requisition Types** - Spares & stores, repair jobs, service orders, adhoc requests, and framework agreements
• **Framework Agreement Support** - Long-term contract management for recurring purchases with automated pricing
• **Inventory Integration** - Direct linking between inventory requirements and procurement requests with automated reordering
• **Automated PO Generation** - Intelligent purchase order creation from RFQ responses with vendor comparison analytics

**Comprehensive Vendor Operations:**
• **Centralized Vendor Database** - Complete vendor master with performance tracking, rating systems, and compliance monitoring
• **Supplier Quote Management** - Multi-format quote import (CSV, Excel, ShipServ integration) with automated comparison
• **Vendor Performance Analytics** - Real-time rating systems, delivery performance tracking, and quality assessments
• **ShipServ Integration** - Catalog synchronization, enhanced sourcing capabilities, and industry-standard procurement workflows

**Intelligent Approval & Control Systems:**
• **Configurable Approval Workflows** - Cost thresholds, vessel-specific rules, user role-based authorization, and project-specific approvals
• **Budget Control Integration** - Budget code linking at requisition level with real-time budget tracking and variance analysis
• **Invoice Matching** - 2-way and 3-way matching capabilities with automated discrepancy identification
• **Complete Audit Logging** - Full traceability from initial requisition through final payment with regulatory compliance

**AI-Powered Analytics & Optimization:**
• **Procurement Decision Support** - AI-driven recommendations for vendor selection and cost optimization
• **Live Performance Dashboards** - Real-time spend analysis, supplier performance monitoring, and procurement KPIs
• **Cost Optimization Algorithms** - Automated identification of cost-saving opportunities and bulk purchasing recommendations
• **Predictive Analytics** - Demand forecasting and procurement planning with seasonal adjustment capabilities

**Technical Features & Integration:**
• **Low-Bandwidth Synchronization** - Optimized for vessel operations with satellite communication constraints
• **IHM Export Support** - Inventory of Hazardous Materials compliance with regulator-ready purchase data
• **System Integration** - Seamless connectivity with inventory management and technical management systems
• **Real-Time Delivery Tracking** - Automated status updates with delivery confirmation and inventory auto-matching

**Maritime-Specific Capabilities:**
• **Port Agent Integration** - Local supplier network management with port-specific procurement workflows
• **Emergency Procurement** - Rapid approval processes for critical operational requirements
• **Multi-Currency Processing** - Global supplier management with automated currency conversion and cost comparison
• **Regulatory Compliance** - Support for maritime procurement regulations and documentation requirements

For procurement system implementation and vendor integration planning, contact info@aniketsolutions.com"""

    # Fallback for products
    return f"""**AniSol Maritime Software Suite** - Integrated Fleet Management Solutions

Our comprehensive maritime software portfolio addresses core operational requirements for modern fleet management with integrated modules and regulatory compliance.

**Available Products:**

**AniSol TMS** - Technical Management System for maintenance scheduling, inspection tracking, and equipment lifecycle management

**AniSol Procurement** - AI-powered purchasing platform with vendor management and cost optimization

**AniSol Inventory Control** - Fleet-wide inventory management with real-time tracking and automated reordering

**AniSol Crewing Module** - Complete crew lifecycle management with compliance tracking and performance analytics

**AniSol Payroll & Master Cash** - Maritime-specific payroll processing with multi-currency support

**Integrated Architecture:**
• Seamless data flow between all modules for unified operations
• Ship and cloud deployment options with offline operational capability
• Ultra-low bandwidth optimization for satellite communication environments
• Comprehensive audit trails and regulatory compliance reporting

For specific product information or implementation requirements, please specify which operational area interests you, or contact info@aniketsolutions.com for detailed consultation."""

def get_service_response_enhanced(query):
    """Enhanced service response using comprehensive keyword matching"""
    
    # Get the best matching category
    category, confidence, matched_keywords = get_best_match_category(query)
    
    # If we have a good match (confidence > 0.3) and it's a service category
    if confidence > 0.3 and category in ['custom_development', 'mobile', 'ai_ml', 'data_services', 'integration', 'chatbot']:
        
        if category == 'chatbot':
            return f"""**AI Chatbot & Virtual Assistant Services** - Intelligent Customer Service Automation

Our AI Chatbot and Virtual Assistant services provide sophisticated customer service automation with natural language processing capabilities, ensuring 24/7 business support with human-like interaction quality.

**Advanced Chatbot Capabilities:**
• **Intelligent Conversation Management** - Context-aware dialogue systems with memory retention and multi-turn conversation handling
• **Multi-Language Support** - Global customer base support with real-time translation and culturally-appropriate responses
• **Smart Customer Routing** - Intelligent escalation to human agents based on conversation complexity and customer sentiment analysis
• **Appointment Scheduling** - Calendar integration with availability checking, booking confirmation, and automated reminder systems
• **Lead Qualification** - Automated information collection, scoring, and CRM integration for sales pipeline management

**Technical Implementation & AI Features:**
• **Natural Language Understanding (NLU)** - Advanced intent recognition, entity extraction, and contextual response generation
• **Machine Learning Integration** - Continuous conversation improvement through user interaction analysis and response optimization
• **Sentiment Analysis** - Real-time emotion detection for customer satisfaction monitoring and appropriate response adjustment
• **Knowledge Base Integration** - Dynamic access to business-specific information, product catalogs, and service documentation
• **Conversation Analytics** - Detailed insights into customer interactions, common inquiries, and performance metrics

**Multi-Channel Deployment Options:**
• **Website Integration** - Embedded chat widgets with customizable design matching brand identity and user experience
• **WhatsApp Business** - Official WhatsApp integration for secure customer communication with rich media support
• **Facebook Messenger** - Social media customer service with automated responses and seamless human handoff
• **SMS & Text Messaging** - Mobile-first customer support with two-way messaging and automated workflows
• **Voice Integration** - Phone-based customer interactions with speech-to-text and text-to-speech capabilities

**Industry-Specific Applications:**
• **Retail & E-commerce** - Product information, order tracking, return processing, size guides, and inventory inquiries
• **Healthcare** - Appointment scheduling, basic medical information, prescription reminders, and patient pre-screening
• **Professional Services** - Service inquiries, quote requests, consultation scheduling, and client onboarding assistance
• **Real Estate** - Property information, viewing appointments, market data, and mortgage calculation assistance
• **Restaurants & Hospitality** - Reservations, menu information, order processing, and special event bookings

**Advanced Features & Customization:**
• **Custom Knowledge Base** - Business-specific information integration with product details, service descriptions, and company policies
• **Workflow Automation** - Complex business process handling including form completion, application processing, and data collection
• **CRM Integration** - Seamless customer data synchronization with existing customer relationship management systems
• **Analytics Dashboard** - Comprehensive conversation insights, performance metrics, and customer satisfaction tracking
• **A/B Testing Capabilities** - Conversation optimization through response testing and performance comparison

**Business Benefits & ROI:**
• **24/7 Availability** - Continuous customer service without staffing costs or time zone limitations
• **Immediate Response Times** - Instant customer support improving satisfaction and reducing abandonment rates
• **Scalable Customer Support** - Handle unlimited simultaneous conversations without proportional staff increases
• **Cost Reduction** - Significant reduction in customer service operational expenses and support ticket volume
• **Data Collection & Insights** - Valuable customer behavior data and frequently asked questions analysis

**Implementation Process:**
• **Requirements Analysis** - Business process evaluation, customer journey mapping, and chatbot scope definition
• **Custom Training** - Domain-specific conversation training with business terminology and industry knowledge
• **Integration Development** - Seamless connectivity with existing business systems, databases, and communication platforms
• **Testing & Optimization** - Comprehensive conversation testing, accuracy validation, and performance optimization
• **Deployment & Monitoring** - Production deployment with ongoing performance monitoring and continuous improvement

For chatbot implementation planning and customization consultation, contact info@aniketsolutions.com"""

        elif category == 'custom_development':
            return f"""**Custom Application Development** - Tailored Software Solutions for Business Excellence

Our Custom Application Development services address specific business requirements through comprehensive software solutions designed for operational efficiency, scalability, and long-term business value.

**Development Capabilities & Technologies:**
• **Enterprise Web Applications** - Modern, responsive applications using cutting-edge frameworks (React, Angular, Vue.js) with progressive web app capabilities
• **Backend Architecture** - Robust server-side systems with Node.js, Python (Django/Flask), Java (Spring), .NET Core architectures
• **Database Solutions** - PostgreSQL, MySQL, MongoDB implementations with optimization, clustering, and backup strategies
• **API Development** - RESTful APIs, GraphQL endpoints, and microservices architecture with scalable cloud deployment
• **Legacy Modernization** - Systematic upgrade of outdated systems while preserving critical functionality and data integrity

**Industry-Specific Applications:**
• **Manufacturing** - Production management systems, quality control platforms, supply chain optimization, and IoT integration
• **Healthcare** - Patient management systems, electronic health records, compliance tracking platforms, and telemedicine solutions
• **Finance** - Risk assessment systems, automated reporting platforms, regulatory compliance tools, and fraud detection systems
• **Logistics** - Supply chain optimization, inventory management, route planning, and real-time tracking systems
• **Maritime** - Vessel operations management, crew scheduling, maintenance tracking, and regulatory compliance systems

**Comprehensive Development Process:**
• **Discovery & Analysis** - Requirements gathering, stakeholder interviews, technical feasibility assessment, and project scope definition
• **Architecture Design** - System architecture planning, technology stack selection, scalability considerations, and security framework design
• **Agile Development** - Iterative development methodology with regular stakeholder feedback, sprint planning, and continuous integration
• **Quality Assurance** - Comprehensive testing including unit testing, integration testing, security validation, and performance optimization
• **Deployment & Support** - Production deployment planning, monitoring setup, ongoing maintenance, and technical support services

**Technical Standards & Best Practices:**
• **Modern Development Practices** - Code quality standards, version control, automated testing, and continuous deployment pipelines
• **Security Implementation** - Industry best practices including data encryption, secure authentication, authorization protocols, and vulnerability assessments
• **Cloud Deployment** - AWS, Azure, Google Cloud deployment options with auto-scaling, load balancing, and disaster recovery
• **Mobile Responsiveness** - Cross-platform accessibility with responsive design principles and mobile-first development approach

**Ongoing Support & Maintenance:**
• **Technical Support** - Dedicated support team with SLA-based response times and issue resolution
• **System Monitoring** - 24/7 monitoring with automated alerts, performance tracking, and proactive maintenance
• **Feature Enhancement** - Continuous improvement based on user feedback and business requirements evolution
• **Training & Documentation** - Comprehensive user training, technical documentation, and knowledge transfer

For detailed project assessment and technical consultation, contact info@aniketsolutions.com"""

        # Add other service responses here (mobile, ai_ml, data_services, integration)
        # [Previous implementations remain the same]

    # Fallback for services
    return f"""**Aniket Solutions Technology Services** - Comprehensive Business Technology Solutions

Our Technology Services portfolio addresses diverse business modernization requirements through specialized expertise, proven methodologies, and cutting-edge technology implementation.

**Available Services:**

**Custom Application Development** - Enterprise software solutions, legacy modernization, and bespoke application development

**Mobile Solutions** - Native iOS/Android applications, cross-platform development, and progressive web apps

**AI & Machine Learning** - Intelligent automation, predictive analytics, natural language processing, and computer vision

**Data Services** - Database migration, data warehousing, business intelligence, and analytics platform development

**System Integration** - API development, enterprise application connectivity, and hybrid cloud-premise architectures

**AI Chatbots & Virtual Assistants** - Conversational AI, customer service automation, and multi-channel deployment

**Implementation Approach:**
• Requirements analysis and technical architecture design
• Agile development methodology with iterative stakeholder feedback
• Quality assurance with security and performance validation
• Deployment planning with comprehensive technical support

**Industry Expertise:** Maritime operations, manufacturing automation, healthcare compliance, financial services, retail technology

For specific service consultation or implementation requirements, please specify which technology challenge you'd like to address, or contact info@aniketsolutions.com for detailed discussion."""

# Enhanced smart response function that uses the comprehensive keyword matching
def generate_smart_response_enhanced(user_message):
    """Enhanced smart response using comprehensive keyword matching"""
    try:
        # Track interaction for keep-alive system
        if "interaction_count" in st.session_state:
            st.session_state.interaction_count += 1
            st.session_state.last_activity = datetime.now()
        
        # First, get the best category match with confidence score
        category, confidence, matched_keywords = get_best_match_category(user_message)
        
        # IMPROVED LOGIC: Always respond based on what the user is asking about, 
        # regardless of their initial selection (products vs services)
        if confidence > 0.3:  # Lowered threshold for better responsiveness
            # Check if it's a product category - respond with product info
            if category in ['inventory', 'payroll', 'crewing', 'tms', 'procurement']:
                return get_product_response_enhanced(user_message)
            # Check if it's a service category - respond with service info
            elif category in ['custom_development', 'mobile', 'ai_ml', 'data_services', 'integration', 'chatbot']:
                return get_service_response_enhanced(user_message)
        
        # Fallback to AI if no strong keyword match and AI is available
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
- Always respond based on what the user is asking about, regardless of any previous category selection
- If they ask about products (inventory, payroll, crewing, TMS, procurement), provide detailed product information
- If they ask about services (development, mobile, AI, data, integration, chatbot), provide detailed service information
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
                max_tokens=600,  # Increased for more detailed responses
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Validate response quality
            prohibited_phrases = [
                "that's a great question", "i'd be happy to", "absolutely", "perfect choice",
                "excellent question", "wonderful", "fantastic", "amazing", "excited to help"
            ]
            
            ai_lower = ai_response.lower()
            if not any(phrase in ai_lower for phrase in prohibited_phrases):
                return ai_response
        
        # Final fallback
        return "For specific information about our maritime products or technology services, please provide more details about your requirements, or contact our specialists at info@aniketsolutions.com for detailed consultation."
        
    except Exception as e:
        return "For detailed information about our maritime products and technology services, contact our specialists at info@aniketsolutions.com"

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
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
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

# =============================================================================
# ACTIVATE KEEP-ALIVE SYSTEMS
# =============================================================================

# Run all keep-alive systems
keep_alive_system()
add_javascript_keepalive()
add_auto_refresh()
add_service_worker()

# Custom CSS for better styling and hide sidebar completely
st.markdown("""
<style>
    /* Hide sidebar completely */
    .css-1d391kg {display: none !important;}
    .css-1rs6os {display: none !important;}
    .css-17eq0hr {display: none !important;}
    section[data-testid="stSidebar"] {display: none !important;}
    
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
    greeting_message = """Hi! I'm Alex from Aniket Solutions. How can I assist you with maritime software or tech services? Please share your corporate email."""
    
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
    
    st.divider()
    
    # Simple status indicator
    st.subheader("🚀 System Status")
    st.success("✅ All systems operational")
    st.caption("Keep-alive system running in background")

# Main chat interface

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

**Technical Architecture:**
• Integrated module communication with seamless data flow
• Ship and cloud deployment options with offline operational capability
• Ultra-low bandwidth optimization for satellite communication environments
• Comprehensive audit trails and regulatory compliance reporting

Which specific operational area requires detailed analysis?"""
            
            add_message_to_chat("assistant", products_overview)
            st.rerun()
    
    with col2:
        if st.button("💻 Technology Services", key="select_services", use_container_width=True):
            add_message_to_chat("user", "I'm interested in your technology services")
            
            # Set category and provide overview
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

**Implementation Approach:**
• Requirements analysis and technical architecture design
• Agile development methodology with iterative stakeholder feedback
• Quality assurance with security and performance validation
• Deployment planning with comprehensive technical support

**Industry Focus:** Maritime operations, manufacturing automation, healthcare compliance, financial services, retail technology.

Which business challenge requires technical consultation?"""
            
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
                placeholder="Ask about our maritime products or technology services...",
                label_visibility="collapsed"
            )
        
        with col2:
            send_button = st.form_submit_button("Send", use_container_width=True)

    # Handle user input with enhanced logic
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
                
                # Generate enhanced smart response
                with st.spinner("Thinking..."):
                    try:
                        ai_response = generate_smart_response_enhanced(user_input)
                        add_message_to_chat("assistant", ai_response)
                        st.rerun()
                        
                    except Exception as e:
                        # Fallback response
                        fallback_response = "For detailed information about our maritime products and technology services, contact our specialists at info@aniketsolutions.com"
                        add_message_to_chat("assistant", fallback_response)
                        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "Powered by Aniket Solutions • Enterprise AI Assistant"
    "</div>",
    unsafe_allow_html=True
)
