# Cost Calculation Flow Diagram

Visual representation of the FEHB cost calculation engine logic.

---

## Overall System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INPUTS                                │
├─────────────────────────────────────────────────────────────────────┤
│  1. Usage Profile (user_needs.json)                                │
│     - Service quantities (visits, prescriptions, etc.)              │
│  2. Standard Costs (user_needs.json)                               │
│     - Market rates for each service                                 │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SCRAPER OUTPUTS                               │
├─────────────────────────────────────────────────────────────────────┤
│  Plan Data (from Tasks 2.x):                                       │
│    - Plan name, code                                                │
│    - Bi-weekly premium                                              │
│    - Annual deductible                                              │
│    - OOP maximum                                                    │
│    - Benefit rules (copay/coinsurance for each service)            │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   COST CALCULATION ENGINE                           │
│                    (CostCalculator class)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 1: Calculate Premium Cost                           │    │
│  │   annual_premium = biweekly_premium × 26                 │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                        │
│                           ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 2: Calculate Variable Costs                         │    │
│  │   For each service in usage_profile:                     │    │
│  │     - Find matching benefit rule                         │    │
│  │     - Apply copay OR coinsurance logic                   │    │
│  │     - Track deductible consumption                       │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                        │
│                           ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 3: Apply OOP Maximum Cap                            │    │
│  │   capped_variable = min(variable_costs, oop_max)        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                        │
│                           ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 4: Calculate Total Cost                             │    │
│  │   total = annual_premium + capped_variable               │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                     │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BATCH PROCESSING                               │
│                 (calculate_all_plans function)                      │
├─────────────────────────────────────────────────────────────────────┤
│  - Process all plans from scraper                                  │
│  - Rank by total_annual_cost (ascending)                           │
│  - Add dynamic cost columns                                         │
│  - Generate summary statistics                                      │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Ranked DataFrame with:                                            │
│    - rank (1 = lowest cost)                                        │
│    - total_annual_cost                                              │
│    - premium_cost_annual                                            │
│    - medical_drug_spend                                             │
│    - deductible_paid                                                │
│    - cost_<service_type> (dynamic columns)                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Detailed: Benefit Rule Application Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│              apply_benefit_rule(rule, market, quantity)             │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Check rule   │
              │ type?        │
              └──────┬───────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
  ┌────────────┐         ┌────────────────┐
  │   COPAY    │         │  COINSURANCE   │
  └──────┬─────┘         └────────┬───────┘
         │                        │
         ▼                        ▼
  ┌────────────────────┐   ┌──────────────────────┐
  │ Simple Formula:    │   │ Check deductible     │
  │                    │   │ remaining?           │
  │ cost = copay_value │   └──────┬───────────────┘
  │        × quantity  │          │
  │                    │          │
  │ Deductible: N/A    │    ┌─────┴─────┐
  │ (not affected)     │    │           │
  └────────────────────┘    ▼           ▼
                      ┌────────────┐  ┌────────────────┐
                      │ Remaining  │  │ Already Met    │
                      │ > 0        │  │ (= 0)          │
                      └──────┬─────┘  └────────┬───────┘
                             │                 │
                             ▼                 ▼
                   ┌──────────────────┐  ┌──────────────────┐
                   │ Deduct portion:  │  │ Only coinsurance:│
                   │                  │  │                  │
                   │ ded = min(market,│  │ cost = market    │
                   │       remaining) │  │        × rate    │
                   │                  │  │                  │
                   │ Reduce:          │  └──────────────────┘
                   │   deductible     │
                   │   remaining      │
                   │                  │
                   │ Then:            │
                   │ coins = (market  │
                   │         - ded)   │
                   │         × rate   │
                   │                  │
                   │ cost = ded +     │
                   │        coins     │
                   └──────────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │ Update:          │
                   │ deductible_paid  │
                   │ += ded           │
                   └──────────────────┘
```

---

## Example: Processing Multiple Services with Deductible

```
Plan: $1,000 deductible, 30% coinsurance
Services: Primary care (4 @ $200), Specialist (8 @ $400), Therapy (100 @ $150)

┌─────────────────────────────────────────────────────────────────────┐
│                      INITIAL STATE                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Deductible Remaining: $1,000                                      │
│  Deductible Paid: $0                                                │
│  Total Cost: $0                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SERVICE 1: Primary Care (4 visits)                     │
├─────────────────────────────────────────────────────────────────────┤
│  Market Cost: 4 × $200 = $800                                      │
│  Deductible Remaining: $1,000                                      │
│                                                                     │
│  Calculation:                                                       │
│    Deductible portion = min($800, $1,000) = $800                  │
│    Remaining for coinsurance = $800 - $800 = $0                   │
│    Coinsurance = $0 × 30% = $0                                    │
│    Cost = $800 + $0 = $800                                        │
│                                                                     │
│  Update:                                                            │
│    Deductible Remaining: $1,000 - $800 = $200                     │
│    Deductible Paid: $0 + $800 = $800                              │
│    Total Cost: $0 + $800 = $800                                   │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              SERVICE 2: Specialist (8 visits)                       │
├─────────────────────────────────────────────────────────────────────┤
│  Market Cost: 8 × $400 = $3,200                                    │
│  Deductible Remaining: $200                                        │
│                                                                     │
│  Calculation:                                                       │
│    Deductible portion = min($3,200, $200) = $200                  │
│    Remaining for coinsurance = $3,200 - $200 = $3,000            │
│    Coinsurance = $3,000 × 30% = $900                             │
│    Cost = $200 + $900 = $1,100                                    │
│                                                                     │
│  Update:                                                            │
│    Deductible Remaining: $200 - $200 = $0 ✓ (MET!)              │
│    Deductible Paid: $800 + $200 = $1,000                         │
│    Total Cost: $800 + $1,100 = $1,900                            │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│            SERVICE 3: Therapy (100 visits)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Market Cost: 100 × $150 = $15,000                                 │
│  Deductible Remaining: $0 (already met)                           │
│                                                                     │
│  Calculation:                                                       │
│    Deductible portion = $0 (skip)                                 │
│    Remaining for coinsurance = $15,000 (all of it)               │
│    Coinsurance = $15,000 × 30% = $4,500                          │
│    Cost = $4,500                                                   │
│                                                                     │
│  Update:                                                            │
│    Deductible Remaining: $0 (no change)                           │
│    Deductible Paid: $1,000 (no change)                            │
│    Total Cost: $1,900 + $4,500 = $6,400                          │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FINAL STATE                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Deductible Paid: $1,000 (100% of deductible)                     │
│  Variable Cost (Raw): $6,400                                       │
│  OOP Check: If OOP max > $6,400 → No cap                          │
│  Total Variable Cost: $6,400                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## OOP Maximum Cap Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│                  Calculate Variable Costs                           │
│                 (sum of all service costs)                          │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
              ┌──────────────────┐
              │ variable_cost_raw│
              └────────┬─────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ Compare to OOP max   │
            └──────────┬───────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
  ┌─────────────────┐        ┌─────────────────┐
  │ raw < oop_max   │        │ raw >= oop_max  │
  └────────┬────────┘        └────────┬────────┘
           │                          │
           ▼                          ▼
  ┌─────────────────┐        ┌─────────────────┐
  │ No cap needed   │        │ Apply cap       │
  │                 │        │                 │
  │ capped = raw    │        │ capped = oop_max│
  │                 │        │                 │
  │ savings = $0    │        │ savings = raw - │
  │                 │        │           oop   │
  └─────────────────┘        └─────────────────┘
           │                          │
           └───────────┬──────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Return capped  │
              │ value          │
              └────────────────┘
```

**Example:**
```
Raw variable cost: $8,500
OOP maximum: $6,000

Result: $6,000 (capped)
Savings: $2,500
```

---

## Service Type Matching Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│         Find benefit rule for "speech_therapy_visits"               │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Try exact match:       │
        │ "speech_therapy_visits"│
        └──────────┬─────────────┘
                   │
            ┌──────┴──────┐
            │             │
            ▼             ▼
        ┌───────┐    ┌─────────┐
        │ Found │    │Not Found│
        └───┬───┘    └────┬────┘
            │             │
            │             ▼
            │    ┌────────────────────┐
            │    │ Try without suffix:│
            │    │ "speech_therapy"   │
            │    └──────────┬─────────┘
            │               │
            │        ┌──────┴──────┐
            │        │             │
            │        ▼             ▼
            │    ┌───────┐    ┌─────────┐
            │    │ Found │    │Not Found│
            │    └───┬───┘    └────┬────┘
            │        │             │
            │        │             ▼
            │        │    ┌──────────────────────┐
            │        │    │ Try fallbacks:       │
            │        │    │ 1. "therapy_services"│
            │        │    │ 2. "rehab_services"  │
            │        │    │ 3. "hab_services"    │
            │        │    └──────────┬───────────┘
            │        │               │
            │        │        ┌──────┴──────┐
            │        │        │             │
            │        │        ▼             ▼
            │        │    ┌───────┐    ┌─────────┐
            │        │    │ Found │    │Not Found│
            │        │    └───┬───┘    └────┬────┘
            │        │        │             │
            │        │        │             ▼
            │        │        │    ┌────────────────┐
            │        │        │    │ Log warning    │
            │        │        │    │ Return None    │
            │        │        │    └────────────────┘
            │        │        │
            └────────┴────────┴─────────┐
                                       │
                                       ▼
                            ┌──────────────────┐
                            │ Use benefit rule │
                            │ for calculation  │
                            └──────────────────┘
```

---

## Batch Processing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│              calculate_all_plans(plans_df, user_needs)              │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ Initialize empty       │
        │ results list           │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ For each plan in       │
        │ DataFrame:             │
        └────────┬───────────────┘
                 │
                 ├─────────────┐
                 │             │
                 ▼             ▼
        ┌────────────────┐  ┌──────────────────┐
        │ Validate       │  │ Create           │
        │ required       │  │ CostCalculator   │
        │ fields         │  │ instance         │
        └────┬───────────┘  └────────┬─────────┘
             │                       │
       ┌─────┴─────┐                │
       │           │                │
       ▼           ▼                │
  ┌────────┐  ┌────────┐           │
  │ Valid  │  │Invalid │           │
  └───┬────┘  └───┬────┘           │
      │           │                │
      │           ▼                │
      │  ┌────────────────┐        │
      │  │ Log warning    │        │
      │  │ Skip plan      │        │
      │  └────────────────┘        │
      │                            │
      └────────────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ calculate_total_   │
              │ cost()             │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ Merge plan data +  │
              │ cost results       │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │ Add to results     │
              │ list               │
              └────────┬───────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │ All plans processed      │
        └────────┬─────────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ Create DataFrame       │
        │ from results           │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ Sort by total_annual_  │
        │ cost (ascending)       │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ Add rank column        │
        │ (1 = lowest cost)      │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ Log summary stats      │
        │ (min, max, median,     │
        │  mean costs)           │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ Return ranked          │
        │ DataFrame              │
        └────────────────────────┘
```

---

## Data Flow Summary

```
USER CONFIG           SCRAPER DATA           CALCULATOR             OUTPUT
─────────────         ────────────           ──────────             ──────

user_needs.json       plans_df               CostCalculator         ranked_plans.csv
   │                     │                        │                      │
   ├─usage_profile      ├─plan_name              ├─premium_cost         ├─rank
   ├─standard_costs     ├─plan_code              ├─variable_cost        ├─plan_name
   │                    ├─biweekly_premium       ├─deductible_paid      ├─total_annual_cost
   │                    ├─annual_deductible      ├─oop_cap              ├─premium_cost_annual
   │                    ├─oop_max                └─total_cost           ├─medical_drug_spend
   │                    └─benefit_rules                                 ├─deductible_paid
   │                                                                     ├─cost_*
   │                                                                     └─...
   │
   └──────────────────────────────┬──────────────────────────────────────┘
                                  │
                         ┌────────▼────────┐
                         │  Integration    │
                         │  main.py        │
                         │  (Task 3.3)     │
                         └─────────────────┘
```

---

## Error Handling Flow

```
                    ┌─────────────────┐
                    │ Start Processing│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Validate Input  │
                    └────────┬────────┘
                             │
                      ┌──────┴──────┐
                      │             │
                      ▼             ▼
            ┌──────────────┐   ┌──────────────┐
            │ Valid        │   │ Invalid      │
            └──────┬───────┘   └──────┬───────┘
                   │                  │
                   │                  ▼
                   │         ┌──────────────────┐
                   │         │ Log ERROR/       │
                   │         │ WARNING          │
                   │         └──────┬───────────┘
                   │                │
                   │                ▼
                   │         ┌──────────────────┐
                   │         │ Handle gracefully│
                   │         │ - Skip item      │
                   │         │ - Continue batch │
                   │         │ - Return partial │
                   │         └──────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │ Process      │
            └──────┬───────┘
                   │
             ┌─────┴─────┐
             │           │
             ▼           ▼
      ┌──────────┐  ┌──────────┐
      │ Success  │  │ Error    │
      └────┬─────┘  └────┬─────┘
           │             │
           │             ▼
           │      ┌─────────────┐
           │      │ Log ERROR   │
           │      │ Try/except  │
           │      │ Continue    │
           │      └─────────────┘
           │
           ▼
    ┌──────────────┐
    │ Add to       │
    │ results      │
    └──────────────┘
```

---

This flow diagram provides a visual representation of how the cost calculator processes data and makes decisions. All flows are implemented in `/src/calculator/cost_engine.py`.
