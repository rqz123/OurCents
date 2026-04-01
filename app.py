"""
OurCents - AI-Powered Family Expense Tracker
Main Streamlit application entry point.
"""

import streamlit as st
from dotenv import load_dotenv
import logging
import os
import sys

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)

logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Page configuration
st.set_page_config(
    page_title="OurCents - Family Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_session_state():
    """Initialize session state variables."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'family_id' not in st.session_state:
        st.session_state.family_id = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'family_name' not in st.session_state:
        st.session_state.family_name = None

def main():
    """Main application router."""
    initialize_session_state()
    logger.info("Application started")
    
    # Import pages
    from ui.pages import login, dashboard, upload, receipts, settings
    
    # Navigation
    if not st.session_state.authenticated:
        login.show()
    else:
        # Sidebar navigation
        st.sidebar.title("OurCents 💰")
        st.sidebar.write(f"Welcome, {st.session_state.username}!")
        
        page = st.sidebar.radio(
            "Navigation",
            ["Dashboard", "Upload Receipt", "Receipts", "Settings", "Logout"]
        )
        logger.info("Navigated to page=%s user=%s family_id=%s", page, st.session_state.username, st.session_state.family_id)
        
        if page == "Logout":
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.family_id = None
            st.session_state.is_admin = False
            st.session_state.username = None
            st.session_state.family_name = None
            st.rerun()
        elif page == "Dashboard":
            dashboard.show()
        elif page == "Upload Receipt":
            upload.show()
        elif page == "Receipts":
            receipts.show()
        elif page == "Settings":
            settings.show()

if __name__ == "__main__":
    main()
