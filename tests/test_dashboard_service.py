"""
Test dashboard service.
"""

import pytest
from datetime import datetime, timedelta
from services.dashboard_service import DashboardService
from storage.database import Database


@pytest.fixture
def test_db_with_data():
    """Create test database with sample data."""
    db = Database(':memory:')
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Create family
        cursor.execute("INSERT INTO families (name) VALUES (?)", ("Test Family",))
        family_id = cursor.lastrowid
        
        # Create user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        """, ("testuser", "test@example.com", "hashed"))
        user_id = cursor.lastrowid
        
        # Create upload file
        cursor.execute("""
            INSERT INTO upload_files (family_id, user_id, filename, content_hash,
                                    file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (family_id, user_id, "test.jpg", "hash123", 1000, "image/jpeg", "test.jpg"))
        upload_id = cursor.lastrowid
        
        # Create test receipts
        now = datetime.utcnow()
        dates = [
            now - timedelta(days=2),
            now - timedelta(days=5),
            now - timedelta(days=15),
            now - timedelta(days=40)
        ]
        
        for i, date in enumerate(dates):
            cursor.execute("""
                INSERT INTO receipts (family_id, user_id, upload_file_id, merchant_name,
                                    merchant_normalized, purchase_date, total_amount, category, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (family_id, user_id, upload_id, f"Store {i}", f"store{i}",
                  date.date().isoformat(), 50.0 * (i + 1), "food", "confirmed"))
            
            receipt_id = cursor.lastrowid
            
            # Add deduction for some receipts
            if i % 2 == 0:
                cursor.execute("""
                    INSERT INTO receipt_deductions (receipt_id, is_deductible, deduction_type,
                                                  evidence_text, evidence_level, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (receipt_id, 1, "medical", "Test evidence", "high", 50.0 * (i + 1)))
        
        conn.commit()
    
    return db, family_id, user_id


def test_dashboard_stats(test_db_with_data):
    """Test dashboard statistics calculation."""
    db, family_id, user_id = test_db_with_data
    service = DashboardService(db)
    
    stats = service.get_family_dashboard(family_id)
    
    # Should have receipts from last week (2 days ago, 5 days ago)
    assert stats.receipt_count_week == 2
    
    # Should have receipts from last month (all except 40 days ago)
    assert stats.receipt_count_month == 3
    
    # Total expenses
    assert stats.total_expenses_week == 150.0  # 50 + 100
    assert stats.total_expenses_month == 300.0  # 50 + 100 + 150
    
    # Category breakdown
    assert 'food' in stats.category_breakdown


def test_deduction_summary(test_db_with_data):
    """Test deduction summary calculation."""
    db, family_id, user_id = test_db_with_data
    service = DashboardService(db)
    
    summary = service.get_deduction_summary(family_id)
    
    # Should have deductions
    assert summary['total_deductible'] > 0
    assert len(summary['summary_by_type']) > 0
    assert 'medical' in summary['summary_by_type']


def test_spending_trends(test_db_with_data):
    """Test spending trends calculation."""
    db, family_id, user_id = test_db_with_data
    service = DashboardService(db)
    
    trends = service.get_spending_trends(family_id, days=30, group_by='day')
    
    # Should have trend data
    assert len(trends) > 0
    assert 'period' in trends[0]
    assert 'total' in trends[0]
    assert 'count' in trends[0]


def test_period_dashboard_handles_datetime_purchase_dates():
    """Month queries should still include receipts stored with datetime strings."""
    db = Database(':memory:')
    reference_now = datetime.now().replace(hour=13, minute=45, second=0, microsecond=0)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO families (name) VALUES (?)", ("Test Family",))
        family_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ("testuser", "test@example.com", "hashed"),
        )
        user_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO upload_files (family_id, user_id, filename, content_hash,
                                      file_size, mime_type, storage_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (family_id, user_id, "test.jpg", "hash123", 1000, "image/jpeg", "test.jpg"),
        )
        upload_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO receipts (family_id, user_id, upload_file_id, merchant_name,
                                  merchant_normalized, purchase_date, total_amount, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                family_id,
                user_id,
                upload_id,
                "Month End Store",
                "monthendstore",
                reference_now.isoformat(),
                88.0,
                "food",
                "confirmed",
            ),
        )
        conn.commit()

    service = DashboardService(db)
    stats = service.get_period_dashboard(family_id, 'month')

    assert stats['receipt_count'] == 1
    assert stats['total_amount'] == 88.0
    assert len(stats['recent_receipts']) == 1


def test_month_period_uses_local_time_boundary(monkeypatch):
    """Month period should follow local time rather than UTC rollover."""
    class FixedDateTime(datetime):
        @classmethod
        def now(cls):
            return cls(2026, 3, 31, 23, 30, 0)

    monkeypatch.setattr('services.dashboard_service.datetime', FixedDateTime)

    service = DashboardService(Database(':memory:'))
    start_date, end_date = service.get_period_bounds('month')

    assert start_date == FixedDateTime(2026, 3, 1, 0, 0, 0)
    assert end_date == FixedDateTime(2026, 3, 31, 23, 30, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
