# Cost Calculator API Reference

Quick reference guide for using the FEHB cost calculation engine.

---

## Quick Start

```python
from src.calculator.cost_engine import CostCalculator, calculate_all_plans
from src.utils.config_loader import load_user_needs

# Load user configuration
user_needs = load_user_needs()

# Calculate costs for all plans
results_df = calculate_all_plans(plans_df, user_needs)

# Get top 5 plans
top_5 = results_df.head(5)
```

---

## Functions

### `calculate_all_plans(plans_df, user_needs)`

Batch process multiple plans and return ranked results.

**Parameters:**
- `plans_df` (pd.DataFrame): DataFrame containing plan data from scraper
- `user_needs` (dict): User configuration from `data/user_needs.json`

**Returns:**
- `pd.DataFrame`: Enhanced DataFrame with cost calculations and ranking

**Required Columns in Input DataFrame:**
- `plan_name` (str): Plan name
- `plan_code` (str): Plan code
- `biweekly_premium` (float): Bi-weekly premium
- `annual_deductible` (float): Annual deductible
- `oop_max` (float): Out-of-pocket maximum
- `benefit_rules` (dict): Service benefit rules

**Output Columns:**
- `rank`: Plan ranking (1 = lowest cost)
- `total_annual_cost`: Total annual cost
- `premium_cost_annual`: Annual premium
- `medical_drug_spend`: Variable costs (capped at OOP)
- `deductible_paid`: Deductible consumed
- `variable_cost_raw`: Variable costs before OOP cap
- `cost_<service_type>`: Dynamic columns for each service

**Example:**
```python
results = calculate_all_plans(plans_df, user_needs)
print(results[['rank', 'plan_name', 'total_annual_cost']].head())
```

---

## Classes

### `CostCalculator`

Calculate costs for a single plan.

#### Constructor

```python
CostCalculator(user_needs, plan_data)
```

**Parameters:**
- `user_needs` (dict): User configuration
  - `usage_profile`: Dict of service quantities
  - `standard_costs`: Dict of market rates
- `plan_data` (dict): Plan characteristics
  - `plan_name`: Plan name
  - `plan_code`: Plan code
  - `biweekly_premium`: Bi-weekly premium
  - `annual_deductible`: Annual deductible
  - `oop_max`: OOP maximum
  - `benefit_rules`: Dict of benefit rules

**Example:**
```python
calculator = CostCalculator(user_needs, plan_data)
```

#### Methods

##### `calculate_total_cost()`

Run complete cost calculation.

**Returns:**
```python
{
    'total_annual_cost': float,      # Total cost
    'premium_cost': float,            # Annual premium
    'medical_drug_spend': float,      # Variable costs (capped)
    'deductible_paid': float,         # Deductible consumed
    'usage_breakdown': dict,          # Per-service costs
    'variable_cost_raw': float        # Before OOP cap
}
```

**Example:**
```python
result = calculator.calculate_total_cost()
print(f"Total: ${result['total_annual_cost']:.2f}")
```

##### `calculate_premium_cost()`

Calculate annual premium only.

**Returns:** `float` - Annual premium (biweekly × 26)

**Example:**
```python
premium = calculator.calculate_premium_cost()
```

##### `apply_benefit_rule(benefit_rule, market_cost, quantity, service_name)`

Apply copay or coinsurance rule to a service.

**Parameters:**
- `benefit_rule` (dict): {"type": "copay"|"coinsurance", "value": float}
- `market_cost` (float): Market rate per service
- `quantity` (int): Number of occurrences
- `service_name` (str): Service name for logging

**Returns:** `float` - Total cost for this service

**Example:**
```python
rule = {'type': 'copay', 'value': 25}
cost = calculator.apply_benefit_rule(rule, 200, 4, 'primary_care')
# Returns: 100.0 (25 × 4)
```

##### `calculate_usage_cost()`

Calculate costs for all services in usage profile.

**Returns:** `dict` - Mapping of service names to costs

**Example:**
```python
breakdown = calculator.calculate_usage_cost()
# Returns: {'primary_care_visits': 100, 'specialist_visits': 360, ...}
```

##### `apply_oop_cap(variable_costs)`

Cap variable costs at OOP maximum.

**Parameters:**
- `variable_costs` (float): Total variable costs before cap

**Returns:** `float` - Capped variable costs

**Example:**
```python
capped = calculator.apply_oop_cap(8500)
# Returns: 6000 (if OOP max is $6,000)
```

---

## Data Structures

### Benefit Rule Format

```python
{
    "type": "copay" | "coinsurance",
    "value": float  # Dollar amount for copay, decimal for coinsurance
}
```

**Examples:**
```python
# Copay: $25 per visit
{"type": "copay", "value": 25}

# Coinsurance: 20% of market cost
{"type": "coinsurance", "value": 0.20}
```

### Plan Data Format

```python
{
    'plan_name': 'Sample HMO Plan',
    'plan_code': 'HMO-001',
    'biweekly_premium': 180.00,
    'annual_deductible': 0,
    'oop_max': 6000,
    'benefit_rules': {
        'primary_care_visits': {'type': 'copay', 'value': 25},
        'specialist_visits': {'type': 'copay', 'value': 45},
        'therapy_services': {'type': 'copay', 'value': 35},
        'generic_drug': {'type': 'copay', 'value': 10},
        'specialty_drug': {'type': 'coinsurance', 'value': 0.50}
    }
}
```

### User Needs Format

```python
{
    'usage_profile': {
        'primary_care_visits': 4,
        'specialist_visits': 8,
        'speech_therapy_visits': 100,
        'tier_1_generics_monthly': 2,
        'tier_4_specialty_monthly': 1
    },
    'standard_costs': {
        'primary_care_visit': 200,
        'specialist_visit': 400,
        'speech_therapy_visit': 150,
        'tier_1_generic_cost': 20,
        'tier_4_specialty_cost': 5000
    }
}
```

---

## Service Type Mapping

The calculator uses flexible matching to find benefit rules:

### Direct Matching
- `primary_care_visits` → `primary_care_visits`
- `specialist_visits` → `specialist_visits`

### Suffix Removal
- `speech_therapy_visits` → `speech_therapy`
- `er_visits` → `er`

### Therapy Fallbacks
- `speech_therapy_visits` → tries:
  1. `speech_therapy`
  2. `therapy_services`
  3. `rehabilitation_services`
  4. `habilitation_services`

- `occupational_therapy_visits` → tries:
  1. `occupational_therapy`
  2. `ot_therapy`
  3. `therapy_services`
  4. `rehabilitation_services`
  5. `habilitation_services`

### Drug Mappings
- `tier_1_generics_monthly` → `generic_drug`
- `tier_4_specialty_monthly` → `specialty_drug`

### Adding New Service Types

1. Add to `usage_profile` in `data/user_needs.json`:
```json
"physical_therapy_visits": 30
```

2. Add market rate to `standard_costs`:
```json
"physical_therapy_visit": 150
```

3. Plan data should include benefit rule:
```python
'benefit_rules': {
    'physical_therapy': {'type': 'copay', 'value': 35}
}
```

No code changes needed!

---

## Calculation Logic

### Copay Calculation
```
Total Cost = copay_value × quantity
Deductible: Not affected
```

**Example:**
- Copay: $25
- Visits: 4
- Cost: $25 × 4 = $100

### Coinsurance Calculation
```
1. Calculate market cost: market_rate × quantity
2. If deductible remaining:
   a. Deductible portion = min(market_cost, deductible_remaining)
   b. Remaining = market_cost - deductible_portion
   c. Coinsurance portion = remaining × coinsurance_rate
   d. Total = deductible_portion + coinsurance_portion
3. Else (deductible met):
   a. Total = market_cost × coinsurance_rate
```

**Example (20% coinsurance, $500 deductible):**
- Market: 10 × $200 = $2,000
- Deductible: $500 (pay 100%)
- Remaining: $2,000 - $500 = $1,500
- Coinsurance: $1,500 × 0.20 = $300
- Total: $500 + $300 = $800

### Total Cost Calculation
```
1. Premium = biweekly_premium × 26
2. Variable costs = sum of all service costs
3. Capped variable = min(variable_costs, oop_max)
4. Total = premium + capped_variable
```

---

## Error Handling

### Missing Required Fields
```python
# Logs warning and skips plan
WARNING: Skipping plan 'XYZ Plan': Missing required fields: ['biweekly_premium']
```

### Missing Benefit Rule
```python
# Logs warning and assumes $0 cost
WARNING: No benefit rule found for 'physical_therapy_visits'. Assuming $0 cost.
```

### Missing Market Cost
```python
# Logs warning and skips service
WARNING: No market cost found for 'physical_therapy_visit' (from usage 'physical_therapy_visits'). Skipping cost calculation.
```

### Calculation Error
```python
# Logs error and skips plan
ERROR: Error calculating costs for plan 'ABC Plan': division by zero
```

---

## Common Usage Patterns

### 1. Calculate Costs for One Plan

```python
from src.calculator.cost_engine import CostCalculator
from src.utils.config_loader import load_user_needs

user_needs = load_user_needs()

plan = {
    'plan_name': 'My Plan',
    'plan_code': 'TEST-001',
    'biweekly_premium': 150,
    'annual_deductible': 500,
    'oop_max': 5000,
    'benefit_rules': {
        'primary_care_visits': {'type': 'copay', 'value': 20}
    }
}

calculator = CostCalculator(user_needs, plan)
result = calculator.calculate_total_cost()

print(f"Total annual cost: ${result['total_annual_cost']:,.2f}")
```

### 2. Rank All Plans

```python
from src.calculator.cost_engine import calculate_all_plans
from src.utils.config_loader import load_user_needs
import pandas as pd

user_needs = load_user_needs()
plans_df = pd.read_csv('plans.csv')  # From scraper

results = calculate_all_plans(plans_df, user_needs)

# Show top 10
print(results[['rank', 'plan_name', 'total_annual_cost']].head(10))

# Save to CSV
results.to_csv('output/ranked_plans.csv', index=False)
```

### 3. Compare Specific Plans

```python
results = calculate_all_plans(plans_df, user_needs)

# Filter to specific plans
my_plans = results[results['plan_code'].isin(['HMO-001', 'PPO-002', 'HDHP-003'])]

# Compare costs
for _, plan in my_plans.iterrows():
    print(f"{plan['plan_name']}: ${plan['total_annual_cost']:,.2f}")
```

### 4. Find Plans Under Budget

```python
results = calculate_all_plans(plans_df, user_needs)

# Find plans under $10,000/year
affordable = results[results['total_annual_cost'] < 10000]

print(f"Found {len(affordable)} plans under $10,000")
print(affordable[['rank', 'plan_name', 'total_annual_cost']])
```

### 5. Analyze Cost Breakdown

```python
calculator = CostCalculator(user_needs, plan_data)
result = calculator.calculate_total_cost()

print(f"Premium: ${result['premium_cost']:,.2f}")
print(f"Medical/Drug: ${result['medical_drug_spend']:,.2f}")
print(f"Deductible Paid: ${result['deductible_paid']:,.2f}")

print("\nService Breakdown:")
for service, cost in result['usage_breakdown'].items():
    print(f"  {service}: ${cost:,.2f}")
```

---

## Testing

### Run Unit Tests

```bash
python tests/test_cost_calculator.py
```

### Run Demo

```bash
python demo_calculator.py
```

### Expected Output

```
============================================================
Cost Calculation Summary:
  Plans processed: 3
  Min total cost: $8,234.56
  Max total cost: $11,456.78
  Median total cost: $9,845.67
  Mean total cost: $9,845.67
============================================================
```

---

## Performance

### Benchmarks

- **Single plan:** < 1ms
- **100 plans:** < 100ms
- **1000 plans:** < 1 second

### Memory

- Minimal memory footprint
- Suitable for processing hundreds of plans
- No memory leaks or accumulation

---

## Logging

### Log Levels

**DEBUG:**
- Individual calculation steps
- Benefit rule matching
- Service cost breakdowns

**INFO:**
- Plan summary costs
- Batch calculation progress
- OOP cap applications
- Fallback rule usage

**WARNING:**
- Missing benefit rules
- Missing market costs
- Skipped services
- Validation failures

**ERROR:**
- Calculation failures
- Missing required fields
- Invalid data types

### Configure Logging

```python
import logging

# Set to DEBUG for detailed output
logging.basicConfig(level=logging.DEBUG)

# Set to INFO for normal operation
logging.basicConfig(level=logging.INFO)

# Set to WARNING for quiet operation
logging.basicConfig(level=logging.WARNING)
```

---

## Troubleshooting

### "No benefit rule found"

**Problem:** Calculator can't find matching benefit rule for service.

**Solution:**
1. Check benefit_rules keys in plan data
2. Verify service name matches or use fallback patterns
3. Add explicit mapping in benefit_rules

### "No market cost found"

**Problem:** Missing entry in standard_costs.

**Solution:**
1. Add market rate to `data/user_needs.json`:
```json
"standard_costs": {
    "new_service_visit": 150
}
```

### "Skipping plan: Missing required fields"

**Problem:** Plan missing required data.

**Solution:**
1. Ensure plan has: plan_name, plan_code, biweekly_premium, annual_deductible, oop_max
2. Check for NaN values in DataFrame
3. Validate scraper output

### Unexpected Total Cost

**Problem:** Cost calculation seems wrong.

**Solution:**
1. Enable DEBUG logging to see calculation steps
2. Verify benefit rules are correct type (copay vs coinsurance)
3. Check deductible tracking
4. Verify OOP cap is applied correctly

---

## Contact & Support

For issues or questions:
- Check `/docs/calculator-implementation-summary.md` for detailed logic
- Review test cases in `/tests/test_cost_calculator.py`
- Run demo script: `python demo_calculator.py`
