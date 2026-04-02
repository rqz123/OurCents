"""
Settings and family management page.
"""

import pandas as pd
import streamlit as st
from models.schema import ExpenseCategory
from storage.database import get_database
from storage.file_storage import get_file_storage
from services.auth_service import AuthService
from services.ai import get_ai_provider
from services.classification_rules_service import ClassificationRulesService


def show():
    """Display settings page."""
    st.title("Settings")
    
    db = get_database()
    file_storage = get_file_storage()
    auth_service = AuthService(db)
    classification_rules = ClassificationRulesService(db)
    
    tab1, tab2, tab3 = st.tabs(["Family Members", "Classification Rules", "Account Settings"])
    
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
    
    with tab2:
        st.header("Classification Rules")

        if not st.session_state.is_admin:
            st.info("Only family administrators can manage merchant aliases and category rules.")
        else:
            st.caption(
                "Aliases standardize merchant names. Category rules override the built-in classifier. "
                "Pending receipt confirmations automatically create feedback rules for future classification."
            )

            alias_col, rule_col = st.columns(2)

            with alias_col:
                st.subheader("Merchant Aliases")
                with st.form("merchant_alias_form"):
                    alias_name = st.text_input("Alias Name", placeholder="Trader Joe's #123")
                    canonical_name = st.text_input("Canonical Merchant Name", placeholder="Trader Joe's")
                    alias_priority = st.number_input("Alias Priority", min_value=1, max_value=1000, value=100, step=10)
                    alias_submit = st.form_submit_button("Save Alias")

                    if alias_submit:
                        if not alias_name.strip() or not canonical_name.strip():
                            st.error("Alias name and canonical merchant name are required.")
                        else:
                            classification_rules.upsert_merchant_alias(
                                family_id=st.session_state.family_id,
                                alias_name=alias_name,
                                canonical_name=canonical_name,
                                priority=int(alias_priority),
                                created_by=st.session_state.user_id,
                            )
                            st.success("Merchant alias saved.")
                            st.rerun()

            with rule_col:
                st.subheader("Merchant Category Rules")
                with st.form("merchant_category_rule_form"):
                    merchant_name = st.text_input("Merchant Name", placeholder="Trader Joe's")
                    category_value = st.selectbox(
                        "Category",
                        options=[category.value for category in ExpenseCategory],
                    )
                    rule_priority = st.number_input("Rule Priority", min_value=1, max_value=1000, value=150, step=10)
                    rule_notes = st.text_input("Notes", placeholder="Grocery chain or custom override")
                    rule_submit = st.form_submit_button("Save Category Rule")

                    if rule_submit:
                        if not merchant_name.strip():
                            st.error("Merchant name is required.")
                        else:
                            classification_rules.upsert_category_rule(
                                family_id=st.session_state.family_id,
                                merchant_name=merchant_name,
                                category=ExpenseCategory(category_value),
                                priority=int(rule_priority),
                                created_by=st.session_state.user_id,
                                source='admin',
                                notes=rule_notes,
                            )
                            st.success("Merchant category rule saved.")
                            st.rerun()

            alias_rows = classification_rules.list_merchant_aliases(st.session_state.family_id)
            if alias_rows:
                st.write("Active Merchant Aliases")
                st.dataframe(pd.DataFrame(alias_rows), use_container_width=True, hide_index=True)

                alias_delete_options = {
                    f"{row['alias_normalized']} -> {row['canonical_name']} (priority {row['priority']})": row['id']
                    for row in alias_rows
                }
                selected_alias_label = st.selectbox(
                    "Delete Alias",
                    options=list(alias_delete_options.keys()),
                    key="delete_alias_select",
                )
                if st.button("Delete Selected Alias"):
                    classification_rules.delete_merchant_alias(
                        st.session_state.family_id,
                        alias_delete_options[selected_alias_label],
                    )
                    st.success("Merchant alias deleted.")
                    st.rerun()
            else:
                st.info("No merchant aliases configured yet.")

            st.divider()

            rule_rows = classification_rules.list_category_rules(st.session_state.family_id)
            if rule_rows:
                st.write("Active Merchant Category Rules")
                st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)

                rule_delete_options = {
                    f"{row['merchant_display_name']} -> {row['category']} ({row['source']}, priority {row['priority']})": row['id']
                    for row in rule_rows
                }
                selected_rule_label = st.selectbox(
                    "Delete Rule",
                    options=list(rule_delete_options.keys()),
                    key="delete_rule_select",
                )
                if st.button("Delete Selected Rule"):
                    classification_rules.delete_category_rule(
                        st.session_state.family_id,
                        rule_delete_options[selected_rule_label],
                    )
                    st.success("Merchant category rule deleted.")
                    st.rerun()
            else:
                st.info("No merchant category rules configured yet.")

            st.divider()
            st.subheader("Batch Reclassify Historical Receipts")
            st.caption(
                "Re-apply aliases and merchant category rules to existing pending, confirmed, and duplicate-suspected receipts. "
                "This also refreshes tax deduction metadata based on the updated category."
            )

            preview = classification_rules.preview_reclassification(st.session_state.family_id)
            preview_col1, preview_col2 = st.columns(2)
            with preview_col1:
                st.metric("Active Receipts Considered", preview['total_active_receipts'])
            with preview_col2:
                st.metric("Receipts That Would Change", preview['changed_receipts'])

            if preview['changes']:
                st.write("Preview Changes")
                st.dataframe(pd.DataFrame(preview['changes'][:50]), use_container_width=True, hide_index=True)
                if preview['changed_receipts'] > 50:
                    st.caption(f"Showing first 50 of {preview['changed_receipts']} pending changes.")

                confirm_reclassify = st.checkbox(
                    "I understand this will update existing receipts using the current alias and category rules.",
                    key="confirm_batch_reclassify",
                )
                if st.button("Apply Batch Reclassification", type="primary"):
                    if not confirm_reclassify:
                        st.error("You must confirm before applying batch reclassification.")
                    else:
                        result = classification_rules.apply_reclassification(
                            family_id=st.session_state.family_id,
                            user_id=st.session_state.user_id,
                        )
                        st.success(f"Updated {result['updated_receipts']} historical receipt(s).")
                        st.rerun()
            else:
                st.info("No historical receipts need reclassification under the current rules.")

    # Account Settings Tab
    with tab3:
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
