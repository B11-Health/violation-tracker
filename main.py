import urllib.request
from bs4 import BeautifulSoup
import mysql.connector
import os
import logging
import json
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time
from google.cloud import storage

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def connect_to_mysql():
    """Connect to MySQL database."""
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST'),
            user=os.environ.get('MYSQL_USER'),
            password=os.environ.get('MYSQL_PASSWORD'),
            database=os.environ.get('MYSQL_DATABASE')
        )
        logger.info("Connected to MySQL database")
        return conn
    except mysql.connector.Error as e:
        logger.error(f"MySQL connection error: {e}")
        raise

def create_table(conn):
    """Create MySQL table if not exists."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company VARCHAR(255) NOT NULL,
                current_parent VARCHAR(255),
                current_parent_industry VARCHAR(255),
                primary_offense_type VARCHAR(255) NOT NULL,
                year INT NOT NULL,
                agency VARCHAR(50) NOT NULL,
                penalty_amount DECIMAL(15,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (company, year, agency, penalty_amount)
            )
        """)
        conn.commit()
        logger.info("Created violations table")
    except mysql.connector.Error as e:
        logger.error(f"Error creating table: {e}")
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(urllib.error.HTTPError),
    before_sleep=lambda retry_state: logger.info(f"Retrying request (attempt {retry_state.attempt_number})...")
)
def fetch_page(url):
    """Fetch a webpage using a request with retry mechanism."""
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read().decode('utf-8')

def scrape_violation_tracker():
    """Scrape data from the violation tracker website."""
    base_url = "https://violationtracker.goodjobsfirst.org/?company_op=starts&company=&penalty_op=%3E&penalty=&offense_group=&case_category=&govt_level=&agency_code_st%5B%5D=&pres_term=&case_type=&free_text=&hq_id=&state=PR&order=pen_year&sort="
    records = []

    for page in range(1, 4):  # Scraping pages 1-3
        time.sleep(10)  # Delay between requests to avoid hitting the site too frequently
        url = f"{base_url}&page={page}" if page > 1 else base_url
        try:
            html = fetch_page(url)
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', class_='views-table')
            if not table:
                logger.warning(f"No table found on page {page}")
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
        except Exception as e:
            logger.error(f"Error on page {page}: {e}")
            continue
    return records

def store_records(conn, records):
    """Store scraped records in MySQL database."""
    try:
        cursor = conn.cursor()
        for record in records:
            cursor.execute("""
                INSERT IGNORE INTO violations (company, current_parent, current_parent_industry, primary_offense_type, year, agency, penalty_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                record['company'], record['current_parent'], record['current_parent_industry'],
                record['primary_offense_type'], record['year'], record['agency'], record['penalty_amount']
            ))
        conn.commit()
        logger.info(f"Stored {len(records)} records in database")
    except mysql.connector.Error as e:
        logger.error(f"Error storing records: {e}")
        raise

def save_logs(records):
    """Save logs to Cloud Storage for later reference."""
    log_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'records_processed': len(records)
    }
    bucket_name = os.environ.get('BUCKET_NAME')
    log_file = f"logs/execution-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(log_file)
        blob.upload_from_string(json.dumps(log_data, indent=2))
        logger.info(f"Saved log to gs://{bucket_name}/{log_file}")
    except Exception as e:
        logger.error(f"Error saving log to Cloud Storage: {e}")

def main_scraper():
    """Main function to scrape data, store it, and save logs."""
    try:
        conn = connect_to_mysql()
        create_table(conn)
        records = scrape_violation_tracker()
        if records:
            store_records(conn, records)
            save_logs(records)
        else:
            logger.info("No records scraped.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
        logger.info("Finished execution.")

# Entry point for Cloud Function
def run_scraper(request):
    """Entry point for the Cloud Function."""
    logger.info("Starting scraper execution...")
    main_scraper()
    return ("Scraper completed.", 200)
