"""
Sheets Handler - Google Sheets read/write operations

Manages reading student data and writing contest results to Google Sheets.
Implements idempotent column insertion (reuses existing column if present).
"""

import logging
import os
from typing import List, Dict, Optional

import gspread
from google.oauth2.service_account import Credentials


logger = logging.getLogger(__name__)

# Google Sheets API scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


class SheetsHandler:
    """Handle all Google Sheets operations."""
    
    def __init__(self, sheet_id: str, sheet_name: str, service_account_file: str):
        """
        Initialize sheets handler with credentials.
        Supports both local file and environment variable for cloud deployment.
        
        Args:
            sheet_id: Google Sheet ID (from URL)
            sheet_name: Name of the sheet tab (e.g., "Real data Leetcode")
            service_account_file: Path to service account JSON file (used locally)
        """
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.service_account_file = service_account_file
        
        # Initialize Google Sheets client
        logger.info("Authenticating with Google Sheets API...")
        
        # Check if running in cloud (environment variable exists)
        service_json_env = os.getenv('SERVICE_JSON')
        
        if service_json_env:
            # Running in cloud - use environment variable
            logger.info("Using SERVICE_JSON from environment variable")
            import json
            credentials_dict = json.loads(service_json_env)
            self.credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=SCOPES
            )
        else:
            # Running locally - use file
            logger.info("Using service account file from disk")
            if not os.path.exists(service_account_file):
                raise FileNotFoundError(
                    f"Service account file not found: {service_account_file}\n"
                    "Please create this file with your Google service account credentials."
                )
            self.credentials = Credentials.from_service_account_file(
                service_account_file,
                scopes=SCOPES
            )
        
        self.client = gspread.authorize(self.credentials)
        
        # Open the spreadsheet and worksheet
        logger.info(f"Opening spreadsheet: {sheet_id}")
        self.spreadsheet = self.client.open_by_key(sheet_id)
        self.worksheet = self.spreadsheet.worksheet(sheet_name)
        logger.info(f"Connected to sheet: {sheet_name}")
    
    def read_students(self) -> List[Dict[str, str]]:
        """
        Read student data from the sheet.
        
        Expected format:
        - Column A (index 0): Reg.No
        - Column B (index 1): Name
        - Column C (index 2): Leet Code ID
        - Row 1 is header (skipped)
        
        Returns:
            List of dictionaries with keys 'name' and 'leetcode_id'
        """
        logger.info("Reading student data from sheet...")
        
        # Get all values from the sheet
        all_values = self.worksheet.get_all_values()
        
        if not all_values:
            logger.warning("Sheet is empty")
            return []
        
        # Skip header row (index 0)
        data_rows = all_values[1:]
        
        students = []
        for idx, row in enumerate(data_rows, start=2):  # Start at row 2 (after header)
            # Ensure row has at least 3 columns
            if len(row) < 3:
                logger.warning(f"Row {idx} has insufficient columns, skipping")
                continue
            
            name = row[1].strip()  # Column B: Name
            leetcode_id = row[2].strip()  # Column C: Leet Code ID
            
            # Skip empty rows
            if not name and not leetcode_id:
                continue
            
            if not leetcode_id:
                logger.warning(f"Row {idx}: Missing LeetCode ID for {name}, skipping")
                continue
            
            students.append({
                'name': name,
                'leetcode_id': leetcode_id,
                'row': idx  # Store row number for reference
            })
        
        logger.info(f"Read {len(students)} students from sheet")
        return students
    
    def find_or_create_contest_column(self, contest_display_name: str) -> int:
        """
        Find existing contest column or create a new one.
        
        Args:
            contest_display_name: Display name for the contest (e.g., "Weekly Contest - 478")
        
        Returns:
            Column index (1-based) where results should be written
        """
        # Get header row
        header_row = self.worksheet.row_values(1)
        
        # Check if contest column already exists
        try:
            col_index = header_row.index(contest_display_name) + 1  # 1-based index
            logger.info(f"Found existing contest column at index {col_index}: '{contest_display_name}'")
            return col_index
        except ValueError:
            pass
        
        # Contest column doesn't exist - create new column at the end
        num_cols = len(header_row)
        new_col_index = num_cols + 1
        
        logger.info(f"Creating new contest column at index {new_col_index}: '{contest_display_name}'")
        
        # Write header to new column
        self.worksheet.update_cell(1, new_col_index, contest_display_name)
        
        return new_col_index
    
    def write_contest_results(self, contest_display_name: str, results: List[str], students: List[Dict] = None) -> None:
        """
        Write contest results to the sheet (idempotent).
        
        Args:
            contest_display_name: Display name for the contest column
            results: List of results (one per student, in order)
            students: Optional list of student dicts with 'row' field for exact row placement
        """
        logger.info(f"Writing results for contest: {contest_display_name}")
        
        # Find or create the contest column
        col_index = self.find_or_create_contest_column(contest_display_name)
        
        # Convert column index to letter (A, B, C, ... AA, AB, ...)
        col_letter = self._col_index_to_letter(col_index)
        
        if students and len(students) == len(results):
            # Write to exact rows using student row numbers
            # Build batch update with specific cells
            cells_to_update = []
            for student, result in zip(students, results):
                row_num = student['row']
                cells_to_update.append({
                    'range': f"{col_letter}{row_num}",
                    'values': [[result]]
                })
            
            logger.info(f"Writing {len(results)} results to column {col_letter} (row-aligned)")
            
            # Batch update all cells
            self.worksheet.batch_update(cells_to_update)
        else:
            # Fallback: Write sequentially starting from row 2
            start_row = 2
            end_row = start_row + len(results) - 1
            range_name = f"{col_letter}{start_row}:{col_letter}{end_row}"
            values = [[result] for result in results]
            
            logger.info(f"Writing {len(results)} results to range {range_name}")
            self.worksheet.update(range_name, values)
        
        logger.info("Results written successfully")
    
    @staticmethod
    def _col_index_to_letter(col_index: int) -> str:
        """
        Convert column index (1-based) to letter(s).
        
        Examples:
            1 -> A
            26 -> Z
            27 -> AA
            52 -> AZ
        """
        result = ""
        while col_index > 0:
            col_index -= 1
            result = chr(col_index % 26 + ord('A')) + result
            col_index //= 26
        return result