"""
Extract out-of-network speech therapy costs from plan brochure PDFs.

This script parses the therapy benefits section of each plan brochure to find
out-of-network costs for speech therapy visits.
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


def extract_oon_speech_therapy_from_pdf(pdf_path: str, plan_name: str) -> dict:
    """
    Extract out-of-network speech therapy costs from a PDF brochure.

    Args:
        pdf_path: Path to the PDF file
        plan_name: Name of the plan for logging

    Returns:
        Dict with out-of-network speech therapy information
    """
    result = {
        'oon_speech_therapy': None,
        'oon_coinsurance_rate': None,
        'oon_notes': None,
        'oon_found': False
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Search through pages looking for therapy benefits
            for page_num, page in enumerate(pdf.pages[:80], 1):
                text = page.extract_text()
                if not text:
                    continue

                # Look for speech therapy section
                if 'speech therapy' not in text.lower():
                    continue

                lines = text.split('\n')

                # Find the therapy benefit section
                for i, line in enumerate(lines):
                    line_lower = line.lower()

                    if 'speech therapy' in line_lower or 'physical therapy' in line_lower:
                        # Get surrounding context (therapy benefits are usually in a table format)
                        start = max(0, i - 5)
                        end = min(len(lines), i + 20)
                        context = '\n'.join(lines[start:end])
                        context_lower = context.lower()

                        # Look for out-of-network patterns
                        # Common patterns:
                        # - "Non-participating: 35% of the Plan allowance"
                        # - "Out-of-network: 40% coinsurance"
                        # - "Out-of-network: 50% of the Plan allowance"
                        # - "You pay all charges"
                        # - "Not covered"

                        # Pattern 1: "You pay all charges" (no coverage)
                        if re.search(r'(?:non-participating|out-of-network|oon).*?you pay all charges', context_lower):
                            result['oon_speech_therapy'] = {'type': 'not_covered', 'value': None, 'raw': 'You pay all charges'}
                            result['oon_notes'] = 'No out-of-network coverage - member pays full cost'
                            result['oon_found'] = True
                            logger.info(f"{plan_name}: Out-of-network not covered (page {page_num})")
                            return result

                        # Pattern 2: Coinsurance percentage - broader pattern
                        # Matches: "Out-of-network: 50% of" or "non-participating: 35% coinsurance"
                        coinsurance_pattern = r'(?:non-participating|out-of-network|oon).*?(\d+)%\s+(?:of|coinsurance)'
                        match = re.search(coinsurance_pattern, context_lower)
                        if match:
                            percentage = int(match.group(1))
                            result['oon_speech_therapy'] = {
                                'type': 'coinsurance',
                                'value': percentage / 100.0,
                                'raw': f'{percentage}% coinsurance'
                            }
                            result['oon_coinsurance_rate'] = percentage / 100.0
                            result['oon_notes'] = f'{percentage}% of plan allowance + balance billing'
                            result['oon_found'] = True
                            logger.info(f"{plan_name}: Found {percentage}% coinsurance for OON (page {page_num})")
                            return result

                        # Pattern 3: Fixed copayment (less common for OON but possible)
                        copay_pattern = r'(?:non-participating|out-of-network)[:\s]+\$(\d+)\s*copayment'
                        match = re.search(copay_pattern, context_lower)
                        if match:
                            copay = int(match.group(1))
                            result['oon_speech_therapy'] = {
                                'type': 'copay',
                                'value': copay,
                                'raw': f'${copay} copayment'
                            }
                            result['oon_notes'] = f'${copay} copayment out-of-network'
                            result['oon_found'] = True
                            logger.info(f"{plan_name}: Found ${copay} copay for OON (page {page_num})")
                            return result

        if not result['oon_found']:
            logger.warning(f"{plan_name}: No out-of-network speech therapy cost found in PDF")

    except Exception as e:
        logger.error(f"{plan_name}: Error parsing PDF - {e}")

    return result


def extract_all_oon_speech_therapy():
    """
    Extract out-of-network speech therapy costs from all downloaded brochures.
    """
    logger.info("Starting out-of-network speech therapy cost extraction from PDFs...")

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

        # Extract out-of-network costs
        oon_info = extract_oon_speech_therapy_from_pdf(
            str(pdf_file),
            f"{plans[0]['carrier_name']} ({brochure_number})"
        )

        # Add to results for each plan in this brochure
        for plan in plans:
            results.append({
                'plan_code': brochure_number,
                'carrier_name': plan['carrier_name'],
                'plan_name': plan['plan_name'],
                'oon_speech_therapy': oon_info['oon_speech_therapy'],
                'oon_coinsurance_rate': oon_info['oon_coinsurance_rate'],
                'oon_notes': oon_info['oon_notes'],
                'oon_found': oon_info['oon_found']
            })

    # Create DataFrame
    results_df = pd.DataFrame(results)

    # Save to CSV
    output_path = 'output/oon_speech_therapy.csv'
    results_df.to_csv(output_path, index=False)
    logger.info(f"\n\nResults saved to: {output_path}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("OUT-OF-NETWORK SPEECH THERAPY EXTRACTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total plans processed: {len(results_df)}")
    logger.info(f"Plans with OON info found: {results_df['oon_found'].sum()}")
    logger.info(f"Plans with no OON info found: {(~results_df['oon_found']).sum()}")

    # Show distribution of OON coverage
    if results_df['oon_found'].any():
        logger.info("\nOut-of-network coverage distribution:")

        # Count by coinsurance rate
        oon_with_rate = results_df[results_df['oon_coinsurance_rate'].notna()]
        if not oon_with_rate.empty:
            rate_counts = oon_with_rate['oon_coinsurance_rate'].value_counts()
            for rate, count in rate_counts.items():
                logger.info(f"  {int(rate * 100)}% coinsurance: {count} plans")

        # Count not covered
        not_covered = results_df[results_df['oon_notes'].str.contains('No out-of-network', na=False)]
        if not not_covered.empty:
            logger.info(f"  Not covered: {len(not_covered)} plans")

    return results_df


if __name__ == "__main__":
    df = extract_all_oon_speech_therapy()

    print("\n" + "=" * 80)
    print("SAMPLE RESULTS")
    print("=" * 80)
    print(df[['carrier_name', 'plan_name', 'oon_notes', 'oon_found']].head(10).to_string(index=False))
