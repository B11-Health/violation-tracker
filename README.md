# Violation Tracker Scraper

The **Violation Tracker Scraper** is a Python-based application deployed as a 2nd generation Google Cloud Function that scrapes violation data from a specified source, stores it in a Cloud SQL MySQL database, and logs execution details to Cloud Storage. The function is triggered daily at 8 AM UTC by a Cloud Scheduler job.

This README provides step-by-step instructions to install, implement, and configure the project in Google Cloud Platform (GCP).

## Prerequisites

- **Google Cloud Account**: Sign up for a [GCP account](https://cloud.google.com/) with $300 free credits.
- **Billing Enabled**: Ensure a billing account is linked to your GCP project.
- **Google Cloud SDK**: Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
- **Project ID**: Use `violation-tracker-scraper` (or create a new project).
- **Basic Knowledge**: Familiarity with GCP services (Cloud SQL, Cloud Functions, Cloud Scheduler, Cloud Storage) and command-line tools.

## Project Structure

```plaintext
violation-tracker-scraper/
├── main.py                # Cloud Function code to scrape and store data
├── requirements.txt       # Python dependencies (e.g., requests, mysql-connector-python)
└── README.md              # This file
```

## Setup Instructions

Follow these steps to configure and deploy the Violation Tracker Scraper in GCP.

### 1. Set Up the GCP Project

1. **Create or Select a Project**:
   ```bash
   gcloud projects create violation-tracker-scraper --name="Violation Tracker Scraper" --set-as-default
   ```
   Or select an existing project:
   ```bash
   gcloud config set project violation-tracker-scraper
   ```

2. **Enable Required APIs**:
   ```bash
   gcloud services enable \
     sqladmin.googleapis.com \
     cloudfunctions.googleapis.com \
     cloudscheduler.googleapis.com \
     storage.googleapis.com \
     run.googleapis.com \
     logging.googleapis.com
   ```

3. **Link Billing Account**:
   - Go to the [GCP Console Billing](https://console.cloud.google.com/billing).
   - Link a billing account to `violation-tracker-scraper`.

### 2. Configure Cloud SQL (MySQL)

1. **Create a Cloud SQL Instance**:
   ```bash
   gcloud sql instances create violations-db \
     --database-version=MYSQL_8_0 \
     --tier=db-f1-micro \
     --region=us-central1 \
     --root-password=Password123!
   ```
   - Note: The instance IP is `34.41.100.236` (from setup).

2. **Create a Database**:
   ```bash
   gcloud sql databases create violations_db --instance=violations-db
   ```

3. **Create the Violations Table**:
   - Connect to the instance:
     ```bash
     gcloud sql connect violations-db --user=root
     ```
     - Enter `Password123!`.
   - Create the table:
     ```sql
     USE violations_db;
     CREATE TABLE violations (
         id INT AUTO_INCREMENT PRIMARY KEY,
         company VARCHAR(255) NOT NULL,
         current_parent VARCHAR(255),
         current_parent_industry VARCHAR(255),
         primary_offense_type VARCHAR(255) NOT NULL,
         year INT NOT NULL,
         agency VARCHAR(50) NOT NULL,
         penalty_amount DECIMAL(15,2) NOT NULL,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         INDEX idx_company (company)
     );
     EXIT;
     ```

### 3. Create a Cloud Storage Bucket

1. **Create the Bucket**:
   ```bash
   gsutil mb -l us-central1 gs://violation-tracker-logs-violation-tracker-scraper
   ```

2. **Set Permissions**:
   - Grant the service account write access (replace `<PROJECT_NUMBER>` with your project number from `gcloud projects describe violation-tracker-scraper`):
     ```bash
     gsutil iam ch serviceAccount:cloud-run-scraper@violation-tracker-scraper.iam.gserviceaccount.com:legacyBucketWriter,objectCreator gs://violation-tracker-logs-violation-tracker-scraper
     ```

### 4. Deploy the Cloud Function

1. **Create a Service Account**:
   ```bash
   gcloud iam service-accounts create cloud-run-scraper \
     --display-name="Cloud Function Scraper"
   ```

2. **Grant Permissions**:
   - Grant Cloud SQL Client and Storage access:
     ```bash
     gcloud projects add-iam-policy-binding violation-tracker-scraper \
       --member="serviceAccount:cloud-run-scraper@violation-tracker-scraper.iam.gserviceaccount.com" \
       --role="roles/cloudsql.client"
     gcloud projects add-iam-policy-binding violation-tracker-scraper \
       --member="serviceAccount:cloud-run-scraper@violation-tracker-scraper.iam.gserviceaccount.com" \
       --role="roles/storage.objectAdmin"
     ```

3. **Deploy the Cloud Function**:
   - From the project directory (`~/violation-tracker-scraper`):
     ```bash
     gcloud functions deploy run-scraper \
       --region=us-central1 \
       --runtime=python39 \
       --trigger-http \
       --source=. \
       --set-env-vars="MYSQL_HOST=34.41.100.236,MYSQL_USER=root,MYSQL_PASSWORD=Password123!,MYSQL_DATABASE=violations_db,BUCKET_NAME=violation-tracker-logs-violation-tracker-scraper" \
       --service-account=cloud-run-scraper@violation-tracker-scraper.iam.gserviceaccount.com
     ```
   - This deploys a 2nd gen Cloud Function with HTTP trigger.

4. **Test the Function**:
   ```bash
   TOKEN=$(gcloud auth print-identity-token)
   curl -H "Authorization: Bearer $TOKEN" https://us-central1-violation-tracker-scraper.cloudfunctions.net/run-scraper
   ```
   - Expect: `{"status": "success", "records_processed": X}`.
   - Check logs:
     ```bash
     gcloud functions logs read run-scraper --region=us-central1 --limit=100
     ```

### 5. Configure Cloud Scheduler

1. **Create a Service Account**:
   ```bash
   gcloud iam service-accounts create cloud-scheduler \
     --display-name="Cloud Scheduler"
   ```

2. **Grant Invocation Permissions**:
   - For 2nd gen Cloud Functions, grant `roles/run.invoker`:
     ```bash
     gcloud functions add-invoker-policy-binding run-scraper \
       --region=us-central1 \
       --member="serviceAccount:cloud-scheduler@violation-tracker-scraper.iam.gserviceaccount.com"
     ```

3. **Create the Scheduler Job**:
   ```bash
   gcloud scheduler jobs create http run-scraper-scheduler \
     --schedule="0 8 * * *" \
     --uri="https://us-central1-violation-tracker-scraper.cloudfunctions.net/run-scraper" \
     --http-method=POST \
     --oidc-service-account-email="cloud-scheduler@violation-tracker-scraper.iam.gserviceaccount.com" \
     --oidc-token-audience="https://us-central1-violation-tracker-scraper.cloudfunctions.net/run-scraper" \
     --location=us-central1 \
     --description="Run Violation Tracker scraper function daily at 8 AM UTC"
   ```

4. **Test the Scheduler**:
   ```bash
   gcloud scheduler jobs run run-scraper-scheduler --location=us-central1 --log-http
   ```
   - Expect: HTTP `200 OK`.
   - Check scheduler logs:
     ```bash
     gcloud logging read "resource.type=cloud_scheduler_job resource.labels.job_id=run-scraper-scheduler" --limit=100
     ```

### 6. Verify the Setup

1. **Check Database Records**:
   ```bash
   gcloud sql connect violations-db --user=root
   ```
   - Enter `Password123!`.
   - Run:
     ```sql
     USE violations_db;
     SELECT COUNT(*) FROM violations;
     ```
     - Expect: ~300 records after runs.
   - Check for duplicates:
     ```sql
     SELECT company, primary_offense_type, year, agency, COUNT(*) as count
     FROM violations
     GROUP BY company, primary_offense_type, year, agency
     HAVING count > 1;
     ```
   - Exit: `EXIT;`

2. **Check Cloud Storage Logs**:
   ```bash
   gsutil ls gs://violation-tracker-logs-violation-tracker-scraper/logs/
   gsutil cat gs://violation-tracker-logs-violation-tracker-scraper/logs/execution-<latest-timestamp>.json
   ```
   - Expect: `{"timestamp": "...", "records_processed": X}`.

3. **Check Console**:
   - **Cloud Scheduler**: Verify `run-scraper-scheduler` is enabled and runs at 8 AM UTC.
   - **Cloud Functions**: Check `run-scraper` logs.
   - **Cloud Storage**: Confirm log files in `violation-tracker-logs-violation-tracker-scraper`.
