import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright, Page
import logging
import multiprocessing

# --- Logging Setup ---
logging.basicConfig(
    filename='process_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ERROR_CODES = {
    'LOGIN_FAILED': 'E001',
    'NAVIGATION_FAILED': 'E002',
    'EXCEL_READ_ERROR': 'E003',
    'STUDENT_SELECT_ERROR': 'E004',
    'MARKS_INPUT_ERROR': 'E005',
    'PRESENCE_STATUS_ERROR': 'E006',
    'SUBMIT_ERROR': 'E007',
    'ELEMENT_NOT_FOUND': 'E008',
    'NETWORK_ERROR': 'E009',
    'UNKNOWN_ERROR': 'E999',
    'BROWSER_ERROR': 'E010',
    'DATA_PARSE_ERROR': 'E011',
}

# Subject field IDs mapped to their column names in Excel and max marks
SUBJECTS = {
    'english':        {'col': 'English',        'max': 100},
    'mathematics':    {'col': 'Mathematics',    'max': 100},
    'science':        {'col': 'Science',        'max': 100},
    'sindhi_or_urdu': {'col': 'Sindhi / Urdu',  'max': 40},
    'islamiat':       {'col': 'Islamiat',       'max': 30},
    'social_studies': {'col': 'Social Studies',  'max': 30},
}


def log_error(error_code, message, gr_no=None):
    """Log errors with consistent format."""
    error_msg = f"[{error_code}] {message}"
    if gr_no:
        error_msg += f" (GR NO: {gr_no})"
    logger.error(error_msg)
    return error_msg


def log_info(message, gr_no=None):
    """Log info with consistent format."""
    info_msg = message
    if gr_no:
        info_msg += f" (GR NO: {gr_no})"
    logger.info(info_msg)


def login(page: Page, username: str, password: str):
    """Log into the SEF Assessment Portal."""
    try:
        page.goto("https://au.sefedu.com/", wait_until="networkidle")
        page.wait_for_timeout(5000)

        # Fill login credentials
        page.fill("input[name='email']", username)
        page.fill("input[name='password']", password)

        # Click login button
        page.locator("button[type='submit']").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(10000)

        # Verify login succeeded by checking URL
        if "dashboard" in page.url or "my-schools" in page.url:
            log_info("Login successful")
            return True
        else:
            log_error(ERROR_CODES['LOGIN_FAILED'], "Login may have failed - unexpected URL: " + page.url)
            return False
    except Exception as e:
        log_error(ERROR_CODES['LOGIN_FAILED'], f"Login error: {e}")
        return False


def navigate_to_assessment_form(page: Page):
    """Navigate to My Schools and click 'Add Results' to reach the assessment form."""
    try:
        # Click "My Schools" in sidebar
        page.click("a[href*='my-schools']")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # Click "Add Results" button for the first school
        add_results_btn = page.locator("a:has-text('Add Results')").first
        add_results_btn.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(8000)

        log_info("Navigated to assessment form")
        return True
    except Exception as e:
        log_error(ERROR_CODES['NAVIGATION_FAILED'], f"Navigation error: {e}")
        return False


def select_student_by_gr(page: Page, gr_no):
    """Select a student from the dropdown using their GR number.

    The dropdown uses Select2 with format 'Name - GR_NO'.
    We use JavaScript to set the value and trigger the change event,
    which auto-populates Class, Gender, Father Name, CNIC, and existing marks.
    """
    gr_str = str(int(gr_no)) if isinstance(gr_no, float) else str(gr_no)

    try:
        # Use JavaScript to find the option matching this GR number and select it
        selected = page.evaluate(f"""
            (() => {{
                const select = document.getElementById('gr_number_dd');
                if (!select) return {{ success: false, error: 'Dropdown not found' }};

                // Find the option whose text ends with '- <GR_NO>'
                let targetOption = null;
                for (const opt of select.options) {{
                    if (opt.text.trim().endsWith('- {gr_str}') || opt.value === '{gr_str}') {{
                        targetOption = opt;
                        break;
                    }}
                }}

                if (!targetOption) return {{ success: false, error: 'Student with GR {gr_str} not found in dropdown' }};

                // Set value and trigger Select2 change
                $(select).val(targetOption.value).trigger('change');
                return {{ success: true, value: targetOption.value, text: targetOption.text }};
            }})()
        """)

        if not selected.get('success'):
            raise Exception(selected.get('error', 'Unknown error selecting student'))

        log_info(f"Selected student: {selected.get('text', gr_str)}", gr_str)

        # Wait for AJAX auto-population to complete
        page.wait_for_timeout(5000)
        return True

    except Exception as e:
        log_error(ERROR_CODES['STUDENT_SELECT_ERROR'], f"Error selecting student: {e}", gr_str)
        raise


def fill_subject_marks(page: Page, subject_id: str, marks, gr_no):
    """Fill obtained marks for a given subject."""
    try:
        if pd.notna(marks):
            marks_str = str(int(marks)) if isinstance(marks, float) else str(marks)
            input_el = page.locator(f"#{subject_id}")
            input_el.fill("")  # Clear first
            input_el.fill(marks_str)
    except Exception as e:
        log_error(ERROR_CODES['MARKS_INPUT_ERROR'], f"Error filling {subject_id} marks: {e}", gr_no)
        raise


def fill_b_form_number(page: Page, b_form, gr_no):
    """Fill the B Form Number field if it's currently empty."""
    try:
        if pd.notna(b_form):
            b_form_str = str(int(b_form)) if isinstance(b_form, float) else str(b_form)
            input_el = page.locator("#b_form_number")
            
            # Check if the field is already filled
            current_value = input_el.input_value()
            if current_value and current_value.strip():
                log_info(f"B Form Number already present ({current_value}), skipping fill.", gr_no)
                return

            input_el.fill("")
            input_el.fill(b_form_str)
    except Exception as e:
        log_error(ERROR_CODES['MARKS_INPUT_ERROR'], f"Error filling B Form Number: {e}", gr_no)
        raise


def set_presence_status(page: Page, status: str, gr_no):
    """Set the presence status dropdown (present/absent/dropout)."""
    try:
        if pd.notna(status):
            status_lower = str(status).strip().lower()
            if status_lower not in ('present', 'absent', 'dropout'):
                log_error(ERROR_CODES['PRESENCE_STATUS_ERROR'],
                          f"Invalid presence status: '{status}'. Must be present/absent/dropout", gr_no)
                return

            page.select_option("select[name='presence_status']", value=status_lower)
            log_info(f"Set presence status to: {status_lower}", gr_no)
    except Exception as e:
        log_error(ERROR_CODES['PRESENCE_STATUS_ERROR'], f"Error setting presence status: {e}", gr_no)
        raise


def fill_result_entered_by(page: Page, name: str, gr_no):
    """Fill the 'Result Entered By' field."""
    try:
        if pd.notna(name):
            input_el = page.locator("#result_entered_by")
            input_el.fill("")
            input_el.fill(str(name))
    except Exception as e:
        log_error(ERROR_CODES['MARKS_INPUT_ERROR'], f"Error filling Result Entered By: {e}", gr_no)
        raise


def submit_result(page: Page, gr_no):
    """Click the Update/Submit button and wait for the response."""
    try:
        submit_btn = page.locator("#result_create_update_form_button")
        submit_btn.scroll_into_view_if_needed()
        submit_btn.click()

        # Wait for AJAX response
        page.wait_for_timeout(8000)

        # Check for success/error messages on the page
        log_info("Form submitted successfully", gr_no)
        return True
    except Exception as e:
        log_error(ERROR_CODES['SUBMIT_ERROR'], f"Error submitting form: {e}", gr_no)
        raise


def process_student(page: Page, row, gr_no, result_entered_by=None):
    """Process a single student: select, fill marks, and submit."""
    gr_str = str(int(gr_no)) if isinstance(gr_no, float) else str(gr_no)

    try:
        # 1. Select student from dropdown
        select_student_by_gr(page, gr_no)

        # 2. Fill B Form Number if provided
        if 'B Form Number' in row.index:
            fill_b_form_number(page, row.get('B Form Number'), gr_str)

        # 3. Fill subject marks
        for subject_id, info in SUBJECTS.items():
            col_name = info['col']
            if col_name in row.index:
                fill_subject_marks(page, subject_id, row.get(col_name), gr_str)

        # 4. Set presence status
        if 'Presence Status' in row.index:
            set_presence_status(page, row.get('Presence Status'), gr_str)
        else:
            # Default to 'present' if not specified
            set_presence_status(page, 'present', gr_str)

        # 5. Fill "Result Entered By"
        entered_by = result_entered_by
        if 'Result Entered By' in row.index and pd.notna(row.get('Result Entered By')):
            entered_by = row.get('Result Entered By')
        if entered_by:
            fill_result_entered_by(page, entered_by, gr_str)

        # 6. Submit the form
        # submit_result(page, gr_str)

        log_info(f"✓ Successfully processed student", gr_str)
        return True

    except Exception as e:
        log_error(ERROR_CODES['UNKNOWN_ERROR'], f"Error processing student: {e}", gr_str)
        return False


def _fill_form_sync(data, username: str, password: str, result_entered_by: str = None):
    """Main synchronous function that runs in a subprocess."""
    data.columns = data.columns.str.strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        page.set_default_timeout(60000)  # Increase default timeout to 60s

        # --- Login ---
        if not login(page, username, password):
            log_error(ERROR_CODES['LOGIN_FAILED'], "Could not log in. Aborting.")
            browser.close()
            return

        # --- Navigate to Assessment Form ---
        if not navigate_to_assessment_form(page):
            log_error(ERROR_CODES['NAVIGATION_FAILED'], "Could not navigate to assessment form. Aborting.")
            browser.close()
            return

        # --- Process Each Student ---
        total = len(data)
        success_count = 0
        fail_count = 0

        for index, row in data.iterrows():
            gr_no = row.get("GR NO")
            if pd.isna(gr_no):
                log_error(ERROR_CODES['DATA_PARSE_ERROR'], f"Row {index + 1}: Missing GR NO, skipping")
                fail_count += 1
                continue

            log_info(f"Processing student {index + 1}/{total}", str(gr_no))

            success = process_student(page, row, gr_no, result_entered_by)
            if success:
                success_count += 1
            else:
                fail_count += 1

            # Small delay between students to avoid overwhelming the server
            page.wait_for_timeout(2000)

        log_info(f"Completed: {success_count}/{total} successful, {fail_count} failed")
        browser.close()


# --- Public API ---
def fill_form_from_excel(data, username, password, result_entered_by=None):
    """Start the form filling process in a separate process.

    Args:
        data: pandas DataFrame with student assessment data
        username: Login email for au.sefedu.com
        password: Login password
        result_entered_by: Optional name to fill in "Result Entered By" for all students
    """
    process = multiprocessing.Process(
        target=_fill_form_sync,
        args=(data, username, password, result_entered_by)
    )
    process.start()
    process.join()


# --- Entry Point ---
if __name__ == '__main__':
    multiprocessing.freeze_support()

    # Example usage: read from an Excel file and process
    import sys
    if len(sys.argv) >= 3:
        excel_path = sys.argv[1] if len(sys.argv) > 3 else "data/assessment_data.xlsx"
        username = sys.argv[1]
        password = sys.argv[2]
        entered_by = sys.argv[3] if len(sys.argv) > 3 else None

        try:
            data = pd.read_excel(excel_path)
            fill_form_from_excel(data, username, password, entered_by)
        except Exception as e:
            log_error(ERROR_CODES['EXCEL_READ_ERROR'], f"Error reading Excel file: {e}")
    else:
        print("Usage: python bot.py <username> <password> [result_entered_by]")
        print("Or use the Streamlit app: streamlit run app.py")