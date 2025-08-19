import requests
import time
import random
from typing import List, Dict
import logging
from urllib.parse import urlencode
import re
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def random_delay(self):
        time.sleep(random.uniform(2, 4))

    def is_job_relevant(self, text: str, keywords: str) -> bool:
        text = text.lower()
        keywords = keywords.lower()
        for kw in keywords.split():
            if len(kw) > 2 and kw in text:
                return True
        return False


class LinkedInJobFetcher(JobFetcher):
    def fetch_jobs(self, location: str = "", limit: int = 100) -> List[Dict]:
        jobs = []
        base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobs"
        start = 0
        count = 25  # Max per page
        total_fetched = 0

        while total_fetched < limit:
            params = {
                'start': start,
                'count': count,
                'location': location or '',
                'f_TPR': 'r604800',  # Last week filter
                'sortBy': 'R'        # Sort by relevance
            }

            try:
                logger.info(f"Fetching LinkedIn jobs at offset {start} for location '{location}'")
                response = self.session.get(base_url, params=params)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = soup.find_all('div', {'class': 'job-card-container'}) or \
                            soup.find_all('li', {'class': 'result-card'}) or \
                            soup.find_all('div', {'class': 'base-card'})

                if not job_cards:
                    logger.info("No more job cards found, stopping pagination.")
                    break

                for card in job_cards:
                    try:
                        job = self.parse_linkedin_job_card(card, '')
                        if job:
                            jobs.append(job)
                            total_fetched += 1
                            if total_fetched >= limit:
                                break
                    except Exception as e:
                        logger.error(f"Error parsing job card: {e}")
                        continue

                start += count

                time.sleep(random.uniform(2, 5))  # polite delay
            except Exception as e:
                logger.error(f"Error fetching LinkedIn jobs: {e}")
                break

        return jobs

    def parse_linkedin_job_card(self, card, keywords):
        # your existing parsing logic remains, with the added check for 'no longer accepting applications'
        # make sure to implement the status and is_active flags here as discussed previously
        # ...
        pass    

    def extract_job_url(self, card):
        try:
            link = card.find('a', href=True)
            if not link:
                return None
            href = link['href']
            if href.startswith('/'):
                href = f"https://www.linkedin.com{href}"

            # Extract job id from known URL patterns
            patterns = [
                r'/jobs/view/(\d+)',
                r'jobId=(\d+)',
                r'/jobs/collections/.+?jobId=(\d+)',
                r'currentJobId=(\d+)',
                r'/jobs-apply/(\d+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    job_id = match.group(1)
                    return f"https://www.linkedin.com/jobs/view/{job_id}/"
            # If fully formed URL and contains LinkedIn jobs, assume valid
            if href.startswith('https://www.linkedin.com/jobs/view/'):
                return href

            return None
        except Exception as e:
            logger.error(f"Error extracting job URL: {e}")
            return None

    def create_linkedin_search_jobs(self, keywords: str, location: str, limit: int):
        jobs = []
        variations = [
            {'keywords': keywords, 'desc': keywords},
            {'keywords': f"{keywords} remote", 'desc': f"Remote {keywords}"},
            {'keywords': f"senior {keywords}", 'desc': f"Senior {keywords}"},
            {'keywords': f"{keywords} developer", 'desc': f"{keywords} Developer"},
        ]
        for i, var in enumerate(variations[:limit]):
            params = {
                'keywords': var['keywords'],
                'location': location or '',
                'f_TPR': 'r604800',  # past week filter
                'sortBy': 'R'  # relevance
            }
            search_url = f"https://www.linkedin.com/jobs/search?{urlencode(params)}"
            jobs.append({
                'title': f"{var['desc']} Opportunities",
                'company': 'Multiple Companies',
                'location': location or 'Various Locations',
                'description': f"Explore {var['desc']} roles at top companies. Apply on LinkedIn.",
                'requirements': f"Click to see job details and requirements.",
                'url': search_url,
                'external_url': search_url,
                'source': 'LinkedIn',
                'date_posted': 'Recent'
            })
        return jobs


class JobAggregator:
    def __init__(self):
        self.linkedin_fetcher = LinkedInJobFetcher()

    def fetch_jobs(self, keywords: str, location: str = "", limit: int = 25) -> List[Dict]:
        return self.linkedin_fetcher.fetch_jobs(keywords, location, limit)

    def fetch_all(self, keywords_list: List[Dict]) -> List[Dict]:
        all_jobs = []
        for kw in keywords_list:
            jobs = self.fetch_jobs(kw.get('keywords', ''), kw.get('location', ''), kw.get('limit', 10))
            all_jobs.extend(jobs)
        return all_jobs
