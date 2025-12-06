"""
PDF Parser Module for FEHB Plan Brochures

This module downloads and parses PDF brochures to extract Tier 4 / Specialty Drug coverage information.
"""

import requests
import pdfplumber
import os
import re
import logging
from typing import Dict, Optional
from pathlib import Path
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFBrochureParser:
    """Parser for FEHB plan brochure PDFs"""

    def __init__(self, output_dir: str = "output/pdfs", timeout: int = 30, max_retries: int = 3):
        """
        Initialize the PDF parser.

        Args:
            output_dir: Directory to save downloaded PDFs
            timeout: Download timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.output_dir = output_dir
        self.timeout = timeout
        self.max_retries = max_retries

        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove invalid characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem
        """
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def download_pdf(self, url: str, plan_code: str, plan_name: str) -> Optional[str]:
        """
        Download PDF brochure from URL.

        Args:
            url: URL of the PDF brochure
            plan_code: Plan code for filename
            plan_name: Plan name for filename

        Returns:
            Path to downloaded PDF file or None if download failed
        """
        # Create filename
        safe_plan_name = self.sanitize_filename(plan_name)
        filename = f"{plan_code}_{safe_plan_name}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        # Check if file already exists (caching)
        if os.path.exists(filepath):
            logger.info(f"PDF already exists, skipping download: {filename}")
            return filepath

        # Download PDF with retry logic
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Downloading PDF for {plan_name} (attempt {attempt + 1}/{self.max_retries})")
                response = requests.get(url, timeout=self.timeout, stream=True)
                response.raise_for_status()

                # Save PDF
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"Successfully downloaded: {filename}")
                return filepath

            except requests.RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to download PDF after {self.max_retries} attempts: {e}")
                    return None

    def extract_text(self, pdf_path: str) -> Optional[str]:
        """
        Extract all text from PDF using pdfplumber.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Combined text from all pages or None if extraction failed
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = []

                for page_num, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text()
                        if text:
                            all_text.append(text)
                    except Exception as e:
                        logger.warning(f"Could not extract text from page {page_num + 1}: {e}")

                if not all_text:
                    logger.warning(f"No text extracted from PDF: {pdf_path}")
                    return None

                combined_text = "\n".join(all_text)
                logger.info(f"Extracted {len(combined_text)} characters from {os.path.basename(pdf_path)}")
                return combined_text

        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return None

    def parse_coverage_rule(self, context_text: str) -> Dict[str, any]:
        """
        Parse coverage rule text to extract copay or coinsurance.

        Args:
            context_text: Text snippet containing coverage rule

        Returns:
            Dict with coverage type and value
        """
        # Look for copay pattern
        copay_pattern = r'\$(\d+(?:\.\d{2})?)\s*(?:copay|copayment|per prescription)?'
        copay_match = re.search(copay_pattern, context_text, re.IGNORECASE)

        if copay_match and '%' not in context_text[:context_text.find(copay_match.group())]:
            return {
                "type": "copay",
                "value": float(copay_match.group(1))
            }

        # Look for coinsurance pattern
        coinsurance_pattern = r'(\d+(?:\.\d+)?)\s*%\s*(?:coinsurance)?'
        coinsurance_match = re.search(coinsurance_pattern, context_text, re.IGNORECASE)

        if coinsurance_match:
            percentage = float(coinsurance_match.group(1))
            return {
                "type": "coinsurance",
                "value": percentage / 100.0
            }

        return {
            "type": "unknown",
            "value": None
        }

    def find_tier4_coverage(self, text: str) -> Dict[str, any]:
        """
        Search for Tier 4 / Specialty Drug coverage in PDF text.

        Args:
            text: Extracted text from PDF

        Returns:
            Dict with tier_4_found, coverage_rule, and raw_text
        """
        if not text:
            return {
                "tier_4_found": False,
                "coverage_rule": "Not specified",
                "coverage_type": "unknown",
                "coverage_value": None,
                "raw_text": ""
            }

        # Keywords to search for
        keywords = [
            r'tier\s*4',
            r'tier\s*four',
            r'specialty\s*drug',
            r'specialty\s*medication',
            r'high[- ]cost\s*specialty',
            r'high[- ]cost\s*drug'
        ]

        # Search for keywords
        for keyword_pattern in keywords:
            match = re.search(keyword_pattern, text, re.IGNORECASE)

            if match:
                # Extract context around the match (500 chars before and after)
                start_pos = max(0, match.start() - 500)
                end_pos = min(len(text), match.end() + 500)
                context = text[start_pos:end_pos]

                # Parse the coverage rule from context
                coverage_info = self.parse_coverage_rule(context)

                logger.info(f"Found Tier 4 coverage: {coverage_info['type']} - {coverage_info['value']}")

                return {
                    "tier_4_found": True,
                    "coverage_rule": f"{coverage_info['value']} {coverage_info['type']}" if coverage_info['value'] else "See brochure",
                    "coverage_type": coverage_info['type'],
                    "coverage_value": coverage_info['value'],
                    "raw_text": context
                }

        # Not found
        logger.warning("Tier 4 coverage not found in PDF")
        return {
            "tier_4_found": False,
            "coverage_rule": "Not specified",
            "coverage_type": "unknown",
            "coverage_value": None,
            "raw_text": ""
        }

    def process_plan_brochure(self, url: str, plan_code: str, plan_name: str) -> Dict[str, any]:
        """
        Complete workflow: download PDF, extract text, find Tier 4 coverage.

        Args:
            url: URL of plan brochure
            plan_code: Plan code
            plan_name: Plan name

        Returns:
            Dict with all extracted Tier 4 information
        """
        # Download PDF
        pdf_path = self.download_pdf(url, plan_code, plan_name)

        if not pdf_path:
            return {
                "tier_4_found": False,
                "coverage_rule": "PDF download failed",
                "coverage_type": "unknown",
                "coverage_value": None,
                "raw_text": "",
                "brochure_local_path": None
            }

        # Extract text
        text = self.extract_text(pdf_path)

        if not text:
            return {
                "tier_4_found": False,
                "coverage_rule": "PDF text extraction failed",
                "coverage_type": "unknown",
                "coverage_value": None,
                "raw_text": "",
                "brochure_local_path": pdf_path
            }

        # Find Tier 4 coverage
        tier4_info = self.find_tier4_coverage(text)
        tier4_info["brochure_local_path"] = pdf_path

        return tier4_info


if __name__ == "__main__":
    # Test the PDF parser
    parser = PDFBrochureParser()

    # Test with a sample URL (this will need a real brochure URL)
    test_url = "https://www.opm.gov/healthcare-insurance/healthcare/plan-information/plan-codes/2024/brochures/71-005.pdf"
    result = parser.process_plan_brochure(test_url, "71-005", "Test Plan")

    print("\nTier 4 Coverage Info:")
    print(f"Found: {result['tier_4_found']}")
    print(f"Coverage Rule: {result['coverage_rule']}")
    print(f"Type: {result['coverage_type']}")
    print(f"Value: {result['coverage_value']}")
