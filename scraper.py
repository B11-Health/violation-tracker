import urllib.request
from bs4 import BeautifulSoup
import sqlite3
import os
import logging
import json
from datetime import datetime, UTC
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_sqlite(db_file):
    """Connect to SQLite database."""
    try:
        conn = sqlite3.connect(db_file)
        logger.info("Connected to SQLite database")
        return conn
    except sqlite3.Error as e:
        logger.error(f"SQLite connection error: {e}")
        raise

def create_table(conn):
    """Create the violations table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                current_parent TEXT,
                current_parent_industry TEXT,
                primary_offense_type TEXT NOT NULL,
                year INTEGER NOT NULL,
                agency TEXT NOT NULL,
                penalty_amount REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (company, year, agency, penalty_amount)
            )
        """)
        conn.commit()
        logger.info("Created violations table")
    except sqlite3.Error as e:
        logger.error(f"Error creating table: {e}")
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(urllib.error.HTTPError),
    before_sleep=lambda retry_state: logger.info(f"Retrying request (attempt {retry_state.attempt_number})...")
)
def fetch_page(url):
    """Fetch a page with retries."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode('utf-8')

def scrape_violation_tracker():
    """Scrape the first three pages of Violation Tracker."""
    base_url = "https://violationtracker.goodjobsfirst.org/?company_op=starts&company=&penalty_op=%3E&penalty=&offense_group=&case_category=&govt_level=&agency_code_st%5B%5D=&pres_term=&case_type=&free_text=&hq_id=&state=PR&order=pen_year&sort="
    records = []

    for page in range(1, 4):
        time.sleep(10)  # Delay to avoid rate-limiting
        url = f"{base_url}&page={page}" if page > 1 else base_url
        try:
            html = fetch_page(url)
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', class_='views-table')
            if not table:
                logger.error(f"No table found on page {page}")
                continue
            rows = table.find('tbody').find_all('tr')

            for row in rows:
                cols = row.find_all('td')
                penalty_text = cols[6].text.strip().replace('$', '').replace(',', '')
                penalty_amount = float(penalty_text) if penalty_text else 0.0
                record = {
                    'company': cols[0].text.strip(),
                    'current_parent': cols[1].text.strip() or None,
                    'current_parent_industry': cols[2].text.strip() or None,
                    'primary_offense_type': cols[3].text.strip(),
                    'year': int(cols[4].text.strip()),
                    'agency': cols[5].text.strip(),
                    'penalty_amount': penalty_amount
                }
                records.append(record)
            logger.info(f"Scraped {len(rows)} records from page {page}")
        except urllib.error.HTTPError as e:
            logger.error(f"Error fetching page {page}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error on page {page}: {e}")
            continue

    return records

def store_records(conn, records):
    """Store records in the database."""
    try:
        cursor = conn.cursor()
        for record in records:
            cursor.execute("""
                INSERT OR IGNORE INTO violations (company, current_parent, current_parent_industry, primary_offense_type, year, agency, penalty_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record['company'], record['current_parent'], record['current_parent_industry'],
                record['primary_offense_type'], record['year'], record['agency'], record['penalty_amount']
            ))
        conn.commit()
        logger.info(f"Stored {len(records)} records in database")
    except sqlite3.Error as e:
        logger.error(f"Error storing records: {e}")
        raise

def save_logs(records):
    """Save execution logs to a file."""
    log_data = {
        'timestamp': datetime.now(UTC).isoformat(),
        'records_processed': len(records)
    }
    os.makedirs('logs', exist_ok=True)
    log_file = f"logs/execution-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2)
    logger.info(f"Saved log to {log_file}")

def verify_results():
    """Verify database records and logs."""
    try:
        conn = sqlite3.connect('violations.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM violations LIMIT 10")
        rows = cursor.fetchall()
        print("First 10 records in violations table:")
        for row in rows:
            print(row)
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Error querying database: {e}")

    print("\nLog files:")
    print(os.listdir('logs'))
    latest_log = sorted(os.listdir('logs'))[-1]
    with open(f'logs/{latest_log}') as f:
        print("\nLatest log contents:")
        print(json.load(f))

def main():
    """Main execution function."""
    db_file = 'violations.db'
    try:
        conn = connect_to_sqlite(db_file)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return

    try:
        create_table(conn)
        records = scrape_violation_tracker()
        if records:
            store_records(conn, records)
        save_logs(records)
        verify_results()
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()
