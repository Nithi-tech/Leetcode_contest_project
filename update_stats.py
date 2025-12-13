import gspread
import requests
import time
from google.oauth2.service_account import Credentials

# Google Sheets setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
SERVICE_ACCOUNT_FILE = 'service.json'
SHEET_NAME = 'WhatsApp Contest Tracker'
TAB_NAME = 'Real data Leetcode'

# API mirrors for round-robin
API_MIRRORS = [
    'https://alfa-nu.vercel.app',
    'https://alfa-weld.vercel.app',
    'https://alfa-pi.vercel.app'
]

current_mirror_index = 0


def get_next_mirror():
    """Get the next API mirror in round-robin fashion."""
    global current_mirror_index
    mirror = API_MIRRORS[current_mirror_index]
    current_mirror_index = (current_mirror_index + 1) % len(API_MIRRORS)
    return mirror


def fetch_solved_count(username, max_retries=3):
    """Fetch total problems solved for a user with retry logic."""
    for attempt in range(max_retries):
        try:
            mirror = get_next_mirror()
            url = f"{mirror}/{username}/solved"
            response = requests.get(url, timeout=10)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 30 * (attempt + 1)))
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            # Check if user exists (API returns specific structure for invalid users)
            if not data or data.get('status') == 'error':
                print(f"Invalid LeetCode ID: {username}")
                return -1  # Signal invalid user
            
            return data.get('solvedProblem', 0)
            
        except requests.exceptions.Timeout:
            print(f"Timeout fetching solved count for {username} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            print(f"Error fetching solved count for {username}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    return 0  # Return 0 after all retries failed


def fetch_contest_rating(username, max_retries=3):
    """Fetch contest rating for a user with retry logic."""
    for attempt in range(max_retries):
        try:
            mirror = get_next_mirror()
            url = f"{mirror}/{username}/contest"
            response = requests.get(url, timeout=10)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 30 * (attempt + 1)))
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            # Check if user exists
            if not data or data.get('status') == 'error':
                print(f"Invalid LeetCode ID: {username}")
                return -1  # Signal invalid user
            
            return data.get('contestRating', 0)
            
        except requests.exceptions.Timeout:
            print(f"Timeout fetching contest rating for {username} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            print(f"Error fetching contest rating for {username}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    return 0  # Return 0 after all retries failed


def update_leetcode_stats():
    """Main function to update Google Sheet with LeetCode stats."""
    # Authenticate with Google Sheets
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    
    # Open the spreadsheet and worksheet
    sheet = client.open(SHEET_NAME)
    worksheet = sheet.worksheet(TAB_NAME)
    
    # Read all LeetCode IDs from column C (starting from row 2)
    leetcode_ids = worksheet.col_values(3)[1:]  # Column C, skip header
    
    # Prepare data for batch update
    solved_counts = []
    contest_ratings = []
    
    print(f"Processing {len(leetcode_ids)} users...")
    
    for idx, username in enumerate(leetcode_ids, start=1):
        if not username or username.strip() == '':
            # Handle empty cells
            solved_counts.append(0)
            contest_ratings.append(0)
            continue
        
        username = username.strip()
        print(f"[{idx}/{len(leetcode_ids)}] Fetching data for: {username}")
        
        # Fetch stats
        solved = fetch_solved_count(username)
        rating = fetch_contest_rating(username)
        
        # Handle invalid users
        if solved == -1 or rating == -1:
            print(f"  ⚠️ Invalid LeetCode ID detected")
            solved_counts.append('INVALID')
            contest_ratings.append('INVALID')
        else:
            solved_counts.append(solved)
            contest_ratings.append(rating)
            print(f"  → Solved: {solved}, Rating: {rating}")
        
        # Delay between users to avoid rate limits
        time.sleep(0.5)
    
    # Batch update columns D and E
    print("\nUpdating Google Sheet...")
    
    # Prepare data ranges for batch update
    start_row = 2
    end_row = start_row + len(leetcode_ids) - 1
    
    # Update column D (Total Problems Solved)
    solved_range = f'D{start_row}:D{end_row}'
    solved_data = [[count] for count in solved_counts]
    worksheet.update(solved_range, solved_data)
    
    # Update column E (Contest Rating)
    rating_range = f'E{start_row}:E{end_row}'
    rating_data = [[rating] for rating in contest_ratings]
    worksheet.update(rating_range, rating_data)
    
    print(f"✓ Successfully updated {len(leetcode_ids)} users!")


if __name__ == '__main__':
    update_leetcode_stats()
