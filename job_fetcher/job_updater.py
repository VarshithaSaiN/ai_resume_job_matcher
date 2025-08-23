# job_fetcher/job_updater.py
from .api_sources import fetch_remotive_jobs, fetch_adzuna_jobs
import psycopg2
from psycopg2 import Error
import json
from datetime import datetime, timedelta  # ← Add timedelta here
import logging  # ← Add logging here
import threading
import time
from .job_sources import JobAggregator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # ← Add logger here

class JobUpdater:
    def __init__(self, db_config):
        self.db_config = db_config
        self.job_aggregator = JobAggregator()
        self.is_running = False
        
    def get_db_connection(self):
        """Get database connection"""
        try:
            connection = psycopg2.connect(**self.db_config)
            return connection
        except Error as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            return None
    
    def clean_old_jobs(self, days_old=7):
        """Remove LinkedIn jobs older than specified days"""
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cutoff_date = datetime.now() - timedelta(days=days_old)
                
                cursor.execute(
                    "DELETE FROM jobs WHERE source = 'LinkedIn' AND created_at < %s",
                    (cutoff_date,)
                )
                
                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                logger.info(f"Cleaned {deleted_count} old LinkedIn jobs")
                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning old jobs: {e}")
            return 0
    
def update_jobs_for_keywords(self, keywords_list=None):
    conn = self.get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    jobs = []
    # Fetch from Remotive and Adzuna for each keyword
    for kw in ["Python Developer", "Data Scientist", "Full Stack Developer"]:
        jobs.extend(fetch_remotive_jobs(kw, limit=10))
        jobs.extend(fetch_adzuna_jobs(kw, limit=10))
    # Insert logic remains the same
    new_count = 0
    for job in jobs:
        url = job["external_url"]
        cursor.execute(
            "SELECT job_id FROM jobs WHERE title=%s AND company=%s AND source=%s",
            (job["title"], job["company"], job["source"])
        )
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO jobs (employer_id, title, description, requirements,
                                  location, company, source, external_url,
                                  status, is_active, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'active',TRUE,%s)
            """, (
                1,
                job["title"],
                job["description"],
                job["requirements"],
                job["location"],
                job["company"],
                job["source"],
                url,
                job["created_at"]
            ))
            new_count += 1
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Added {new_count} new jobs from Remotive & Adzuna.")

    def run_job_update_cycle(self):
        """Run a complete job update cycle - LinkedIn only"""
        logger.info("Starting LinkedIn job update cycle...")
        
        # Clean old jobs first
        self.clean_old_jobs(days_old=7)
        
        # LinkedIn job search keywords
        keywords_list = [
            {'keywords': 'Python Developer', 'location': 'Remote', 'limit_per_source': 15},
            {'keywords': 'Data Scientist', 'location': 'Remote', 'limit_per_source': 12},
            {'keywords': 'Full Stack Developer', 'location': 'Remote', 'limit_per_source': 15},
            {'keywords': 'Software Engineer', 'location': 'Remote', 'limit_per_source': 15},
            {'keywords': 'DevOps Engineer', 'location': 'Remote', 'limit_per_source': 10},
            {'keywords': 'Frontend Developer', 'location': 'Remote', 'limit_per_source': 12},
            {'keywords': 'Backend Developer', 'location': 'Remote', 'limit_per_source': 12},
            {'keywords': 'Machine Learning Engineer', 'location': 'Remote', 'limit_per_source': 10},
        ]
        
        self.update_jobs_for_keywords(keywords_list)
        logger.info("LinkedIn job update cycle completed")
    
    def start_background_updater(self, update_interval_hours=6):
        """Start background job updater"""
        if self.is_running:
            logger.warning("Background updater is already running")
            return
        
        self.is_running = True
        
        def update_loop():
            while self.is_running:
                try:
                    self.run_job_update_cycle()
                    logger.info(f"Sleeping for {update_interval_hours} hours...")
                    time.sleep(update_interval_hours * 3600)  # Convert hours to seconds
                except Exception as e:
                    logger.error(f"Error in update loop: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying
        
        # Start updater thread
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
        
        logger.info(f"Background job updater started (updates every {update_interval_hours} hours)")
    
    def stop_background_updater(self):
        """Stop background job updater"""
        self.is_running = False
        logger.info("Background job updater stopped")
