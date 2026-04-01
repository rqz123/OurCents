"""
Login and family registration page.
"""

import streamlit as st
from storage.database import get_database
from services.auth_service import AuthService


def show():
    """Display login/registration page."""
    st.title("OurCents - Family Expense Tracker")
    
    tab1, tab2 = st.tabs(["Login", "Create Family Account"])
    
    # Login Tab
    with tab1:
        st.header("Login")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    try:
                        db = get_database()
                        auth_service = AuthService(db)
                        user_info = auth_service.authenticate(username, password)
                        
                        if user_info:
                            # Set session state
                            st.session_state.authenticated = True
                            st.session_state.user_id = user_info['user_id']
                            st.session_state.username = user_info['username']
                            st.session_state.family_id = user_info['family_id']
                            st.session_state.family_name = user_info['family_name']
                            st.session_state.is_admin = user_info['is_admin']
                            st.success(f"Welcome back, {username}!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                    except Exception as e:
                        st.error(f"Login failed: {str(e)}")
    
    # Registration Tab
    with tab2:
        st.header("Create Family Account")
        st.write("Create a new family account. You will be the family administrator.")
        
        with st.form("register_form"):
            family_name = st.text_input("Family Name", help="e.g., 'Smith Family'")
            admin_username = st.text_input("Admin Username", help="Your login username")
            admin_email = st.text_input("Admin Email")
            admin_password = st.text_input("Admin Password", type="password")
            admin_password_confirm = st.text_input("Confirm Password", type="password")
            
            submit = st.form_submit_button("Create Family Account")
            
            if submit:
                if not all([family_name, admin_username, admin_email, admin_password]):
                    st.error("Please fill in all fields")
                elif admin_password != admin_password_confirm:
                    st.error("Passwords do not match")
                elif len(admin_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    try:
                        db = get_database()
                        auth_service = AuthService(db)
                        
                        family_id, user_id = auth_service.create_family_with_admin(
                            family_name, admin_username, admin_email, admin_password
                        )
                        
                        st.success(f"Family account created successfully! Please login.")
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"Registration failed: {str(e)}")
