"""
HTML Scraper Module for OPM FEHB Plan Comparison Table

This module scrapes plan data from the OPM healthcare plan comparison website,
extracting plan details, premiums, deductibles, and benefit information.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import logging
from typing import Dict, List, Optional, Tuple
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OPMScraper:
    """Scraper for OPM FEHB Plan Comparison Table"""

    def __init__(self, url: str, timeout: int = 30, max_retries: int = 3):
        """
        Initialize the OPM scraper.

        Args:
            url: Target URL for OPM comparison table
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch_page(self) -> BeautifulSoup:
        """
        Fetch the HTML page from OPM website with retry logic.

        Returns:
            BeautifulSoup object containing parsed HTML

        Raises:
            Exception: If page cannot be fetched after max retries
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching page from {self.url} (attempt {attempt + 1}/{self.max_retries})")
                response = requests.get(self.url, timeout=self.timeout)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'lxml')
                logger.info("Successfully fetched and parsed HTML")
                return soup

            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to fetch page after {self.max_retries} attempts: {e}")

    def parse_benefit_string(self, benefit_text: str) -> Dict[str, any]:
        """
        Parse benefit text to identify copay vs coinsurance.

        Args:
            benefit_text: Raw benefit text from table cell

        Returns:
            Dict with 'type' (copay/coinsurance/unknown) and 'value' (numeric)
        """
        if not benefit_text or benefit_text.strip() == "":
            return {"type": "unknown", "value": None, "raw": benefit_text}

        text = benefit_text.strip().lower()

        # Handle "No charge" or "$0"
        if "no charge" in text or text == "$0" or text == "0":
            return {"type": "copay", "value": 0, "raw": benefit_text}

        # Handle "Not covered"
        if "not covered" in text or "n/a" in text:
            return {"type": "not_covered", "value": None, "raw": benefit_text}

        # Try to match copay pattern: $XX or XX copay
        copay_match = re.search(r'\$(\d+(?:\.\d{2})?)', text)
        if copay_match and '%' not in text:
            return {"type": "copay", "value": float(copay_match.group(1)), "raw": benefit_text}

        # Try to match coinsurance pattern: XX%
        coinsurance_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if coinsurance_match:
            percentage = float(coinsurance_match.group(1))
            return {"type": "coinsurance", "value": percentage / 100.0, "raw": benefit_text}

        # Complex case - flag for manual review
        logger.warning(f"Complex benefit text flagged for manual review: '{benefit_text}'")
        return {"type": "complex", "value": None, "raw": benefit_text}

    def extract_brochure_link(self, row_soup) -> Optional[str]:
        """
        Extract brochure/summary PDF link from plan row.

        Args:
            row_soup: BeautifulSoup object for the plan row

        Returns:
            Full URL to PDF brochure or None if not found
        """
        # Common link text patterns
        link_patterns = [
            'brochure', 'summary', 'details', 'plan information',
            'view plan', 'pdf'
        ]

        # Find all links in the row
        links = row_soup.find_all('a', href=True)

        for link in links:
            link_text = link.get_text().lower()
            href = link['href']

            # Check if link text matches brochure patterns
            for pattern in link_patterns:
                if pattern in link_text or '.pdf' in href.lower():
                    # Handle relative vs absolute URLs
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        # Construct full URL
                        base_url = 'https://www.opm.gov'
                        return base_url + href
                    else:
                        logger.warning(f"Unexpected URL format: {href}")
                        return href

        return None

    def parse_plan_row(self, row) -> Optional[Dict]:
        """
        Parse a single plan row from the comparison table.

        Args:
            row: BeautifulSoup row element

        Returns:
            Dict containing plan data or None if parsing fails
        """
        try:
            cells = row.find_all(['td', 'th'])

            if len(cells) < 8:  # Minimum expected columns
                return None

            # Extract basic plan info
            # Note: Column indices may need adjustment based on actual table structure
            plan_data = {
                'plan_name': cells[0].get_text(strip=True) if len(cells) > 0 else '',
                'plan_code': cells[1].get_text(strip=True) if len(cells) > 1 else '',
            }

            # Skip if no plan name
            if not plan_data['plan_name']:
                return None

            # Extract premium (bi-weekly for Self & Family)
            premium_text = cells[2].get_text(strip=True) if len(cells) > 2 else '0'
            premium_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', premium_text)
            plan_data['biweekly_premium'] = float(premium_match.group(1).replace(',', '')) if premium_match else 0.0

            # Extract deductible
            deductible_text = cells[3].get_text(strip=True) if len(cells) > 3 else '0'
            deductible_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', deductible_text)
            plan_data['annual_deductible'] = float(deductible_match.group(1).replace(',', '')) if deductible_match else 0.0

            # Extract OOP Max
            oop_text = cells[4].get_text(strip=True) if len(cells) > 4 else '0'
            oop_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', oop_text)
            plan_data['oop_max'] = float(oop_match.group(1).replace(',', '')) if oop_match else 0.0

            # Extract benefits (indices will need adjustment based on actual table)
            # This is a placeholder - actual implementation needs to inspect the table structure
            if len(cells) > 5:
                plan_data['primary_care'] = self.parse_benefit_string(cells[5].get_text(strip=True))
            if len(cells) > 6:
                plan_data['specialist'] = self.parse_benefit_string(cells[6].get_text(strip=True))
            if len(cells) > 7:
                plan_data['er_visit'] = self.parse_benefit_string(cells[7].get_text(strip=True))
            if len(cells) > 8:
                plan_data['inpatient_hospital'] = self.parse_benefit_string(cells[8].get_text(strip=True))

            # Try to find therapy benefits
            # Look for therapy-related text in cells
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True).lower()
                if any(keyword in cell_text for keyword in ['therapy', 'rehabilitation', 'habilitation']):
                    # Next cell likely contains the benefit
                    if i + 1 < len(cells):
                        benefit_value = self.parse_benefit_string(cells[i + 1].get_text(strip=True))

                        # Determine if it's speech, OT, or combined
                        if 'speech' in cell_text:
                            plan_data['speech_therapy'] = benefit_value
                        elif 'occupational' in cell_text or 'ot' in cell_text:
                            plan_data['occupational_therapy'] = benefit_value
                        else:
                            # Combined therapy services
                            plan_data['therapy_services'] = benefit_value

            # Extract drug benefits
            if len(cells) > 9:
                plan_data['tier_1_generic'] = self.parse_benefit_string(cells[9].get_text(strip=True))
            if len(cells) > 10:
                plan_data['tier_2_brand'] = self.parse_benefit_string(cells[10].get_text(strip=True))

            # Extract brochure link
            plan_data['brochure_url'] = self.extract_brochure_link(row)

            if not plan_data['brochure_url']:
                logger.warning(f"No brochure link found for plan: {plan_data['plan_name']}")

            return plan_data

        except Exception as e:
            logger.error(f"Error parsing plan row: {e}")
            return None

    def extract_plans_table(self, soup: BeautifulSoup) -> pd.DataFrame:
        """
        Extract and parse the plans comparison table.

        Args:
            soup: BeautifulSoup object containing the page

        Returns:
            DataFrame with all extracted plan data
        """
        # Find the comparison table
        # This may need adjustment based on actual HTML structure
        table = soup.find('table')  # May need more specific selector

        if not table:
            logger.error("Could not find comparison table")
            return pd.DataFrame()

        rows = table.find_all('tr')
        logger.info(f"Found {len(rows)} rows in table")

        plans = []
        for row in rows[1:]:  # Skip header row
            plan_data = self.parse_plan_row(row)
            if plan_data:
                plans.append(plan_data)
                logger.info(f"Extracted plan: {plan_data['plan_name']}")

        logger.info(f"Successfully extracted {len(plans)} plans")
        return pd.DataFrame(plans)

    def scrape_all_plans(self) -> pd.DataFrame:
        """
        Main method to scrape all plans from OPM comparison table.

        Returns:
            DataFrame with all plan data
        """
        logger.info("Starting OPM plan scraping")

        # Fetch page
        soup = self.fetch_page()

        # Extract plans
        plans_df = self.extract_plans_table(soup)

        logger.info(f"Scraping complete. Total plans: {len(plans_df)}")
        return plans_df


if __name__ == "__main__":
    # Test the scraper
    from src.utils.config_loader import load_app_config

    config = load_app_config()
    scraper = OPMScraper(
        url=config['target_url'],
        timeout=config.get('pdf_download_timeout', 30),
        max_retries=config.get('max_retries', 3)
    )

    df = scraper.scrape_all_plans()
    print(f"\nScraped {len(df)} plans")
    print("\nFirst 3 plans:")
    print(df.head(3))
