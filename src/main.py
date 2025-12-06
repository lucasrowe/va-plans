"""
Main Entry Point for FEHB Plan Cost Analyzer

This module orchestrates the complete pipeline: scraping, PDF parsing, cost calculation, and output generation.
"""

import os
import logging
import argparse
from pathlib import Path

from src.utils.config_loader import load_user_needs, load_app_config
from src.scraper.augmentation_pipeline import run_full_scrape_pipeline
from src.calculator.cost_engine import calculate_all_plans

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main pipeline function to run the complete FEHB plan analysis."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='FEHB Plan Cost Analyzer')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--user-needs',
        type=str,
        default='data/user_needs.json',
        help='Path to user needs configuration file'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='data/config.json',
        help='Path to application configuration file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Path to output CSV file (default: output/ranked_plans.csv)'
    )

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    logger.info("=" * 80)
    logger.info("FEHB PLAN COST ANALYZER")
    logger.info("=" * 80)

    try:
        # Step 1: Load configurations
        logger.info("\n[Step 1/4] Loading configurations...")
        user_needs = load_user_needs(args.user_needs)
        app_config = load_app_config(args.config)

        logger.info("Configurations loaded successfully")
        logger.info(f"  - Target ZIP: {app_config.get('zip_code')}")
        logger.info(f"  - Family Type: {app_config.get('family_type')}")
        logger.info(f"  - Network: {app_config.get('network_type')}")

        # Log usage profile summary
        usage_profile = user_needs['usage_profile']
        logger.info("\nUsage Profile:")
        for service, quantity in usage_profile.items():
            if quantity > 0:
                logger.info(f"  - {service}: {quantity}")

        # Step 2: Run scraping pipeline (HTML + PDF)
        logger.info("\n[Step 2/4] Running scraping pipeline...")
        logger.info("This may take several minutes as PDFs are downloaded and parsed...")

        plans_df = run_full_scrape_pipeline(app_config)

        if len(plans_df) == 0:
            logger.error("No plans were scraped. Exiting.")
            return 1

        logger.info(f"Scraping complete. {len(plans_df)} plans extracted.")

        # Step 3: Calculate costs for all plans
        logger.info("\n[Step 3/4] Calculating costs for all plans...")

        results_df = calculate_all_plans(plans_df, user_needs)

        if len(results_df) == 0:
            logger.error("No plans were successfully calculated. Exiting.")
            return 1

        logger.info(f"Cost calculation complete. {len(results_df)} plans ranked.")

        # Step 4: Save results
        logger.info("\n[Step 4/4] Saving results...")

        # Determine output path
        if args.output:
            output_path = args.output
        else:
            output_dir = app_config.get('output_directory', 'output')
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_path = os.path.join(output_dir, 'ranked_plans.csv')

        # Save to CSV
        results_df.to_csv(output_path, index=False)
        logger.info(f"Results saved to: {output_path}")

        # Display top 10 plans
        logger.info("\n" + "=" * 80)
        logger.info("TOP 10 PLANS BY TOTAL ANNUAL COST")
        logger.info("=" * 80)

        top_10 = results_df.head(10)

        for _, row in top_10.iterrows():
            logger.info(
                f"\n#{row['rank']}: {row['plan_name']} ({row['plan_code']})"
            )
            logger.info(f"  Total Annual Cost: ${row['total_annual_cost']:,.2f}")
            logger.info(f"    - Premium:       ${row['premium_cost_annual']:,.2f}")
            logger.info(f"    - Medical/Drug:  ${row['medical_drug_spend']:,.2f}")
            logger.info(f"  Deductible Paid:   ${row['deductible_paid']:,.2f}")

            # Show therapy costs if they exist
            if 'cost_speech_therapy_visits' in row:
                logger.info(f"  Speech Therapy:    ${row['cost_speech_therapy_visits']:,.2f}")
            if 'cost_occupational_therapy_visits' in row:
                logger.info(f"  Occupational Therapy: ${row['cost_occupational_therapy_visits']:,.2f}")

        logger.info("\n" + "=" * 80)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Full results available at: {output_path}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.error("Please ensure data/user_needs.json and data/config.json exist.")
        return 1

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
