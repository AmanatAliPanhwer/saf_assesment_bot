# SAF Assessment Bot

A powerful automation tool for the SEF Assessment Portal. This Streamlit web application automates the process of entering student assessment results from an Excel file into the EMIS web form using Playwright.

## Features

- **Streamlit Interface**: Easy-to-use web interface for uploading data and monitoring progress.
- **Excel Automation**: Bulk entry of marks for multiple subjects from a single Excel file.
- **Smart Form Handling**:
  - Auto-selects students by GR Number.
  - Automatically identifies subject columns.
  - Fills "Presence Status" and "B Form Number" conditionally.
  - Includes a "Result Entered By" field that can be set globally or overridden per student.
- **Error Handling & Logging**: Detailed logging of every operation in `process_log.txt`.
- **Headless Options**: Uses Playwright for reliable browser automation.

## Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AmanatAliPanhwer/saf_assesment_bot.git
    cd saf_assesment_bot
    ```

2.  **Install dependencies:**
    Make sure you have [uv](https://github.com/astral-sh/uv) installed. Then, run the following command to install the project dependencies:
    ```bash
    uv sync
    ```

3.  **Install Playwright browser:**
    Playwright requires a browser for automation. Install Chromium using:
    ```bash
    uv run playwright install chromium
    ```

## How to Run

To start the Streamlit application:

```bash
uv run streamlit run app.py
```

The application will be available at `http://localhost:8501`.

## Required Excel Format

The application expects an Excel file (`.xlsx`) with specific headers. You can download a **template file** directly from the application's interface.

### Expected Columns:
- `GR NO` (Required: Primary identifier for student selection)
- `English` (Max 100)
- `Mathematics` (Max 100)
- `Science` (Max 100)
- `Sindhi / Urdu` (Max 40)
- `Islamiat` (Max 30)
- `Social Studies` (Max 30)
- `Presence Status` (Optional: present/absent/dropout)
- `B Form Number` (Optional: Added if the field on the portal is empty)
- `Result Entered By` (Optional: Name of the person entereing marks)

## Logging and Troubleshooting

- The bot creates a detailed log file named `process_log.txt` in the root directory.
- If a student's data cannot be processed, the error code and reason will be logged there.
- Common error codes:
  - `E001`: Login Failed
  - `E004`: Student Select Error (GR Number not found)
  - `E007`: Submit Error
- **Note**: The bot currently runs in non-headless mode (browser window visible) so you can monitor the automation in real-time.
