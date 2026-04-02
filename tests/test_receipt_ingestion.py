"""
Test receipt ingestion service.
"""

import pytest
import asyncio
from datetime import datetime
from services.receipt_ingestion_service import ReceiptIngestionService
from storage.database import Database
from storage.file_storage import FileStorage
from models.schema import DeductionType, ExpenseCategory, ReceiptStatus, ReceiptExtractionResult, ReceiptItemData
from domain.classification import ClassificationEngine


@pytest.fixture
def test_db():
    """Create test database."""
    db = Database(':memory:')
    
    # Create test family and user
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO families (name) VALUES (?)", ("Test Family",))
        family_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        """, ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO family_members (family_id, user_id, role)
            VALUES (?, ?, ?)
        """, (family_id, user_id, "admin"))
        
        conn.commit()
    
    return db, family_id, user_id


def test_hash_duplicate_detection(test_db, tmp_path):
    """Test that identical file hashes are detected as duplicates."""
    db, family_id, user_id = test_db
    storage = FileStorage(str(tmp_path))
    service = ReceiptIngestionService(db, storage)
    
    # Create test file content
    test_content = b"fake image content"
    file_hash = storage.compute_file_hash(test_content)
    
    # Insert duplicate hash
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO upload_files (family_id, user_id, filename, content_hash,
                                    file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (family_id, user_id, "test.jpg", file_hash, 100, "image/jpeg", "test.jpg"))
        conn.commit()
    
    # Check duplicate detection
    assert service._check_hash_duplicate(file_hash, family_id) == True
    assert service._check_hash_duplicate("different_hash", family_id) == False


def test_merchant_name_normalization():
    """Test merchant name normalization."""
    from domain.deduplication import DuplicateDetector
    
    assert DuplicateDetector.normalize_merchant_name("Walmart Inc.") == "walmart"
    assert DuplicateDetector.normalize_merchant_name("Target Store #1234") == "target"
    assert DuplicateDetector.normalize_merchant_name("Joe's Pizza!") == "joes pizza"


def test_category_classification():
    """Test expense category classification."""

    assert ClassificationEngine.classify_by_merchant("Safeway") == ExpenseCategory.FOOD
    assert ClassificationEngine.classify_by_merchant("Home Depot") == ExpenseCategory.TOOLS
    assert ClassificationEngine.classify_by_merchant("CVS Pharmacy") == ExpenseCategory.HEALTHCARE
    assert ClassificationEngine.classify_by_merchant("Trader Joe's") == ExpenseCategory.FOOD


def test_merchant_override_beats_restaurant_like_items():
    """A grocery merchant should stay food even if item names resemble restaurant items."""
    category = ClassificationEngine.refine_classification(
        ExpenseCategory.RESTAURANT,
        "Trader Joe's",
        ["Orange Chicken", "Beer", "Wine"],
    )

    assert category == ExpenseCategory.FOOD


def test_deduction_rules():
    """Test tax deduction evaluation."""
    from domain.deduction_rules import DeductionRules
    from models.schema import DeductionType, EvidenceLevel
    
    is_ded, dtype, evidence, level = DeductionRules.evaluate_deduction(
        ExpenseCategory.HEALTHCARE,
        "CVS Pharmacy",
        ["Prescription medication"],
        None,
        ""
    )
    
    assert is_ded == True
    assert dtype == DeductionType.MEDICAL
    assert level in [EvidenceLevel.HIGH, EvidenceLevel.MEDIUM]


def test_admin_can_delete_receipt_and_image(monkeypatch, test_db, tmp_path):
    """Admin deletion should remove receipt records and stored image."""
    db, family_id, user_id = test_db
    storage = FileStorage(str(tmp_path))
    monkeypatch.setattr('services.receipt_ingestion_service.get_ai_provider', lambda: object())
    service = ReceiptIngestionService(db, storage)

    relative_path = storage.get_storage_path(family_id, 1, 'abc123def4567890', 'jpg')
    storage.save_file(b'fake image content', relative_path)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO upload_files (family_id, user_id, filename, content_hash, file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (family_id, user_id, 'test.jpg', 'hash123', 100, 'image/jpeg', relative_path),
        )
        upload_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO receipts (family_id, user_id, upload_file_id, merchant_name,
                                  merchant_normalized, purchase_date, total_amount, currency,
                                  category, status, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_id,
                user_id,
                upload_id,
                'Trader Joe\'s',
                'trader joes',
                '2026-04-01',
                42.50,
                'USD',
                ExpenseCategory.FOOD.value,
                ReceiptStatus.CONFIRMED.value,
                0.88,
            ),
        )
        receipt_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO receipt_items (receipt_id, description, quantity, unit_price, total_price, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, 'Bread', 1.0, 3.99, 3.99, ExpenseCategory.FOOD.value),
        )
        cursor.execute(
            """
            INSERT INTO receipt_deductions (receipt_id, is_deductible, deduction_type, evidence_text, evidence_level, amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, 0, DeductionType.NONE.value, '', 'none', 0.0),
        )
        conn.commit()

    deleted_receipt = service.delete_receipt(family_id, receipt_id, user_id)

    assert deleted_receipt['merchant_name'] == "Trader Joe's"
    assert deleted_receipt['purchase_date'] == '2026-04-01'
    assert deleted_receipt['total_amount'] == 42.50
    assert deleted_receipt['status'] == ReceiptStatus.CONFIRMED.value

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM receipts WHERE id = ?", (receipt_id,))
        assert cursor.fetchone()['count'] == 0
        cursor.execute("SELECT COUNT(*) AS count FROM upload_files WHERE id = ?", (upload_id,))
        assert cursor.fetchone()['count'] == 0
        cursor.execute("SELECT COUNT(*) AS count FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
        assert cursor.fetchone()['count'] == 0
        cursor.execute("SELECT COUNT(*) AS count FROM receipt_deductions WHERE receipt_id = ?", (receipt_id,))
        assert cursor.fetchone()['count'] == 0

    assert storage.get_file(relative_path) is None


def test_non_admin_cannot_delete_receipt(monkeypatch, test_db, tmp_path):
    """Only family admins should be able to delete receipts."""
    db, family_id, user_id = test_db
    storage = FileStorage(str(tmp_path))
    monkeypatch.setattr('services.receipt_ingestion_service.get_ai_provider', lambda: object())
    service = ReceiptIngestionService(db, storage)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ('memberuser', 'member@example.com', 'hashed_password'),
        )
        member_user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO family_members (family_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            (family_id, member_user_id, 'member'),
        )
        cursor.execute(
            """
            INSERT INTO upload_files (family_id, user_id, filename, content_hash, file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (family_id, user_id, 'test.jpg', 'hash123', 100, 'image/jpeg', 'missing.jpg'),
        )
        upload_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO receipts (family_id, user_id, upload_file_id, merchant_name,
                                  merchant_normalized, purchase_date, total_amount, currency,
                                  category, status, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_id,
                user_id,
                upload_id,
                'Trader Joe\'s',
                'trader joes',
                '2026-04-01',
                42.50,
                'USD',
                ExpenseCategory.FOOD.value,
                ReceiptStatus.PENDING.value,
                0.88,
            ),
        )
        receipt_id = cursor.lastrowid
        conn.commit()

    with pytest.raises(ValueError, match='Only admins can delete receipts'):
        service.delete_receipt(family_id, receipt_id, member_user_id)


def test_process_receipt_upload_defaults_to_ocr(monkeypatch, test_db, tmp_path):
    """OCR-first processing should create a pending receipt without calling AI."""
    db, family_id, user_id = test_db
    storage = FileStorage(str(tmp_path))

    class DummyAIProvider:
        async def extract_receipt_data(self, image_content, mime_type):
            raise AssertionError('AI should not be used in OCR-first test')

    monkeypatch.setattr('services.receipt_ingestion_service.get_ai_provider', lambda: DummyAIProvider())
    service = ReceiptIngestionService(db, storage)

    async def fake_ocr_extract(image_content, mime_type):
        return ReceiptExtractionResult(
            merchant_name="Trader Joe's",
            purchase_date=datetime(2026, 4, 2, 12, 0, 0),
            total_amount=23.45,
            currency='USD',
            items=[
                ReceiptItemData(
                    description='Bananas',
                    quantity=1.0,
                    unit_price=2.49,
                    total_price=2.49,
                    category=ExpenseCategory.FOOD,
                )
            ],
            confidence_score=0.67,
            category_suggestion=ExpenseCategory.FOOD,
        )

    monkeypatch.setattr(service.ocr_extractor, 'extract_receipt_data', fake_ocr_extract)

    status, receipt_id, info = asyncio.run(
        service.process_receipt_upload(
            family_id=family_id,
            user_id=user_id,
            file_content=b'fake-image',
            filename='receipt.jpg',
            mime_type='image/jpeg',
            extraction_method='ocr',
        )
    )

    assert status == 'pending_confirmation'
    assert receipt_id is not None
    assert info['extraction_method'] == 'ocr'
    assert info['extraction']['merchant_name'] == "Trader Joe's"


def test_reread_receipt_with_ai_updates_existing_pending_receipt(monkeypatch, test_db, tmp_path):
    """AI re-read should update the existing receipt in place rather than flagging itself as a duplicate."""
    db, family_id, user_id = test_db
    storage = FileStorage(str(tmp_path))

    class DummyAIProvider:
        async def extract_receipt_data(self, image_content, mime_type):
            return ReceiptExtractionResult(
                merchant_name='Safeway',
                purchase_date=datetime(2026, 4, 3, 9, 30, 0),
                total_amount=31.2,
                currency='USD',
                items=[
                    ReceiptItemData(
                        description='Milk',
                        quantity=1.0,
                        unit_price=4.29,
                        total_price=4.29,
                        category=ExpenseCategory.FOOD,
                    )
                ],
                confidence_score=0.94,
                category_suggestion=ExpenseCategory.FOOD,
            )

    monkeypatch.setattr('services.receipt_ingestion_service.get_ai_provider', lambda: DummyAIProvider())
    service = ReceiptIngestionService(db, storage)

    async def fake_ocr_extract(image_content, mime_type):
        return ReceiptExtractionResult(
            merchant_name='Unknown Merchant',
            purchase_date=datetime(2026, 4, 3, 9, 30, 0),
            total_amount=31.2,
            currency='USD',
            items=[],
            confidence_score=0.41,
            category_suggestion=ExpenseCategory.OTHER,
        )

    monkeypatch.setattr(service.ocr_extractor, 'extract_receipt_data', fake_ocr_extract)

    status, receipt_id, info = asyncio.run(
        service.process_receipt_upload(
            family_id=family_id,
            user_id=user_id,
            file_content=b'fake-image',
            filename='receipt.jpg',
            mime_type='image/jpeg',
            extraction_method='ocr',
        )
    )

    assert status == 'pending_confirmation'
    assert info['extraction_method'] == 'ocr'

    update_info = asyncio.run(service.reread_receipt_with_ai(family_id, receipt_id))

    assert update_info['status'] == 'pending_confirmation'
    assert update_info['extraction_method'] == 'ai'
    assert update_info['extraction']['merchant_name'] == 'Safeway'

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT merchant_name, category, confidence_score, status FROM receipts WHERE id = ?",
            (receipt_id,),
        )
        receipt = cursor.fetchone()

    assert receipt['merchant_name'] == 'Safeway'
    assert receipt['category'] == ExpenseCategory.FOOD.value
    assert receipt['status'] == ReceiptStatus.PENDING.value
    assert receipt['confidence_score'] == 0.94


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
