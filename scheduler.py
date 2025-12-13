"""
Contest Scheduler - Automated trigger at specific times

Runs the fraud detection pipeline automatically:
- Daily Stats Update: Every day at 12:00 PM IST (6:30 AM UTC / 1:30 AM US East)
- Weekly Contest: Every Sunday 9:34 AM IST (4:04 AM UTC / 11:04 PM Saturday US East)
- Biweekly Contest: Every alternate Saturday 9:34 PM IST (4:04 PM UTC / 11:04 AM US East)

Note: Railway deployment uses US East (Virginia) timezone = UTC-5
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
import subprocess
import sys

from contest_detector import get_recent_contests
from contest_fetcher import fetch_contest_problems
from submissions_parser import evaluate_student_submissions
from sheets_handler import SheetsHandler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
class ContestStatusTracker:
    """Track which contests have been processed to prevent duplicates."""
    def __init__(self, status_file: str = "contest_status.json"):
        self.status_file = Path(status_file)
        self.status = self._load_status()
    
    def _load_status(self) -> Dict:
        """Load existing status from disk."""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load status file: {e}")
                return {"processed_contests": {}}
        return {"processed_contests": {}}
    
    def _save_status(self):
        """Save status to disk."""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save status file: {e}")
    
    def is_processed(self, contest_slug: str) -> bool:
        """Check if contest has already been processed."""
        return contest_slug in self.status['processed_contests']
    
    def is_stats_updated_today(self) -> bool:
        """Check if daily stats have been updated today."""
        last_update = self.status.get('last_stats_update', '')
        today = datetime.now().strftime('%Y-%m-%d')
        return last_update == today
    
    def mark_stats_updated(self):
        """Mark daily stats as updated for today."""
        today = datetime.now().strftime('%Y-%m-%d')
        self.status['last_stats_update'] = today
        self._save_status()
        logger.info(f"Marked stats updated for {today}")
    
    def mark_processed(self, contest_slug: str, timestamp: int = None):
        """Mark contest as processed."""
        if timestamp is None:
            timestamp = int(time.time())
        
        self.status['processed_contests'][contest_slug] = {
            'processed_at': timestamp,
            'processed_time': datetime.fromtimestamp(timestamp).isoformat()
        }
        self._save_status()
        logger.info(f"Marked {contest_slug} as processed")


class ContestScheduler:
    """Schedule and run contest processing at specific times."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize scheduler.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.status_tracker = ContestStatusTracker()
    
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def get_current_time_ist(self) -> datetime:
        """Get current time in IST, accounting for Railway's timezone."""
        # Railway servers run on US East (UTC-5 or UTC-4 during DST)
        # To get IST time: convert local time to UTC, then add IST offset
        now_local = datetime.now()
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        return now_ist.replace(tzinfo=None)  # Remove timezone for comparison
    
    def is_weekly_trigger_time(self) -> bool:
        """
        Check if current time is weekly contest trigger time.
        Weekly: Sunday 9:34 AM IST (4 minutes after 9:30 AM contest end)
        """
        now_ist = self.get_current_time_ist()
        
        # Check if it's Sunday (weekday 6)
        if now_ist.weekday() != 6:
            return False
        
        # Check if it's between 9:34 AM and 9:35 AM IST
        if now_ist.hour == 9 and 34 <= now_ist.minute <= 35:
            return True
        
        return False
    
    def is_biweekly_trigger_time(self) -> bool:
        """
        Check if current time is biweekly contest trigger time.
        Biweekly: Saturday 9:34 PM IST (4 minutes after 9:30 PM contest end)
        Only triggers on alternate Saturdays when biweekly contest actually happens.
        """
        now_ist = self.get_current_time_ist()
        
        # Check if it's Saturday (weekday 5)
        if now_ist.weekday() != 5:
            return False
        
        # Check if it's between 9:34 PM and 9:35 PM IST
        if now_ist.hour == 21 and 34 <= now_ist.minute <= 35:
            # Check if there's actually a biweekly contest today by checking recent contests
            try:
                recent = get_recent_contests()
                biweekly = recent.get('biweekly')
                if biweekly:
                    # Check if the biweekly contest ended recently (within last 2 hours)
                    contest_end = biweekly.get('end_time', 0)
                    time_since_end = time.time() - contest_end
                    # Should be between 4 minutes and 2 hours after contest end
                    if 240 <= time_since_end <= 7200:  # 4 min to 2 hours
                        return True
            except Exception as e:
                logger.error(f"Error checking biweekly contest: {e}")
            return False
        
        return False
    
    def is_daily_stats_trigger_time(self) -> bool:
        """
        Check if current time is daily stats update trigger time.
        Daily: 12:00 PM IST (noon) - updates total problems solved and contest rating
        """
        now_ist = self.get_current_time_ist()
        
        # Check if it's between 12:00 PM and 12:01 PM IST
        if now_ist.hour == 12 and 0 <= now_ist.minute <= 1:
            # Check if not already updated today
            if not self.status_tracker.is_stats_updated_today():
                return True
        
        return False
    def process_contest(self, contest: Dict) -> bool:
        """
        Process a single contest.
        
        Args:
            contest: Contest information dictionary with keys:
                - slug: Contest slug
                - title: Contest display name
                - start_time: Unix timestamp
                - end_time: Unix timestamp
                - problems: List of problem slugs
        Returns:
            True if processing was successful
        """
        slug = contest['slug']
        title = contest['title']
        start_time = contest['start_time']
        end_time = contest['end_time']
        problems = contest.get('problems', [])
        # Check if already processed
        if self.status_tracker.is_processed(slug):
            logger.info(f"{slug} already processed today. Skipping.")
            return False
        
        logger.info("=" * 70)
        logger.info(f"PROCESSING CONTEST: {title}")
        logger.info(f"Contest Slug: {slug}")
        logger.info(f"Time Window: {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}")
        logger.info("=" * 70)
        
        try:
            # Step 1: Fetch contest problems if not provided
            if not problems:
                logger.info("Step 1: Fetching contest problems...")
                problems = fetch_contest_problems(slug)
                
                if not problems:
                    logger.error(f"No problems found for {slug}")
                    return False
                
            logger.info(f"Found {len(problems)} problems: {', '.join(problems)}")
            
            # Step 2: Read student data
            logger.info("Step 2: Reading student data from Google Sheets...")
            sheet_id = self.config.get('sheet_id')
            sheet_name = self.config.get('sheet_name')
            service_account_file = self.config.get('service_account_file')
            
            if not all([sheet_id, sheet_name, service_account_file]):
                logger.error("Missing Google Sheets configuration in config.json")
                return False
            
            sheets = SheetsHandler(sheet_id, sheet_name, service_account_file)
            students = sheets.read_students()
            logger.info(f"Loaded {len(students)} students from sheet")
            
            # Step 3: Evaluate submissions
            logger.info("Step 3: Evaluating student submissions...")
            results = []
            results_dict = {}
            stats = {'N/A': 0, '0': 0, 'INVALID ID': 0, 'solved': {}}
            
            for idx, student in enumerate(students, 1):
                name = student['name']
                leetcode_id = student['leetcode_id']
                
                logger.info(f"[{idx}/{len(students)}] Processing: {name} ({leetcode_id})")
                
                result = evaluate_student_submissions(
                    leetcode_id=leetcode_id,
                    contest_slug=slug,
                    contest_problems=problems,
                    contest_start_ts=start_time,
                    contest_end_ts=end_time
                )
                
                results.append(result)
                results_dict[leetcode_id] = result
                
                # Update statistics
                if result == 'N/A':
                    stats['N/A'] += 1
                elif result == '0':
                    stats['0'] += 1
                elif result == 'INVALID ID':
                    stats['INVALID ID'] += 1
                else:
                    solved_count = int(result)
                    stats['solved'][solved_count] = stats['solved'].get(solved_count, 0) + 1
                
                logger.info(f"  Result: {result}")
                
                # Add small delay between students to prevent rate limiting
                if idx < len(students):
                    time.sleep(0.5)
            
            # Step 4: Write results to Google Sheets
            logger.info("Step 4: Writing results to Google Sheets...")
            sheets.write_contest_results(title, results, students)  # Pass students for row-aligned writing
            logger.info("Results written successfully to Google Sheets")
            
            # Print summary
            logger.info("-" * 70)
            logger.info("Processing Summary:")
            logger.info(f"  Total students: {len(students)}")
            logger.info(f"  N/A (no submissions): {stats['N/A']}")
            logger.info(f"  0 (attempted, none accepted): {stats['0']}")
            logger.info(f"  INVALID ID: {stats['INVALID ID']}")
            if stats['solved']:
                logger.info("  Solved distribution:")
                for count in sorted(stats['solved'].keys()):
                    logger.info(f"    {count} problem(s): {stats['solved'][count]} students")
            
            # Mark as processed
            self.status_tracker.mark_processed(slug)
            
            # Save backup
            self._save_results_backup(slug, title, results_dict)
            
            logger.info("=" * 70)
            logger.info(f"✅ Successfully processed {slug}")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to process {slug}: {e}", exc_info=True)
            return False
    
    def _save_results_backup(self, slug: str, title: str, results: Dict):
        """Save results to JSON file as backup."""
        backup_dir = Path("results_backup")
        backup_dir.mkdir(exist_ok=True)
        
        backup_file = backup_dir / f"{slug}_{int(time.time())}.json"
        
        try:
            with open(backup_file, 'w') as f:
                json.dump({
                    'contest_slug': slug,
                    'contest_title': title,
                    'processed_at': datetime.now().isoformat(),
                    'results': results
                }, f, indent=2)
            logger.info(f"Saved backup to {backup_file}")
        except Exception as e:
            logger.error(f"Failed to save backup: {e}")
    
    def try_process_weekly(self):
        """Try to process weekly contest if it's trigger time."""
        if not self.is_weekly_trigger_time():
            return
        
        logger.info("🎯 Weekly contest trigger time detected!")
        
        try:
            # Get most recent weekly contest
            recent = get_recent_contests()
            weekly = recent.get('weekly')
            
            if not weekly:
                logger.warning("No recent weekly contest found")
                return
            
            # Process the contest
            self.process_contest(weekly)
            
        except Exception as e:
            logger.error(f"Error processing weekly contest: {e}", exc_info=True)
    
    def try_process_biweekly(self):
        """Try to process biweekly contest if it's trigger time."""
        if not self.is_biweekly_trigger_time():
            return
        
        logger.info("🎯 Biweekly contest trigger time detected!")
        
        try:
            # Get most recent biweekly contest
            recent = get_recent_contests()
            biweekly = recent.get('biweekly')
            
            if not biweekly:
                logger.warning("No recent biweekly contest found")
                return
            
            # Process the contest
            self.process_contest(biweekly)
            
        except Exception as e:
            logger.error(f"Error processing biweekly contest: {e}", exc_info=True)
    
    def try_update_daily_stats(self):
        """Try to update daily stats if it's trigger time."""
        if not self.is_daily_stats_trigger_time():
            return
        
        logger.info("📊 Daily stats update trigger time detected!")
        
        try:
            # Run update_stats.py
            logger.info("Running update_stats.py to update LeetCode statistics...")
            result = subprocess.run(
                [sys.executable, 'update_stats.py'],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode == 0:
                logger.info("✅ Daily stats updated successfully!")
                logger.info(f"Output: {result.stdout}")
                self.status_tracker.mark_stats_updated()
            else:
                logger.error(f"❌ Stats update failed with code {result.returncode}")
                logger.error(f"Error: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            logger.error("Stats update timed out after 10 minutes")
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}", exc_info=True)
    
    def run(self):
        """
        Run the scheduler continuously.
        Checks every minute for trigger times.
        """
        logger.info("=" * 70)
        logger.info("LEETCODE CONTEST SCHEDULER STARTED")
        logger.info("=" * 70)
        logger.info("Schedule (IST):")
        logger.info("  Daily Stats Update: Every day at 12:00 PM (noon)")
        logger.info("  Weekly Contest:     Every Sunday at 9:34 AM")
        logger.info("  Biweekly Contest:   Every alternate Saturday at 9:34 PM")
        logger.info("=" * 70)
        logger.info(f"Server Local Time: {datetime.now()}")
        logger.info(f"IST Time: {self.get_current_time_ist()}")
        logger.info("Monitoring for trigger times...")
        logger.info("=" * 70)
        
        while True:
            try:
                now = datetime.now()
                
                # Check every minute
                if now.second < 10:  # Only check in first 10 seconds of each minute
                    self.try_update_daily_stats()
                    self.try_process_weekly()
                    self.try_process_biweekly()
                
                # Sleep for 50 seconds to avoid duplicate checks in same minute
                time.sleep(50)
                
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in scheduler: {e}", exc_info=True)
                logger.info("Continuing after error...")
                time.sleep(60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='LeetCode Contest Scheduler - Auto-trigger at specific times'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to config file (default: config.json)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process latest contests immediately'
    )
    
    args = parser.parse_args()
    
    scheduler = ContestScheduler(config_path=args.config)
    
    if args.test:
        logger.info("TEST MODE: Processing latest contests now...")
        recent = get_recent_contests()
        
        if recent['weekly']:
            logger.info("Processing weekly contest...")
            scheduler.process_contest(recent['weekly'])
        
        if recent['biweekly']:
            logger.info("Processing biweekly contest...")
            scheduler.process_contest(recent['biweekly'])
    else:
        scheduler.run()


if __name__ == '__main__':
    main()
