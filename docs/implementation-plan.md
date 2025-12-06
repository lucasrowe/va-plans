# Implementation Plan: FEHB Plan Cost Analyzer
## Phases 1-3 (Setup, Data Ingestion, Cost Calculation)

**Version:** 1.0
**Status:** Ready for Development
**Date:** 2025-12-05

---

## Phase 1: Project Setup & Configuration

### Task 1.1: Project Structure Setup
**Owner:** Agent 1 (Setup Agent)
**Priority:** High (Blocking)
**Dependencies:** None

**Deliverables:**
```
va-plans/
├── src/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── html_scraper.py      # HTML table scraper
│   │   └── pdf_parser.py         # PDF brochure parser
│   ├── calculator/
│   │   ├── __init__.py
│   │   └── cost_engine.py        # Cost calculation logic
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config_loader.py      # Load JSON configs
│   │   └── logger.py             # Logging utilities
│   └── main.py                   # Entry point
├── data/
│   ├── user_needs.json           # User config (Task 1.2)
│   └── config.json               # App config (Task 1.2)
├── output/
│   ├── pdfs/                     # Downloaded plan brochures
│   └── ranked_plans.csv          # Final output
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_calculator.py
│   └── fixtures/                 # Test data
├── requirements.txt
├── README.md
└── .gitignore
```

**Implementation Steps:**
1. Create directory structure as shown above
2. Create empty `__init__.py` files for Python packages
3. Create `requirements.txt` with initial dependencies:
   ```
   beautifulsoup4==4.12.2
   pandas==2.1.4
   requests==2.31.0
   pdfplumber==0.10.3
   lxml==4.9.3
   ```
4. Create `.gitignore` to exclude:
   - `__pycache__/`
   - `*.pyc`
   - `output/pdfs/`
   - `output/*.csv`
   - `.venv/`
   - `.env`
5. Create basic `README.md` with project title and placeholder sections

**Acceptance Criteria:**
- All directories and files created
- `pip install -r requirements.txt` runs successfully
- Project structure matches PRD technical stack requirements

---

### Task 1.2: Configuration File Creation
**Owner:** Agent 1 (Setup Agent)
**Priority:** High (Blocking)
**Dependencies:** Task 1.1

**Deliverables:**

**File 1: `data/user_needs.json`**
```json
{
  "usage_profile": {
    "primary_care_visits": 4,
    "specialist_visits": 8,
    "er_visits": 1,
    "speech_therapy_visits": 100,
    "occupational_therapy_visits": 24,
    "tier_1_generics_monthly": 2,
    "tier_4_specialty_monthly": 1,
    "inpatient_surgeries": 0
  },
  "standard_costs": {
    "description": "Assumed base price (market rate) before insurance",
    "primary_care_visit": 200,
    "specialist_visit": 400,
    "er_visit": 2100,
    "speech_therapy_visit": 150,
    "occupational_therapy_visit": 150,
    "inpatient_surgery": 25000,
    "tier_1_generic_cost": 20,
    "tier_4_specialty_cost": 5000
  }
}
```

**Note on Extensibility:** The usage_profile and standard_costs are designed to be extensible. Additional service types can be added by:
1. Adding the service name and quantity to `usage_profile` (e.g., `"physical_therapy_visits": 30`)
2. Adding the corresponding market rate to `standard_costs` (e.g., `"physical_therapy_visit": 150`)
3. Ensuring the plan data includes the benefit rule for that service type

The cost calculator will automatically process any matching keys between usage_profile and standard_costs.

**File 2: `data/config.json`**
```json
{
  "target_url": "https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c",
  "zip_code": "27705",
  "family_type": "Self & Family",
  "network_type": "In-Network",
  "pdf_download_timeout": 30,
  "max_retries": 3,
  "output_directory": "output",
  "pdf_directory": "output/pdfs"
}
```

**File 3: `src/utils/config_loader.py`**
- Create `load_user_needs()` function to read and validate `user_needs.json`
- Create `load_app_config()` function to read `config.json`
- Add JSON schema validation for both configs
- Raise helpful errors if files are missing or malformed

**File 4: `src/utils/service_type_mapper.py`**
- Create mapping utilities for flexible service type matching
- Handle variations in how plans label therapy services:
  ```python
  THERAPY_BENEFIT_MAPPING = {
      'speech_therapy_visits': [
          'speech_therapy',
          'speech_language_therapy',
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
      ]
  }
  ```
- Function to find best matching benefit rule for a given usage type
- Log when fallback mappings are used

**Acceptance Criteria:**
- Both JSON files are valid and match PRD specifications
- Config loader functions successfully load both files
- Validation catches common errors (missing keys, wrong types)

---

## Phase 2: Core Functionality - Data Ingestion

### Task 2.1: HTML Scraper Module - Core Structure
**Owner:** Agent 2 (Scraper Agent)
**Priority:** High (Blocking)
**Dependencies:** Task 1.1, Task 1.2

**Deliverables:**

**File: `src/scraper/html_scraper.py`**

**Key Components:**

1. **Class: `OPMScraper`**
   ```python
   class OPMScraper:
       def __init__(self, url: str, timeout: int = 30)
       def fetch_page(self) -> BeautifulSoup
       def extract_plans_table(self, soup: BeautifulSoup) -> pd.DataFrame
       def parse_plan_row(self, row) -> dict
       def scrape_all_plans(self) -> pd.DataFrame
   ```

2. **Data Extraction Requirements (per PRD 4.1):**
   - Plan Name
   - Plan Code
   - Bi-weekly Premium (Family) - extract from "Self & Family" column
   - Annual Deductible (Family)
   - OOP Max (Family)
   - Benefit details:
     - Primary Care (copay or coinsurance %)
     - Specialist (copay or coinsurance %)
     - Inpatient Hospital (copay or coinsurance %)
     - Speech Therapy (copay or coinsurance %)
     - Occupational Therapy (copay or coinsurance %)
     - Generic Drug / Tier 1 (copay or coinsurance %)
     - Brand Drug / Tier 2-3 (copay or coinsurance %)

   **Note:** Therapy benefits may be listed under various labels in the OPM table:
   - "Therapy Services", "Rehabilitation Services", "Habilitation Services"
   - "Speech Therapy", "Occupational Therapy", "Physical Therapy"
   - May be combined or separate line items
   - The scraper should attempt to extract both combined and individual therapy benefits

3. **Benefit Parsing Logic:**
   - Identify if benefit is a copay (e.g., "$40") or coinsurance (e.g., "30%")
   - Handle variations: "$40 copay", "30% after deductible", "No charge"
   - Store as structured data: `{"type": "copay", "value": 40}` or `{"type": "coinsurance", "value": 0.30}`
   - Flag complex/ambiguous entries for manual review

4. **Error Handling:**
   - Retry logic for network failures (use config.max_retries)
   - Graceful handling of missing table cells
   - Log warnings for unparseable benefit text

**Implementation Steps:**
1. Implement `fetch_page()` with requests + BeautifulSoup
2. Identify the correct HTML table structure (inspect target URL)
3. Implement `extract_plans_table()` to locate the comparison table
4. Implement `parse_plan_row()` with regex patterns for benefit parsing
5. Create helper function `parse_benefit_string()` to normalize copay/coinsurance
6. Add logging for each scraped plan
7. Return pandas DataFrame with all extracted fields

**Acceptance Criteria:**
- Successfully fetches HTML from target URL
- Extracts 100% of plans from the comparison table
- Correctly identifies copay vs coinsurance for all benefit fields
- Flags ambiguous entries with warning logs
- Returns clean DataFrame ready for augmentation

---

### Task 2.2: HTML Scraper Module - Brochure Link Extraction
**Owner:** Agent 2 (Scraper Agent)
**Priority:** High
**Dependencies:** Task 2.1

**Deliverables:**

**Enhancement to `src/scraper/html_scraper.py`:**

1. **New Method: `extract_brochure_links()`**
   ```python
   def extract_brochure_links(self, soup: BeautifulSoup, plan_code: str) -> str
   ```
   - Search for plan brochure/summary PDF links within each plan's row
   - Common patterns: "Plan Brochure", "Summary", "Details"
   - Return full URL to PDF
   - Handle relative vs absolute URLs

2. **Integration:**
   - Add `brochure_url` column to DataFrame in `scrape_all_plans()`
   - Log warning if brochure link not found for a plan

**Acceptance Criteria:**
- Extracts brochure links for 100% of plans (or logs warning)
- URLs are valid and downloadable
- DataFrame includes `brochure_url` column

---

### Task 2.3: PDF Parser Module - Download & Basic Extraction
**Owner:** Agent 3 (PDF Agent)
**Priority:** High
**Dependencies:** Task 2.2

**Deliverables:**

**File: `src/scraper/pdf_parser.py`**

**Key Components:**

1. **Class: `PDFBrochureParser`**
   ```python
   class PDFBrochureParser:
       def __init__(self, output_dir: str = "output/pdfs")
       def download_pdf(self, url: str, plan_code: str, plan_name: str) -> str
       def extract_text(self, pdf_path: str) -> str
       def find_tier4_coverage(self, text: str) -> dict
   ```

2. **Download Functionality:**
   - Download PDF from brochure URL
   - Save as `{plan_code}_{plan_name}.pdf` (sanitize filename)
   - Add timeout handling (use config.pdf_download_timeout)
   - Skip if file already exists (caching)

3. **Text Extraction:**
   - Use pdfplumber to extract full text from PDF
   - Handle multi-page documents
   - Preserve structure for pattern matching

4. **Tier 4 Drug Coverage Search (per PRD 4.1):**
   - Search for keywords: "Specialty Drug", "Tier 4", "High-Cost Specialty"
   - Extract surrounding text (e.g., "50% coinsurance after deductible")
   - Return structured data:
     ```python
     {
       "tier_4_found": True,
       "coverage_rule": "50% coinsurance after deductible",
       "raw_text": "..."  # Context snippet
     }
     ```
   - If not found, return `{"tier_4_found": False, "coverage_rule": "Not specified", "raw_text": ""}`

**Implementation Steps:**
1. Implement `download_pdf()` with requests
2. Implement `extract_text()` with pdfplumber
3. Create regex patterns for Tier 4 keywords
4. Implement `find_tier4_coverage()` with pattern matching
5. Add error handling for corrupt/unreadable PDFs
6. Add logging for each PDF processed

**Acceptance Criteria:**
- Downloads all plan brochures successfully
- Saves PDFs with correct naming convention
- Extracts Tier 4 coverage for at least 80% of plans
- Logs plans where Tier 4 data is missing
- Returns structured Tier 4 data for cost calculation

---

### Task 2.4: Data Augmentation Pipeline
**Owner:** Agent 3 (PDF Agent)
**Priority:** Medium
**Dependencies:** Task 2.3

**Deliverables:**

**File: `src/scraper/augmentation_pipeline.py`**

**Key Components:**

1. **Function: `augment_plans_with_tier4()`**
   ```python
   def augment_plans_with_tier4(plans_df: pd.DataFrame, pdf_parser: PDFBrochureParser) -> pd.DataFrame
   ```
   - Iterate through each plan in DataFrame
   - Download PDF and extract Tier 4 data
   - Add new columns:
     - `tier_4_coverage_rule` (parsed benefit string)
     - `tier_4_coverage_type` (copay or coinsurance)
     - `tier_4_coverage_value` (numeric value)
     - `brochure_local_path` (path to downloaded PDF)
   - Handle plans where Tier 4 is not found

2. **Integration Function:**
   ```python
   def run_full_scrape_pipeline(config: dict) -> pd.DataFrame
   ```
   - Orchestrates HTML scraping + PDF augmentation
   - Returns complete DataFrame ready for cost calculation

**Acceptance Criteria:**
- All plans have Tier 4 data or "Not specified" flag
- DataFrame includes local PDF paths
- Pipeline runs end-to-end without errors
- Logs summary of augmentation results

---

## Phase 3: Cost Calculation Engine

### Task 3.1: Cost Calculation Core Logic
**Owner:** Agent 4 (Calculator Agent)
**Priority:** High (Blocking)
**Dependencies:** Task 1.2, Task 2.4

**Deliverables:**

**File: `src/calculator/cost_engine.py`**

**Key Components:**

1. **Class: `CostCalculator`**
   ```python
   class CostCalculator:
       def __init__(self, user_needs: dict, plan_data: dict)
       def calculate_total_cost(self) -> dict
       def calculate_premium_cost(self) -> float
       def calculate_usage_cost(self) -> dict
       def apply_benefit_rule(self, service_type: str, market_cost: float, quantity: int) -> float
       def apply_oop_cap(self, variable_costs: float) -> float
   ```

2. **Premium Calculation (per PRD 4.3 step 2):**
   ```python
   def calculate_premium_cost(self) -> float:
       # Annual Premium = Bi-weekly Premium * 26
       return self.plan_data['biweekly_premium'] * 26
   ```

3. **Variable Cost Calculation (per PRD 4.3 step 3):**
   - Implement for each service type:
     - Primary Care Visits
     - Specialist Visits
     - ER Visits
     - Speech Therapy Visits
     - Occupational Therapy Visits
     - Tier 1 Generics (monthly * 12)
     - Tier 4 Specialty (monthly * 12)
     - Inpatient Surgeries

   **Service Type Mapping Strategy:**
   The calculator should use a flexible mapping approach:
   - If plan has separate "speech_therapy" and "occupational_therapy" benefits, use those
   - If plan only has combined "therapy_services" benefit, apply it to both speech and OT
   - If plan has "rehabilitation_services", use as fallback for therapy types
   - Log which benefit rule was applied for each therapy type

4. **Copay vs Coinsurance Logic (per PRD 4.3):**
   ```python
   def apply_benefit_rule(self, benefit_rule: dict, market_cost: float, quantity: int) -> float:
       """
       Args:
           benefit_rule: {"type": "copay", "value": 40} or {"type": "coinsurance", "value": 0.30}
           market_cost: Base price from standard_costs
           quantity: Number of occurrences

       Returns:
           Total cost for this service type
       """
       if benefit_rule['type'] == 'copay':
           # Copay: Fixed amount per service, deductible ignored
           return benefit_rule['value'] * quantity

       elif benefit_rule['type'] == 'coinsurance':
           # Coinsurance: User pays full cost until deductible met, then pays percentage
           # Simplified logic per PRD 4.3
           total_market_cost = market_cost * quantity

           if self.deductible_remaining > 0:
               # Pay full cost up to remaining deductible
               deductible_portion = min(total_market_cost, self.deductible_remaining)
               self.deductible_remaining -= deductible_portion

               # Pay coinsurance on remaining amount
               coinsurance_portion = (total_market_cost - deductible_portion) * benefit_rule['value']

               return deductible_portion + coinsurance_portion
           else:
               # Deductible already met, only pay coinsurance
               return total_market_cost * benefit_rule['value']
   ```

5. **Deductible Tracking:**
   - Initialize `deductible_remaining = plan_data['annual_deductible']` at start
   - Decrement as coinsurance services are processed
   - Note: Copays do NOT count toward deductible (standard FEHB rule)

6. **OOP Max Cap (per PRD 4.3 step 4):**
   ```python
   def apply_oop_cap(self, variable_costs: float) -> float:
       """Cap variable costs at plan's OOP maximum"""
       oop_max = self.plan_data['oop_max']
       return min(variable_costs, oop_max)
   ```

7. **Total Cost Calculation:**
   ```python
   def calculate_total_cost(self) -> dict:
       premium_cost = self.calculate_premium_cost()
       usage_breakdown = self.calculate_usage_cost()
       variable_cost_raw = sum(usage_breakdown.values())
       variable_cost_capped = self.apply_oop_cap(variable_cost_raw)

       return {
           'total_annual_cost': premium_cost + variable_cost_capped,
           'premium_cost': premium_cost,
           'medical_drug_spend': variable_cost_capped,
           'usage_breakdown': usage_breakdown  # Line items per service type
       }
   ```

**Implementation Steps:**
1. Create `CostCalculator` class with init method
2. Implement `calculate_premium_cost()`
3. Implement `apply_benefit_rule()` with copay/coinsurance logic
4. Implement deductible tracking mechanism
5. Implement `calculate_usage_cost()` to iterate through all service types
6. Implement `apply_oop_cap()`
7. Implement `calculate_total_cost()` to orchestrate all calculations
8. Add detailed logging for each calculation step

**Acceptance Criteria:**
- Correctly calculates premium costs (biweekly * 26)
- Correctly applies copay rules (fixed cost, no deductible)
- Correctly applies coinsurance rules (full cost until deductible, then %)
- Correctly tracks deductible consumption across services
- Correctly caps variable costs at OOP max
- Returns structured breakdown of all costs
- Calculations match manual verification for sample plans

---

### Task 3.2: Batch Cost Calculation & Ranking
**Owner:** Agent 4 (Calculator Agent)
**Priority:** High
**Dependencies:** Task 3.1

**Deliverables:**

**Enhancement to `src/calculator/cost_engine.py`:**

1. **Function: `calculate_all_plans()`**
   ```python
   def calculate_all_plans(plans_df: pd.DataFrame, user_needs: dict) -> pd.DataFrame:
       """
       Run cost calculation for all plans and add result columns

       Args:
           plans_df: DataFrame from scraper (with Tier 4 augmentation)
           user_needs: Loaded from user_needs.json

       Returns:
           Enhanced DataFrame with cost calculations and ranking
       """
   ```

2. **New Columns to Add:**
   - `total_annual_cost` (sorting metric)
   - `premium_cost_annual`
   - `medical_drug_spend`
   - `deductible_paid` (how much of deductible was used)
   - Line item columns (dynamic based on usage_profile):
     - `cost_primary_care`
     - `cost_specialist`
     - `cost_er`
     - `cost_speech_therapy`
     - `cost_occupational_therapy`
     - `cost_tier1_generics`
     - `cost_tier4_specialty`
     - `cost_inpatient_surgery`

   **Note:** The line item columns should be dynamically generated based on keys in the usage_profile, allowing for easy addition of new service types without code changes.

3. **Ranking:**
   ```python
   # Sort by total cost (ascending) and add rank column
   result_df = result_df.sort_values('total_annual_cost')
   result_df.insert(0, 'rank', range(1, len(result_df) + 1))
   ```

4. **Error Handling:**
   - Skip plans with missing critical data (log warning)
   - Handle edge cases (e.g., $0 deductible plans)
   - Validate all costs are non-negative

**Implementation Steps:**
1. Create loop to iterate through all plans in DataFrame
2. For each plan, instantiate `CostCalculator` and run calculation
3. Collect results into new DataFrame columns
4. Add ranking based on total cost
5. Add validation checks for results
6. Log summary statistics (min, max, median cost)

**Acceptance Criteria:**
- All plans have complete cost calculations
- Ranking is correct (1 = lowest cost)
- All line item columns are populated
- No negative costs or NaN values
- Summary statistics are logged

---

### Task 3.3: Integration & Main Entry Point
**Owner:** Agent 4 (Calculator Agent)
**Priority:** Medium
**Dependencies:** Task 3.2

**Deliverables:**

**File: `src/main.py`**

**Key Components:**

1. **Main Pipeline Function:**
   ```python
   def main():
       # Load configs
       user_needs = load_user_needs()
       app_config = load_app_config()

       # Run scraping pipeline
       print("Step 1: Scraping OPM comparison table...")
       plans_df = run_full_scrape_pipeline(app_config)
       print(f"Scraped {len(plans_df)} plans")

       # Calculate costs
       print("Step 2: Calculating costs for all plans...")
       results_df = calculate_all_plans(plans_df, user_needs)

       # Save output (placeholder for Phase 4)
       print("Step 3: Saving results...")
       output_path = os.path.join(app_config['output_directory'], 'ranked_plans.csv')
       results_df.to_csv(output_path, index=False)
       print(f"Results saved to {output_path}")

       # Print top 5 plans
       print("\nTop 5 Plans:")
       print(results_df[['rank', 'plan_name', 'total_annual_cost']].head())

   if __name__ == "__main__":
       main()
   ```

2. **Command-line Interface (Optional Enhancement):**
   - Add argparse for custom config paths
   - Add `--debug` flag for verbose logging

**Acceptance Criteria:**
- `python src/main.py` runs end-to-end without errors
- Outputs CSV file to correct location
- Prints summary of results to console
- All imports work correctly

---

## Dependencies & Execution Order

### Parallel Execution Opportunities:

**Sprint 1 (Can run in parallel):**
- Agent 1: Tasks 1.1 + 1.2 (Project Setup)
- Agent 2: Design HTML scraper class structure (planning only)
- Agent 3: Design PDF parser class structure (planning only)
- Agent 4: Design cost calculator class structure (planning only)

**Sprint 2 (Sequential):**
1. Task 1.1 + 1.2 complete → Task 2.1 starts
2. Task 2.1 complete → Task 2.2 starts
3. Task 2.2 complete → Task 2.3 starts
4. Task 2.3 complete → Task 2.4 starts

**Sprint 3 (Parallel):**
- Task 2.4 continues
- Task 3.1 can start (only needs Task 1.2 for config format)

**Sprint 4 (Sequential):**
1. Task 3.1 complete → Task 3.2 starts
2. Task 3.2 complete + Task 2.4 complete → Task 3.3 starts

---

## Risk Mitigation

### Technical Risks:

1. **HTML Structure Changes**
   - *Risk:* OPM website updates table structure
   - *Mitigation:* Add unit tests with saved HTML fixtures; flag structure changes

2. **PDF Parsing Failures**
   - *Risk:* PDFs are image-based or poorly formatted
   - *Mitigation:* Implement fallback to manual review flagging; test with sample PDFs first

3. **Tier 4 Data Not Found**
   - *Risk:* 20%+ of plans don't have extractable Tier 4 data
   - *Mitigation:* Acceptable per PRD; flag for manual review

4. **Complex Benefit Rules**
   - *Risk:* Benefit text doesn't match "copay" or "coinsurance" patterns
   - *Mitigation:* Extensive regex testing; manual review flags

---

## Testing Strategy (Phase 3)

### Unit Tests to Write:

1. **test_calculator.py:**
   - Test copay calculation (no deductible impact)
   - Test coinsurance with full deductible
   - Test coinsurance with partial deductible consumption
   - Test OOP cap enforcement
   - Test edge cases ($0 copay, 100% coinsurance)

2. **test_scraper.py:**
   - Test benefit string parsing (copay, coinsurance, mixed)
   - Test HTML table extraction with fixtures
   - Test brochure link extraction

3. **test_pdf_parser.py:**
   - Test Tier 4 keyword detection with sample text
   - Test PDF download retry logic

---

## Deliverables Summary (Phases 1-3)

At completion of Phase 3, we will have:

1. ✅ Complete Python project structure
2. ✅ Configuration files (user_needs.json, config.json)
3. ✅ HTML scraper extracting all plan data from OPM table
4. ✅ PDF downloader saving all plan brochures
5. ✅ PDF parser extracting Tier 4 coverage rules
6. ✅ Cost calculation engine with copay/coinsurance logic
7. ✅ Batch processor calculating costs for all plans
8. ✅ Preliminary CSV output (will be enhanced in Phase 4)
9. ✅ Main entry point to run full pipeline

**Not included in Phases 1-3:**
- Final CSV formatting (Phase 4)
- Comprehensive testing suite (Phase 5)
- Documentation polish (Phase 6)

---

## Next Steps

After reviewing this plan, we can:
1. Refine task assignments based on agent availability
2. Create GitHub issues/tasks for each item
3. Begin parallel execution of Sprint 1 tasks
4. Set up progress tracking and check-ins
