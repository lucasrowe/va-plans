"""Test script for cost calculation engine with sample plan data."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.calculator.cost_engine import CostCalculator, calculate_all_plans
from src.utils.config_loader import load_user_needs
import pandas as pd
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_plans():
    """Create sample plan data for testing different scenarios."""

    return [
        # Plan 1: Low premium, copay-based plan (typical HMO)
        {
            'plan_name': 'Sample HMO Plan A (Copay)',
            'plan_code': 'HMO-001',
            'biweekly_premium': 150.00,
            'annual_deductible': 0,  # No deductible for copay plans
            'oop_max': 6000,
            'benefit_rules': {
                'primary_care_visits': {'type': 'copay', 'value': 20},
                'specialist_visits': {'type': 'copay', 'value': 40},
                'er_visits': {'type': 'copay', 'value': 150},
                'speech_therapy': {'type': 'copay', 'value': 30},
                'occupational_therapy': {'type': 'copay', 'value': 30},
                'generic_drug': {'type': 'copay', 'value': 10},
                'specialty_drug': {'type': 'copay', 'value': 100}
            }
        },

        # Plan 2: High premium, low deductible coinsurance plan
        {
            'plan_name': 'Sample PPO Plan B (Low Deductible)',
            'plan_code': 'PPO-002',
            'biweekly_premium': 250.00,
            'annual_deductible': 500,
            'oop_max': 5000,
            'benefit_rules': {
                'primary_care_visits': {'type': 'coinsurance', 'value': 0.20},
                'specialist_visits': {'type': 'coinsurance', 'value': 0.30},
                'er_visits': {'type': 'coinsurance', 'value': 0.30},
                'therapy_services': {'type': 'coinsurance', 'value': 0.20},  # Combined therapy
                'generic_drug': {'type': 'copay', 'value': 5},
                'specialty_drug': {'type': 'coinsurance', 'value': 0.50}
            }
        },

        # Plan 3: Low premium, high deductible plan (HDHP)
        {
            'plan_name': 'Sample HDHP Plan C (High Deductible)',
            'plan_code': 'HDHP-003',
            'biweekly_premium': 100.00,
            'annual_deductible': 3000,
            'oop_max': 7000,
            'benefit_rules': {
                'primary_care_visits': {'type': 'coinsurance', 'value': 0.10},
                'specialist_visits': {'type': 'coinsurance', 'value': 0.10},
                'er_visits': {'type': 'coinsurance', 'value': 0.10},
                'speech_therapy': {'type': 'coinsurance', 'value': 0.10},
                'occupational_therapy': {'type': 'coinsurance', 'value': 0.10},
                'generic_drug': {'type': 'coinsurance', 'value': 0.10},
                'specialty_drug': {'type': 'coinsurance', 'value': 0.10}
            }
        },

        # Plan 4: Very high usage that hits OOP max
        {
            'plan_name': 'Sample Plan D (Will Hit OOP Max)',
            'plan_code': 'TEST-004',
            'biweekly_premium': 200.00,
            'annual_deductible': 1000,
            'oop_max': 4000,
            'benefit_rules': {
                'primary_care_visits': {'type': 'coinsurance', 'value': 0.30},
                'specialist_visits': {'type': 'coinsurance', 'value': 0.40},
                'er_visits': {'type': 'coinsurance', 'value': 0.50},
                'therapy_services': {'type': 'coinsurance', 'value': 0.30},
                'generic_drug': {'type': 'copay', 'value': 15},
                'specialty_drug': {'type': 'coinsurance', 'value': 0.50}
            }
        }
    ]


def test_individual_plan(plan_data, user_needs, test_name):
    """Test calculation for a single plan."""

    logger.info(f"\n{'='*80}")
    logger.info(f"TEST: {test_name}")
    logger.info(f"{'='*80}")

    # Create calculator
    calculator = CostCalculator(user_needs, plan_data)

    # Calculate costs
    result = calculator.calculate_total_cost()

    # Print detailed breakdown
    logger.info(f"\nPlan: {plan_data['plan_name']}")
    logger.info(f"Plan Code: {plan_data['plan_code']}")
    logger.info(f"\nPlan Characteristics:")
    logger.info(f"  Bi-weekly Premium: ${plan_data['biweekly_premium']:.2f}")
    logger.info(f"  Annual Deductible: ${plan_data['annual_deductible']:.2f}")
    logger.info(f"  OOP Maximum: ${plan_data['oop_max']:.2f}")

    logger.info(f"\nCost Breakdown:")
    logger.info(f"  Annual Premium: ${result['premium_cost']:.2f}")
    logger.info(f"  Medical/Drug Spend: ${result['medical_drug_spend']:.2f}")
    logger.info(f"  Deductible Paid: ${result['deductible_paid']:.2f}")
    logger.info(f"  Variable Cost (Raw): ${result['variable_cost_raw']:.2f}")

    logger.info(f"\nService-Level Costs:")
    for service, cost in sorted(result['usage_breakdown'].items()):
        logger.info(f"  {service}: ${cost:.2f}")

    logger.info(f"\nTOTAL ANNUAL COST: ${result['total_annual_cost']:.2f}")

    return result


def verify_copay_calculation():
    """Verify copay calculations are correct."""

    logger.info(f"\n{'#'*80}")
    logger.info("VERIFICATION TEST 1: Copay Calculation")
    logger.info(f"{'#'*80}")

    # Simple test case: copays don't use deductible
    user_needs = {
        'usage_profile': {
            'primary_care_visits': 5,
            'specialist_visits': 10
        },
        'standard_costs': {
            'primary_care_visit': 200,
            'specialist_visit': 400
        }
    }

    plan_data = {
        'plan_name': 'Copay Test Plan',
        'plan_code': 'TEST-COPAY',
        'biweekly_premium': 100,
        'annual_deductible': 1000,  # Should be ignored for copays
        'oop_max': 10000,
        'benefit_rules': {
            'primary_care_visits': {'type': 'copay', 'value': 20},
            'specialist_visits': {'type': 'copay', 'value': 40}
        }
    }

    calculator = CostCalculator(user_needs, plan_data)
    result = calculator.calculate_total_cost()

    # Expected: Primary care = 5 * $20 = $100, Specialist = 10 * $40 = $400
    expected_primary = 5 * 20
    expected_specialist = 10 * 40
    expected_variable = expected_primary + expected_specialist
    expected_premium = 100 * 26
    expected_total = expected_premium + expected_variable

    assert result['usage_breakdown']['primary_care_visits'] == expected_primary, \
        f"Primary care copay incorrect: {result['usage_breakdown']['primary_care_visits']} != {expected_primary}"

    assert result['usage_breakdown']['specialist_visits'] == expected_specialist, \
        f"Specialist copay incorrect: {result['usage_breakdown']['specialist_visits']} != {expected_specialist}"

    assert result['deductible_paid'] == 0, \
        f"Deductible should not be paid for copays: {result['deductible_paid']} != 0"

    assert result['total_annual_cost'] == expected_total, \
        f"Total cost incorrect: {result['total_annual_cost']} != {expected_total}"

    logger.info("PASSED: Copay calculation correct")
    logger.info(f"  Primary care: ${expected_primary:.2f}")
    logger.info(f"  Specialist: ${expected_specialist:.2f}")
    logger.info(f"  Deductible paid: $0.00 (correct - copays don't count)")
    logger.info(f"  Total: ${expected_total:.2f}")


def verify_coinsurance_with_deductible():
    """Verify coinsurance calculations with deductible."""

    logger.info(f"\n{'#'*80}")
    logger.info("VERIFICATION TEST 2: Coinsurance with Deductible")
    logger.info(f"{'#'*80}")

    # Test case: coinsurance uses deductible first
    user_needs = {
        'usage_profile': {
            'primary_care_visits': 10  # 10 visits at $200 each = $2000 market cost
        },
        'standard_costs': {
            'primary_care_visit': 200
        }
    }

    plan_data = {
        'plan_name': 'Coinsurance Test Plan',
        'plan_code': 'TEST-COINS',
        'biweekly_premium': 100,
        'annual_deductible': 500,
        'oop_max': 10000,
        'benefit_rules': {
            'primary_care_visits': {'type': 'coinsurance', 'value': 0.20}  # 20% coinsurance
        }
    }

    calculator = CostCalculator(user_needs, plan_data)
    result = calculator.calculate_total_cost()

    # Expected:
    # - Total market cost: 10 * $200 = $2000
    # - First $500 toward deductible (pay 100%)
    # - Remaining $1500 * 20% = $300
    # - Total: $500 + $300 = $800

    expected_variable = 500 + (1500 * 0.20)
    expected_deductible_paid = 500

    assert result['usage_breakdown']['primary_care_visits'] == expected_variable, \
        f"Coinsurance calculation incorrect: {result['usage_breakdown']['primary_care_visits']} != {expected_variable}"

    assert result['deductible_paid'] == expected_deductible_paid, \
        f"Deductible paid incorrect: {result['deductible_paid']} != {expected_deductible_paid}"

    logger.info("PASSED: Coinsurance with deductible correct")
    logger.info(f"  Market cost: $2,000.00")
    logger.info(f"  Deductible paid: ${expected_deductible_paid:.2f}")
    logger.info(f"  Coinsurance (20% of $1,500): $300.00")
    logger.info(f"  Total variable cost: ${expected_variable:.2f}")


def verify_oop_cap():
    """Verify OOP maximum cap is applied correctly."""

    logger.info(f"\n{'#'*80}")
    logger.info("VERIFICATION TEST 3: OOP Maximum Cap")
    logger.info(f"{'#'*80}")

    # Test case: very high usage that exceeds OOP max
    user_needs = {
        'usage_profile': {
            'specialist_visits': 50  # 50 visits at $400 = $20,000 market cost
        },
        'standard_costs': {
            'specialist_visit': 400
        }
    }

    plan_data = {
        'plan_name': 'OOP Cap Test Plan',
        'plan_code': 'TEST-OOP',
        'biweekly_premium': 100,
        'annual_deductible': 1000,
        'oop_max': 5000,  # Should cap here
        'benefit_rules': {
            'specialist_visits': {'type': 'coinsurance', 'value': 0.50}  # 50% coinsurance
        }
    }

    calculator = CostCalculator(user_needs, plan_data)
    result = calculator.calculate_total_cost()

    # Without cap: $1000 (deductible) + ($19,000 * 50%) = $10,500
    # With cap: $5,000

    expected_variable_raw = 1000 + (19000 * 0.50)
    expected_variable_capped = 5000

    assert result['variable_cost_raw'] == expected_variable_raw, \
        f"Raw variable cost incorrect: {result['variable_cost_raw']} != {expected_variable_raw}"

    assert result['medical_drug_spend'] == expected_variable_capped, \
        f"OOP cap not applied: {result['medical_drug_spend']} != {expected_variable_capped}"

    logger.info("PASSED: OOP cap applied correctly")
    logger.info(f"  Variable cost (before cap): ${expected_variable_raw:.2f}")
    logger.info(f"  Variable cost (after cap): ${expected_variable_capped:.2f}")
    logger.info(f"  Savings from OOP cap: ${expected_variable_raw - expected_variable_capped:.2f}")


def test_batch_calculation():
    """Test batch calculation of multiple plans."""

    logger.info(f"\n{'#'*80}")
    logger.info("BATCH CALCULATION TEST")
    logger.info(f"{'#'*80}")

    # Load user needs from config
    user_needs = load_user_needs()

    # Create sample plans DataFrame
    sample_plans = create_sample_plans()
    plans_df = pd.DataFrame(sample_plans)

    # Run batch calculation
    results_df = calculate_all_plans(plans_df, user_needs)

    # Display results
    logger.info(f"\nRanked Plans (by total cost):")
    logger.info(f"{'-'*80}")

    display_columns = ['rank', 'plan_name', 'total_annual_cost', 'premium_cost_annual',
                      'medical_drug_spend', 'deductible_paid']

    for idx, row in results_df.iterrows():
        logger.info(f"\nRank #{row['rank']}: {row['plan_name']}")
        logger.info(f"  Total Annual Cost: ${row['total_annual_cost']:,.2f}")
        logger.info(f"  Premium (Annual): ${row['premium_cost_annual']:,.2f}")
        logger.info(f"  Medical/Drug Spend: ${row['medical_drug_spend']:,.2f}")
        logger.info(f"  Deductible Paid: ${row['deductible_paid']:,.2f}")

    return results_df


def main():
    """Run all tests."""

    logger.info("\n" + "="*80)
    logger.info("COST CALCULATOR TEST SUITE")
    logger.info("="*80)

    # Load user needs from config file
    try:
        user_needs = load_user_needs()
        logger.info("\nLoaded user needs configuration:")
        logger.info(f"  Usage profile: {len(user_needs['usage_profile'])} service types")
        logger.info(f"  Standard costs: {len([k for k in user_needs['standard_costs'] if k != 'description'])} service types")
    except Exception as e:
        logger.error(f"Failed to load user needs: {e}")
        return

    # Run verification tests
    try:
        verify_copay_calculation()
        verify_coinsurance_with_deductible()
        verify_oop_cap()
    except AssertionError as e:
        logger.error(f"\nVERIFICATION FAILED: {e}")
        return
    except Exception as e:
        logger.error(f"\nVERIFICATION ERROR: {e}", exc_info=True)
        return

    # Test individual plans with full user profile
    sample_plans = create_sample_plans()

    for i, plan in enumerate(sample_plans, 1):
        test_individual_plan(plan, user_needs, f"Individual Plan Test {i}")

    # Test batch calculation
    try:
        results_df = test_batch_calculation()

        logger.info(f"\n{'='*80}")
        logger.info("ALL TESTS PASSED SUCCESSFULLY")
        logger.info(f"{'='*80}")

        # Save results for inspection
        output_file = 'tests/test_results.csv'
        results_df.to_csv(output_file, index=False)
        logger.info(f"\nTest results saved to: {output_file}")

    except Exception as e:
        logger.error(f"\nBatch calculation failed: {e}", exc_info=True)
        return


if __name__ == "__main__":
    main()
