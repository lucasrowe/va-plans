"""
Merge out-of-network speech therapy data into the main plan extraction.

This script loads the OON speech therapy data and merges it with the
plan data from the JSON extractor, creating a complete dataset with
both in-network and out-of-network costs.
"""

import pandas as pd
import ast
from src.scraper.json_extractor import OPMJsonExtractor

def main():
    print("Fetching plan data from OPM...")
    url = 'https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c'
    extractor = OPMJsonExtractor(url)
    plans_df = extractor.scrape_all_plans()

    print(f"Loaded {len(plans_df)} plans from JSON")

    # Load OON data
    print("Loading out-of-network speech therapy data...")
    oon_df = pd.read_csv('output/oon_speech_therapy.csv')

    # The oon_speech_therapy column is a string representation of a dict, convert it
    def parse_oon_benefit(row):
        if pd.isna(row['oon_speech_therapy']) or row['oon_speech_therapy'] == '':
            return None
        try:
            return ast.literal_eval(row['oon_speech_therapy'])
        except:
            return None

    oon_df['oon_speech_therapy_parsed'] = oon_df.apply(parse_oon_benefit, axis=1)

    # Create merge key (plan_code + plan_name to ensure unique matching)
    plans_df['merge_key'] = plans_df['plan_code'] + '|' + plans_df['plan_name']
    oon_df['merge_key'] = oon_df['plan_code'] + '|' + oon_df['plan_name']

    # Merge the data frames
    merged_df = plans_df.merge(
        oon_df[['merge_key', 'oon_speech_therapy_parsed', 'oon_coinsurance_rate', 'oon_notes', 'oon_found']],
        on='merge_key',
        how='left'
    )

    # Drop the merge key
    merged_df = merged_df.drop('merge_key', axis=1)

    # For plans without OON data, assume no coverage (100% member pays)
    # This is conservative - most HMO plans don't cover out-of-network
    merged_df['oon_found'] = merged_df['oon_found'].fillna(False)
    merged_df['oon_notes'] = merged_df['oon_notes'].fillna('No out-of-network coverage detected')

    # Rename the column for clarity
    merged_df = merged_df.rename(columns={'oon_speech_therapy_parsed': 'oon_speech_therapy_visits'})

    # Save combined data
    output_path = 'output/complete_plan_data.csv'
    merged_df.to_csv(output_path, index=False)
    print(f"\nComplete plan data saved to: {output_path}")

    # Summary
    print("\n" + "=" * 80)
    print("MERGED DATA SUMMARY")
    print("=" * 80)
    print(f"Total plans: {len(merged_df)}")
    print(f"Plans with OON speech therapy data: {merged_df['oon_found'].sum()}")
    print(f"Plans without OON data (assumed no coverage): {(~merged_df['oon_found']).sum()}")

    # Show sample
    print("\n" + "=" * 80)
    print("SAMPLE DATA (First 5 plans)")
    print("=" * 80)
    sample_cols = ['carrier_name', 'plan_name', 'biweekly_premium', 'annual_deductible',
                   'oop_max', 'oon_found', 'oon_notes']
    print(merged_df[sample_cols].head(5).to_string(index=False))

    return merged_df


if __name__ == "__main__":
    df = main()
