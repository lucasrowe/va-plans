"""
Download all FEHB plan brochure PDFs for local reference.

This script extracts all plan brochure numbers from the OPM JSON data
and downloads the corresponding PDF files to the output/pdfs/ directory.
"""

import os
import logging
from pathlib import Path
from src.scraper.json_extractor import OPMJsonExtractor
from src.scraper.pdf_parser import PDFBrochureParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OPM brochure URL pattern for 2026
OPM_BROCHURE_BASE_URL = "https://www.opm.gov/healthcare-insurance/healthcare/plan-information/plans/pdf/2026/brochures/{brochure_number}.pdf"


def get_all_brochure_numbers():
    """
    Extract all unique brochure numbers from OPM data.

    Returns:
        List of tuples: (brochure_number, carrier_name, plan_name)
    """
    logger.info("Fetching plan data from OPM...")

    url = "https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c"
    extractor = OPMJsonExtractor(url)

    # Fetch HTML and extract JSON
    html = extractor.fetch_page_html()
    carriers_data = extractor.extract_carriers_json(html)

    brochures = []

    for carrier in carriers_data.get('Carriers', []):
        carrier_name = carrier.get('Name', 'Unknown')
        brochure_number = carrier.get('BrochureNumber', '')

        if not brochure_number:
            logger.warning(f"No brochure number for {carrier_name}, skipping")
            continue

        # Get first plan name for reference
        plans = carrier.get('Plans', [])
        plan_name = plans[0].get('Name', 'Unknown') if plans else 'Unknown'

        brochures.append((brochure_number, carrier_name, plan_name))

    logger.info(f"Found {len(brochures)} unique brochures to download")
    return brochures


def download_all_brochures():
    """
    Download all plan brochure PDFs to output/pdfs/ directory.
    """
    # Create output directory
    output_dir = Path("output/pdfs")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"PDFs will be saved to: {output_dir.absolute()}")

    # Get all brochure numbers
    brochures = get_all_brochure_numbers()

    if not brochures:
        logger.error("No brochures found to download!")
        return

    # Initialize PDF parser
    parser = PDFBrochureParser(output_dir=str(output_dir))

    # Download each brochure
    successful = 0
    failed = 0

    for idx, (brochure_number, carrier_name, plan_name) in enumerate(brochures, 1):
        logger.info(f"\n[{idx}/{len(brochures)}] Processing {carrier_name} - Brochure {brochure_number}")

        # Construct PDF URL
        pdf_url = OPM_BROCHURE_BASE_URL.format(brochure_number=brochure_number)

        try:
            # Download PDF (using carrier_name as plan_name for filename)
            pdf_path = parser.download_pdf(pdf_url, brochure_number, carrier_name)

            if pdf_path:
                logger.info(f"  ✓ Downloaded: {brochure_number}_{carrier_name}.pdf")
                successful += 1
            else:
                logger.warning(f"  ✗ Failed to download: {brochure_number}_{carrier_name}.pdf")
                failed += 1

        except Exception as e:
            logger.error(f"  ✗ Error downloading {brochure_number}_{carrier_name}.pdf: {e}")
            failed += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total brochures: {len(brochures)}")
    logger.info(f"Successful downloads: {successful}")
    logger.info(f"Failed downloads: {failed}")
    logger.info(f"PDFs saved to: {output_dir.absolute()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    download_all_brochures()
