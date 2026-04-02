"""Tests for configurable merchant aliases and category rules."""

from datetime import date

import pytest

from models.schema import DeductionType, ExpenseCategory, ReceiptStatus
from services.classification_rules_service import ClassificationRulesService
from services.receipt_ingestion_service import ReceiptIngestionService
from storage.database import Database
from storage.file_storage import FileStorage


@pytest.fixture
def rules_db(tmp_path):
    """Create a database, storage, and family context for rule tests."""
    db = Database(':memory:')
    storage = FileStorage(str(tmp_path))

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO families (name) VALUES (?)", ("Rules Family",))
        family_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ("admin", "admin@example.com", "hashed"),
        )
        user_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO family_members (family_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            (family_id, user_id, "admin"),
        )
        conn.commit()

    return db, storage, family_id, user_id


def test_alias_and_category_rule_override(rules_db):
    """Admin-configured alias and category rules should override static classification."""
    db, storage, family_id, user_id = rules_db
    service = ClassificationRulesService(db)

    service.upsert_merchant_alias(
        family_id=family_id,
        alias_name="Trader Joe's #123",
        canonical_name="Trader Joe's",
        priority=120,
        created_by=user_id,
    )
    service.upsert_category_rule(
        family_id=family_id,
        merchant_name="Trader Joe's",
        category=ExpenseCategory.FOOD,
        priority=180,
        created_by=user_id,
        source='admin',
        notes='Configured grocery override',
    )

    result = service.classify_receipt(
        family_id=family_id,
        ai_suggestion=ExpenseCategory.RESTAURANT,
        merchant_name="Trader Joe's #123",
        item_descriptions=["Orange Chicken", "Beer"],
    )

    assert result['merchant_name'] == "Trader Joe's"
    assert result['merchant_normalized'] == 'trader joes'
    assert result['category'] == ExpenseCategory.FOOD
    assert result['rule_source'] == 'admin'


def test_confirm_receipt_records_feedback_rule(monkeypatch, rules_db):
    """Manual confirmation should feed future classification with a feedback rule."""
    db, storage, family_id, user_id = rules_db

    monkeypatch.setattr(
        'services.receipt_ingestion_service.get_ai_provider',
        lambda: object(),
    )

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO upload_files (family_id, user_id, filename, content_hash, file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (family_id, user_id, 'receipt.jpg', 'hash123', 100, 'image/jpeg', 'receipt.jpg'),
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
                "Trader Joe's",
                'trader joes',
                '2026-04-01',
                42.50,
                'USD',
                ExpenseCategory.RESTAURANT.value,
                ReceiptStatus.PENDING.value,
                0.88,
            ),
        )
        receipt_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO receipt_deductions (receipt_id, is_deductible, deduction_type, evidence_text, evidence_level, amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, 0, DeductionType.NONE.value, '', 'none', 0.0),
        )
        conn.commit()

    ingestion_service = ReceiptIngestionService(db, storage)
    ingestion_service.confirm_receipt(
        family_id=family_id,
        receipt_id=receipt_id,
        merchant_name="Trader Joe's",
        purchase_date_value=date(2026, 4, 1),
        total_amount=42.50,
        category=ExpenseCategory.FOOD,
        is_deductible=False,
        deduction_type=DeductionType.NONE,
        deduction_evidence='',
        items=[],
        notes='Reviewed by admin',
    )

    rules_service = ClassificationRulesService(db)
    rule_rows = rules_service.list_category_rules(family_id)

    assert len(rule_rows) == 1
    assert rule_rows[0]['merchant_display_name'] == "Trader Joe's"
    assert rule_rows[0]['category'] == ExpenseCategory.FOOD.value
    assert rule_rows[0]['source'] == 'feedback'


def test_batch_reclassification_preview_and_apply(rules_db):
    """Historical receipts should preview and apply category changes under configured rules."""
    db, storage, family_id, user_id = rules_db
    service = ClassificationRulesService(db)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO upload_files (family_id, user_id, filename, content_hash, file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (family_id, user_id, 'receipt.jpg', 'hash123', 100, 'image/jpeg', 'receipt.jpg'),
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
                "Trader Joe's #55",
                'trader joes 55',
                '2026-03-30',
                55.03,
                'USD',
                ExpenseCategory.RESTAURANT.value,
                ReceiptStatus.CONFIRMED.value,
                0.91,
            ),
        )
        receipt_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO receipt_items (receipt_id, description, quantity, unit_price, total_price, category)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, 'Orange Chicken', 1.0, 5.99, 5.99, ExpenseCategory.RESTAURANT.value),
        )

        cursor.execute(
            """
            INSERT INTO receipt_deductions (receipt_id, is_deductible, deduction_type, evidence_text, evidence_level, amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (receipt_id, 0, DeductionType.NONE.value, '', 'none', 0.0),
        )
        conn.commit()

    service.upsert_merchant_alias(
        family_id=family_id,
        alias_name="Trader Joe's #55",
        canonical_name="Trader Joe's",
        priority=120,
        created_by=user_id,
    )
    service.upsert_category_rule(
        family_id=family_id,
        merchant_name="Trader Joe's",
        category=ExpenseCategory.FOOD,
        priority=180,
        created_by=user_id,
        source='admin',
        notes='Grocery override',
    )

    preview = service.preview_reclassification(family_id)

    assert preview['changed_receipts'] == 1
    assert preview['changes'][0]['current_category'] == ExpenseCategory.RESTAURANT.value
    assert preview['changes'][0]['new_category'] == ExpenseCategory.FOOD.value
    assert preview['changes'][0]['new_merchant_name'] == "Trader Joe's"

    result = service.apply_reclassification(family_id, user_id=user_id)

    assert result['updated_receipts'] == 1

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT merchant_name, merchant_normalized, category FROM receipts WHERE id = ?",
            (receipt_id,),
        )
        updated_receipt = dict(cursor.fetchone())

        cursor.execute(
            "SELECT deduction_type, amount FROM receipt_deductions WHERE receipt_id = ?",
            (receipt_id,),
        )
        deduction = dict(cursor.fetchone())

    assert updated_receipt['merchant_name'] == "Trader Joe's"
    assert updated_receipt['merchant_normalized'] == 'trader joes'
    assert updated_receipt['category'] == ExpenseCategory.FOOD.value
    assert deduction['deduction_type'] == DeductionType.NONE.value
    assert deduction['amount'] == 0.0