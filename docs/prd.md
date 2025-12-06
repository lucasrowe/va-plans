

# **Product Requirements Document: FEHB Plan Cost Analyzer**

| Project Name | FEHB Cost Analyzer (Zip 27705\) |
| :---- | :---- |
| **Version** | 1.0 (Final) |
| **Status** | Ready for Development |
| **Target URL** | [OPM Comparison for Zip 27705](https://www.opm.gov/healthcare-insurance/healthcare/plan-information/compare-plans/fehb/Plans?ZipCode=27705&IncludeNationwide=True&empType=a&payPeriod=c) |

## 

## **1\. Problem Statement**

Federal employees need a way to compare healthcare plans based on **total estimated annual cost** (Premium \+ Out-of-Pocket) rather than just premiums. Manual comparison is error-prone due to complex "coinsurance vs. copay" rules and missing high-level details for high-cost items like Specialty (Tier 4\) drugs.

## **2\. Goals & Success Metrics**

* **Goal:** Produce a ranked CSV of all available plans for Zip 27705, sorted by total estimated cost.  
* **Metric:** Successfully extract Premium, Deductible, OOP Max, and key benefit percentages/copays for 100% of plans in the HTML table.  
* **Metric:** Augment the table with "Tier 4 Drug Coverage" details (extracted from PDF or detailed drill-down) for every plan.

## **3\. User Stories**

* **As a user,** I want to define my family's medical usage (e.g., "1 ER visit, 2 monthly Specialty Prescriptions") so the costs reflect my actual life.  
* **As a user,** I want the tool to apply "Standard Reference Costs" (e.g., ER visit \= $2,100) to percentage-based benefits so I get a real dollar amount estimate.  
* **As a user,** I want to see the specific breakdown of costs (Premiums vs. Usage) in the final CSV.  
* **As a user,** I want the tool to assume "In-Network" providers to simplify the analysis.

## **4\. Functional Requirements**

### **4.1 Data Ingestion (Hybrid Approach)**

* **Step 1 (HTML Scraper):** Scrape the OPM Comparison Table at the Target URL (hardcoded).  
  * **Extract:** Plan Name, Code, Bi-weekly Premium (Family), Annual Deductible, OOP Max.  
  * **Extract Benefits:** Primary Care, Specialist, Inpatient Hospital, Generic Drug (Tier 1), Brand Drug (Tier 2/3).  
* **Step 2 (PDF/Detail Augmentation):**  
  * Identify the link to the Plan Brochure/Summary.  
  * **Target Data:** Search specifically for **"Specialty Drug"** or **"Tier 4"** coverage. (Note: This is often missing from the main HTML table and requires deeper parsing).  
  * **Download:** Save the PDF locally as {PlanCode}\_{PlanName}.pdf for manual verification.

### **4.2 Usage Configuration (JSON)**

The tool will load user\_needs.json. This file defines *quantity* of care and *assumed market price* of care.

JSON  
{  
  "usage\_profile": {  
    "primary\_care\_visits": 4,  
    "specialist\_visits": 8,  
    "er\_visits": 1,  
    "tier\_1\_generics\_monthly": 2,  
    "tier\_4\_specialty\_monthly": 1,  
    "inpatient\_surgeries": 0  
  },  
  "standard\_costs": {  
    "description": "Assumed base price (market rate) before insurance",  
    "primary\_care\_visit": 200,  
    "specialist\_visit": 400,  
    "er\_visit": 2100,  
    "inpatient\_surgery": 25000,  
    "tier\_1\_generic\_cost": 20,  
    "tier\_4\_specialty\_cost": 5000  
  }  
}

**Note on Tier 4:** We assume a market cost of **$5,000/month** for specialty drugs in the config. If a plan has "30% coinsurance," the cost to the user is $1,500. If a plan has "$200 copay," the cost is $200.

### **4.3 Cost Calculation Engine**

For each plan, perform the following simulation:

1. **Initialize:** Total\_Spend \= 0, Deductible\_Paid \= 0.  
2. **Fixed Costs:** Add (Bi-weekly Premium \* 26\) to Total\_Spend.  
3. **Variable Costs Loop:** Iterate through each item in usage\_profile.  
   * **Get Benefit Rule:** Look up the plan's rule for that service (e.g., "30% after deductible" or "$40 copay").  
   * **Get Market Rate:** Look up the cost in standard\_costs.  
   * **Calculate Item Cost:**  
     * *If Benefit is Copay (Fixed $):* Cost \= Copay (Deductible ignored).  
     * *If Benefit is Coinsurance (%):*  
       * **Simplified Logic:** User pays full Market Rate until Deductible is met. Once Deductible is met, user pays the Coinsurance %.  
   * **Accumulate:** Add result to Total\_Spend.  
4. **OOP Cap:** If (Total\_Spend \- Premiums) \> OOP\_Max, set the variable portion to OOP\_Max.

### **4.4 Output (ranked\_plans.csv)**

The output file must contain the following columns:

1. **Rank** (1 \= Lowest Total Cost)  
2. **Plan Name**  
3. **Plan Code**  
4. **TOTAL ANNUAL COST** (The sorting metric)  
5. **Premium Cost** (Annual)  
6. **Medical/Drug Spend** (Estimated Out-of-Pocket)  
7. **Deductible** (Family)  
8. **OOP Max** (Family)  
9. **Tier 4 Coverage Rule** (Extracted text, e.g., "50% coinsurance")  
10. **Brochure Link** (Local Path)  
11. **Usage Line Items:** (Dynamic columns based on JSON, e.g., "Cost of ER Visits", "Cost of Specialist Visits", "Cost of Tier 4 Rx")

## **5\. Assumptions & Constraints**

* **Family Plan:** The tool will scrape the "Self & Family" column for premiums and deductibles.  
* **Network:** All calculations assume providers are **In-Network**.  
* **Drug Formulary:** All "Generic" scripts are assumed to be Tier 1, and "Brand" scripts are assumed to be Tier 2/Preferred. We will explicitly look up Tier 4\.  
* **Parsing Limits:** If a table cell is too complex, the tool will flag it for manual review.

## **6\. Technical Stack**

* **Language:** Python  
* **Parsing:** BeautifulSoup (HTML), pdfplumber or pypdf (for PDF text extraction if simple scraping fails).  
* **Data:** Pandas for calculation logic and CSV generation.

