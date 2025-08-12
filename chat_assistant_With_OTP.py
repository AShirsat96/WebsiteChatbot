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
# ENHANCED SERVER-SIDE KEEP-ALIVE
# =============================================================================

def add_server_side_keepalive():
    """Add server-side keep-alive that runs every page load"""
    # Auto-increment a counter every time the page loads/refreshes
    if "server_heartbeat_count" not in st.session_state:
        st.session_state.server_heartbeat_count = 0
    
    st.session_state.server_heartbeat_count += 1
    
    # Hidden element that forces server activity
    st.markdown(f"""
    <div style="display: none;" id="heartbeat-{st.session_state.server_heartbeat_count}">
        Server heartbeat: {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)
    
    # Add META refresh as ultimate backup for inactivity detection
    st.markdown("""
    <meta http-equiv="refresh" content="210">
    <script>
    // Override meta refresh if user is active
    let metaRefresh = document.querySelector('meta[http-equiv="refresh"]');
    let userActive = false;
    
    // Track if user has been active in last 3 minutes
    ['click', 'keypress', 'scroll', 'mousemove', 'touchstart', 'input'].forEach(event => {
        document.addEventListener(event, function() {
            userActive = true;
            // Remove meta refresh if user is active
            if (metaRefresh) {
                metaRefresh.remove();
                metaRefresh = null;
            }
        }, { passive: true, once: true });
    });
    
    console.log('Meta refresh backup set for 3.5 minutes');
    </script>
    """, unsafe_allow_html=True)
    
    # Force a tiny server operation every page load
    current_time = datetime.now()
    if "last_server_ping" not in st.session_state:
        st.session_state.last_server_ping = current_time
    
    # Update server ping timestamp
    st.session_state.last_server_ping = current_time

# =============================================================================
# CONVERSATION INACTIVITY AND ENDING LOGIC
# =============================================================================

def check_auto_reset():
    """Check if conversation should auto-reset after ending"""
    if (st.session_state.get("auto_reset_triggered") and 
        st.session_state.get("auto_reset_time")):
        
        current_time = datetime.now()
        time_since_reset_trigger = (current_time - st.session_state.auto_reset_time).total_seconds()
        
        # Auto-reset after 10 seconds of showing the closure message
        if time_since_reset_trigger > 10:
            # Clear ALL session state for complete reset
            keys_to_keep = []  # Don't keep anything - complete fresh start
            
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            # Force immediate rerun to restart chatbot
            st.rerun()
    
    return False

def check_conversation_inactivity():
    """Check for conversation inactivity and handle ending logic"""
    
    # Initialize inactivity tracking
    if "last_user_activity" not in st.session_state:
        st.session_state.last_user_activity = datetime.now()
        st.session_state.conversation_ending_initiated = False
        st.session_state.final_question_asked = False
        st.session_state.waiting_for_final_response = False
        st.session_state.conversation_ended = False
        st.session_state.inactivity_timer_start = None
    
    current_time = datetime.now()
    
    # Check if conversation has already ended
    if st.session_state.conversation_ended:
        return True
    
    # Skip inactivity check if still in initial flow (email validation, OTP, selection)
    if (st.session_state.conversation_flow.get("awaiting_email") or 
        st.session_state.conversation_flow.get("awaiting_otp") or 
        st.session_state.conversation_flow.get("awaiting_selection")):
        return False
    
    # Check if we're in the middle of a business conversation (after initial setup)
    if (st.session_state.conversation_flow.get("otp_verified") and 
        not st.session_state.conversation_flow.get("awaiting_selection")):
        
        # Calculate time since last user activity
        time_since_activity = current_time - st.session_state.last_user_activity
        
        # If 3 minutes of inactivity and no ending sequence started
        if (time_since_activity.total_seconds() > 180 and  # 3 minutes
            not st.session_state.conversation_ending_initiated and
            not st.session_state.final_question_asked):
            
            # Start ending sequence
            st.session_state.conversation_ending_initiated = True
            st.session_state.final_question_asked = True
            st.session_state.waiting_for_final_response = True
            st.session_state.inactivity_timer_start = current_time
            
            # Add final question message
            add_message_to_chat("assistant", 
                "Is there anything else you'd like to know about our maritime products or technology services?")
            
            return False
        
        # If waiting for final response and 3 minutes has passed
        elif (st.session_state.waiting_for_final_response and 
              st.session_state.inactivity_timer_start and
              (current_time - st.session_state.inactivity_timer_start).total_seconds() > 180):  # 3 minutes
            
            # End conversation
            st.session_state.conversation_ended = True
            st.session_state.waiting_for_final_response = False
            
            # Add closing message
            add_message_to_chat("assistant", 
                """Thank you for your interest in Aniket Solutions! 

Due to inactivity, this conversation is now closed. 

For further assistance, please:
• Contact us at info@aniketsolutions.com
• Visit our website: https://www.aniketsolutions.com
• Start a new conversation

We look forward to helping you with your technology needs!""")
            
            # AUTOMATIC RESET: Clear all session state and restart after 10 seconds
            st.session_state.auto_reset_triggered = True
            st.session_state.auto_reset_time = current_time
            
            return True
    
    return False

def update_user_activity():
    """Update the last user activity timestamp"""
    st.session_state.last_user_activity = datetime.now()
    
    # Reset ending sequence if user responds during final question period
    if st.session_state.waiting_for_final_response:
        st.session_state.conversation_ending_initiated = False
        st.session_state.final_question_asked = False
        st.session_state.waiting_for_final_response = False
        st.session_state.inactivity_timer_start = None

def add_inactivity_javascript():
    """Add JavaScript to handle real-time inactivity checking with forced rerun"""
    js_code = """
    <script>
    let inactivityTimer;
    let lastActivityTime = Date.now();
    let inactivityCheckInterval;
    
    function resetInactivityTimer() {
        lastActivityTime = Date.now();
        clearTimeout(inactivityTimer);
        
        console.log('Activity detected - resetting 3-minute timer');
        
        // Set timer for 3 minutes of inactivity
        inactivityTimer = setTimeout(function() {
            console.log('3 minutes of inactivity detected - forcing page refresh to trigger server check');
            // Force a page refresh to trigger server-side inactivity logic
            window.location.reload();
        }, 180000); // 3 minutes
    }
    
    // CRITICAL: Check every 30 seconds if we should trigger inactivity
    inactivityCheckInterval = setInterval(function() {
        const timeSinceActivity = Date.now() - lastActivityTime;
        
        if (timeSinceActivity >= 180000) { // 3 minutes
            console.log('Inactivity check: 3+ minutes detected, forcing refresh');
            clearInterval(inactivityCheckInterval);
            window.location.reload();
        } else {
            const remaining = (180000 - timeSinceActivity) / 1000;
            console.log(`Inactivity check: ${Math.round(remaining)} seconds until timeout`);
        }
    }, 30000); // Check every 30 seconds
    
    // Monitor user interactions
    const events = ['click', 'keypress', 'scroll', 'mousemove', 'touchstart', 'input', 'change'];
    events.forEach(event => {
        document.addEventListener(event, resetInactivityTimer, { passive: true });
    });
    
    // Initial timer setup
    resetInactivityTimer();
    
    // Page visibility change handling
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            console.log('Page became visible - checking inactivity status');
            const timeSinceActivity = Date.now() - lastActivityTime;
            if (timeSinceActivity >= 180000) {
                console.log('Page visible but 3+ minutes inactive - forcing refresh');
                window.location.reload();
            }
        }
    });
    
    // Window focus handling
    window.addEventListener('focus', function() {
        console.log('Window focused - checking inactivity status');
        const timeSinceActivity = Date.now() - lastActivityTime;
        if (timeSinceActivity >= 180000) {
            console.log('Window focused but 3+ minutes inactive - forcing refresh');
            window.location.reload();
        }
    });
    
    console.log('Enhanced inactivity monitoring initialized - will check every 30 seconds');
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)

# =============================================================================
# ADVANCED KEEP-ALIVE SYSTEM TO PREVENT STREAMLIT SLEEPING
# =============================================================================

def keep_alive_system():
    """ENHANCED keep-alive system with more aggressive timing"""
    
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
    
    # MUCH more aggressive auto-refresh - refresh if inactive for 3 minutes instead of 8
    time_since_activity = current_time - st.session_state.last_activity
    uptime = current_time - st.session_state.app_start_time
    
    # Refresh if inactive too long (but not immediately on first load)
    if time_since_activity.total_seconds() > 180 and uptime.total_seconds() > 60:  # 3 minutes instead of 8
        st.session_state.last_activity = current_time
        st.session_state.heartbeat_count += 1
        # Force a rerun to keep the app alive
        st.rerun()

def add_javascript_keepalive():
    """Add comprehensive JavaScript keep-alive system with aggressive timing"""
    js_code = """
    <script>
    // AGGRESSIVE Keep-alive system for Streamlit
    let keepAliveInterval;
    let activityTimeout;
    let heartbeatCount = 0;
    let isPageVisible = true;
    
    function logActivity(action) {
        console.log(`Keep-alive: ${action} at ${new Date().toLocaleTimeString()}`);
    }
    
    function sendHeartbeat() {
        // Multiple heartbeat methods for redundancy
        Promise.all([
            // Method 1: HEAD request
            fetch(window.location.href, {
                method: 'HEAD',
                cache: 'no-cache',
                mode: 'no-cors'
            }).catch(() => {}),
            
            // Method 2: GET request to favicon (lighter)
            fetch('/favicon.ico', {
                method: 'GET',
                cache: 'no-cache',
                mode: 'no-cors'
            }).catch(() => {}),
            
            // Method 3: Streamlit-specific ping
            fetch('/_stcore/health', {
                method: 'GET',
                cache: 'no-cache'
            }).catch(() => {})
        ]).then(() => {
            heartbeatCount++;
            logActivity(`Multi-heartbeat #${heartbeatCount} sent successfully`);
        }).catch(err => {
            console.warn('All heartbeat methods failed:', err);
            // Force reload if heartbeats consistently fail
            if (heartbeatCount % 10 === 0) {
                window.location.reload();
            }
        });
    }
    
    function resetActivity() {
        clearTimeout(activityTimeout);
        logActivity('User activity detected - resetting timers');
        
        // Much more aggressive timing - send heartbeat after 2 minutes of inactivity
        activityTimeout = setTimeout(function() {
            logActivity('2-minute inactivity timeout - sending emergency heartbeat');
            sendHeartbeat();
        }, 120000); // 2 minutes instead of 7
    }
    
    // Monitor ALL possible user interactions
    const events = [
        'click', 'keypress', 'keydown', 'keyup', 'scroll', 'mousemove', 
        'mousedown', 'mouseup', 'touchstart', 'touchend', 'touchmove',
        'focus', 'blur', 'resize', 'wheel', 'input', 'change'
    ];
    events.forEach(event => {
        document.addEventListener(event, resetActivity, { passive: true });
    });
    
    // Initial setup
    resetActivity();
    
    // MUCH more frequent heartbeat - every 90 seconds instead of 4 minutes
    keepAliveInterval = setInterval(function() {
        if (isPageVisible) {
            logActivity('Regular 90-second heartbeat');
            sendHeartbeat();
        }
    }, 90000); // 90 seconds - very aggressive
    
    // Page visibility handling
    document.addEventListener('visibilitychange', function() {
        isPageVisible = !document.hidden;
        if (!document.hidden) {
            logActivity('Page became visible - immediate heartbeat');
            sendHeartbeat();
            resetActivity();
        } else {
            logActivity('Page hidden - maintaining background heartbeat');
        }
    });
    
    // Window focus/blur handling
    window.addEventListener('focus', function() {
        logActivity('Window focused - immediate heartbeat');
        sendHeartbeat();
        resetActivity();
    });
    
    window.addEventListener('blur', function() {
        logActivity('Window blurred - will continue background heartbeat');
    });
    
    // Prevent page unload during active sessions
    window.addEventListener('beforeunload', function(e) {
        logActivity('Page attempting to unload');
        // Don't prevent unload, just log it
    });
    
    // Emergency heartbeat for mobile browsers
    setInterval(function() {
        if (document.hidden) {
            logActivity('Background emergency heartbeat for mobile');
            sendHeartbeat();
        }
    }, 60000); // Every minute when page is hidden
    
    logActivity('AGGRESSIVE keep-alive system initialized with 90-second intervals');
    sendHeartbeat(); // Immediate initial heartbeat
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)

def add_auto_refresh():
    """Add emergency auto-refresh with inactivity-specific timing"""
    refresh_code = """
    <script>
    // EMERGENCY auto-refresh after 3.5 minutes to catch missed inactivity
    setTimeout(function(){
        console.log('EMERGENCY: 3.5-minute safety refresh for inactivity detection');
        window.location.reload(1);
    }, 210000); // 3.5 minutes - just after the 3-minute inactivity threshold
    
    // Additional safety net - ping every 30 seconds when page is active
    setInterval(function() {
        if (!document.hidden) {
            // Create a tiny image request to generate server activity
            var img = new Image();
            img.src = '/favicon.ico?' + Date.now();
            console.log('30-second safety ping sent');
        }
    }, 30000); // Every 30 seconds
    
    // Force check inactivity on any Streamlit rerun
    window.addEventListener('streamlit:rerun', function() {
        console.log('Streamlit rerun detected - this should trigger inactivity check');
    });
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

# Alternative avatar options
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
    'inventory', 'stock', 'spare', 'spares', 'consumable', 'consumables', 'stores', 'rob',
    'parts', 'supplies', 'materials', 'warehouse', 'storage', 'stockroom',
    'ship stores', 'vessel inventory', 'marine supplies', 'deck stores', 'engine room stores',
    'provision stores', 'slop chest', 'bond stores', 'ship chandler', 'chandlery',
    'reorder', 'requisition', 'shortage', 'stock level', 'stock control', 'asset tracking',
    'store keeping', 'storekeeping', 'procurement requisition', 'stock management',
    'remaining onboard', 'onboard inventory', 'ship inventory', 'fleet inventory',
    'component mapping', 'spare parts management', 'consumable tracking', 'stock alerts',
    'inventory optimization', 'stock rotation', 'expiry tracking', 'shelf life',
    'inventory audit', 'stock count', 'cycle counting', 'stock reconciliation'
]

PAYROLL_KEYWORDS = [
    'payroll', 'wages', 'salary', 'cash', 'crew payment', 'master cash', 'pay', 
    'compensation', 'finance', 'money', 'advance', 'payment',
    'crew wages', 'seafarer pay', 'maritime payroll', 'ship payroll', 'vessel payroll',
    'portage bill', 'crew account', 'seaman wages', 'mariner pay', 'sailor wages',
    'crew compensation', 'maritime salary', 'ship crew pay',
    'overtime', 'bonus', 'allowance', 'deduction', 'allotment', 'tax', 'contribution',
    'salary advance', 'cash advance', 'loan', 'fine', 'penalty', 'reimbursement',
    'petty cash', 'cash management', 'crew cash', 'onboard cash',
    'multi currency', 'exchange rate', 'currency conversion', 'foreign exchange',
    'bank transfer', 'wire transfer', 'remittance', 'crew banking',
    'mla compliance', 'flag state requirements', 'crew contract', 'employment agreement'
]

CREWING_KEYWORDS = [
    'crew', 'crewing', 'staff', 'personnel', 'maritime crew', 'seafarer', 'seafarers',
    'manning', 'human resources', 'hr', 'employee', 'employees', 'crew management',
    'captain', 'master', 'chief officer', 'engineer', 'bosun', 'seaman', 'able seaman',
    'ordinary seaman', 'deck crew', 'engine crew', 'galley crew', 'steward', 'cook',
    'chief engineer', 'second engineer', 'third engineer', 'oiler', 'wiper', 'fitter',
    'crew scheduling', 'crew rotation', 'crew deployment', 'crew planning', 'shift management',
    'watch keeping', 'duty roster', 'crew roster', 'manning schedule', 'crew assignment',
    'embarkation', 'disembarkation', 'sign on', 'sign off', 'crew change',
    'crew documents', 'certificates', 'endorsements', 'stcw', 'mlc', 'flag state',
    'medical certificate', 'passport', 'visa', 'seamans book', 'discharge book',
    'coc', 'certificate of competency', 'endorsement', 'training records',
    'crew appraisal', 'performance review', 'competency assessment', 'training',
    'crew evaluation', 'performance management', 'skill assessment', 'crew development',
    'crew performance', 'crew rating', 'crew feedback'
]

TMS_KEYWORDS = [
    'tms', 'maintenance', 'technical', 'planned maintenance', 'pms', 'repair', 'repairs',
    'equipment', 'machinery', 'technical management', 'maintenance management',
    'preventive maintenance', 'corrective maintenance', 'predictive maintenance',
    'condition based maintenance', 'routine maintenance', 'scheduled maintenance',
    'unplanned maintenance', 'emergency repair', 'breakdown', 'overhaul',
    'engine', 'main engine', 'auxiliary engine', 'generator', 'pump', 'compressor',
    'boiler', 'heat exchanger', 'separator', 'purifier', 'winch', 'crane', 'hatch cover',
    'steering gear', 'propeller', 'shaft', 'bearing', 'valve', 'pipe', 'tank',
    'inspection', 'survey', 'class survey', 'intermediate survey',
    'annual survey', 'special survey', 'psc', 'port state control', 'flag state inspection',
    'vetting inspection', 'internal audit', 'safety inspection',
    'certificate', 'class certificate', 'safety certificate', 'statutory certificate',
    'renewal', 'extension', 'endorsement', 'survey due', 'certificate expiry',
    'work order', 'job card', 'maintenance report', 'defect', 'non conformity',
    'finding', 'observation', 'maintenance log', 'engine log', 'technical log',
    'condition monitoring', 'vibration monitoring', 'oil analysis', 'performance monitoring',
    'alarm system', 'automation', 'control system', 'instrumentation'
]

PROCUREMENT_KEYWORDS = [
    'procurement', 'purchasing', 'supplier', 'vendor', 'po', 'purchase order',
    'buying', 'sourcing', 'rfq', 'request for quotation', 'quotation', 'quote',
    'ship supply', 'vessel supply', 'marine supply', 'port supply', 'ship chandler',
    'bunker', 'fuel', 'lubricant', 'provisions', 'fresh water', 'technical supply',
    'requisition', 'purchase requisition', 'approval', 'authorization', 'budget approval',
    'vendor selection', 'supplier evaluation', 'price comparison', 'negotiation',
    'contract', 'framework agreement', 'blanket order', 'spot purchase',
    'delivery', 'shipment', 'logistics', 'freight', 'customs', 'port agent',
    'local agent', 'emergency supply', 'urgent supply', 'stock replenishment',
    'vendor management', 'supplier management', 'vendor assessment', 'supplier audit',
    'vendor performance', 'supplier rating', 'approved vendor list', 'blacklist',
    'shipserv', 'marine marketplace', 'e-procurement', 'digital procurement',
    'procurement portal', 'supplier portal', 'catalog', 'price list',
    'invoice', 'payment', 'accounts payable', 'cost control', 'budget management',
    'cost analysis', 'spend analysis', 'savings', 'cost reduction'
]

CUSTOM_DEVELOPMENT_KEYWORDS = [
    'custom', 'development', 'software', 'application', 'web app', 'webapp',
    'bespoke', 'tailored', 'build', 'create', 'develop', 'programming',
    'custom software', 'enterprise software', 'business application', 'web application',
    'desktop application', 'cloud application', 'saas', 'software as a service',
    'enterprise solution', 'business solution', 'digital solution',
    'react', 'angular', 'vue', 'node.js', 'python', 'java', 'dot net', '.net',
    'javascript', 'typescript', 'php', 'ruby', 'c#', 'mysql', 'postgresql',
    'mongodb', 'oracle', 'sql server', 'database', 'api', 'rest api', 'graphql',
    'legacy modernization', 'system upgrade', 'digital transformation',
    'business automation', 'workflow automation', 'process automation',
    'enterprise integration', 'system integration', 'platform development',
    'maritime software', 'shipping software', 'fleet management software',
    'healthcare software', 'financial software', 'manufacturing software',
    'logistics software', 'supply chain software', 'erp', 'crm', 'hrms'
]

MOBILE_KEYWORDS = [
    'mobile', 'app', 'mobile app', 'ios', 'android', 'smartphone', 'tablet',
    'pwa', 'progressive web app', 'react native', 'flutter', 'mobile development',
    'iphone', 'ipad', 'apple', 'google play', 'app store', 'play store',
    'mobile application', 'native app', 'hybrid app', 'cross platform',
    'offline app', 'push notification', 'gps', 'location', 'camera', 'scanner',
    'qr code', 'barcode', 'biometric', 'fingerprint', 'face id', 'touch id',
    'mobile payments', 'in app purchase', 'mobile commerce', 'm-commerce',
    'field service app', 'sales app', 'crm app', 'inventory app', 'tracking app',
    'delivery app', 'logistics app', 'maintenance app', 'inspection app',
    'workforce app', 'employee app', 'customer app', 'mobile portal',
    'swift', 'kotlin', 'xamarin', 'cordova', 'phonegap', 'ionic', 'unity'
]

AI_ML_KEYWORDS = [
    'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
    'neural', 'neural network', 'nlp', 'natural language processing',
    'computer vision', 'automation', 'intelligent automation',
    'chatbot', 'virtual assistant', 'conversational ai', 'voice assistant',
    'recommendation engine', 'recommendation system', 'predictive analytics',
    'fraud detection', 'anomaly detection', 'sentiment analysis', 'text analysis',
    'supervised learning', 'unsupervised learning', 'reinforcement learning',
    'classification', 'regression', 'clustering', 'decision tree', 'random forest',
    'support vector machine', 'svm', 'neural networks', 'cnn', 'rnn', 'lstm',
    'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'opencv', 'spacy', 'nltk',
    'hugging face', 'openai', 'gpt', 'bert', 'transformer', 'generative ai',
    'business intelligence', 'predictive maintenance', 'demand forecasting',
    'price optimization', 'customer segmentation', 'lead scoring', 'churn prediction',
    'quality control', 'defect detection', 'process optimization', 'smart automation',
    'ai for maritime', 'ai for shipping', 'ai for logistics', 'ai for healthcare',
    'ai for finance', 'ai for manufacturing', 'ai for retail', 'fintech ai'
]

DATA_SERVICES_KEYWORDS = [
    'data', 'database', 'migration', 'analytics', 'reporting', 'etl', 'elt',
    'warehouse', 'data warehouse', 'data lake', 'bi', 'business intelligence',
    'data migration', 'database migration', 'data transfer', 'data conversion',
    'data transformation', 'data integration', 'data synchronization',
    'data backup', 'data recovery', 'disaster recovery', 'data archiving',
    'dashboard', 'report', 'kpi', 'metrics', 'data visualization', 'charts',
    'graphs', 'tableau', 'power bi', 'qlik', 'looker', 'excel', 'pivot table',
    'data analysis', 'statistical analysis', 'trend analysis', 'forecasting',
    'sql', 'nosql', 'mysql', 'postgresql', 'oracle', 'sql server', 'mongodb',
    'cassandra', 'redis', 'elasticsearch', 'hadoop', 'spark', 'kafka',
    'aws', 'azure', 'google cloud', 'cloud migration', 'cloud database',
    's3', 'redshift', 'bigquery', 'azure sql', 'cosmos db', 'dynamodb',
    'data quality', 'data cleansing', 'data validation', 'master data',
    'data governance', 'data lineage', 'metadata', 'data catalog',
    'gdpr', 'data privacy', 'data security', 'compliance'
]

INTEGRATION_KEYWORDS = [
    'integration', 'api', 'connect', 'sync', 'synchronization', 'system integration',
    'erp', 'crm', 'middleware', 'interface', 'connector', 'bridge',
    'system integration', 'application integration', 'data integration',
    'enterprise integration', 'cloud integration', 'hybrid integration',
    'real time integration', 'batch integration', 'event driven integration',
    'rest', 'soap', 'graphql', 'webhook', 'api gateway', 'message queue',
    'kafka', 'rabbitmq', 'azure service bus', 'aws sqs', 'mule', 'tibco',
    'logic apps', 'azure logic apps', 'aws step functions', 'zapier',
    'erp integration', 'crm integration', 'sap', 'salesforce', 'dynamics',
    'oracle', 'netsuite', 'quickbooks', 'sage', 'workday', 'successfactors',
    'sharepoint', 'office 365', 'google workspace', 'slack integration',
    'shopify', 'magento', 'woocommerce', 'amazon', 'ebay', 'payment gateway',
    'stripe', 'paypal', 'square', 'shipping integration', 'fedex', 'ups', 'dhl',
    'two way sync', 'one way sync', 'real time sync', 'batch sync',
    'data synchronization', 'master data sync', 'customer sync', 'product sync'
]

CHATBOT_KEYWORDS = [
    'chatbot', 'chat bot', 'virtual assistant', 'customer service', 'conversational ai',
    'support bot', 'chat', 'assistant', 'ai assistant', 'digital assistant',
    'customer support', 'help desk', 'support ticket', 'live chat', 'customer care',
    'customer experience', 'cx', 'customer engagement', 'self service', 'faq bot',
    'website chat', 'web chat', 'whatsapp bot', 'facebook messenger', 'telegram bot',
    'slack bot', 'discord bot', 'sms bot', 'voice bot', 'phone bot', 'ivr',
    'natural language', 'nlp', 'intent recognition', 'entity extraction',
    'conversation flow', 'dialogue management', 'context awareness', 'memory',
    'multilingual', 'sentiment analysis', 'escalation', 'handoff', 'live agent',
    'lead generation', 'lead qualification', 'appointment booking', 'scheduling',
    'order taking', 'product recommendation', 'troubleshooting', 'onboarding',
    'survey bot', 'feedback collection', 'hr bot', 'it support bot',
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
    """Enhanced keyword matching that finds the best category match for a query"""
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())
    
    matches = {}
    
    for category, keywords in COMPREHENSIVE_KEYWORD_MAPPING.items():
        matched_keywords = []
        score = 0
        
        for keyword in keywords:
            if keyword in query_lower:
                matched_keywords.append(keyword)
                if ' ' in keyword:
                    score += 5
                else:
                    score += 2
        
        keyword_words = set()
        for keyword in keywords:
            keyword_words.update(keyword.split())
        
        common_words = query_words.intersection(keyword_words)
        score += len(common_words) * 0.5
        
        if len(query_words) <= 2:
            primary_keywords = keywords[:10]
            for keyword in primary_keywords:
                if keyword == query_lower:
                    score += 5
                elif keyword in query_lower and len(keyword) > 3:
                    score += 3
        
        if score > 0:
            matches[category] = {
                'score': score,
                'matched_keywords': matched_keywords,
                'confidence': min(score / 8, 1.0)
            }
    
    if not matches:
        return None, 0, []
    
    best_category = max(matches.keys(), key=lambda k: matches[k]['score'])
    best_match = matches[best_category]
    
    return best_category, best_match['confidence'], best_match['matched_keywords']

# =============================================================================
# ENHANCED PRODUCT AND SERVICE RESPONSE FUNCTIONS
# =============================================================================

def get_product_response_enhanced(query):
    """Enhanced product response using comprehensive keyword matching"""
    category, confidence, matched_keywords = get_best_match_category(query)
    
    if confidence > 0.25 and category in ['inventory', 'payroll', 'crewing', 'tms', 'procurement']:
        
        if category == 'inventory':
            return """**AniSol Inventory Control** - Fleet inventory management SOFTWARE for tracking spares and consumables across vessels.

**Key Features:**
• Software for tracking spares & consumables inventory
• Real-time ROB (Remaining Onboard) monitoring system
• Automated reordering and shortage alert software
• Integration with maintenance and procurement systems
• Fleet-wide visibility and audit compliance tools

*We provide inventory management SOFTWARE - not physical supplies or chandlery services.*

Contact info@aniketsolutions.com for software implementation."""

        elif category == 'payroll':
            return """**AniSol Payroll & Master Cash** - Maritime crew financial management SOFTWARE with compliance features.

**Key Features:**
• Automated payroll software with overtime and allowances
• Multi-currency support and exchange rate systems
• Digital master's cash and petty cash management
• Portage bill generation and audit trail software
• Integration with accounting systems

*We provide payroll management SOFTWARE - not financial services or banking.*

Contact info@aniketsolutions.com for software setup consultation."""

        elif category == 'crewing':
            return """**AniSol Crewing Module** - Complete crew lifecycle management SOFTWARE for maritime operations.

**Key Features:**
• Crew scheduling and deployment planning software
• Digital document and certification management
• STCW and MLC compliance tracking systems
• Performance appraisals and training record software
• Payroll and cash management integration

*We provide crew management SOFTWARE - not recruitment or manning services.*

Contact info@aniketsolutions.com for software consultation."""

        elif category == 'tms':
            return """**AniSol TMS** - Technical Management SOFTWARE for maritime maintenance and compliance tracking.

**Key Features:**
• Planned and unplanned maintenance scheduling software
• PSC inspection and class survey tracking systems
• Digital work order management and history
• Certificate lifecycle management software
• Integration with inventory for spare parts tracking

*We provide maintenance management SOFTWARE - not physical repair or drydocking services.*

Contact info@aniketsolutions.com for software implementation."""

        elif category == 'procurement':
            return """**AniSol Procurement** - AI-powered maritime purchasing management SOFTWARE with vendor tracking.

**Key Features:**
• Multi-type requisition management software
• Vendor database and performance tracking systems
• Automated approval workflow software
• ShipServ integration and quote comparison tools
• Budget control and audit logging systems

*We provide procurement management SOFTWARE - not physical supplies or chandlery services.*

Contact info@aniketsolutions.com for software setup."""

    return """**AniSol Maritime Software Suite** - Integrated fleet management solutions:

• **TMS** - Technical maintenance management
• **Procurement** - AI-powered purchasing
• **Inventory** - Fleet-wide stock control
• **Crewing** - Crew lifecycle management
• **Payroll** - Maritime financial management

Contact info@aniketsolutions.com for product consultation."""

def get_service_response_enhanced(query):
    """Enhanced service response using comprehensive keyword matching"""
    category, confidence, matched_keywords = get_best_match_category(query)
    
    if confidence > 0.25 and category in ['custom_development', 'mobile', 'ai_ml', 'data_services', 'integration', 'chatbot']:
        
        if category == 'chatbot':
            return """**AI Chatbot & Virtual Assistant Services** - Intelligent customer service automation with 24/7 support capabilities.

**Key Features:**
• Natural language conversation management
• Multi-channel deployment (website, WhatsApp, SMS)
• Smart escalation to human agents
• CRM integration and analytics
• Custom knowledge base training

Contact info@aniketsolutions.com for chatbot implementation."""

        elif category == 'custom_development':
            return """**Custom Application Development** - Tailored software solutions for specific business requirements.

**Key Features:**
• Enterprise web and desktop applications
• Modern frameworks (React, Angular, Node.js)
• Database design and API development
• Legacy system modernization
• Cloud deployment and scaling

Contact info@aniketsolutions.com for development consultation."""

        elif category == 'mobile':
            return """**Mobile Application Development** - Native and cross-platform mobile solutions.

**Key Features:**
• iOS and Android native development
• Cross-platform solutions (React Native, Flutter)
• Offline capabilities and data sync
• Enterprise integration and security
• App store deployment support

Contact info@aniketsolutions.com for mobile development."""

        elif category == 'ai_ml':
            return """**AI & Machine Learning Services** - Intelligent automation and predictive analytics solutions.

**Key Features:**
• Predictive analytics and forecasting
• Natural language processing
• Computer vision and automation
• Custom AI model development
• Business intelligence integration

Contact info@aniketsolutions.com for AI consultation."""

        elif category == 'data_services':
            return """**Data Services & Migration** - Database solutions and business intelligence platforms.

**Key Features:**
• Database migration and optimization
• Data warehousing and analytics
• Business intelligence dashboards
• ETL processes and data integration
• Cloud data platform setup

Contact info@aniketsolutions.com for data consultation."""

        elif category == 'integration':
            return """**System Integration Services** - Connecting business applications and data flow automation.

**Key Features:**
• API development and management
• ERP and CRM integration
• Real-time data synchronization
• Cloud and on-premise connectivity
• Workflow automation

Contact info@aniketsolutions.com for integration planning."""

    return """**Technology Services Portfolio** - Comprehensive business technology solutions:

• **Custom Development** - Tailored software solutions
• **Mobile Apps** - iOS/Android development
• **AI & ML** - Intelligent automation
• **Data Services** - Migration and analytics
• **Integration** - System connectivity
• **Chatbots** - Customer service automation

Contact info@aniketsolutions.com for service consultation."""

def generate_smart_response_enhanced(user_message):
    """Enhanced smart response using comprehensive keyword matching"""
    try:
        if "interaction_count" in st.session_state:
            st.session_state.interaction_count += 1
            st.session_state.last_activity = datetime.now()
        
        update_user_activity()
        
        category, confidence, matched_keywords = get_best_match_category(user_message)
        
        if confidence > 0.25:
            if category in ['inventory', 'payroll', 'crewing', 'tms', 'procurement']:
                return get_product_response_enhanced(user_message)
            elif category in ['custom_development', 'mobile', 'ai_ml', 'data_services', 'integration', 'chatbot']:
                return get_service_response_enhanced(user_message)
        
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
            
            ai_response = response.choices[0].message.content.strip()
            
            prohibited_phrases = [
                "that's a great question", "i'd be happy to", "absolutely", "perfect choice",
                "excellent question", "wonderful", "fantastic", "amazing", "excited to help"
            ]
            
            ai_lower = ai_response.lower()
            if not any(phrase in ai_lower for phrase in prohibited_phrases):
                return ai_response
        
        return "For information about our maritime software products and technology services, contact our specialists at info@aniketsolutions.com for detailed consultation."
        
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
        
        sender_email = SES_FROM_EMAIL
        
        if not sender_email:
            try:
                response = ses_client.list_verified_email_addresses()
                verified_emails = response.get('VerifiedEmailAddresses', [])
                
                if verified_emails:
                    sender_email = verified_emails[0]
                else:
                    return False, "No verified email addresses found in AWS SES. Please verify at least one email address."
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

def moderate_content(text):
    """Check content using OpenAI Moderation API"""
    try:
        if not client:
            return True, "Content moderation unavailable - proceeding"
        
        response = client.moderations.create(input=text)
        moderation_result = response.results[0]
        
        if moderation_result.flagged:
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
        return True, f"Moderation check failed, proceeding: {str(e)}"

def detect_gibberish(text):
    """Detect if text is gibberish or meaningless"""
    text_clean = text.lower().strip()
    
    if len(text_clean) < 2:
        return True, "Message too short"
    
    if len(set(text_clean)) <= 2 and len(text_clean) > 5:
        return True, "Excessive character repetition detected"
    
    vowels = set('aeiou')
    consonants = set('bcdfghjklmnpqrstvwxyz')
    
    vowel_count = sum(1 for char in text_clean if char in vowels)
    consonant_count = sum(1 for char in text_clean if char in consonants)
    total_letters = vowel_count + consonant_count
    
    if total_letters > 5:
        vowel_ratio = vowel_count / total_letters
        if vowel_ratio < 0.1 or vowel_ratio > 0.8:
            return True, "Unusual character pattern detected"
    
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
            return False, "Content unclear but allowed"
            
    except Exception as e:
        return False, f"AI gibberish check failed: {str(e)}"

def comprehensive_content_filter(text):
    """Comprehensive content filtering combining moderation and gibberish detection"""
    is_safe, moderation_message = moderate_content(text)
    if not is_safe:
        return False, f"🚫 Content Moderation: {moderation_message}"
    
    is_gibberish, gibberish_message = detect_gibberish(text)
    if is_gibberish:
        return False, f"🤖 Content Quality: {gibberish_message}. Please provide a meaningful business inquiry."
    
    if len(text.strip()) > 20:
        is_ai_gibberish, ai_message = advanced_gibberish_check_with_openai(text)
        if is_ai_gibberish:
            return False, f"🤖 Content Analysis: {ai_message}. Please provide a clear business inquiry."
    
    return True, "Content approved"

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
    
    corporate_indicators = [
        '.edu',  # Educational institutions
        '.gov',  # Government
        '.org',  # Organizations (many are corporate)
    ]
    
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
# ACTIVATE ALL KEEP-ALIVE SYSTEMS AND INACTIVITY MONITORING
# =============================================================================

# Run ALL keep-alive systems with enhanced timing
keep_alive_system()
add_javascript_keepalive()
add_auto_refresh()
add_service_worker()
add_inactivity_javascript()
add_server_side_keepalive()  # NEW: Server-side heartbeat

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
    
    /* Conversation ended styling with countdown animation */
    .conversation-ended {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 2px solid #dc3545;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 15px rgba(220, 53, 69, 0.2);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 4px 15px rgba(220, 53, 69, 0.2); }
        50% { box-shadow: 0 4px 25px rgba(220, 53, 69, 0.4); }
        100% { box-shadow: 0 4px 15px rgba(220, 53, 69, 0.2); }
    }
    
    .conversation-ended h3 {
        color: #dc3545;
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
    if validation_result['is_valid']:
        validation_response = "✅ Email validated successfully."
        add_message_to_chat("assistant", validation_response)
        
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

# Check for auto-reset first (before anything else)
check_auto_reset()

# Check for conversation inactivity BEFORE displaying chat
conversation_ended = check_conversation_inactivity()

# Add initial greeting if messages is empty
if len(st.session_state.messages) == 0:
    add_initial_greeting()

# If conversation has ended, show closure message with auto-reset countdown
if conversation_ended:
    # Calculate time remaining for auto-reset
    time_remaining = 10
    if (st.session_state.get("auto_reset_triggered") and 
        st.session_state.get("auto_reset_time")):
        time_since_reset = (datetime.now() - st.session_state.auto_reset_time).total_seconds()
        time_remaining = max(0, 10 - int(time_since_reset))
    
    if time_remaining > 0:
        st.markdown(f"""
        <div class="conversation-ended">
            <h3>🔒 Conversation Closed</h3>
            <p>This conversation has been closed due to inactivity.</p>
            <p>Thank you for your interest in Aniket Solutions!</p>
            <p style="color: #007bff; font-weight: bold;">
                🔄 Automatically restarting in {time_remaining} seconds...
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Add JavaScript countdown and auto-refresh
        st.markdown(f"""
        <script>
        let countdown = {time_remaining};
        const countdownInterval = setInterval(function() {{
            countdown--;
            const countdownElement = document.querySelector('.conversation-ended p:last-child');
            if (countdownElement && countdown > 0) {{
                countdownElement.innerHTML = '🔄 Automatically restarting in ' + countdown + ' seconds...';
            }} else if (countdown <= 0) {{
                clearInterval(countdownInterval);
                window.location.reload();
            }}
        }}, 1000);
        
        console.log('Auto-reset countdown started: {time_remaining} seconds');
        </script>
        """, unsafe_allow_html=True)
    else:
        # Fallback if timing is off
        st.markdown("🔄 Restarting chatbot...")
        st.rerun()
    
    # Still show manual restart option
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Restart Now", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    with col2:
        if st.button("📧 Contact Us", use_container_width=True):
            st.markdown("**Contact Aniket Solutions:**")
            st.markdown("📧 Email: info@aniketsolutions.com")
            st.markdown("🌐 Website: https://www.aniketsolutions.com")
    
    st.stop()

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
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
        st.success("✅ API Key configured from .env file")
        st.session_state.api_key = OPENAI_API_KEY
        if "openai_client" not in st.session_state:
            st.session_state.openai_client = client
    
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
            st.session_state.last_user_activity = datetime.now()
            st.session_state.conversation_ending_initiated = False
            st.session_state.final_question_asked = False
            st.session_state.waiting_for_final_response = False
            st.session_state.conversation_ended = False
            st.session_state.inactivity_timer_start = None
            add_initial_greeting()
            st.rerun()
    
    st.divider()
    
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
    
    if avatar_choice == "default":
        new_avatar = ALEX_AVATAR_URL
    else:
        new_avatar = ALTERNATIVE_AVATARS[avatar_choice]
    
    if st.session_state.selected_avatar != new_avatar:
        st.session_state.selected_avatar = new_avatar
        st.rerun()
    
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
    
    st.subheader("💬 Conversation Status")
    
    if (st.session_state.get("waiting_for_final_response") and 
        st.session_state.get("inactivity_timer_start")):
        
        time_remaining = 180 - (datetime.now() - st.session_state.inactivity_timer_start).total_seconds()
        if time_remaining > 0:
            st.warning(f"⏰ Conversation will close in {int(time_remaining)} seconds")
        else:
            st.error("⏰ Conversation closing...")
    elif st.session_state.get("conversation_ended"):
        st.error("🔒 Conversation closed")
    elif st.session_state.get("otp_verified"):
        time_since_activity = (datetime.now() - st.session_state.get("last_user_activity", datetime.now())).total_seconds()
        if time_since_activity > 120:  # 2 minutes
            st.warning(f"⏰ Inactive for {int(time_since_activity/60)} minutes")
        else:
            st.success("✅ Active conversation")
    else:
        st.info("🔄 Setting up conversation")
    
    st.divider()
    
    if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        st.warning("⚠️ AWS SES not configured. Please add AWS credentials to .env file.")
    else:
        st.success("✅ AWS SES configured")
        if not SES_FROM_EMAIL:
            st.info("ℹ️ SES_FROM_EMAIL not set - will use first verified email")
        else:
            st.success(f"📧 Sender email: {SES_FROM_EMAIL}")
    
    st.divider()
    
    st.subheader("🛡️ Content Moderation")
    if client:
        st.success("✅ Content moderation active")
        st.caption("OpenAI Moderation API + Gibberish Detection")
    else:
        st.warning("⚠️ Content moderation requires OpenAI API")
        st.caption("Basic gibberish detection only")
    
    st.divider()
    
    st.subheader("🚀 System Status")
    st.success("✅ All systems operational")
    st.caption("Keep-alive system running in background")

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
        
        Please:
        1. Check your email inbox (and spam folder)
        2. Find the 6-digit verification code
        3. Enter the code below
        
        The verification code will expire in 10 minutes.
        """)
        
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
            if st.button("📧 Resend Code", key="resend_otp", use_container_width=True):
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
                        add_message_to_chat("assistant", "📧 New verification code sent to your email!")
                        st.success("New verification code sent!")
                    else:
                        add_message_to_chat("assistant", f"❌ Failed to resend verification code: {message}")
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

    if send_button and user_input.strip():
        if not st.session_state.api_key:
            st.error("Please configure your OpenAI API key to start chatting.")
        else:
            update_user_activity()
            
            content_is_safe, filter_message = comprehensive_content_filter(user_input)
            
            if not content_is_safe:
                add_message_to_chat("user", user_input)
                add_message_to_chat("assistant", 
                    f"I apologize, but I cannot process your message. {filter_message}\n\n"
                    "Please rephrase your message with a clear business inquiry about our technology solutions or services."
                )
                st.rerun()
            else:
                add_message_to_chat("user", user_input)
                
                with st.spinner("Thinking..."):
                    try:
                        ai_response = generate_smart_response_enhanced(user_input)
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
    "Powered by Aniket Solutions • Enterprise AI Assistant"
    "</div>",
    unsafe_allow_html=True
)
