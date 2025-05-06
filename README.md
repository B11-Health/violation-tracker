# Violation Tracker Scraper

This project scrapes violation data from the Violation Tracker website ([link](https://violationtracker.goodjobsfirst.org/?company_op=starts&company=&penalty_op=%3E&penalty=&offense_group=&case_category=&govt_level=&agency_code_st%5B%5D=&pres_term=&case_type=&free_text=&hq_id=&state=PR&order=pen_year&sort=)) for the first three pages, extracting company names, regulatory agencies, years, penalty amounts, and optional fields (current parent, industry, offense type). Data is stored in a SQLite database (`violations.db`). The script runs in Google Colab.

## Expected Output
- **Database Records**: Scraped records stored in SQLite (`violations.db`), with the first 10 displayed, e.g.:
  ```
  (1, 'Best Petroleum Corp.', None, None, 'air pollution violation', 2024, 'EPA', 316721.0, '2025-05-06 14:16:21')
  (2, 'Almonte Geo Service Group', None, None, 'nuclear safety violation', 2024, 'NRC', 17500.0, '2025-05-06 14:16:21')
  (3, 'Neolpharma, Inc.', None, None, 'Medicare Coverage Gap Discount Program violation', 2024, 'CMS', 5410.0, '2025-05-06 14:16:21')
  (4, 'Windmar Home/Windmar P.V. Energy Inc.', None, None, 'wage and hour violation', 2024, 'WHD', 238746.0, '2025-05-06 14:16:21')
  (5, 'Applied Energy Systems Puerto Rico, LP', None, None, 'air pollution violation', 2024, 'EPA', 3100000.0, '2025-05-06 14:16:21')
  (6, 'Centro Medico Wilma N Vazquez Snf', None, None, 'nursing home violation', 2024, 'CMS', 29998.0, '2025-05-06 14:16:21')
  (7, 'Argos Puerto Rico Corp.', 'Argos', 'building materials', 'air pollution violation', 2024, 'EPA', 311000.0, '2025-05-06 14:16:21')
  (8, 'Damas Hospital Snf', None, None, 'nursing home violation', 2024, 'CMS', 10839.0, '2025-05-06 14:16:21')
  (9, 'AES Puerto Rico, L.P.', 'AES Corp.', 'utilities and power generation', 'water pollution violation', 2024, 'EPA', 71845.0, '2025-05-06 14:16:21')
  (10, 'Transporte Rodriguez Asfalto, Inc.', None, None, 'water pollution violation', 2024, 'EPA', 80000.0, '2025-05-06 14:16:21')
  ```
- **Logs**: JSON file in `logs/` directory, e.g.:
  ```
  Log files: ['execution-20250506141621.json']
  Latest log contents: {'timestamp': '2025-05-06T14:16:21.490980+00:00', 'records_processed': 303}
  ```

## Setup in Google Colab
1. **Open Notebook**:
   - Access the Colab notebook: [https://colab.research.google.com/drive/1vM-hD2pclo-VTWqmAhXwgLLwo-iqlXtH?usp=sharing](https://colab.research.google.com/drive/1vM-hD2pclo-VTWqmAhXwgLLwo-iqlXtH?usp=sharing)
   - Save a copy to your Google Drive: File > Save a copy in Drive.

2. **Dependencies**:
   - The "Install Dependencies" cell installs required libraries (`beautifulsoup4`, `tenacity`). SQLite is built into Python, and no external database setup is needed.

## Execution
1. **Run Cells**:
   - Run all cells in sequence (Runtime > Run all) or individually.
   - The "Install Dependencies" cell installs libraries.
   - The "Main Execution Function" cell scrapes records and stores them in `violations.db`.
   - The "Test and Verify Results" cell displays the first 10 records and log details.

2. **Verify Output**:
   - Check the "Test and Verify Results" cell for:
     - First 10 records (as shown above).
     - Log file confirming records processed.
   - If fewer records are scraped, check logs in `logs/` or increase the delay in the "Scrape Violation Tracker" cell.

## Verification
- **Database Records**:
  ```python
  import sqlite3
  conn = sqlite3.connect('violations.db')
  cursor = conn.cursor()
  cursor.execute("SELECT * FROM violations LIMIT 10")
  rows = cursor.fetchall()
  for row in rows:
      print(row)
  conn.close()
  ```
- **Logs**:
  ```python
  import os
  import json
  print(os.listdir('logs'))
  with open('logs/execution-<latest-timestamp>.json') as f:
      print(json.load(f))
  ```
