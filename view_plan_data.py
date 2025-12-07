"""
View extracted plan data in a readable format.

This script fetches plan data and displays it in various formats for inspection.
"""

from src.scraper.json_extractor import OPMJsonExtractor
import pandas as pd

# Set pandas display options for better readability
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)

def main():
    print("\n" + "=" * 80)
    print("FEHB PLAN DATA VIEWER")
    print("=" * 80)

    # Extract plan data
    url = 'https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c'
    extractor = OPMJsonExtractor(url)
    df = extractor.scrape_all_plans()

    print(f"\nTotal plans extracted: {len(df)}")
    print("\n" + "=" * 80)
    print("BASIC PLAN INFO")
    print("=" * 80)

    # Show basic plan info
    basic_cols = ['carrier_name', 'plan_name', 'plan_code', 'biweekly_premium',
                  'annual_deductible', 'oop_max']
    print(df[basic_cols].to_string(index=True))

    print("\n" + "=" * 80)
    print("THERAPY BENEFITS (First 10 plans)")
    print("=" * 80)

    # Show therapy benefits
    for idx in range(min(10, len(df))):
        row = df.iloc[idx]
        print(f"\n[{idx}] {row['carrier_name']} - {row['plan_name']}")
        print(f"    Speech Therapy: {row['speech_therapy_visits']}")
        print(f"    Occupational Therapy: {row['occupational_therapy_visits']}")

    print("\n" + "=" * 80)
    print("SAVE TO CSV")
    print("=" * 80)

    # Save to CSV for easy viewing
    csv_path = 'output/plan_data_review.csv'
    df.to_csv(csv_path, index=False)
    print(f"Full data saved to: {csv_path}")
    print("\nYou can open this file in Excel or any spreadsheet program.")

    print("\n" + "=" * 80)
    print("COLUMN LIST")
    print("=" * 80)
    print("\nAll columns in the dataset:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col}")

if __name__ == "__main__":
    main()
