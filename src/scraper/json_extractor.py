"""
JSON Data Extractor for OPM Embedded Data

The OPM website embeds plan data as JavaScript in the HTML.
This module extracts and parses that embedded JSON data.
"""

import requests
import json
import re
import logging
from typing import Dict, List, Optional
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OPMJsonExtractor:
    """Extracts plan data from OPM's embedded JavaScript JSON"""

    def __init__(self, url: str, timeout: int = 30):
        """
        Initialize the JSON extractor.

        Args:
            url: Target URL for OPM comparison page
            timeout: Request timeout in seconds
        """
        self.url = url
        self.timeout = timeout

    def fetch_page_html(self) -> str:
        """
        Fetch the raw HTML from the OPM page.

        Returns:
            HTML content as string
        """
        logger.info(f"Fetching page from {self.url}")
        response = requests.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def extract_carriers_json(self, html: str) -> Dict:
        """
        Extract the Carriers JSON object from embedded JavaScript.

        The OPM page embeds data like:
        Carriers = new CarriersVM({ Carriers: [{...}] });

        Args:
            html: HTML content

        Returns:
            Parsed JSON data as dict
        """
        logger.info("Extracting embedded JSON data")

        # Find the line with Carriers initialization
        # It starts with "Carriers = new CarriersVM" and contains the JSON
        pattern = r'Carriers\s*=\s*new\s*CarriersVM\s*\(\s*\{(.*?)\}\s*\);'

        match = re.search(pattern, html, re.DOTALL)

        if not match:
            logger.error("Could not find Carriers JSON in HTML")
            return {"Carriers": []}

        # Extract the JSON portion
        json_content = "{" + match.group(1) + "}"

        try:
            # The data is JavaScript object notation, not JSON
            # Keys are not quoted, so we need to convert it
            # Only quote keys that come after { or , or at start
            # This avoids quoting colons in URLs like "https:"
            json_content = re.sub(r'([{,]\s*)(\w+):', r'\1"\2":', json_content)
            # Also handle keys at the very start
            json_content = re.sub(r'^(\s*)(\w+):', r'\1"\2":', json_content)

            # Try to parse as JSON
            data = json.loads(json_content)
            logger.info(f"Successfully parsed JSON with {len(data.get('Carriers', []))} carriers")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            # Save for debugging
            with open('debug_json.txt', 'w') as f:
                f.write(json_content[:10000])
            logger.info("Saved JSON snippet to debug_json.txt")
            return {"Carriers": []}

    def parse_benefit_value(self, benefit_text: str) -> Dict:
        """
        Parse a benefit value string to extract type and value.

        Args:
            benefit_text: E.g., "$30 Copayment", "15% Coinsurance", "Member Pays Nothing"

        Returns:
            Dict with type and value
        """
        if not benefit_text or benefit_text.strip() == "":
            return {"type": "unknown", "value": None, "raw": benefit_text}

        text = benefit_text.strip()

        # Handle "Member Pays Nothing" / "No charge"
        if "nothing" in text.lower() or "no charge" in text.lower():
            return {"type": "copay", "value": 0, "raw": benefit_text}

        # Handle "Not Covered" / "Member Pays All"
        if "not covered" in text.lower() or "member pays all" in text.lower():
            return {"type": "not_covered", "value": None, "raw": benefit_text}

        # Extract copay: $XX
        copay_match = re.search(r'\$(\d+(?:\.\d{2})?)', text)
        if copay_match and '%' not in text:
            return {"type": "copay", "value": float(copay_match.group(1)), "raw": benefit_text}

        # Extract coinsurance: XX%
        coinsurance_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if coinsurance_match:
            percentage = float(coinsurance_match.group(1))
            return {"type": "coinsurance", "value": percentage / 100.0, "raw": benefit_text}

        # Unknown/complex
        logger.warning(f"Could not parse benefit: '{benefit_text}'")
        return {"type": "complex", "value": None, "raw": benefit_text}

    def extract_plans_data(self, carriers_data: Dict) -> pd.DataFrame:
        """
        Convert carriers JSON to DataFrame of plans.

        Args:
            carriers_data: Parsed JSON from extract_carriers_json()

        Returns:
            DataFrame with plan data
        """
        plans = []

        for carrier in carriers_data.get('Carriers', []):
            carrier_name = carrier.get('Name', 'Unknown')
            brochure_number = carrier.get('BrochureNumber', '')

            for plan in carrier.get('Plans', []):
                plan_name = plan.get('Name', 'Unknown')

                # Get enrollment data for "Self & Family"
                enrollment_types = plan.get('EnrollmentTypes', {})
                family_enrollment = enrollment_types.get('Self & Family', {})

                if not family_enrollment:
                    logger.warning(f"No Self & Family data for {carrier_name} - {plan_name}")
                    continue

                # Extract premium
                rate = family_enrollment.get('Rate', {})
                biweekly_premium = rate.get('Employee', 0)

                # Extract plan costs
                plan_costs = family_enrollment.get('PlanCosts', {})
                deductible = plan_costs.get('Calendar Year Deductible', {}).get('NumericValue', 0)
                oop_max = plan_costs.get('Catastrophic Limit', {}).get('NumericValue', 0)

                # Extract benefits from tiers
                tiers = plan.get('Tiers', {})
                in_network = tiers.get('In-network', {})
                benefits = in_network.get('Benefits', {})

                # Create plan record
                plan_record = {
                    'carrier_name': carrier_name,
                    'plan_name': plan_name,
                    'plan_code': brochure_number,
                    'biweekly_premium': biweekly_premium,
                    'annual_deductible': deductible,
                    'oop_max': oop_max,
                }

                # Add key benefit rules
                benefit_mapping = {
                    'Primary Care Office Visit': 'primary_care_visits',
                    'Specialist Office Visit': 'specialist_visits',
                    'Emergency Care': 'er_visits',
                    'Speech Therapy': 'speech_therapy_visits',
                    'Occupational Therapy': 'occupational_therapy_visits',
                    'Tier 1 Prescriptions': 'tier_1_generics_monthly',
                    'Tier 4 Prescriptions': 'tier_4_specialty_monthly',
                    'Hospital Inpatient Cost Per Admission': 'inpatient_surgeries',
                }

                for benefit_name, field_name in benefit_mapping.items():
                    benefit_data = benefits.get(benefit_name, {})
                    benefit_value = benefit_data.get('Value', '')
                    parsed_benefit = self.parse_benefit_value(benefit_value)
                    plan_record[field_name] = parsed_benefit

                plans.append(plan_record)

        logger.info(f"Extracted {len(plans)} plans")
        return pd.DataFrame(plans)

    def scrape_all_plans(self) -> pd.DataFrame:
        """
        Main method to scrape all plans.

        Returns:
            DataFrame with all plan data
        """
        # Fetch HTML
        html = self.fetch_page_html()

        # Extract JSON
        carriers_data = self.extract_carriers_json(html)

        # Convert to DataFrame
        plans_df = self.extract_plans_data(carriers_data)

        return plans_df


if __name__ == "__main__":
    # Test the extractor
    url = "https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c"

    extractor = OPMJsonExtractor(url)
    df = extractor.scrape_all_plans()

    print(f"\nExtracted {len(df)} plans")
    print("\nFirst 3 plans:")
    print(df[['carrier_name', 'plan_name', 'biweekly_premium', 'annual_deductible']].head(3))

    # Check therapy benefits
    print("\nTherapy benefits in first plan:")
    first_plan = df.iloc[0]
    print(f"Speech Therapy: {first_plan['speech_therapy_visits']}")
    print(f"Occupational Therapy: {first_plan['occupational_therapy_visits']}")
