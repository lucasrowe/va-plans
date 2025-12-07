"""
Calculate costs for all plans with therapy visit limits.

This script fetches plan data and calculates total annual costs for all plans.
"""

from src.scraper.json_extractor import OPMJsonExtractor
from src.calculator.cost_engine import CostCalculator
from src.utils.config_loader import load_user_needs
import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("\n" + "=" * 80)
    print("FEHB PLAN COST CALCULATOR - ALL PLANS")
    print("=" * 80)

    # Load user needs
    user_needs = load_user_needs('data/user_needs.json')

    # Extract plan data
    url = 'https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c'
    extractor = OPMJsonExtractor(url)
    df = extractor.scrape_all_plans(include_oon=True, include_therapy_limits=True)

    print(f"\nTotal plans extracted: {len(df)}")
    print(f"Plans with therapy limits: {df['therapy_limit_found'].sum()}")
    print(f"Plans with OON coverage: {df['oon_found'].sum()}")

    # Calculate costs for all plans
    results = []

    for idx, row in df.iterrows():
        plan_dict = row.to_dict()

        try:
            calculator = CostCalculator(user_needs, plan_dict)
            cost_result = calculator.calculate_total_cost()

            # Combine plan data with cost result
            result = {
                'rank': 0,  # Will be set after sorting
                'carrier_name': row['carrier_name'],
                'plan_name': row['plan_name'],
                'plan_code': row['plan_code'],
                'total_annual_cost': cost_result['total_annual_cost'],
                'premium_cost_annual': cost_result['premium_cost'],
                'medical_drug_spend': cost_result['medical_drug_spend'],
                'deductible_paid': cost_result['deductible_paid'],
                'covered_cost_before_cap': cost_result.get('covered_cost_before_cap', 0),
                'covered_cost_after_cap': cost_result.get('covered_cost_after_cap', 0),
                'non_covered_costs': cost_result.get('non_covered_costs', 0),
                'therapy_visit_limit': row.get('therapy_visit_limit', 'No limit'),
                'therapy_limit_found': row.get('therapy_limit_found', False),
                'oon_coinsurance_rate': row.get('oon_coinsurance_rate', 'N/A'),
                'oon_found': row.get('oon_found', False),
                'annual_deductible': row.get('annual_deductible', 0),
                'oop_max': row.get('oop_max', 0),
            }

            # Add usage breakdown
            for service, cost in cost_result['usage_breakdown'].items():
                result[f'cost_{service}'] = cost

            results.append(result)

        except Exception as e:
            logger.error(f"Error calculating costs for {row['plan_name']}: {e}")
            continue

    # Create DataFrame and sort by total cost
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('total_annual_cost')
    results_df['rank'] = range(1, len(results_df) + 1)

    # Reorder columns
    cols = ['rank'] + [col for col in results_df.columns if col != 'rank']
    results_df = results_df[cols]

    print("\n" + "=" * 80)
    print("TOP 10 PLANS BY TOTAL ANNUAL COST")
    print("=" * 80)

    for _, row in results_df.head(10).iterrows():
        print(f"\n#{int(row['rank'])}: {row['plan_name']} ({row['plan_code']})")
        print(f"  Total Annual Cost: ${row['total_annual_cost']:,.2f}")
        print(f"    - Premium:       ${row['premium_cost_annual']:,.2f}")
        print(f"    - Medical/Drug:  ${row['medical_drug_spend']:,.2f}")
        print(f"  Deductible Paid:   ${row['deductible_paid']:,.2f}")

        # Show therapy limit info
        if row['therapy_limit_found']:
            limit = row['therapy_visit_limit']
            if pd.notna(limit):
                print(f"  Therapy Limit:     {int(limit)} visits/year")
            else:
                print(f"  Therapy Limit:     No limit found")
        else:
            print(f"  Therapy Limit:     No limit data")

        # Show non-covered costs
        if row['non_covered_costs'] > 0:
            print(f"  Non-covered Costs: ${row['non_covered_costs']:,.2f} (beyond limit)")

        # Show OON info
        if row['oon_found']:
            print(f"  OON Coinsurance:   {row['oon_coinsurance_rate']*100:.0f}%")

    # Save results
    output_path = 'output/ranked_plans_with_limits.csv'
    results_df.to_csv(output_path, index=False)
    print("\n" + "=" * 80)
    print(f"Full results saved to: {output_path}")
    print("=" * 80)

    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total plans analyzed: {len(results_df)}")
    print(f"Plans with therapy limits: {results_df['therapy_limit_found'].sum()}")
    print(f"Plans with non-covered costs: {(results_df['non_covered_costs'] > 0).sum()}")
    print(f"\nCost range:")
    print(f"  Lowest:  ${results_df['total_annual_cost'].min():,.2f}")
    print(f"  Highest: ${results_df['total_annual_cost'].max():,.2f}")
    print(f"  Average: ${results_df['total_annual_cost'].mean():,.2f}")

if __name__ == "__main__":
    main()
