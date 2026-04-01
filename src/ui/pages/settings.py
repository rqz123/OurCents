"""
Settings and family management page.
"""

import streamlit as st
from storage.database import get_database
from storage.file_storage import get_file_storage
from services.auth_service import AuthService
from services.ai import get_ai_provider


def show():
    """Display settings page."""
    st.title("Settings")
    
    db = get_database()
    file_storage = get_file_storage()
    auth_service = AuthService(db)
    
    tab1, tab2 = st.tabs(["Family Members", "Account Settings"])
    
    # Family Members Tab
    with tab1:
        st.header("Family Members")
        
        members = auth_service.get_family_members(st.session_state.family_id)
        
        st.write(f"Total members: {len(members)}")
        
        for member in members:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{member['username']}** ({member['email']})")
            with col2:
                st.write(f"Role: {member['role']}")
            with col3:
                st.write(f"Joined: {member['joined_at'][:10]}")
        
        st.divider()
        
        # Add member (admin only)
        if st.session_state.is_admin:
            st.subheader("Add Family Member")
            
            with st.form("add_member_form"):
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                
                submit = st.form_submit_button("Add Member")
                
                if submit:
                    if not all([new_username, new_email, new_password]):
                        st.error("Please fill in all fields")
                    elif len(new_password) < 8:
                        st.error("Password must be at least 8 characters")
                    else:
                        try:
                            user_id = auth_service.create_family_member(
                                family_id=st.session_state.family_id,
                                username=new_username,
                                email=new_email,
                                password=new_password,
                                creator_user_id=st.session_state.user_id
                            )
                            st.success(f"Member '{new_username}' added successfully!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                        except Exception as e:
                            st.error(f"Failed to add member: {str(e)}")
        else:
            st.info("Only family administrators can add new members")
    
    # Account Settings Tab
    with tab2:
        st.header("Account Settings")
        
        st.write(f"**Username:** {st.session_state.username}")
        st.write(f"**Family:** {st.session_state.family_name or _get_family_name(db, st.session_state.family_id)}")
        st.write(f"**Role:** {'Administrator' if st.session_state.is_admin else 'Member'}")
        
        st.divider()
        
        st.subheader("Configuration")
        st.info("Application configuration settings")
        
        import os
        st.write(f"**AI Provider:** {_get_effective_ai_provider()}")
        st.write(f"**Database:** {os.getenv('DATABASE_PATH', './data/ourcents.db')}")
        st.write(f"**Storage:** {os.getenv('RECEIPTS_STORAGE_PATH', './data/receipts')}")

        st.divider()

        if st.session_state.is_admin:
            st.subheader("Danger Zone")
            st.warning(
                "Debug-only action. This will permanently delete the entire database, all users, "
                "all families, and all stored receipt images."
            )

            with st.expander("Reset database and receipt images"):
                st.write("This action cannot be undone.")
                confirm_understand = st.checkbox(
                    "I understand this will permanently delete all application data.",
                    key="reset_understand",
                )
                confirm_family = st.text_input(
                    "Type your family name to confirm",
                    key="reset_family_name",
                    placeholder=st.session_state.family_name or "Family Name",
                )
                confirm_phrase = st.text_input(
                    "Type RESET ALL DATA to continue",
                    key="reset_phrase",
                    placeholder="RESET ALL DATA",
                )

                if st.button("Delete database and receipt images", type="primary"):
                    family_name = st.session_state.family_name or _get_family_name(db, st.session_state.family_id)
                    if not confirm_understand:
                        st.error("You must acknowledge the destructive action first.")
                    elif confirm_family.strip() != family_name:
                        st.error("Family name confirmation does not match.")
                    elif confirm_phrase.strip() != "RESET ALL DATA":
                        st.error("You must type RESET ALL DATA exactly.")
                    else:
                        db.reset_application_data()
                        file_storage.clear_all_files()
                        _clear_session_and_logout()
                        st.success("Application data deleted. You have been logged out.")
                        st.rerun()
        else:
            st.info("Only family administrators can access debug reset controls.")


def _get_effective_ai_provider() -> str:
    """Return the effective AI provider in use."""
    try:
        return get_ai_provider().provider_name
    except Exception:
        import os
        return os.getenv('AI_PROVIDER', 'gemini')


def _get_family_name(db, family_id: int) -> str:
    """Fetch family name when session state is missing it."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM families WHERE id = ?", (family_id,))
        row = cursor.fetchone()
        return row['name'] if row else 'Unknown Family'


def _clear_session_and_logout() -> None:
    """Clear the authenticated session after destructive reset."""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.family_id = None
    st.session_state.family_name = None
    st.session_state.is_admin = False
    st.session_state.username = None
