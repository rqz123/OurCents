"""
Receipts list and search page.
"""

import logging
import streamlit as st
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
from PIL import Image
from storage.database import get_database
from storage.file_storage import get_file_storage
from services.receipt_ingestion_service import ReceiptIngestionService
from models.schema import DeductionType, ExpenseCategory, ReceiptStatus


logger = logging.getLogger(__name__)


def show():
    """Display receipts list page."""
    st.title("Receipts")
    
    db = get_database()
    storage = get_file_storage()
    ingestion_service = ReceiptIngestionService(db, storage)
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_filter = st.selectbox(
            "Date Range",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
        )
    
    with col2:
        category_filter = st.selectbox(
            "Category",
            ["All Categories"] + [category.value for category in ExpenseCategory]
        )
    
    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All Status", "Pending", "confirmed", "duplicate_confirmed"]
        )
    
    # Determine date range
    date_mapping = {
        "Last 7 Days": 7,
        "Last 30 Days": 30,
        "Last 90 Days": 90,
        "All Time": None
    }
    days_back = date_mapping[date_filter]
    
    # Build query
    query = """
        SELECT r.id, r.merchant_name, r.purchase_date, r.total_amount,
               r.currency, r.category, r.status, r.confidence_score,
               u.username, uf.storage_path
        FROM receipts r
        JOIN users u ON u.id = r.user_id
        JOIN upload_files uf ON uf.id = r.upload_file_id
        WHERE r.family_id = ?
    """
    params = [st.session_state.family_id]
    
    if days_back:
        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).date()
        query += " AND r.purchase_date >= ?"
        params.append(cutoff_date.isoformat())
    
    if category_filter != "All Categories":
        query += " AND r.category = ?"
        params.append(category_filter)
    
    if status_filter == "Pending":
        query += " AND r.status IN (?, ?)"
        params.extend([
            ReceiptStatus.PENDING.value,
            ReceiptStatus.DUPLICATE_SUSPECTED.value,
        ])
    elif status_filter != "All Status":
        query += " AND r.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY r.purchase_date DESC, r.created_at DESC"
    
    # Execute query
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            receipts = [dict(row) for row in cursor.fetchall()]
        
        # Display results
        st.write(f"Found {len(receipts)} receipt(s)")
        
        if receipts:
            for receipt in receipts:
                with st.expander(
                    f"{receipt['merchant_name']} - ${receipt['total_amount']:.2f} - {receipt['purchase_date']}"
                ):
                    details = ingestion_service.get_receipt_details(
                        st.session_state.family_id,
                        receipt['id'],
                    )
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Merchant:** {receipt['merchant_name']}")
                        st.write(f"**Date:** {receipt['purchase_date']}")
                        st.write(f"**Amount:** {receipt['currency']} ${receipt['total_amount']:.2f}")
                        st.write(f"**Category:** {receipt['category']}")
                        st.write(f"**Status:** {receipt['status']}")
                        st.write(f"**Uploaded by:** {receipt['username']}")

                        deduction = details.get('deduction') if details else None
                        if deduction and deduction['is_deductible']:
                            st.write(
                                f"**Tax Deductible:** Yes ({deduction['deduction_type']}, "
                                f"{deduction['evidence_level']} confidence)"
                            )
                            if deduction.get('evidence_text'):
                                st.write(f"**Deduction Evidence:** {deduction['evidence_text']}")
                        else:
                            st.write("**Tax Deductible:** No")

                        items = details.get('items', []) if details else []
                        if items:
                            st.write("**Extracted Items:**")
                            for item in items:
                                st.write(
                                    f"- {item['description']} | qty {item['quantity']} | "
                                    f"${item['total_price']:.2f} | {item['category']}"
                                )

                        if receipt['status'] in [ReceiptStatus.PENDING.value, ReceiptStatus.DUPLICATE_SUSPECTED.value]:
                            edit_mode_key = f"edit_mode_{receipt['id']}"
                            if edit_mode_key not in st.session_state:
                                st.session_state[edit_mode_key] = False

                            if not st.session_state[edit_mode_key]:
                                if st.button("Edit Pending Receipt", key=f"edit_receipt_{receipt['id']}"):
                                    st.session_state[edit_mode_key] = True
                                    st.rerun()
                            else:
                                editable = _build_editable_receipt_values(details)
                                st.write("**Editable Confirmation Fields:**")
                                st.caption("Esc cancels the current cell edit inside the editors below. Confirmation only happens when you click Confirm Receipt.")

                                edited_receipt = st.data_editor(
                                    pd.DataFrame([{
                                        'merchant_name': editable['merchant_name'],
                                        'purchase_date': editable['purchase_date'],
                                        'total_amount': editable['total_amount'],
                                        'category': editable['category'],
                                        'is_deductible': editable['is_deductible'],
                                        'deduction_type': editable['deduction_type'],
                                        'deduction_evidence': editable['deduction_evidence'],
                                        'notes': editable['notes'],
                                    }]),
                                    key=f"receipt_editor_{receipt['id']}",
                                    use_container_width=True,
                                    hide_index=True,
                                    num_rows="fixed",
                                    column_config={
                                        "merchant_name": st.column_config.TextColumn("Merchant", required=True),
                                        "purchase_date": st.column_config.DateColumn("Purchase Date", format="YYYY-MM-DD"),
                                        "total_amount": st.column_config.NumberColumn("Total Amount", min_value=0.0, step=0.01),
                                        "category": st.column_config.SelectboxColumn(
                                            "Category",
                                            options=[category.value for category in ExpenseCategory],
                                        ),
                                        "is_deductible": st.column_config.CheckboxColumn("Tax Deductible"),
                                        "deduction_type": st.column_config.SelectboxColumn(
                                            "Deduction Type",
                                            options=[deduction_type.value for deduction_type in DeductionType],
                                        ),
                                        "deduction_evidence": st.column_config.TextColumn("Deduction Evidence"),
                                        "notes": st.column_config.TextColumn("Review Notes"),
                                    },
                                )

                                edited_items = st.data_editor(
                                    pd.DataFrame(editable['items']),
                                    key=f"items_editor_{receipt['id']}",
                                    use_container_width=True,
                                    hide_index=True,
                                    num_rows="dynamic",
                                    column_config={
                                        "description": st.column_config.TextColumn("Description", required=True),
                                        "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, step=1.0),
                                        "unit_price": st.column_config.NumberColumn("Unit Price", min_value=0.0, step=0.01),
                                        "total_price": st.column_config.NumberColumn("Total Price", min_value=0.0, step=0.01),
                                        "category": st.column_config.SelectboxColumn(
                                            "Category",
                                            options=[category.value for category in ExpenseCategory],
                                        ),
                                    },
                                )

                                receipt_row = edited_receipt.to_dict(orient='records')[0]

                                action_col1, action_col2, action_col3 = st.columns(3)
                                with action_col1:
                                    if st.button("Confirm Receipt", key=f"confirm_receipt_{receipt['id']}", type="primary"):
                                        ingestion_service.confirm_receipt(
                                            st.session_state.family_id,
                                            receipt['id'],
                                            str(receipt_row.get('merchant_name') or '').strip(),
                                            _parse_date_value(receipt_row.get('purchase_date')),
                                            float(receipt_row.get('total_amount') or 0.0),
                                            ExpenseCategory(receipt_row.get('category') or ExpenseCategory.OTHER.value),
                                            bool(receipt_row.get('is_deductible')),
                                            DeductionType(receipt_row.get('deduction_type') or DeductionType.NONE.value),
                                            str(receipt_row.get('deduction_evidence') or ''),
                                            _normalize_items_for_save(edited_items),
                                            str(receipt_row.get('notes') or ''),
                                        )
                                        st.session_state[edit_mode_key] = False
                                        logger.info("Receipt confirmed from receipts page receipt_id=%s", receipt['id'])
                                        st.success("Receipt confirmed.")
                                        st.rerun()
                                with action_col2:
                                    if st.button("Cancel Edits", key=f"cancel_receipt_{receipt['id']}"):
                                        _reset_pending_editor_state(receipt['id'])
                                        st.session_state[edit_mode_key] = False
                                        st.rerun()
                                with action_col3:
                                    if st.button("Mark as Duplicate", key=f"mark_duplicate_{receipt['id']}"):
                                        ingestion_service.update_receipt_status(
                                            st.session_state.family_id,
                                            receipt['id'],
                                            ReceiptStatus.DUPLICATE_CONFIRMED,
                                            str(receipt_row.get('notes') or ''),
                                        )
                                        st.session_state[edit_mode_key] = False
                                        logger.info("Receipt marked duplicate from receipts page receipt_id=%s", receipt['id'])
                                        st.success("Receipt marked as duplicate.")
                                        st.rerun()
                    
                    with col2:
                        st.write("**Receipt Image:**")
                        image_bytes = storage.get_file(receipt['storage_path'])
                        if image_bytes:
                            st.image(_resize_image_for_preview(image_bytes), use_container_width=False)
                        else:
                            st.info(f"Image not found: {receipt['storage_path']}")
        else:
            st.info("No receipts found matching your filters")
            
    except Exception as e:
        st.error(f"Error loading receipts: {str(e)}")


def _build_editable_receipt_values(details):
    """Build editable defaults from stored receipt details."""
    deduction = details.get('deduction') if details else None
    return {
        'merchant_name': details.get('merchant_name', ''),
        'purchase_date': _parse_date_value(details.get('purchase_date')),
        'total_amount': float(details.get('total_amount') or 0.0),
        'category': details.get('category') or ExpenseCategory.OTHER.value,
        'is_deductible': bool(deduction.get('is_deductible')) if deduction else False,
        'deduction_type': deduction.get('deduction_type') if deduction else DeductionType.NONE.value,
        'deduction_evidence': deduction.get('evidence_text') if deduction else '',
        'items': details.get('items') or [],
        'notes': details.get('notes') or '',
    }


def _parse_date_value(value):
    """Parse stored receipt date values into a date object."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    return date.today()


def _enum_index(enum_cls, value):
    """Return selectbox index for an enum value string."""
    values = [enum_value.value for enum_value in enum_cls]
    return values.index(value) if value in values else 0


def _normalize_items_for_save(edited_items):
    """Normalize Streamlit data editor output into a serializable item list."""
    if hasattr(edited_items, 'to_dict'):
        records = edited_items.to_dict(orient='records')
    else:
        records = list(edited_items)

    normalized = []
    for item in records:
        normalized.append({
            'description': str(item.get('description') or '').strip(),
            'quantity': float(item.get('quantity') or 1.0),
            'unit_price': None if item.get('unit_price') in (None, '') else float(item.get('unit_price')),
            'total_price': float(item.get('total_price') or 0.0),
            'category': item.get('category') or ExpenseCategory.OTHER.value,
        })
    return normalized


def _reset_pending_editor_state(receipt_id: int) -> None:
    """Reset all widget state for a pending receipt review form."""
    keys_to_clear = [
        f'merchant_{receipt_id}',
        f'purchase_date_{receipt_id}',
        f'amount_{receipt_id}',
        f'category_{receipt_id}',
        f'deductible_{receipt_id}',
        f'deduction_type_{receipt_id}',
        f'evidence_{receipt_id}',
        f'notes_{receipt_id}',
        f'items_editor_{receipt_id}',
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def _resize_image_for_preview(file_content: bytes, max_width: int = 520, max_height: int = 720) -> bytes:
    """Resize preview images to keep receipt previews within a predictable range."""
    with Image.open(BytesIO(file_content)) as image:
        preview_image = image.copy()
        preview_image.thumbnail((max_width, max_height))
        output = BytesIO()
        preview_format = preview_image.format or image.format or 'PNG'
        preview_image.save(output, format=preview_format)
        return output.getvalue()
