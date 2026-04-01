# OurCents - Project File Inventory

Generated: March 31, 2026

## Total Files: 38

### Root Configuration (5)
- .env.example           # Environment configuration template
- .gitignore            # Git ignore rules
- LICENSE               # MIT License
- README.md             # Main project documentation
- requirements.txt      # Python dependencies

### Documentation (2)
- GETTING_STARTED.md    # Setup and usage guide
- IMPLEMENTATION.md     # Implementation summary

### Application Entry (1)
- app.py                # Streamlit application entry point

### Launch Scripts (2)
- start.sh              # Unix/Mac launch script
- start.ps1             # Windows PowerShell launch script

### Source Code (24)

#### Models & Schema (2)
- src/models/__init__.py
- src/models/schema.py              # Data models, enums, Pydantic schemas

#### Storage Layer (3)
- src/storage/__init__.py
- src/storage/database.py           # SQLite database management
- src/storage/file_storage.py       # Local file storage operations

#### Domain Logic (4)
- src/domain/__init__.py
- src/domain/classification.py      # Expense categorization rules
- src/domain/deduction_rules.py     # Tax deduction evaluation
- src/domain/deduplication.py       # Duplicate detection logic

#### Service Layer (6)
- src/services/__init__.py
- src/services/auth_service.py              # Authentication & user management
- src/services/dashboard_service.py         # Dashboard statistics
- src/services/receipt_ingestion_service.py # Receipt processing orchestration
- src/services/ai/__init__.py               # AI provider factory
- src/services/ai/receipt_ai_provider.py    # AI provider interface

#### AI Providers (3)
- src/services/ai/providers/__init__.py
- src/services/ai/providers/gemini_provider.py  # Google Gemini implementation
- src/services/ai/providers/openai_provider.py  # OpenAI placeholder

#### UI Layer (6)
- src/ui/__init__.py
- src/ui/pages/__init__.py
- src/ui/pages/dashboard.py     # Family dashboard page
- src/ui/pages/login.py         # Login & registration page
- src/ui/pages/receipts.py      # Receipt list & search page
- src/ui/pages/settings.py      # Settings & member management
- src/ui/pages/upload.py        # Receipt upload page

### Tests (3)
- tests/__init__.py
- tests/test_dashboard_service.py    # Dashboard service tests
- tests/test_receipt_ingestion.py    # Receipt ingestion tests

## Lines of Code (Estimated)

- Python Code: ~2,800 lines
- Documentation: ~600 lines
- Configuration: ~100 lines
- **Total: ~3,500 lines**

## Key Components Summary

### Database Schema (8 tables)
1. families - Family accounts
2. users - User credentials
3. family_members - User-family relationships
4. upload_files - File metadata & hashes
5. receipts - Receipt records
6. receipt_items - Itemized line items
7. receipt_deductions - Tax deduction info
8. audit_logs - Activity logging

### AI Processing Pipeline
1. Image upload → Hash computation
2. Hash duplicate check
3. AI extraction (Gemini/OpenAI)
4. Merchant normalization
5. Semantic duplicate check
6. Category refinement
7. Tax deduction evaluation
8. Database persistence

### UI Pages (5)
1. Login/Registration
2. Dashboard (with charts)
3. Upload Receipt
4. Receipts List
5. Settings

### Core Features
- ✅ Multi-user family accounts
- ✅ Role-based access control
- ✅ AI-powered receipt extraction
- ✅ Dual-layer duplicate detection
- ✅ Smart categorization
- ✅ Tax deduction tracking
- ✅ Visual analytics
- ✅ Local deployment ready

## Quick Start Commands

```bash
# Setup and run (Mac/Linux)
./start.sh

# Setup and run (Windows)
.\start.ps1

# Manual setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add GEMINI_API_KEY
streamlit run app.py

# Run tests
pytest tests/ -v
```

## Next Actions

1. **Configure**: Add your Gemini API key to `.env`
2. **Run**: Execute `./start.sh` or `streamlit run app.py`
3. **Test**: Create family account and upload first receipt
4. **Deploy**: For production, consider Docker containerization

---

Project ready for deployment and testing.
