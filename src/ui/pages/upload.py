"""
Receipt upload page with drag-and-drop functionality.
"""

import streamlit as st
import asyncio
import logging
import pandas as pd
from io import BytesIO

from PIL import Image
from storage.database import get_database
from storage.file_storage import get_file_storage
from services.receipt_ingestion_service import ReceiptIngestionService


logger = logging.getLogger(__name__)


def show():
    """Display receipt upload page."""
    if 'upload_uploader_key' not in st.session_state:
        st.session_state.upload_uploader_key = 0
    if 'upload_processing_results' not in st.session_state:
        st.session_state.upload_processing_results = []

    st.title("Upload Receipt")
    
    st.write("Upload receipt images to automatically extract and categorize expense data.")
    st.caption("Drag files into the upload box below, or click the box to browse manually.")

    _render_processing_results(st.session_state.upload_processing_results)
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Drop receipt images here or click to browse",
        type=['png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=True,
        help="Supported formats: PNG, JPG, JPEG, WEBP",
        key=f"upload_uploader_{st.session_state.upload_uploader_key}"
    )
    
    if uploaded_files:
        st.write(f"{len(uploaded_files)} file(s) selected")
        
        if st.button("Process Receipts", type="primary"):
            process_uploads(uploaded_files)
            st.session_state.upload_uploader_key += 1
            st.rerun()


def process_uploads(uploaded_files):
    """Process uploaded receipt files."""
    db = get_database()
    storage = get_file_storage()
    ingestion_service = ReceiptIngestionService(db, storage)
    processing_results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(uploaded_files)
    
    for idx, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processing {uploaded_file.name}...")
        logger.info("Upload page started processing filename=%s", uploaded_file.name)
        
        try:
            # Read file content
            file_content = uploaded_file.getvalue()
            mime_type = uploaded_file.type
            
            # Process receipt
            status, receipt_id, info = asyncio.run(
                ingestion_service.process_receipt_upload(
                    family_id=st.session_state.family_id,
                    user_id=st.session_state.user_id,
                    file_content=file_content,
                    filename=uploaded_file.name,
                    mime_type=mime_type,
                    extraction_method='ocr',
                )
            )

            processing_results.append({
                'filename': uploaded_file.name,
                'status': status,
                'receipt_id': receipt_id,
                'info': info,
                'file_content': file_content,
                'mime_type': mime_type,
            })
            
            # Display result
            if status == 'pending_confirmation':
                st.success(f"{uploaded_file.name} was processed and is waiting for confirmation in Receipts > Pending.")
            elif status == 'duplicate_hash':
                st.warning(f"⚠️ {uploaded_file.name} - {info['reason']}")
            elif status == 'duplicate_semantic':
                st.warning(f"{uploaded_file.name} looks similar to an existing receipt and needs confirmation in Receipts > Pending.")
            else:
                st.error(f"❌ {uploaded_file.name} - Processing failed")
                
        except Exception as e:
            logger.exception("Upload page failed while processing filename=%s", uploaded_file.name)
            st.error(f"❌ {uploaded_file.name} - Error: {str(e)}")
            processing_results.append({
                'filename': uploaded_file.name,
                'status': 'error',
                'receipt_id': None,
                'info': {'error': str(e), 'extraction_method': 'ocr'},
                'file_content': file_content,
                'mime_type': mime_type,
            })
        
        progress_bar.progress((idx + 1) / total)
    
    status_text.text("Processing complete!")
    st.balloons()
    st.session_state.upload_processing_results = processing_results


def _render_processing_results(processing_results):
    """Render the latest upload results after the uploader resets."""
    if not processing_results:
        return

    st.success("Processing complete. The uploader is ready for another batch.")

    for result_index, result in enumerate(processing_results):
        filename = result['filename']
        status = result['status']
        info = result.get('info') or {}

        if status == 'pending_confirmation':
            st.success(f"{filename} was processed and is waiting for confirmation in Receipts > Pending.")
            _render_receipt_preview(
                filename,
                result['file_content'],
                result['receipt_id'],
                info,
                status,
                result_index=result_index,
            )
        elif status == 'duplicate_hash':
            st.warning(f"⚠️ {filename} - {info.get('reason', 'Duplicate receipt detected')}")
        elif status == 'duplicate_semantic':
            st.warning(f"{filename} looks similar to an existing receipt and needs confirmation in Receipts > Pending.")
            _render_receipt_preview(
                filename,
                result['file_content'],
                result['receipt_id'],
                info,
                status,
                result_index=result_index,
            )
        else:
            st.error(f"❌ {filename} - {info.get('error', 'Processing failed')}")
            if result.get('file_content') and result.get('mime_type') and info.get('extraction_method') == 'ocr':
                if st.button("Process With AI Instead", key=f"upload-ai-fallback-{result_index}"):
                    _process_failed_upload_with_ai(result_index)


def _render_receipt_preview(filename, file_content, receipt_id, info, status, result_index):
    """Render extraction preview and tell the user to confirm from Pending receipts."""
    extraction = info.get('extraction', {}) if info else {}
    extraction_method = info.get('extraction_method', 'ocr') if info else 'ocr'

    with st.container(border=True):
        st.subheader(f"Review: {filename}")
        col1, col2 = st.columns([1, 1])

        with col1:
            st.write("Receipt Image")
            st.image(_resize_image_for_preview(file_content), use_container_width=False)

        with col2:
            st.write("Extracted Summary")
            st.caption(f"Source: {extraction_method.upper()}")
            st.write(f"Merchant: {extraction.get('merchant_name', 'Unknown')}")
            st.write(f"Purchase Date: {extraction.get('purchase_date', 'Unknown')}")
            st.write(f"Total Amount: {extraction.get('currency', 'USD')} {extraction.get('total_amount', 0)}")
            st.write(f"Suggested Category: {extraction.get('category_suggestion', 'other')}")
            st.write(f"Confidence: {extraction.get('confidence_score', 0):.2f}")
            st.write(f"Tax Deductible: {'Yes' if extraction.get('tax_deductible') else 'No'}")
            if extraction.get('deduction_evidence'):
                st.write(f"Deduction Evidence: {extraction.get('deduction_evidence')}")

            if extraction_method == 'ocr' and extraction.get('confidence_score', 0) < 0.75:
                st.warning("OCR confidence is limited. If fields look wrong, re-read this receipt with AI.")

        items = extraction.get('items', [])
        if items:
            st.write("Extracted Items")
            st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)

        if status == 'duplicate_semantic' and info.get('duplicates'):
            with st.expander("View similar receipts"):
                for duplicate in info['duplicates']:
                    st.write(
                        f"Receipt #{duplicate['id']} | {duplicate['merchant_name']} | "
                        f"{duplicate['purchase_date']} | ${duplicate['total_amount']:.2f}"
                    )

        if extraction_method == 'ocr' and receipt_id:
            if st.button("Re-read With AI", key=f"upload-reread-ai-{receipt_id}"):
                _reread_receipt_with_ai(result_index)

        st.info(f"Receipt #{receipt_id} now requires confirmation in Receipts > Pending.")


def _reread_receipt_with_ai(result_index: int):
    """Re-read an OCR-created pending receipt with AI and update the cached preview."""
    result = st.session_state.upload_processing_results[result_index]
    db = get_database()
    storage = get_file_storage()
    ingestion_service = ReceiptIngestionService(db, storage)

    try:
        update_info = asyncio.run(
            ingestion_service.reread_receipt_with_ai(
                family_id=st.session_state.family_id,
                receipt_id=result['receipt_id'],
            )
        )
        result['status'] = update_info['status']
        result['info'] = update_info
        st.session_state.upload_processing_results[result_index] = result
        st.rerun()
    except Exception as exc:
        st.error(f"AI re-read failed: {exc}")


def _process_failed_upload_with_ai(result_index: int):
    """Retry a failed OCR upload with AI extraction instead."""
    result = st.session_state.upload_processing_results[result_index]
    db = get_database()
    storage = get_file_storage()
    ingestion_service = ReceiptIngestionService(db, storage)

    try:
        status, receipt_id, info = asyncio.run(
            ingestion_service.process_receipt_upload(
                family_id=st.session_state.family_id,
                user_id=st.session_state.user_id,
                file_content=result['file_content'],
                filename=result['filename'],
                mime_type=result['mime_type'],
                extraction_method='ai',
            )
        )
        result['status'] = status
        result['receipt_id'] = receipt_id
        result['info'] = info
        st.session_state.upload_processing_results[result_index] = result
        st.rerun()
    except Exception as exc:
        st.error(f"AI processing failed: {exc}")


def _resize_image_for_preview(file_content: bytes, max_width: int = 520, max_height: int = 720) -> bytes:
    """Resize preview images to keep receipt previews within a predictable range."""
    with Image.open(BytesIO(file_content)) as image:
        preview_image = image.copy()
        preview_image.thumbnail((max_width, max_height))
        output = BytesIO()
        preview_format = preview_image.format or image.format or 'PNG'
        preview_image.save(output, format=preview_format)
        return output.getvalue()
