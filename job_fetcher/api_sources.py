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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def random_delay(self):
        time.sleep(random.uniform(2, 4))

class LinkedInJobFetcher(JobFetcher):
    """
    Fetch jobs from LinkedIn's guest jobs API using current parameters:
      - keywords: search keywords
      - location: location filter
      - start: pagination offset
      - count: number of jobs per page
    """
    def fetch_jobs(self, keywords: str = "", location: str = "", limit: int = 100) -> List[Dict]:
        jobs = []
        base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobs"
        start = 0
        count = 25  # jobs per request
        total_fetched = 0

        while total_fetched < limit:
            params = {
                'keywords': keywords,
                'location': location or '',
                'start': start,
                'count': count
            }

            try:
                logger.info(f"Fetching LinkedIn jobs: keywords='{keywords}', location='{location}', start={start}")
                response = self.session.get(base_url, params=params)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = (
                    soup.find_all('div', {'class': 'job-card-container'}) or
                    soup.find_all('li', {'class': 'result-card'}) or
                    soup.find_all('div', {'class': 'base-card'})
                )

                if not job_cards:
                    logger.info("No more job cards found; ending pagination.")
                    break

                for card in job_cards:
                    if total_fetched >= limit:
                        break
                    try:
                        job = self.parse_linkedin_job_card(card)
                        if job:
                            jobs.append(job)
                            total_fetched += 1
                    except Exception as e:
                        logger.error(f"Error parsing job card: {e}")
                        continue

                start += count
                self.random_delay()

            except Exception as e:
                logger.error(f"Error fetching LinkedIn jobs: {e}")
                break

        return jobs

    def parse_linkedin_job_card(self, card) -> Dict:
        """
        Parse a single LinkedIn job card element into a job dict.
        Must extract title, company, location, description snippet, external_url, source, and created_at.
        """
        try:
            title_el = card.find('a', {'data-control-name': 'job_card_company_link'}) or card.find('h3')
            title = title_el.get_text(strip=True) if title_el else "No Title"

            company_el = card.find('h4') or card.find('span', {'class': 'result-card__subtitle-link'})
            company = company_el.get_text(strip=True) if company_el else None

            location_el = card.find('span', {'class': 'job-card__location'}) or card.find('span', {'class': 'result-card__location'})
            location = location_el.get_text(strip=True) if location_el else None

            desc_el = card.find('p', {'class': 'job-card-container__metadata-item'}) or card.find('p')
            description = desc_el.get_text(strip=True) if desc_el else ""

            external_url = self.extract_job_url(card)

            date_el = card.find('time')
            created_at = date_el['datetime'] if date_el and date_el.has_attr('datetime') else None

            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'requirements': "",
                'external_url': external_url,
                'url': external_url,
                'source': 'LinkedIn',
                'created_at': created_at
            }
        except Exception as e:
            logger.error(f"parse_linkedin_job_card error: {e}")
            return None

    def extract_job_url(self, card) -> str:
        """
        Find the job detail URL from the card, normalize to full LinkedIn view URL.
        """
        try:
            link = card.find('a', href=True)
            if not link:
                return None
            href = link['href']
            if href.startswith('/'):
                href = f"https://www.linkedin.com{href}"

            patterns = [
                r'/jobs/view/(\d+)',
                r'jobId=(\d+)',
                r'/jobs-apply/(\d+)',
            ]
            for pattern in patterns:
                m = re.search(pattern, href)
                if m:
                    job_id = m.group(1)
                    return f"https://www.linkedin.com/jobs/view/{job_id}/"
            return href if 'linkedin.com/jobs/view/' in href else None

        except Exception as e:
            logger.error(f"Error extracting job URL: {e}")
            return None

    def create_linkedin_search_jobs(self, keywords: str, location: str, limit: int) -> List[Dict]:
        """
        Fallback: generate placeholder search pages rather than scraping.
        """
        jobs = []
        variations = [
            {'keywords': keywords, 'desc': keywords},
            {'keywords': f"{keywords} remote", 'desc': f"Remote {keywords}"},
            {'keywords': f"senior {keywords}", 'desc': f"Senior {keywords}"},
            {'keywords': f"{keywords} developer", 'desc': f"{keywords} Developer"},
        ]
        for var in variations[:limit]:
            params = {'keywords': var['keywords'], 'location': location or ''}
            search_url = f"https://www.linkedin.com/jobs/search?{urlencode(params)}"
            jobs.append({
                'title': f"{var['desc']} Opportunities",
                'company': 'Multiple Companies',
                'location': location or 'Various Locations',
                'description': f"Explore {var['desc']} roles on LinkedIn.",
                'requirements': "Click to view details on LinkedIn.",
                'external_url': search_url,
                'url': search_url,
                'source': 'LinkedIn',
                'created_at': None
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
            jobs = self.fetch_jobs(
                keywords=kw.get('keywords', ''),
                location=kw.get('location', ''),
                limit=kw.get('limit', 10)
            )
            all_jobs.extend(jobs)
        return all_jobs
