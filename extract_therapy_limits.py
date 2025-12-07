"""
Extract therapy visit limits from plan brochure PDFs.

This script parses Section 5 of each plan brochure to find visit limits
for occupational therapy, physical therapy, and speech therapy.
"""

import os
import re
import logging
from pathlib import Path
import pdfplumber
import pandas as pd
from src.scraper.json_extractor import OPMJsonExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_therapy_limit_from_pdf(pdf_path: str, plan_name: str) -> dict:
    """
    Extract therapy visit limits from a PDF brochure.

    Args:
        pdf_path: Path to the PDF file
        plan_name: Name of the plan for logging

    Returns:
        Dict with therapy limit information
    """
    result = {
        'therapy_visit_limit': None,
        'therapy_limit_notes': None,
        'therapy_limit_found': False
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Search through pages looking for therapy limits
            for page_num, page in enumerate(pdf.pages[:80], 1):  # Check first 80 pages
                text = page.extract_text()
                if not text:
                    continue

                # Look for therapy visit limits
                lines = text.split('\n')

                # First pass: look for lines mentioning therapy limits
                for i, line in enumerate(lines):
                    line_lower = line.lower()

                    # Check if this line mentions therapy OR limit keywords
                    # (they may be on different lines that we'll combine)
                    has_therapy = any(t in line_lower for t in ['occupational therapy', 'physical therapy', 'speech therapy', 'occupational', 'physical'])
                    has_limit_keyword = any(word in line_lower for word in ['visit', 'limit', 'maximum', 'up to', 'combined', 'benefits are limited'])

                    if (has_therapy or has_limit_keyword):
                        # Combine current line with next few lines to catch multi-line patterns
                        combined_text = ' '.join(lines[i:min(len(lines), i+5)])
                        combined_lower = combined_text.lower()

                        # Verify combined text mentions therapy
                        has_therapy_in_combined = any(t in combined_lower for t in ['occupational', 'physical', 'speech'])

                        if has_therapy_in_combined:
                            # Check for rehabilitative/habilitative specific patterns
                            # Look for patterns like "Up to 60 per year for rehabilitative/habilitative"
                            rehab_pattern = r'up\s+to\s+(\d+)\s+per\s+year\s+for\s+(?:per\s+condition\s+)?(?:rehabilitative|habilitative)'
                            rehab_match = re.search(rehab_pattern, combined_lower)
                            if rehab_match:
                                limit = int(rehab_match.group(1))
                                if 10 <= limit <= 200:
                                    result['therapy_visit_limit'] = limit
                                    result['therapy_limit_found'] = True
                                    result['therapy_limit_notes'] = combined_text[:300]
                                    logger.info(f"{plan_name}: Found limit of {limit} visits (rehab/habilitative) on page {page_num}")
                                    return result

                            # Try to extract numeric limit from combined text
                            # Patterns: "limited to 75", "75 visits", "up to 75 visits", "maximum of 75"
                            patterns = [
                                r'benefits?\s+are\s+limited\s+to\s+(\d+)',
                                r'limited?\s+to\s+(\d+)\s+visits',
                                r'(\d+)\s+visits?\s+per\s+(?:person|calendar)',
                                r'up\s+to\s+(\d+)\s+(?:visits|outpatient)',
                                r'maximum\s+of\s+(\d+)\s+visits'
                            ]

                            for pattern in patterns:
                                number_match = re.search(pattern, combined_lower)
                                if number_match:
                                    limit = int(number_match.group(1))
                                    # Sanity check: therapy limits are typically 10-200 visits
                                    if 10 <= limit <= 200:
                                        result['therapy_visit_limit'] = limit
                                        result['therapy_limit_found'] = True
                                        result['therapy_limit_notes'] = combined_text[:300]

                                        logger.info(f"{plan_name}: Found limit of {limit} visits on page {page_num}")
                                        return result

        if not result['therapy_limit_found']:
            logger.warning(f"{plan_name}: No therapy visit limit found in PDF")

    except Exception as e:
        logger.error(f"{plan_name}: Error parsing PDF - {e}")

    return result


def extract_all_therapy_limits():
    """
    Extract therapy limits from all downloaded brochures.
    """
    logger.info("Starting therapy limit extraction from PDFs...")

    # Get plan data to map brochure numbers to plan names
    url = 'https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c'
    extractor = OPMJsonExtractor(url)
    df = extractor.scrape_all_plans()

    # Create mapping of plan_code to plan info
    plan_map = {}
    for _, row in df.iterrows():
        key = row['plan_code']
        if key not in plan_map:
            plan_map[key] = []
        plan_map[key].append({
            'carrier_name': row['carrier_name'],
            'plan_name': row['plan_name']
        })

    # Process each PDF
    pdf_dir = Path('output/pdfs')
    results = []

    for pdf_file in sorted(pdf_dir.glob('*.pdf')):
        # Extract brochure number from filename
        brochure_number = pdf_file.stem.split('_')[0]

        logger.info(f"\n[Processing] {pdf_file.name}")

        # Get plans for this brochure
        plans = plan_map.get(brochure_number, [])
        if not plans:
            logger.warning(f"No plans found for brochure {brochure_number}")
            continue

        # Extract therapy limit
        limit_info = extract_therapy_limit_from_pdf(
            str(pdf_file),
            f"{plans[0]['carrier_name']} ({brochure_number})"
        )

        # Add to results for each plan in this brochure
        for plan in plans:
            results.append({
                'plan_code': brochure_number,
                'carrier_name': plan['carrier_name'],
                'plan_name': plan['plan_name'],
                'therapy_visit_limit': limit_info['therapy_visit_limit'],
                'therapy_limit_notes': limit_info['therapy_limit_notes'],
                'therapy_limit_found': limit_info['therapy_limit_found']
            })

    # Create DataFrame
    results_df = pd.DataFrame(results)

    # Save to CSV
    output_path = 'output/therapy_limits.csv'
    results_df.to_csv(output_path, index=False)
    logger.info(f"\n\nResults saved to: {output_path}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("THERAPY LIMIT EXTRACTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total plans processed: {len(results_df)}")
    logger.info(f"Plans with limits found: {results_df['therapy_limit_found'].sum()}")
    logger.info(f"Plans with no limit found: {(~results_df['therapy_limit_found']).sum()}")

    # Show distribution of limits
    if results_df['therapy_limit_found'].any():
        logger.info("\nLimit distribution:")
        limit_counts = results_df[results_df['therapy_limit_found']]['therapy_visit_limit'].value_counts()
        for limit, count in limit_counts.items():
            limit_text = "Unlimited" if limit == 999 else f"{limit} visits"
            logger.info(f"  {limit_text}: {count} plans")

    return results_df


if __name__ == "__main__":
    df = extract_all_therapy_limits()

    print("\n" + "=" * 80)
    print("SAMPLE RESULTS")
    print("=" * 80)
    print(df[['carrier_name', 'plan_name', 'therapy_visit_limit', 'therapy_limit_found']].head(10).to_string(index=False))
