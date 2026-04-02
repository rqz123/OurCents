# Getting Started with OurCents

This guide covers local setup, first use, and the current workflow.

## Prerequisites

- Python 3.10 or higher
- Tesseract OCR installed locally
- OpenAI API key

On macOS:

```bash
brew install tesseract
```

## Quick Start

### macOS/Linux

```bash
chmod +x start.sh
./start.sh
```

### Windows

```powershell
.\start.ps1
```

The startup scripts create the environment file if needed, install dependencies, create required directories, and launch Streamlit.

## Manual Setup

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`.

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your_actual_api_key_here
AI_PROVIDER=openai
```

Optional Gemini configuration is still supported, but OpenAI is the default runtime path.

### 3. Run the Application

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## First-Time Setup

### Create a Family Account

1. Open the login page.
2. Choose the family account creation flow.
3. Enter a family name and admin account details.
4. Sign in with the new account.

### Upload Your First Receipt

1. Open `Upload Receipt` from the sidebar.
2. Drop in a receipt image or browse for a file.
3. Click `Process Receipts`.
4. Review the OCR extraction preview.
5. If OCR looks wrong, use `Re-read With AI` from the preview card.
6. Open `Receipts` and switch to the pending view.
7. Edit fields if needed and confirm the receipt.

## Current Workflow Notes

### Upload
- Upload scans and previews receipts with OCR first.
- Each OCR result can be re-read with AI from the preview card.
- Upload does not directly confirm receipts.
- After processing completes, the uploader returns to its empty state.

### Pending Confirmation
- Pending receipts are the only confirmation step.
- Fields and line items can be edited before confirmation.
- Similar receipts can be marked as duplicates.

### Dashboard
- Dashboard supports `This Week`, `This Month`, and `This Year`.
- Periods use local calendar time semantics.
- Analysis focuses on category-based spending and recent receipts.

## Troubleshooting

### `OPENAI_API_KEY` Missing

Make sure:
1. `.env` exists.
2. `OPENAI_API_KEY` is set to a real key.
3. The app was restarted after updating `.env`.

### Import Errors

Make sure:
1. The virtual environment is activated.
2. Dependencies were installed with `pip install -r requirements.txt`.
3. You are running commands from the project root.

### Database Reset

If you need a clean local reset:
1. Use the admin-only reset flow in `Settings`, or
2. Remove `data/ourcents.db` and `data/receipts/` manually before restarting.

### AI Processing Errors

If receipt processing fails:
1. Check that your API key is valid.
2. Confirm the image is a supported format.
3. Review the terminal logs for extraction or provider errors.

### OCR Unavailable

If OCR fails before extraction starts:
1. Confirm that `tesseract` is installed and available in your shell.
2. Restart the app after installing Tesseract.
3. Use the AI fallback button on failed uploads if OCR is temporarily unavailable.

## Data Locations

- Database: `data/ourcents.db`
- Receipt images: `data/receipts/`
- Temporary uploads: `data/temp/`

## Backup Recommendation

To back up current data, copy:
- `data/ourcents.db`
- `data/receipts/`

## Next Reading

- `README.md` for overview and current feature set
- `IMPLEMENTATION.md` for roadmap and remaining work
