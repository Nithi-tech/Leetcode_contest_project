"""
Contest Fetcher - Retrieve contest problems from LeetCode API

Fetches the list of problems (titleSlugs) for a given contest using
LeetCode's REST API endpoint with cloudscraper to bypass Cloudflare protection.
"""

import logging
import time
from typing import List

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    import requests


logger = logging.getLogger(__name__)

LEETCODE_CONTEST_API = "https://leetcode.com/contest/api/info"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def fetch_contest_problems(contest_slug: str, manual_problems: List[str] = None) -> List[str]:
    """
    Fetch contest problems using LeetCode REST API with cloudscraper or use manual list.
    
    Args:
        contest_slug: Contest identifier (e.g., "weekly-contest-478")
        manual_problems: Optional pre-defined list of problem titleSlugs
    
    Returns:
        List of problem titleSlugs (e.g., ["problem-a", "problem-b"])
    
    Raises:
        RuntimeError: If unable to fetch contest data after retries
    """
    # If manual problems provided, use them
    if manual_problems:
        logger.info(f"Using manually configured problems ({len(manual_problems)} problems)")
        return manual_problems
    
    # Check if cloudscraper is available
    if not CLOUDSCRAPER_AVAILABLE:
        logger.warning("cloudscraper not installed. Install it with: pip install cloudscraper")
        logger.info("Falling back to manual problems if provided")
        if manual_problems:
            return manual_problems
        raise RuntimeError(
            "cloudscraper is required to bypass Cloudflare protection. "
            "Install it with: pip install cloudscraper"
        )
    
    # Use REST API endpoint
    url = f"{LEETCODE_CONTEST_API}/{contest_slug}/"
    
    logger.info(f"Fetching contest info: {url}")
    
    # Retry loop with exponential backoff
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching contest problems (attempt {attempt}/{MAX_RETRIES})...")
            
            # Create cloudscraper session to bypass Cloudflare
            scraper = cloudscraper.create_scraper()
            
            response = scraper.get(url, timeout=10)
            
            logger.info(f"Status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Non-200 status code: {response.status_code}")
                logger.debug(f"Response: {response.text[:500]}")
                
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError(
                        f"Contest API returned {response.status_code}. "
                        "Contest may not be unlocked yet or invalid contest name."
                    )
            
            data = response.json()
            
            # Check for contest data
            if 'questions' not in data:
                logger.error("No questions found in response")
                
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"Contest not found or no questions: {contest_slug}")
            
            questions = data.get('questions', [])
            
            if not questions:
                logger.warning("Contest found but contains no questions")
                return []
            
            # Extract titleSlugs - LeetCode API returns "title_slug" field
            title_slugs = []
            for q in questions:
                slug = q.get('title_slug')
                if slug:
                    title_slugs.append(slug)
                    logger.debug(f"Found problem: {slug}")
            
            logger.info(f"Successfully fetched {len(title_slugs)} problems")
            return title_slugs
            
        except Exception as e:
            logger.error(f"Request error: {e}")
            
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise RuntimeError(f"Failed to fetch contest problems: {e}")
    
    raise RuntimeError("Failed to fetch contest problems after all retries")