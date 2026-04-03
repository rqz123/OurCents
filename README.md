# OurCents

OurCents is a self-hosted family receipt management app for local expense tracking, duplicate detection, category analysis, and tax-deductible expense review.

It is designed for small household use with local SQLite storage, local receipt image storage, and AI-assisted receipt extraction.

## Current Status

The MVP is implemented and usable.

Core capabilities already available:
- family account creation and member management
- upload and AI extraction of receipt images
- pending confirmation workflow with editable fields and items
- duplicate detection for exact and similar receipts
- category-based dashboard analysis for week, month, and year
- admin reset of database and stored receipt images

## Main Features

### Receipt Processing
- Drag-and-drop or browse receipt uploads
- AI extraction of merchant, date, amount, items, and category hints
- Preview shown immediately after processing
- Upload widget resets after processing completes

### Confirmation Workflow
- New receipts go to Receipts > Pending
- Pending receipts are the single confirmation point
- Users can edit merchant, date, amount, category, deductible state, and line items
- Suspected duplicates can be reviewed before confirmation

### Analytics
- This Week, This Month, and This Year dashboard views
- Category breakdown and ranking
- Spending trend visualization
- Tax-deductible summary for the selected period
- Recent receipt list for the selected period

### Family and Admin Features
- Shared family workspace
- Admin/member role separation
- Family member management
- Admin-only destructive reset for debugging and clean re-tests

## Technology Stack

- Frontend: Streamlit
- Backend: Python
- Database: SQLite
- File Storage: local filesystem
- AI: OpenAI by default, Gemini supported through the provider abstraction

## Quick Start

### Prerequisites

- Python 3.10 or higher
- OpenAI API key

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

## Configuration

Example `.env` values:

```env
OPENAI_API_KEY=your_api_key_here
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
DATABASE_PATH=./data/ourcents.db
RECEIPTS_STORAGE_PATH=./data/receipts
SECRET_KEY=change_this_to_random_string
```

Gemini can still be used as an alternate provider if configured explicitly.

## Typical Workflow

1. Create a family account.
2. Upload one or more receipt images.
3. Review the extraction preview.
4. Open Receipts > Pending.
5. Edit and confirm the receipt.
6. Review dashboard analytics.

## Project Structure

```text
OurCents/
├── app.py
├── README.md
├── GETTING_STARTED.md
├── IMPLEMENTATION.md
├── requirements.txt
├── src/
│   ├── domain/
│   ├── models/
│   ├── services/
│   ├── storage/
│   └── ui/
├── tests/
└── data/
```

## Testing

Run the test suite with:

```bash
pytest tests/
```

## Current Gaps

The most important remaining work is:
- richer dashboard comparisons and member filtering
- configurable category rules
- export features
- backup and restore
- documentation and warning cleanup

See `IMPLEMENTATION.md` for the current roadmap.
