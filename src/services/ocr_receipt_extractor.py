"""OCR-first receipt extraction with lightweight heuristic parsing."""

import asyncio
import os
import re
import shutil
from datetime import datetime
from io import BytesIO
from typing import List, Optional

from PIL import Image, ImageFilter, ImageOps
from dateutil import parser as date_parser

from models.schema import (
    DeductionType,
    EvidenceLevel,
    ExpenseCategory,
    ReceiptExtractionResult,
    ReceiptItemData,
)

try:
    import pytesseract
except ImportError:  # pragma: no cover - handled by validate_configuration
    pytesseract = None


class OCRReceiptExtractor:
    """Use local OCR to extract receipt data before spending AI tokens."""

    MONEY_PATTERN = re.compile(r"(?:\$\s*)?(\d{1,4}(?:[\.,]\d{3})*(?:[\.,]\d{2}))")
    DATE_PATTERNS = [
        re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
        re.compile(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"),
        re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b", re.IGNORECASE),
    ]
    TOTAL_LABELS = ('total', 'amount due', 'balance due', 'grand total')
    NOISE_LINE_PATTERNS = (
        re.compile(r"^[\W_]+$"),
        re.compile(r"^(receipt|invoice|thank you|visa|mastercard|subtotal|tax)\b", re.IGNORECASE),
    )

    def __init__(self):
        self.tesseract_cmd = self._resolve_tesseract_cmd()
        if pytesseract is not None and self.tesseract_cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def validate_configuration(self) -> bool:
        """Return whether local OCR is available."""
        return pytesseract is not None and self.tesseract_cmd is not None

    async def extract_receipt_data(self, image_content: bytes, mime_type: str) -> ReceiptExtractionResult:
        """Run OCR and parse a structured receipt result."""
        return await asyncio.to_thread(self._extract_sync, image_content)

    def _extract_sync(self, image_content: bytes) -> ReceiptExtractionResult:
        if not self.validate_configuration():
            raise RuntimeError(
                "OCR is unavailable because Tesseract is not installed. Install Tesseract locally or switch to AI reading."
            )

        with Image.open(BytesIO(image_content)) as image:
            processed = self._prepare_image(image)
            text = pytesseract.image_to_string(processed)

        return self._parse_text(text)

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        grayscale = ImageOps.grayscale(image)
        contrasted = ImageOps.autocontrast(grayscale)
        filtered = contrasted.filter(ImageFilter.SHARPEN)
        return filtered

    def _parse_text(self, text: str) -> ReceiptExtractionResult:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        merchant_name = self._extract_merchant(lines)
        purchase_date = self._extract_date(lines) or datetime.now()
        total_amount = self._extract_total(lines)
        items = self._extract_items(lines)
        category_suggestion = self._suggest_category(merchant_name, items)
        confidence_score = self._estimate_confidence(merchant_name, purchase_date, total_amount, items, lines)

        return ReceiptExtractionResult(
            merchant_name=merchant_name,
            purchase_date=purchase_date,
            total_amount=total_amount,
            currency='USD',
            items=items,
            confidence_score=confidence_score,
            category_suggestion=category_suggestion,
            tax_deductible=False,
            deduction_type=DeductionType.NONE,
            deduction_evidence='OCR-first extraction. Review and switch to AI if fields look wrong.',
            evidence_level=EvidenceLevel.NONE,
        )

    def _extract_merchant(self, lines: List[str]) -> str:
        candidates = []
        for line in lines[:8]:
            if any(pattern.search(line) for pattern in self.NOISE_LINE_PATTERNS):
                continue
            if self._extract_money_values(line):
                continue
            if any(pattern.search(line) for pattern in self.DATE_PATTERNS):
                continue
            if len(line) < 3:
                continue
            candidates.append(line)

        if candidates:
            return max(candidates, key=len)
        return lines[0] if lines else 'Unknown Merchant'

    def _extract_date(self, lines: List[str]) -> Optional[datetime]:
        for line in lines:
            for pattern in self.DATE_PATTERNS:
                match = pattern.search(line)
                if match:
                    try:
                        return date_parser.parse(match.group(0), fuzzy=True, default=datetime.now())
                    except (ValueError, OverflowError):
                        continue
        return None

    def _extract_total(self, lines: List[str]) -> float:
        labeled_totals = []
        all_amounts = []

        for line in lines:
            amounts = self._extract_money_values(line)
            all_amounts.extend(amounts)
            if any(label in line.lower() for label in self.TOTAL_LABELS):
                labeled_totals.extend(amounts)

        if labeled_totals:
            return max(labeled_totals)
        if all_amounts:
            return max(all_amounts)
        return 0.0

    def _extract_items(self, lines: List[str]) -> List[ReceiptItemData]:
        items = []
        for line in lines:
            amounts = self._extract_money_values(line)
            if len(amounts) != 1:
                continue
            if any(label in line.lower() for label in self.TOTAL_LABELS):
                continue
            description = re.sub(r"(?:\$\s*)?\d{1,4}(?:[\.,]\d{3})*(?:[\.,]\d{2})", '', line).strip(' -')
            if len(description) < 2:
                continue
            items.append(
                ReceiptItemData(
                    description=description,
                    quantity=1.0,
                    unit_price=amounts[0],
                    total_price=amounts[0],
                    category=ExpenseCategory.OTHER,
                )
            )
            if len(items) >= 10:
                break
        return items

    def _suggest_category(self, merchant_name: str, items: List[ReceiptItemData]) -> ExpenseCategory:
        from domain.classification import ClassificationEngine

        item_descriptions = [item.description for item in items]
        return ClassificationEngine.refine_classification(
            ExpenseCategory.OTHER,
            merchant_name,
            item_descriptions,
        )

    def _estimate_confidence(
        self,
        merchant_name: str,
        purchase_date: datetime,
        total_amount: float,
        items: List[ReceiptItemData],
        lines: List[str],
    ) -> float:
        score = 0.15
        if merchant_name and merchant_name != 'Unknown Merchant':
            score += 0.25
        if purchase_date:
            score += 0.2
        if total_amount > 0:
            score += 0.25
        if items:
            score += 0.1
        if len(lines) >= 6:
            score += 0.05
        return round(min(score, 0.95), 2)

    def _extract_money_values(self, line: str) -> List[float]:
        values = []
        for match in self.MONEY_PATTERN.findall(line):
            normalized = match.replace(',', '')
            try:
                values.append(float(normalized))
            except ValueError:
                continue
        return values

    def _resolve_tesseract_cmd(self) -> Optional[str]:
        command = shutil.which('tesseract')
        if command:
            return command

        candidates = [
            '/opt/homebrew/bin/tesseract',
            '/usr/local/bin/tesseract',
            '/opt/local/bin/tesseract',
        ]

        configured_path = os.getenv('TESSERACT_CMD')
        if configured_path:
            candidates.insert(0, configured_path)

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        return None