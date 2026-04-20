# eLab Scraper 🧪

A Python-based web scraper for SRM's eLab platform that automatically extracts and compiles your solved programming questions into a comprehensive PDF report.

## Features

- 🔐 **Automated Authentication** — Logs in using your eLab credentials securely
- 🌳 **Recursive Tree Traversal** — Navigates the nested "flare" question tree structure
- 📋 **Question Extraction** — Collects all solved Level 2 & Level 3 problems
- 📄 **PDF Report Generation** — Outputs a clean, formatted PDF of all solved questions

## Requirements

```bash
pip install requests fpdf2
```

## Usage

1. Clone the repository:
   ```bash
   git clone https://github.com/ankit020308/-eLab-Scraper.git
   cd -eLab-Scraper
   ```

2. Run the scraper:
   ```bash
   python elab_scraper.py
   ```

3. Enter your SRM eLab credentials when prompted.

4. The solved questions will be saved as `elab_solved.pdf` in the current directory.

## Output

The script generates a PDF (`elab_solved.pdf`) containing:
- Question titles
- Difficulty levels
- Problem categories

## Disclaimer

This tool is intended for **personal use only** to track your own progress on the eLab platform. Do not use it to violate any terms of service.

---

**Author:** [Ankit Aman](https://github.com/ankit020308)
