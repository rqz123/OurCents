"""
Test receipt ingestion service.
"""

import pytest
from datetime import datetime
from services.receipt_ingestion_service import ReceiptIngestionService
from storage.database import Database
from storage.file_storage import FileStorage
from models.schema import ExpenseCategory
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
