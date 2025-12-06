"""
Data Augmentation Pipeline

This module orchestrates the full scraping pipeline: HTML scraping + PDF augmentation.
"""

import pandas as pd
import logging
from typing import Dict
from src.scraper.html_scraper import OPMScraper
from src.scraper.pdf_parser import PDFBrochureParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def augment_plans_with_tier4(plans_df: pd.DataFrame, pdf_parser: PDFBrochureParser) -> pd.DataFrame:
    """
    Augment plans DataFrame with Tier 4 coverage data from PDF brochures.

    Args:
        plans_df: DataFrame from HTML scraper
        pdf_parser: PDFBrochureParser instance

    Returns:
        Enhanced DataFrame with Tier 4 data
    """
    logger.info(f"Starting PDF augmentation for {len(plans_df)} plans")

    # Initialize new columns
    plans_df['tier_4_coverage_rule'] = None
    plans_df['tier_4_coverage_type'] = None
    plans_df['tier_4_coverage_value'] = None
    plans_df['brochure_local_path'] = None
    plans_df['tier_4_raw_text'] = None

    successful_extractions = 0
    failed_extractions = 0

    for idx, row in plans_df.iterrows():
        plan_name = row.get('plan_name', 'Unknown')
        plan_code = row.get('plan_code', 'Unknown')
        brochure_url = row.get('brochure_url')

        if not brochure_url or pd.isna(brochure_url):
            logger.warning(f"No brochure URL for plan {plan_name} ({plan_code})")
            plans_df.at[idx, 'tier_4_coverage_rule'] = "No brochure URL"
            plans_df.at[idx, 'tier_4_coverage_type'] = "unknown"
            failed_extractions += 1
            continue

        try:
            # Process the brochure
            tier4_info = pdf_parser.process_plan_brochure(brochure_url, plan_code, plan_name)

            # Add to DataFrame
            plans_df.at[idx, 'tier_4_coverage_rule'] = tier4_info['coverage_rule']
            plans_df.at[idx, 'tier_4_coverage_type'] = tier4_info['coverage_type']
            plans_df.at[idx, 'tier_4_coverage_value'] = tier4_info['coverage_value']
            plans_df.at[idx, 'brochure_local_path'] = tier4_info['brochure_local_path']
            plans_df.at[idx, 'tier_4_raw_text'] = tier4_info.get('raw_text', '')

            if tier4_info['tier_4_found']:
                successful_extractions += 1
            else:
                failed_extractions += 1

        except Exception as e:
            logger.error(f"Error processing brochure for {plan_name}: {e}")
            plans_df.at[idx, 'tier_4_coverage_rule'] = "Processing error"
            plans_df.at[idx, 'tier_4_coverage_type'] = "unknown"
            failed_extractions += 1

    # Log summary
    logger.info(f"PDF augmentation complete:")
    logger.info(f"  - Successfully extracted Tier 4 data: {successful_extractions}")
    logger.info(f"  - Failed or not found: {failed_extractions}")
    logger.info(f"  - Success rate: {successful_extractions / len(plans_df) * 100:.1f}%")

    return plans_df


def run_full_scrape_pipeline(config: Dict) -> pd.DataFrame:
    """
    Run the complete scraping pipeline: HTML + PDF augmentation.

    Args:
        config: Configuration dict loaded from config.json

    Returns:
        Complete DataFrame with all plan data including Tier 4 information
    """
    logger.info("=" * 60)
    logger.info("Starting Full Scraping Pipeline")
    logger.info("=" * 60)

    # Step 1: HTML Scraping
    logger.info("\n[Step 1/2] Scraping HTML comparison table...")
    scraper = OPMScraper(
        url=config['target_url'],
        timeout=config.get('pdf_download_timeout', 30),
        max_retries=config.get('max_retries', 3)
    )

    plans_df = scraper.scrape_all_plans()
    logger.info(f"HTML scraping complete. Extracted {len(plans_df)} plans")

    if len(plans_df) == 0:
        logger.error("No plans extracted from HTML. Aborting pipeline.")
        return pd.DataFrame()

    # Step 2: PDF Augmentation
    logger.info("\n[Step 2/2] Augmenting with PDF brochure data...")
    pdf_parser = PDFBrochureParser(
        output_dir=config.get('pdf_directory', 'output/pdfs'),
        timeout=config.get('pdf_download_timeout', 30),
        max_retries=config.get('max_retries', 3)
    )

    enhanced_df = augment_plans_with_tier4(plans_df, pdf_parser)

    # Log final statistics
    logger.info("\n" + "=" * 60)
    logger.info("Pipeline Complete - Summary Statistics")
    logger.info("=" * 60)
    logger.info(f"Total plans processed: {len(enhanced_df)}")
    logger.info(f"Plans with brochure URLs: {enhanced_df['brochure_url'].notna().sum()}")
    logger.info(f"Plans with Tier 4 data: {(enhanced_df['tier_4_coverage_type'] != 'unknown').sum()}")
    logger.info(f"Copay-based Tier 4: {(enhanced_df['tier_4_coverage_type'] == 'copay').sum()}")
    logger.info(f"Coinsurance-based Tier 4: {(enhanced_df['tier_4_coverage_type'] == 'coinsurance').sum()}")

    return enhanced_df


if __name__ == "__main__":
    # Test the pipeline
    from src.utils.config_loader import load_app_config

    config = load_app_config()
    result_df = run_full_scrape_pipeline(config)

    print(f"\nPipeline complete. {len(result_df)} plans processed.")
    print("\nSample data:")
    print(result_df[['plan_name', 'plan_code', 'tier_4_coverage_rule']].head())
