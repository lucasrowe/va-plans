"""Cost calculation engine for FEHB plans."""

import logging
from typing import Dict, Any
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CostCalculator:
    """
    Calculates total annual cost for a specific FEHB plan based on user needs.

    Handles premium costs, variable usage costs with copay/coinsurance logic,
    deductible tracking, and OOP maximum caps.
    """

    def __init__(self, user_needs: Dict[str, Any], plan_data: Dict[str, Any]):
        """
        Initialize the cost calculator.

        Args:
            user_needs: Dictionary containing:
                - usage_profile: Dict of service types and quantities
                - standard_costs: Dict of market rates for each service
            plan_data: Dictionary containing plan details:
                - plan_name: Name of the plan
                - plan_code: Plan code
                - biweekly_premium: Bi-weekly premium cost
                - annual_deductible: Annual deductible amount
                - oop_max: Out-of-pocket maximum
                - benefit_rules: Dict of service types to benefit rules
                    Each rule: {"type": "copay"|"coinsurance", "value": numeric}
        """
        self.user_needs = user_needs
        self.plan_data = plan_data
        self.usage_profile = user_needs.get('usage_profile', {})
        self.standard_costs = user_needs.get('standard_costs', {})

        # Initialize deductible tracking
        self.deductible_remaining = plan_data.get('annual_deductible', 0)
        self.deductible_paid = 0

        # Track variable costs before cap
        self.variable_cost_raw = 0

        logger.debug(f"Initialized CostCalculator for plan: {plan_data.get('plan_name', 'Unknown')}")
        logger.debug(f"Initial deductible: ${self.deductible_remaining}")

    def calculate_premium_cost(self) -> float:
        """
        Calculate annual premium cost.

        Premium = Bi-weekly Premium * 26 pay periods

        Returns:
            Annual premium cost
        """
        biweekly_premium = self.plan_data.get('biweekly_premium', 0)
        annual_premium = biweekly_premium * 26

        logger.debug(f"Premium calculation: ${biweekly_premium} * 26 = ${annual_premium}")

        return annual_premium

    def apply_benefit_rule(
        self,
        benefit_rule: Dict[str, Any],
        market_cost: float,
        quantity: int,
        service_name: str
    ) -> float:
        """
        Apply benefit rule (copay or coinsurance) to calculate cost for a service.

        Copay Logic:
            - Fixed amount per service
            - Does NOT count toward deductible
            - Total = copay * quantity

        Coinsurance Logic:
            - User pays percentage of market cost
            - Must meet deductible first (pay 100% until deductible met)
            - After deductible: pay coinsurance percentage
            - Total market cost = market_cost * quantity

        Args:
            benefit_rule: Dict with "type" (copay/coinsurance) and "value"
            market_cost: Base market rate for one service
            quantity: Number of service occurrences
            service_name: Name of service (for logging)

        Returns:
            Total cost for this service type
        """
        if not benefit_rule or quantity <= 0 or market_cost <= 0:
            logger.debug(f"{service_name}: No cost (missing rule or zero quantity)")
            return 0.0

        benefit_type = benefit_rule.get('type', 'copay').lower()
        benefit_value = benefit_rule.get('value', 0)

        if benefit_type == 'copay':
            # Copay: Fixed amount per service, deductible ignored
            total_cost = benefit_value * quantity
            logger.debug(
                f"{service_name} (Copay): ${benefit_value} x {quantity} = ${total_cost:.2f}"
            )
            return total_cost

        elif benefit_type == 'coinsurance':
            # Coinsurance: User pays full cost until deductible met, then pays percentage
            total_market_cost = market_cost * quantity

            if self.deductible_remaining > 0:
                # Pay full cost up to remaining deductible
                deductible_portion = min(total_market_cost, self.deductible_remaining)
                self.deductible_remaining -= deductible_portion
                self.deductible_paid += deductible_portion

                # Pay coinsurance on remaining amount
                remaining_market_cost = total_market_cost - deductible_portion
                coinsurance_portion = remaining_market_cost * benefit_value

                total_cost = deductible_portion + coinsurance_portion

                logger.debug(
                    f"{service_name} (Coinsurance {benefit_value*100:.0f}%): "
                    f"Market=${total_market_cost:.2f}, Deductible=${deductible_portion:.2f}, "
                    f"Coinsurance=${coinsurance_portion:.2f}, Total=${total_cost:.2f}"
                )
            else:
                # Deductible already met, only pay coinsurance
                total_cost = total_market_cost * benefit_value
                logger.debug(
                    f"{service_name} (Coinsurance {benefit_value*100:.0f}%): "
                    f"Market=${total_market_cost:.2f}, Total=${total_cost:.2f} "
                    f"(deductible already met)"
                )

            return total_cost

        else:
            logger.warning(
                f"{service_name}: Unknown benefit type '{benefit_type}', treating as $0 cost"
            )
            return 0.0

    def calculate_usage_cost(self) -> Dict[str, float]:
        """
        Calculate variable costs for all service types in usage profile.

        Iterates through usage_profile, matches with standard_costs and benefit_rules,
        and calculates cost for each service type.

        Returns:
            Dictionary mapping service names to calculated costs
        """
        usage_breakdown = {}
        benefit_rules = self.plan_data.get('benefit_rules', {})

        for usage_key, quantity in self.usage_profile.items():
            if quantity <= 0:
                continue

            # Map usage key to cost key (e.g., "primary_care_visits" -> "primary_care_visit")
            # Remove trailing 's' and '_monthly' for matching
            cost_key = usage_key.rstrip('s')
            if cost_key.endswith('_monthly'):
                cost_key = cost_key.replace('_monthly', '_cost')
                # Monthly prescriptions: multiply by 12
                quantity = quantity * 12

            # Get market cost for this service
            market_cost = self.standard_costs.get(cost_key, 0)

            if market_cost <= 0:
                logger.warning(
                    f"No market cost found for '{cost_key}' (from usage '{usage_key}'). "
                    f"Skipping cost calculation."
                )
                continue

            # Get benefit rule for this service
            # Try exact match first, then fallbacks
            benefit_rule = self._find_benefit_rule(usage_key, benefit_rules)

            if not benefit_rule:
                logger.warning(
                    f"No benefit rule found for '{usage_key}'. Assuming $0 cost."
                )
                usage_breakdown[usage_key] = 0.0
                continue

            # Calculate cost for this service
            cost = self.apply_benefit_rule(
                benefit_rule,
                market_cost,
                quantity,
                usage_key
            )

            usage_breakdown[usage_key] = cost

        logger.debug(f"Total usage breakdown: {len(usage_breakdown)} service types calculated")

        return usage_breakdown

    def _find_benefit_rule(
        self,
        usage_key: str,
        benefit_rules: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        Find the appropriate benefit rule for a given usage key.

        Supports flexible matching for therapy services that may be listed
        under different names in plan data.

        Args:
            usage_key: Key from usage_profile (e.g., "speech_therapy_visits")
            benefit_rules: Dictionary of available benefit rules

        Returns:
            Benefit rule dict or None if not found
        """
        # Try exact match first
        if usage_key in benefit_rules:
            logger.debug(f"Exact match found for '{usage_key}'")
            return benefit_rules[usage_key]

        # Try without '_visits' suffix
        base_key = usage_key.replace('_visits', '')
        if base_key in benefit_rules:
            logger.debug(f"Match found for '{usage_key}' as '{base_key}'")
            return benefit_rules[base_key]

        # Therapy service fallback mappings
        therapy_fallbacks = {
            'speech_therapy_visits': [
                'speech_therapy',
                'therapy_services',
                'rehabilitation_services',
                'habilitation_services'
            ],
            'occupational_therapy_visits': [
                'occupational_therapy',
                'ot_therapy',
                'therapy_services',
                'rehabilitation_services',
                'habilitation_services'
            ],
            'physical_therapy_visits': [
                'physical_therapy',
                'pt_therapy',
                'therapy_services',
                'rehabilitation_services',
                'habilitation_services'
            ]
        }

        if usage_key in therapy_fallbacks:
            for fallback_key in therapy_fallbacks[usage_key]:
                if fallback_key in benefit_rules:
                    logger.info(
                        f"Using fallback benefit rule '{fallback_key}' for '{usage_key}'"
                    )
                    return benefit_rules[fallback_key]

        # Try generic mapping patterns
        # e.g., "tier_1_generics_monthly" -> "tier_1_generics" or "generic_drug"
        if '_generics' in usage_key and 'generic_drug' in benefit_rules:
            logger.info(f"Using 'generic_drug' benefit rule for '{usage_key}'")
            return benefit_rules['generic_drug']

        if '_specialty' in usage_key and 'specialty_drug' in benefit_rules:
            logger.info(f"Using 'specialty_drug' benefit rule for '{usage_key}'")
            return benefit_rules['specialty_drug']

        # No match found
        return None

    def apply_oop_cap(self, variable_costs: float) -> float:
        """
        Cap variable costs at plan's out-of-pocket maximum.

        Args:
            variable_costs: Total variable costs before OOP cap

        Returns:
            Variable costs capped at OOP maximum
        """
        oop_max = self.plan_data.get('oop_max', float('inf'))

        if variable_costs > oop_max:
            logger.info(
                f"OOP cap applied: ${variable_costs:.2f} capped at ${oop_max:.2f} "
                f"(saved ${variable_costs - oop_max:.2f})"
            )
            return oop_max
        else:
            logger.debug(f"OOP cap not reached: ${variable_costs:.2f} < ${oop_max:.2f}")
            return variable_costs

    def calculate_total_cost(self) -> Dict[str, Any]:
        """
        Orchestrate all cost calculations and return complete breakdown.

        Returns:
            Dictionary containing:
                - total_annual_cost: Premium + capped variable costs
                - premium_cost: Annual premium
                - medical_drug_spend: Variable costs (capped at OOP max)
                - deductible_paid: Amount of deductible consumed
                - usage_breakdown: Dict of per-service costs
                - variable_cost_raw: Variable costs before OOP cap
        """
        # Reset deductible tracking
        self.deductible_remaining = self.plan_data.get('annual_deductible', 0)
        self.deductible_paid = 0

        # Calculate premium
        premium_cost = self.calculate_premium_cost()

        # Calculate variable costs
        usage_breakdown = self.calculate_usage_cost()
        variable_cost_raw = sum(usage_breakdown.values())

        # Apply OOP cap
        variable_cost_capped = self.apply_oop_cap(variable_cost_raw)

        # Total annual cost
        total_annual_cost = premium_cost + variable_cost_capped

        result = {
            'total_annual_cost': round(total_annual_cost, 2),
            'premium_cost': round(premium_cost, 2),
            'medical_drug_spend': round(variable_cost_capped, 2),
            'deductible_paid': round(self.deductible_paid, 2),
            'usage_breakdown': {k: round(v, 2) for k, v in usage_breakdown.items()},
            'variable_cost_raw': round(variable_cost_raw, 2)
        }

        logger.info(
            f"Plan: {self.plan_data.get('plan_name', 'Unknown')} | "
            f"Total: ${result['total_annual_cost']:.2f} | "
            f"Premium: ${result['premium_cost']:.2f} | "
            f"Medical/Drug: ${result['medical_drug_spend']:.2f}"
        )

        return result


def calculate_all_plans(plans_df: pd.DataFrame, user_needs: Dict[str, Any]) -> pd.DataFrame:
    """
    Run cost calculation for all plans and add result columns.

    Args:
        plans_df: DataFrame from scraper with plan data
        user_needs: Loaded from user_needs.json

    Returns:
        Enhanced DataFrame with cost calculations and ranking
    """
    logger.info(f"Starting batch cost calculation for {len(plans_df)} plans...")

    results = []

    for idx, row in plans_df.iterrows():
        try:
            # Convert row to plan_data dictionary
            plan_data = row.to_dict()

            # Validate required fields
            required_fields = ['plan_name', 'biweekly_premium', 'annual_deductible', 'oop_max']
            missing_fields = [f for f in required_fields if f not in plan_data or pd.isna(plan_data[f])]

            if missing_fields:
                logger.warning(
                    f"Skipping plan '{plan_data.get('plan_name', 'Unknown')}': "
                    f"Missing required fields: {missing_fields}"
                )
                continue

            # Initialize calculator and run calculation
            calculator = CostCalculator(user_needs, plan_data)
            cost_result = calculator.calculate_total_cost()

            # Merge plan data with cost results
            result_row = plan_data.copy()
            result_row.update({
                'total_annual_cost': cost_result['total_annual_cost'],
                'premium_cost_annual': cost_result['premium_cost'],
                'medical_drug_spend': cost_result['medical_drug_spend'],
                'deductible_paid': cost_result['deductible_paid'],
                'variable_cost_raw': cost_result['variable_cost_raw']
            })

            # Add line item columns dynamically based on usage breakdown
            usage_breakdown = cost_result['usage_breakdown']
            for service_type, cost in usage_breakdown.items():
                column_name = f"cost_{service_type}"
                result_row[column_name] = cost

            results.append(result_row)

        except Exception as e:
            logger.error(
                f"Error calculating costs for plan '{plan_data.get('plan_name', 'Unknown')}': {e}",
                exc_info=True
            )
            continue

    if not results:
        logger.error("No plans were successfully processed!")
        return pd.DataFrame()

    # Create results DataFrame
    result_df = pd.DataFrame(results)

    # Sort by total cost (ascending) and add rank
    result_df = result_df.sort_values('total_annual_cost', ascending=True)
    result_df.insert(0, 'rank', range(1, len(result_df) + 1))

    # Reset index
    result_df = result_df.reset_index(drop=True)

    # Log summary statistics
    logger.info(f"\n{'='*60}")
    logger.info(f"Cost Calculation Summary:")
    logger.info(f"  Plans processed: {len(result_df)}")
    logger.info(f"  Min total cost: ${result_df['total_annual_cost'].min():.2f}")
    logger.info(f"  Max total cost: ${result_df['total_annual_cost'].max():.2f}")
    logger.info(f"  Median total cost: ${result_df['total_annual_cost'].median():.2f}")
    logger.info(f"  Mean total cost: ${result_df['total_annual_cost'].mean():.2f}")
    logger.info(f"{'='*60}\n")

    return result_df
