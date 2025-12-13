"""
Contest Detector - Auto-detect latest LeetCode contests

Fetches contest information from LeetCode API and determines:
- Latest Weekly Contest (WC XXX)
- Latest Biweekly Contest (BWC XXX)
- Contest slugs, start/end timestamps
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime

import requests

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


logger = logging.getLogger(__name__)

LEETCODE_CONTEST_LIST_API = "https://leetcode.com/contest/api/list/"
LEETCODE_CONTEST_INFO_API = "https://leetcode.com/contest/api/info"
MAX_RETRIES = 3
RETRY_DELAY = 2

# Contest number estimation constants
# Weekly Contest #1 started around Jan 2016
# Biweekly Contest #1 started around May 2019
WEEKLY_CONTEST_START_DATE = datetime(2016, 1, 1)
BIWEEKLY_CONTEST_START_DATE = datetime(2019, 5, 1)


def estimate_current_contest_numbers():
    """
    Estimate current contest numbers based on date.
    Returns tuple: (weekly_estimate, biweekly_estimate)
    """
    now = datetime.now()
    
    # Weekly contests: ~52 per year, happens every Sunday
    weeks_since_weekly_start = (now - WEEKLY_CONTEST_START_DATE).days / 7
    weekly_estimate = int(weeks_since_weekly_start)
    
    # Biweekly contests: ~26 per year, happens every 2 weeks
    weeks_since_biweekly_start = (now - BIWEEKLY_CONTEST_START_DATE).days / 7
    biweekly_estimate = int(weeks_since_biweekly_start / 2)
    
    logger.debug(f"Estimated contest numbers: Weekly ~{weekly_estimate}, Biweekly ~{biweekly_estimate}")
    return weekly_estimate, biweekly_estimate


def fetch_contest_list() -> list:
    """
    Fetch list of all contests from LeetCode API.
    
    Returns:
        List of contest objects with basic info
    """
    url = LEETCODE_CONTEST_LIST_API
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if CLOUDSCRAPER_AVAILABLE:
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=15)
            else:
                response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                raise RuntimeError(f"API returned {response.status_code}")
            
            data = response.json()
            contests = data.get('contests', [])
            
            logger.debug(f"Fetched {len(contests)} total contests")
            return contests
            
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            else:
                raise RuntimeError(f"Failed to fetch contest list: {e}")
    
    return []


def fetch_detailed_contest_info(contest_slug: str) -> Dict:
    """
    Fetch detailed contest information including problems.
    
    Args:
        contest_slug: Contest identifier (e.g., "weekly-contest-478")
    
    Returns:
        Dictionary with start_time, duration, problems, etc.
    """
    url = f"{LEETCODE_CONTEST_INFO_API}/{contest_slug}/"
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if CLOUDSCRAPER_AVAILABLE:
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=15)
            else:
                response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                raise RuntimeError(f"API returned {response.status_code}")
            
            data = response.json()
            
            # Extract contest metadata
            contest_info = data.get('contest', {})
            start_time = contest_info.get('start_time')
            duration = contest_info.get('duration')
            title = contest_info.get('title', '')
            
            # Extract problems
            questions = data.get('questions', [])
            problems = [q.get('title_slug') for q in questions if 'title_slug' in q]
            
            return {
                'title': title,
                'slug': contest_slug,
                'start_time': int(start_time) if start_time else None,
                'duration': int(duration) if duration else None,
                'end_time': int(start_time) + int(duration) if (start_time and duration) else None,
                'problems': problems
            }
            
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed for {contest_slug}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            else:
                logger.error(f"Failed to fetch detailed info for {contest_slug}")
                return None
    
    return None


def parse_contest_id(title_slug: str) -> Optional[int]:
    """
    Extract contest number from slug.
    
    Examples:
        "weekly-contest-478" -> 478
        "biweekly-contest-145" -> 145
    
    Args:
        title_slug: Contest slug
    
    Returns:
        Contest number or None
    """
    try:
        parts = title_slug.split('-')
        return int(parts[-1])
    except (ValueError, IndexError):
        return None


def get_recent_contests(include_upcoming: bool = False) -> Dict:
    """
    Get the most recent Weekly and Biweekly contests using range-based search.
    LeetCode's contest list API is unreliable, so we check contest numbers directly.
    Uses dynamic range calculation to avoid hard-coded limits.
    """
    logger.info("Detecting recent contests...")
    
    current_time = int(time.time())
    
    latest_weekly = None
    latest_biweekly = None
    
    # Get estimated current contest numbers
    weekly_estimate, biweekly_estimate = estimate_current_contest_numbers()
    
    # Search for latest weekly contest (check backwards from estimate)
    # Search range: estimate to (estimate - 20) to handle gaps/skipped contests
    weekly_start = max(weekly_estimate, 470)  # Minimum 470 as safety floor
    weekly_end = weekly_start - 25
    
    logger.info(f"Searching for latest weekly contest in range {weekly_start} to {weekly_end}...")
    for i in range(weekly_start, weekly_end, -1):
        slug = f"weekly-contest-{i}"
        contest_info = fetch_detailed_contest_info(slug)
        
        if contest_info and contest_info['start_time']:
            start_time = contest_info['start_time']
            end_time = contest_info['end_time']
            
            # If we want recent completed contests
            if not include_upcoming and end_time < current_time:
                latest_weekly = contest_info
                logger.info(f"Found latest weekly: {slug}")
                break
            # If we want upcoming contests too
            elif include_upcoming:
                latest_weekly = contest_info
                logger.info(f"Found weekly: {slug}")
                break
    
    # Search for latest biweekly contest (check backwards from estimate)
    biweekly_start = max(biweekly_estimate, 140)  # Minimum 140 as safety floor
    biweekly_end = biweekly_start - 15
    
    logger.info(f"Searching for latest biweekly contest in range {biweekly_start} to {biweekly_end}...")
    for i in range(biweekly_start, biweekly_end, -1):
        slug = f"biweekly-contest-{i}"
        contest_info = fetch_detailed_contest_info(slug)
        
        if contest_info and contest_info['start_time']:
            start_time = contest_info['start_time']
            end_time = contest_info['end_time']
            
            # If we want recent completed contests
            if not include_upcoming and end_time < current_time:
                latest_biweekly = contest_info
                logger.info(f"Found latest biweekly: {slug}")
                break
            # If we want upcoming contests too
            elif include_upcoming:
                latest_biweekly = contest_info
                logger.info(f"Found biweekly: {slug}")
                break
    
    return {
        "weekly": latest_weekly,
        "biweekly": latest_biweekly
    }
def get_upcoming_contests() -> Dict:
    """
    Get upcoming contests that haven't started yet.
    Uses dynamic range calculation based on current date.
    
    Returns:
        Dictionary with next weekly and biweekly contests
    """
    logger.info("Detecting upcoming contests...")
    
    current_time = int(time.time())
    
    next_weekly = None
    next_biweekly = None
    
    # Get estimated current contest numbers
    weekly_estimate, biweekly_estimate = estimate_current_contest_numbers()
    
    # Try to find next weekly contest (check forward from estimate)
    weekly_start = max(weekly_estimate - 2, 470)  # Start slightly before estimate
    weekly_end = weekly_start + 10
    
    logger.info(f"Searching for next weekly contest in range {weekly_start} to {weekly_end}...")
    for i in range(weekly_start, weekly_end):
        slug = f"weekly-contest-{i}"
        contest_info = fetch_detailed_contest_info(slug)
        
        if contest_info and contest_info['start_time']:
            start_time = contest_info['start_time']
            
            if start_time > current_time:
                next_weekly = contest_info
                logger.info(f"Found next weekly: {slug} at {datetime.fromtimestamp(start_time)}")
                break
    
    # Try to find next biweekly contest (check forward from estimate)
    biweekly_start = max(biweekly_estimate - 1, 140)  # Start slightly before estimate
    biweekly_end = biweekly_start + 8
    
    logger.info(f"Searching for next biweekly contest in range {biweekly_start} to {biweekly_end}...")
    for i in range(biweekly_start, biweekly_end):
        slug = f"biweekly-contest-{i}"
        contest_info = fetch_detailed_contest_info(slug)
        
        if contest_info and contest_info['start_time']:
            start_time = contest_info['start_time']
            
            if start_time > current_time:
                next_biweekly = contest_info
                logger.info(f"Found next biweekly: {slug} at {datetime.fromtimestamp(start_time)}")
                break
    
    return {
        "weekly": next_weekly,
        "biweekly": next_biweekly
    }


if __name__ == '__main__':
    # Test the module
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 70)
    print("TESTING CONTEST DETECTOR")
    print("=" * 70)
    
    # Test 1: Get recent contests
    print("\n1. Recent Contests:")
    recent = get_recent_contests()
    
    if recent['weekly']:
        wc = recent['weekly']
        print(f"\nWeekly: {wc['title']}")
        print(f"  Slug: {wc['slug']}")
        print(f"  Start: {wc['start_time']} ({datetime.fromtimestamp(wc['start_time'])})")
        print(f"  End: {wc['end_time']} ({datetime.fromtimestamp(wc['end_time'])})")
        print(f"  Problems: {len(wc['problems'])}")
    
    if recent['biweekly']:
        bc = recent['biweekly']
        print(f"\nBiweekly: {bc['title']}")
        print(f"  Slug: {bc['slug']}")
        print(f"  Start: {bc['start_time']} ({datetime.fromtimestamp(bc['start_time'])})")
        print(f"  End: {bc['end_time']} ({datetime.fromtimestamp(bc['end_time'])})")
        print(f"  Problems: {len(bc['problems'])}")
    
    # Test 2: Get upcoming contests
    print("\n" + "=" * 70)
    print("2. Upcoming Contests:")
    upcoming = get_upcoming_contests()
    
    if upcoming['weekly']:
        wc = upcoming['weekly']
        print(f"\nNext Weekly: {wc['title']}")
        print(f"  Starts at: {datetime.fromtimestamp(wc['start_time'])}")
    
    if upcoming['biweekly']:
        bc = upcoming['biweekly']
        print(f"\nNext Biweekly: {bc['title']}")
        print(f"  Starts at: {datetime.fromtimestamp(bc['start_time'])}")