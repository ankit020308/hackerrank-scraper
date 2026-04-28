# HackerRank Solved Problems Scraper

A powerful automation tool that extracts your solved problems from HackerRank, enriches them with difficulty data, and generates beautiful, structured reports in **Excel** and **PDF** formats.

## Features

- **Automated Extraction**: Fetches all your accepted submissions directly from the HackerRank API.
- **Difficulty Enrichment**: Automatically maps challenges to their difficulty levels (Medium, Hard, Expert, Advanced).
- **Beautiful Exports**:
  - **Excel (.xlsx)**: Color-coded by difficulty, formatted with links to the problems.
  - **PDF**: Professional document layout for easy sharing or printing.
- **Cookie Authentication**: Simple and secure session verification.

## Project Structure

```
├── .gitignore
├── README.md
├── debug_login.py          # Utility to verify your HackerRank session
└── hackerrank_scraper.py   # Core scraper logic and report generator
```

## Setup & Installation

1. **Clone the repository** (if applicable)
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   *(Note: Ensure you have `requests`, `openpyxl`, and `reportlab` installed.)*

## How to Use

### 1. Get your HackerRank Cookie

To authenticate, the script requires your active HackerRank session cookie:

1. Log in to [hackerrank.com](https://www.hackerrank.com) in your browser.
2. Open Developer Tools (`F12` or `Cmd+Option+I`).
3. Go to the **Network** tab and refresh the page.
4. Click on any request to `hackerrank.com`.
5. Scroll to **Request Headers** and copy the value of the `cookie:` field.

### 2. Verify Login (Optional)

You can verify your session before scraping:

1. Save your cookie string in a file named `cookie.txt` in the project root.
2. Run the verification script:
   ```bash
   python debug_login.py
   ```

### 3. Run the Scraper

Execute the main script:

```bash
python hackerrank_scraper.py
```

Paste your cookie string when prompted. The script will generate `hackerrank_solved.xlsx` and `hackerrank_solved.pdf`.

## License

This project is open-source and available under the [MIT License](LICENSE).
