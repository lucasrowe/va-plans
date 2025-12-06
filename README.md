# FEHB Plan Cost Analyzer

A Python tool for comparing Federal Employee Health Benefits (FEHB) plans based on personalized usage patterns.

## Overview

This tool scrapes plan data from the OPM website, calculates total annual costs based on your specific healthcare needs, and ranks plans from most to least cost-effective.

## Features

- Automated scraping of FEHB plan data from OPM comparison tables
- PDF parsing for detailed benefit information
- Personalized cost calculation based on your usage profile
- Support for therapy visits (speech therapy, occupational therapy)
- Flexible benefit mapping for different plan structures
- Out-of-pocket maximum cap enforcement
- CSV export of ranked plans

## Project Structure

```
va-plans/
├── src/                    # Source code
│   ├── scraper/           # Web scraping and PDF parsing
│   ├── calculator/        # Cost calculation engine
│   ├── utils/             # Configuration and utilities
│   └── main.py            # Entry point
├── data/                  # Configuration files
├── output/                # Results and downloaded PDFs
└── tests/                 # Unit tests
```

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Edit `data/user_needs.json` to customize your healthcare usage profile:
- Primary care visits
- Specialist visits
- Therapy visits (speech, occupational)
- Prescription drugs
- Emergency room visits
- Inpatient surgeries

## Usage

Run the analyzer:
```bash
python src/main.py
```

Results will be saved to `output/ranked_plans.csv`.

## Development Status

This project is currently under development. Implementation follows a phased approach:
- Phase 1: Project Setup & Configuration
- Phase 2: Data Ingestion (HTML scraping, PDF parsing)
- Phase 3: Cost Calculation Engine
- Phase 4: Output Formatting & Reporting
- Phase 5: Testing
- Phase 6: Documentation

## License

This project is for personal use.
