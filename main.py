#!/usr/bin/env python3
"""
LeetCode Fraud Detector - Main Entry Point

Orchestrates the contest verification pipeline:
1. Load configuration
2. Fetch contest problems
3. Read student data from Google Sheets
4. Evaluate each student's submissions
5. Write results back to Google Sheets
"""

import argparse
import json
import logging
import sys
from typing import Dict, List

from contest_fetcher import fetch_contest_problems
from submissions_parser import evaluate_student_submissions
from sheets_handler import SheetsHandler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = 'config.json') -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        sys.exit(1)


def validate_config(config: Dict) -> None:
    """Validate required configuration fields."""
    required_fields = [
        'sheet_id', 'sheet_name', 'service_account_file',
        'contest_slug', 'contest_display_name',
        'contest_start_ts', 'contest_end_ts'
    ]
    
    missing_fields = [field for field in required_fields if field not in config]
    
    if missing_fields:
        logger.error(f"Missing required configuration fields: {', '.join(missing_fields)}")
        sys.exit(1)
    
    logger.info("Configuration validation passed")


def run_pipeline(config: Dict, dry_run: bool = False) -> None:
    """
    Execute the full fraud detection pipeline.
    
    Args:
        config: Configuration dictionary
        dry_run: If True, simulate without writing to sheet
    """
    logger.info("=" * 70)
    logger.info("LeetCode Fraud Detector Pipeline Starting")
    logger.info("=" * 70)
    
    # Extract configuration
    contest_slug = config['contest_slug']
    contest_display_name = config['contest_display_name']
    contest_start_ts = config['contest_start_ts']
    contest_end_ts = config['contest_end_ts']
    
    logger.info(f"Contest: {contest_display_name} ({contest_slug})")
    logger.info(f"Time window: {contest_start_ts} - {contest_end_ts}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    logger.info("-" * 70)
    
    # Step 1: Fetch contest problems
    logger.info("Step 1: Fetching contest problems...")
    manual_problems = config.get('contest_problems')
    
    # If no manual problems provided, fetch from API
    if not manual_problems:
        contest_problems = fetch_contest_problems(contest_slug, manual_problems)
        
        if not contest_problems:
            logger.error("No contest problems found. Aborting.")
            sys.exit(1)
        
        logger.info(f"Found {len(contest_problems)} problems: {', '.join(contest_problems)}")
    else:
        contest_problems = manual_problems
        logger.info(f"Using {len(contest_problems)} manually configured problems: {', '.join(contest_problems)}")
    
    logger.info("-" * 70)
    
    # Step 2: Initialize sheets handler and read student data
    logger.info("Step 2: Reading student data from Google Sheets...")
    sheets_handler = SheetsHandler(
        sheet_id=config['sheet_id'],
        sheet_name=config['sheet_name'],
        service_account_file=config['service_account_file']
    )
    
    students = sheets_handler.read_students()
    logger.info(f"Loaded {len(students)} students from sheet")
    logger.info("-" * 70)
    
    # Step 3: Process each student
    logger.info("Step 3: Evaluating student submissions...")
    results = []
    stats = {'N/A': 0, '0': 0, 'solved': {}}
    
    for idx, student in enumerate(students, 1):
        name = student['name']
        leetcode_id = student['leetcode_id']
        
        logger.info(f"[{idx}/{len(students)}] Processing: {name} ({leetcode_id})")
        
        # Evaluate student submissions using official contest metadata
        # The function will automatically fetch start_time and duration from LeetCode API
        result = evaluate_student_submissions(
            leetcode_id=leetcode_id,
            contest_slug=contest_slug,
            contest_problems=contest_problems,
            contest_start_ts=contest_start_ts,
            contest_end_ts=contest_end_ts
        )
        
        results.append(result)
        
        # Update statistics
        if result == 'N/A':
            stats['N/A'] += 1
        elif result == '0':
            stats['0'] += 1
        else:
            solved_count = int(result)
            stats['solved'][solved_count] = stats['solved'].get(solved_count, 0) + 1
        
        logger.info(f"  Result: {result}")
    
    logger.info("-" * 70)
    
    # Step 4: Write results to sheet
    if dry_run:
        logger.info("Step 4: DRY RUN - Results that would be written:")
        for idx, (student, result) in enumerate(zip(students, results), 1):
            logger.info(f"  Row {idx + 1}: {student['name']} -> {result}")
    else:
        logger.info("Step 4: Writing results to Google Sheets...")
        sheets_handler.write_contest_results(
            contest_display_name=contest_display_name,
            results=results
        )
        logger.info("Results written successfully")
    
    logger.info("-" * 70)
    
    # Step 5: Print summary
    logger.info("Pipeline Summary:")
    logger.info(f"  Total students processed: {len(students)}")
    logger.info(f"  N/A (no submissions): {stats['N/A']}")
    logger.info(f"  0 (attempted, none accepted): {stats['0']}")
    
    if stats['solved']:
        logger.info("  Solved distribution:")
        for count in sorted(stats['solved'].keys()):
            logger.info(f"    {count} problem(s) solved: {stats['solved'][count]} students")
    
    logger.info("=" * 70)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 70)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='LeetCode Fraud Detector - Verify student contest participation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --dry-run    # Test without writing to sheet
  python main.py              # Run full pipeline and update sheet
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run pipeline without writing to Google Sheets (test mode)'
    )
    
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    
    args = parser.parse_args()
    
    # Load and validate configuration
    config = load_config(args.config)
    validate_config(config)
    
    # Run the pipeline
    try:
        run_pipeline(config, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
