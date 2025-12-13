"""
Submissions Parser - Fetch and evaluate student submissions

Uses official LeetCode contest metadata (start_time, duration) to determine
if submissions were made during the actual contest window.
"""

import logging
import time
from typing import List, Dict

import requests

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False


logger = logging.getLogger(__name__)

# Multiple API endpoints to distribute load and avoid rate limiting
SUBMISSIONS_API_ENDPOINTS = [
    "https://alfa-pi.vercel.app",
    "https://alfa-weld.vercel.app",
    "https://alfa-nu.vercel.app"
]
LEETCODE_CONTEST_API = "https://leetcode.com/contest/api/info"
MAX_RETRIES = 3
RETRY_DELAY = 3  # seconds (increased to avoid rate limits)

# Global counter to rotate through API endpoints
_api_endpoint_index = 0


def fetch_contest_metadata(contest_slug: str) -> Dict:
    """
    Fetch official contest metadata including start_time and duration.
    
    Args:
        contest_slug: Contest identifier (e.g., "weekly-contest-477")
    
    Returns:
        Dictionary with 'start_time', 'duration', and 'problems' (list of titleSlugs)
    """
    url = f"{LEETCODE_CONTEST_API}/{contest_slug}/"
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Use cloudscraper to bypass Cloudflare
            if CLOUDSCRAPER_AVAILABLE:
                scraper = cloudscraper.create_scraper()
                response = scraper.get(url, timeout=15)
            else:
                response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                raise RuntimeError(f"API returned {response.status_code}")
            
            data = response.json()
            
            # Extract from nested 'contest' object
            contest_info = data.get('contest', {})
            start_time = contest_info.get('start_time')
            duration = contest_info.get('duration')
            
            # Extract problems from root level
            questions = data.get('questions', [])
            problems = [q.get('title_slug') for q in questions if 'title_slug' in q]
            
            if start_time is None or duration is None:
                raise RuntimeError("Missing start_time or duration")
            
            return {
                'start_time': int(start_time),
                'duration': int(duration),
                'problems': problems
            }
            
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            else:
                raise RuntimeError(f"Failed to fetch contest metadata: {e}")
    
    raise RuntimeError("Failed after all retries")


def fetch_user_submissions(leetcode_id: str):
    """
    Fetch all submissions for a user from the deployed API.
    Uses multiple API endpoints in round-robin fashion to avoid rate limiting.
    
    Args:
        leetcode_id: LeetCode username
    
    Returns:
        List of submission dictionaries with keys:
        - titleSlug: Problem identifier
        - timestamp: Submission time (UNIX seconds as string)
        - statusDisplay: Result status (e.g., "Accepted")
        - lang: Programming language
        
        Returns None if user ID is invalid (404 error)
    """
    global _api_endpoint_index
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Retry loop with round-robin API endpoints and exponential backoff
    for attempt in range(1, MAX_RETRIES + 1):
        # Select API endpoint in round-robin fashion
        api_base = SUBMISSIONS_API_ENDPOINTS[_api_endpoint_index % len(SUBMISSIONS_API_ENDPOINTS)]
        _api_endpoint_index += 1
        
        url = f"{api_base}/{leetcode_id}/submission"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for invalid user - API returns {"count":0,"submission":[]} for invalid IDs
            # Valid users have count > 0 or at least some submission data
            count = data.get('count', 0)
            submissions = data.get('submission', [])
            
            # If count is 0 AND submissions is empty, it's likely an invalid user
            # But we need to differentiate from users with no submissions
            # Invalid users return exactly {"count":0,"submission":[]}
            if count == 0 and len(submissions) == 0:
                # Check if this is truly invalid by verifying the response structure
                # Invalid users return minimal response, valid users may have other fields
                if len(data) == 2 and 'count' in data and 'submission' in data:
                    logger.warning(f"Invalid LeetCode ID: {leetcode_id} (no user data)")
                    return None  # Signal invalid ID
            
            logger.debug(f"Fetched {len(submissions)} submissions for {leetcode_id} from {api_base}")
            return submissions
            
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching submissions for {leetcode_id} from {api_base} (attempt {attempt}/{MAX_RETRIES})")
            
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                time.sleep(delay)
            else:
                logger.error(f"Failed to fetch submissions for {leetcode_id}: Timeout")
                return []
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error for {leetcode_id} from {api_base}: {e} (attempt {attempt}/{MAX_RETRIES})")
            
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                time.sleep(delay)
            else:
                logger.error(f"Failed to fetch submissions for {leetcode_id}: {e}")
                return []
        
        except Exception as e:
            logger.error(f"Unexpected error fetching submissions for {leetcode_id}: {e}")
            return []
    
    return []


def evaluate_student_submissions(
    leetcode_id: str,
    contest_slug: str,
    contest_problems: List[str] = None,
    contest_start_ts: int = None,
    contest_end_ts: int = None
) -> str:
    """
    Evaluate a student's contest performance using official contest metadata.
    
    Args:
        leetcode_id: LeetCode username
        contest_slug: Contest identifier (e.g., "weekly-contest-477")
        contest_problems: Optional pre-defined list (will fetch if not provided)
        contest_start_ts: Optional start timestamp (will fetch if not provided)
        contest_end_ts: Optional end timestamp (will fetch if not provided)
    
    Returns:
        "N/A" if no submissions during contest period
        "0" if submitted but none accepted
        "{k}" where k is number of unique problems solved
    
    Note:
        If contest_problems/timestamps are not provided, this function will
        fetch official contest metadata from LeetCode API to get accurate
        start_time and duration for strict verification.
    """
    # If metadata not provided, fetch it from LeetCode API
    if contest_problems is None or contest_start_ts is None or contest_end_ts is None:
        try:
            metadata = fetch_contest_metadata(contest_slug)
            contest_problems = metadata['problems']
            contest_start_ts = metadata['start_time']
            contest_end_ts = metadata['start_time'] + metadata['duration']
            logger.debug(f"Using official contest window: {contest_start_ts} - {contest_end_ts}")
        except Exception as e:
            logger.error(f"Failed to fetch contest metadata: {e}")
            # Fall back to provided values or return N/A
            if contest_problems is None:
                return "N/A"
    
    # Fetch all submissions for the user
    submissions = fetch_user_submissions(leetcode_id)
    
    # Check for invalid ID
    if submissions is None:
        logger.warning(f"Invalid LeetCode ID: {leetcode_id}")
        return "INVALID ID"
    
    if not submissions:
        logger.debug(f"No submissions found for {leetcode_id}")
        return "N/A"
    
    # Filter submissions:
    # 1. Problem is in contest_problems
    # 2. Timestamp is within contest window (using official metadata)
    # 3. Status is "Accepted"
    
    contest_problem_set = set(contest_problems)
    relevant_submissions = []
    accepted_problems = set()
    
    for sub in submissions:
        title_slug = sub.get('titleSlug', '')
        timestamp_str = sub.get('timestamp', '0')
        status = sub.get('statusDisplay', '')
        
        # Convert timestamp to int
        try:
            timestamp = int(timestamp_str)
        except (ValueError, TypeError):
            continue
        
        # Check if this is a contest problem
        if title_slug not in contest_problem_set:
            continue
        
        # Check if submission is within official contest window
        if not (contest_start_ts <= timestamp <= contest_end_ts):
            continue
        
        # This is a relevant submission
        relevant_submissions.append(sub)
        
        # Track accepted problems
        if status == "Accepted":
            accepted_problems.add(title_slug)
    
    # Determine result
    if not relevant_submissions:
        # No submissions for contest problems during contest
        return "N/A"
    
    if not accepted_problems:
        # Submitted but none accepted
        return "0"
    
    # Return count of unique accepted problems
    return str(len(accepted_problems))