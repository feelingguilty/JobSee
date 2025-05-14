#!/usr/bin/env python3
# Single-file script for Job Application Tailoring using Gemini API
# Now tailored for the specific Amritanshu Srivastava LaTeX template
# INCLUDES PDF COMPILATION STEP

import argparse
import requests
from bs4 import BeautifulSoup
import re
import os
import logging
from datetime import datetime
import json
import google.generativeai as genai
from dotenv import load_dotenv
import subprocess  # <<< --- IMPORT SUBPROCESS ---

# --- Configuration Constants ---
# ... (rest of constants remain the same) ...
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LATEX_TEMPLATE_PATH = os.path.join(BASE_DIR, 'templates', 'resume', 'base_resume.tex')
EMAIL_TEMPLATE_PATH = os.path.join(BASE_DIR, 'templates', 'email', 'cold_email_template.txt')
RESUME_OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'resumes')
EMAIL_OUTPUT_DIR = os.path.join(BASE_DIR, 'output', 'emails')
HEADERS = { # ... headers ...
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
LATEX_SUMMARY_PLACEHOLDER = "%<SUMMARY_PLACEHOLDER>%"
LATEX_SKILLS_PLACEHOLDER = "%<SKILLS_LIST_PLACEHOLDER>%"
EMAIL_ROLE_PLACEHOLDER = "{ROLE_TITLE}"
# ... (other email placeholders) ...
EMAIL_COMPANY_PLACEHOLDER = "{COMPANY_NAME}"
EMAIL_KEY_SKILLS_PLACEHOLDER = "{KEY_SKILLS}"
EMAIL_SPECIFIC_JD_POINT_PLACEHOLDER = "[Mention something specific from the JD]"
EMAIL_YOUR_NAME_PLACEHOLDER = "{YOUR_NAME}"
EMAIL_YOUR_CONTACT_PLACEHOLDER = "{YOUR_CONTACT_INFO}"

# --- Logging Setup ---
# ... (logging setup remains the same) ...
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- API Key Setup ---
# ... (API key setup remains the same) ...
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY: #... error handling ...
    logging.error("GOOGLE_API_KEY not found...")
    print("Error: GOOGLE_API_KEY is required...")
    exit(1)
try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e: #... error handling ...
    logging.error(f"Failed to configure Gemini API: {e}")
    print(f"Error: Failed to configure Gemini API: {e}")
    exit(1)

# --- Helper Functions ---
# sanitize_filename (same)
# get_clean_text_from_html (same)
def sanitize_filename(filename): # ... same ...
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = sanitized.replace(" ", "_")
    return sanitized[:100]

def get_clean_text_from_html(soup: BeautifulSoup) -> str: # ... same ...
    for script_or_style in soup(["script", "style", "header", "footer", "nav", "aside"]):
        script_or_style.decompose()
    main_content = soup.find('main') or soup.find('article') or soup.find('div', id=re.compile(r'content|main', re.I)) or soup.find('div', class_=re.compile(r'content|main|job-description', re.I))
    if main_content: text = main_content.get_text(separator='\n', strip=True)
    else: text = soup.body.get_text(separator='\n', strip=True) if soup.body else soup.get_text(separator='\n', strip=True)
    text = re.sub(r'\n\s*\n', '\n', text); text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

# --- Core Logic Functions ---
# scrape_url (same)
# extract_data_with_gemini (same)
# modify_latex_template (same)
# generate_email (same)
def scrape_url(url: str) -> tuple[BeautifulSoup | None, str | None]: # ... same ...
    logging.info(f"Attempting to scrape URL: {url}")
    try: # ... same logic ...
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        if 'html' not in content_type: return None, None
        html_content = response.text
        soup = BeautifulSoup(html_content, 'lxml')
        return soup, html_content
    except Exception as e: logging.error(f"Error scraping/parsing {url}: {e}"); return None, None

def extract_data_with_gemini(text_content: str, url: str) -> dict: # ... same ...
    logging.info("Attempting data extraction using Gemini API...")
    default_data = { 'job_title': "Unknown Role (Gemini)", 'company_name': "Unknown Company (Gemini)", 'job_description': "Could not extract Job Description via Gemini.", 'required_skills': [], 'emails': [] }
    max_chars = 15000 # ... same logic ...
    if len(text_content) > max_chars: text_content = text_content[:max_chars] + "\n... [Content Truncated]"
    prompt = f"""... (same prompt as before) ..."""
    try: # ... same logic ...
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # safety_settings = [...]
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.2))
        response_text = response.text.strip()
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL | re.IGNORECASE)
        json_str = json_match.group(1) if json_match else response_text
        extracted_data = json.loads(json_str)
        final_data = default_data.copy(); final_data.update(extracted_data)
        if not isinstance(final_data.get('required_skills'), list): final_data['required_skills'] = []
        if not isinstance(final_data.get('emails'), list): final_data['emails'] = []
        return final_data
    except Exception as e: logging.error(f"Gemini/JSON error: {e}"); return default_data

def modify_latex_template(template_path: str, output_path: str, extracted_data: dict) -> bool:

    logging.info(f"Attempting to modify LaTeX template: {template_path}")
    try:
        # Read the LaTeX template
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        modified_content = template_content

        # --- Summary Section ---
        summary_text = extracted_data.get('job_description', '')
        if not summary_text or len(summary_text) < 30 or summary_text.startswith("Could not extract"):
            summary_text = f"Highly motivated professional seeking the {extracted_data.get('job_title', 'challenging')} position at {extracted_data.get('company_name', 'your esteemed company')}."
        else:
            summary_text = f"Summary based on job description: {summary_text} My background aligns with the requirements of the {extracted_data.get('job_title', 'role')} position."
        summary_text = summary_text.replace('%', '\\%').replace('&', '\\&').replace('_', '\\_')
        modified_content = modified_content.replace(LATEX_SUMMARY_PLACEHOLDER, summary_text)

        # --- Skills Section ---
        skills_list = extracted_data.get('required_skills', [])
        if skills_list:
            skills_latex_items = "\n".join([f"    \\item {skill.replace('%', '\\%').replace('&', '\\&').replace('_', '\\_')}" for skill in skills_list])
        else:
            skills_latex_items = "    \\item No specific skills extracted."
        modified_content = modified_content.replace(LATEX_SKILLS_PLACEHOLDER, skills_latex_items)

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save the modified LaTeX content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        logging.info(f"Successfully modified and saved LaTeX template to {output_path}")
        return True
    except Exception as e:
        logging.error(f"Error modifying/saving LaTeX: {e}")
        return False

def generate_email(template_path: str, extracted_data: dict) -> str | None: # ... same ...
    logging.info(f"Attempting to generate email from template: {template_path}")
    try: # ... same logic ...
        with open(template_path, 'r', encoding='utf-8') as f: email_template = f.read()
        role_title = extracted_data.get('job_title', 'the position')
        company_name = extracted_data.get('company_name', 'your company')
        key_skills_list = extracted_data.get('required_skills', [])
        key_skills_str = ", ".join(key_skills_list[:3]) if key_skills_list else "relevant skills"
        your_name_value = "Amritanshu Srivastava"
        your_contact_value = "amritanshus550@gmail.com | +91-939588293"
        email_text = email_template.format( ROLE_TITLE=role_title, COMPANY_NAME=company_name, KEY_SKILLS=key_skills_str, SPECIFIC_JD_POINT=EMAIL_SPECIFIC_JD_POINT_PLACEHOLDER, YOUR_NAME=your_name_value, YOUR_CONTACT_INFO=your_contact_value )
        return email_text
    except Exception as e: logging.error(f"Error generating email: {e}"); return None


# --- NEW FUNCTION: Compile LaTeX to PDF ---
def compile_latex_to_pdf(tex_filepath: str) -> bool:
    """
    Compiles a .tex file to .pdf using pdflatex.

    Args:
        tex_filepath: The full path to the .tex file.

    Returns:
        True if compilation succeeded (PDF generated), False otherwise.
    """
    if not os.path.exists(tex_filepath):
        logging.error(f"Cannot compile: LaTeX file not found at {tex_filepath}")
        return False

    tex_filename = os.path.basename(tex_filepath)
    output_dir = os.path.dirname(tex_filepath)
    pdf_filename = tex_filename.replace('.tex', '.pdf')
    pdf_filepath = os.path.join(output_dir, pdf_filename)

    # Command to run pdflatex
    # -interaction=nonstopmode: Prevents stopping on minor errors
    # -output-directory: Specifies where output files go (using cwd is often better)
    command = [
        'pdflatex',
        '-interaction=nonstopmode',
        tex_filename  # Just the filename, as we'll run in its directory
    ]

    logging.info(f"Attempting to compile {tex_filename} to PDF in {output_dir}...")
    print(f"Attempting to compile {tex_filename} to PDF...") # User feedback

    try:
        # Run pdflatex command within the directory of the .tex file
        # Capture output and errors
        result = subprocess.run(
            command,
            cwd=output_dir,        # Execute in the directory containing the .tex file
            capture_output=True,   # Capture stdout and stderr
            text=True,             # Decode output as text
            check=False            # Don't raise exception automatically on non-zero exit
        )

        # Check if pdflatex completed successfully (exit code 0)
        if result.returncode != 0:
            logging.error(f"pdflatex failed with exit code {result.returncode}")
            logging.error(f"pdflatex stdout:\n{result.stdout}")
            logging.error(f"pdflatex stderr:\n{result.stderr}")
            print(f"Error: pdflatex failed. Check logs in {output_dir} (e.g., {tex_filename.replace('.tex', '.log')})")
            return False
        else:
            # Double-check if the PDF file was actually created
            if os.path.exists(pdf_filepath):
                logging.info(f"Successfully compiled {tex_filename} to {pdf_filename}")
                # Optional: Clean up auxiliary files (.log, .aux, .out)
                # cleanup_latex_aux_files(output_dir, tex_filename.replace('.tex', ''))
                return True
            else:
                logging.error(f"pdflatex ran successfully but PDF file not found at {pdf_filepath}")
                logging.error(f"pdflatex stdout:\n{result.stdout}") # Log output even on success if PDF missing
                print(f"Error: pdflatex ran but PDF was not generated. Check logs.")
                return False

    except FileNotFoundError:
        logging.error("pdflatex command not found. Is LaTeX installed and in your system's PATH?")
        print("Error: 'pdflatex' command not found. Please ensure a LaTeX distribution is installed and in your PATH.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during LaTeX compilation: {e}")
        print(f"An unexpected error occurred during PDF compilation: {e}")
        return False

# --- Optional Helper: Cleanup Aux Files ---
def cleanup_latex_aux_files(directory: str, base_filename_no_ext: str):
    """Removes common LaTeX auxiliary files."""
    extensions_to_remove = ['.log', '.aux', '.out', '.toc', '.nav', '.snm', '.fls', '.fdb_latexmk']
    logging.info(f"Cleaning up auxiliary files for {base_filename_no_ext} in {directory}...")
    for ext in extensions_to_remove:
        filepath = os.path.join(directory, base_filename_no_ext + ext)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logging.debug(f"Removed {filepath}")
            except Exception as e:
                logging.warning(f"Could not remove auxiliary file {filepath}: {e}")


# --- Main Execution Block (Modified) ---
def main():
    parser = argparse.ArgumentParser(description='Tailor Amritanshu Srivastava LaTeX resume, generate cold email, and compile PDF using Gemini API.') # Updated description
    parser.add_argument('--url', type=str, required=True, help='URL of the job posting.')
    parser.add_argument('--cleanup', action='store_true', help='Remove LaTeX auxiliary files (.log, .aux) after successful compilation.') # Optional cleanup flag
    args = parser.parse_args()

    job_url = args.url
    logging.info(f"--- Starting Job Tailor Process (Gemini/Specific Template/PDF) for URL: {job_url} ---")

    # ... (Steps 1, 2, 3: Scrape, Prepare Text, Extract via Gemini - remain the same) ...
    # Step 1: Scrape
    soup, html_content = scrape_url(job_url)
    if not soup or not html_content: logging.error("Failed scrape/parse."); print("Error: Could not retrieve/parse URL."); return
    # Step 2: Prepare text
    logging.info("Preparing clean text..."); clean_text = get_clean_text_from_html(soup)
    if not clean_text: logging.error("No text extracted."); print("Error: No text found."); return
    # Step 3: Extract via Gemini
    extracted_data = extract_data_with_gemini(clean_text, job_url)
    # Print summary...
    print("\n--- Gemini Extracted Information Summary ---")
    print(f"Job Title: {extracted_data['job_title']}")
    print(f"Company Name: {extracted_data['company_name']}")
    # ... (rest of summary print) ...
    print(f"Extracted Skills: {', '.join(extracted_data['required_skills']) if extracted_data['required_skills'] else 'None'}")
    print(f"Potential Emails: {', '.join(extracted_data['emails']) if extracted_data['emails'] else 'None'}")
    print(f"JD Extracted: {'Yes' if extracted_data['job_description'] and not extracted_data['job_description'].startswith('Could not') else 'No/Failed'}")
    print("-------------------------------------------\n")


    # Step 4: Modify LaTeX Resume
    print(f"Attempting to modify LaTeX resume template: {LATEX_TEMPLATE_PATH}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_company = sanitize_filename(extracted_data['company_name'])
    safe_role = sanitize_filename(extracted_data['job_title'])
    # Define base filename without extension for easier use later
    base_filename = f"{safe_company}_{safe_role}_{timestamp}"
    output_tex_filename = f"{base_filename}.tex"
    output_tex_path = os.path.join(RESUME_OUTPUT_DIR, output_tex_filename)

    latex_success = modify_latex_template(
        template_path=LATEX_TEMPLATE_PATH,
        output_path=output_tex_path,
        extracted_data=extracted_data
    )

    pdf_path = None # Initialize pdf_path
    if latex_success:
        print(f"LaTeX resume saved to: {output_tex_path}")

        # --- Step 4b: Compile LaTeX to PDF --- <<< --- ADDED STEP ---
        pdf_success = compile_latex_to_pdf(output_tex_path)
        if pdf_success:
            pdf_path = output_tex_path.replace(".tex", ".pdf")
            print(f"Successfully compiled PDF: {pdf_path}")
            if args.cleanup:
                 cleanup_latex_aux_files(RESUME_OUTPUT_DIR, base_filename)
        else:
            print("Failed to compile LaTeX to PDF.")
        # --- End of Added Step ---

    else:
        print("Error: Failed to modify or save LaTeX resume. Skipping PDF compilation.")

    # Step 5: Generate Cold Email
    # (Remains the same, but now we could potentially mention the PDF if generated)
    print(f"\nAttempting to generate email draft using template: {EMAIL_TEMPLATE_PATH}")
    email_text = generate_email(
        template_path=EMAIL_TEMPLATE_PATH,
        extracted_data=extracted_data
    )
    if email_text:
        # Optionally modify email text to mention PDF if it exists
        if pdf_path:
            # Example: Find a line like "My attached resume provides..." and adjust
            email_text = email_text.replace("My attached resume provides", f"My attached resume (PDF) provides", 1)

        output_email_filename = f"{base_filename}_email.txt"
        output_email_path = os.path.join(EMAIL_OUTPUT_DIR, output_email_filename)
        try:
            os.makedirs(os.path.dirname(output_email_path), exist_ok=True)
            with open(output_email_path, 'w', encoding='utf-8') as f: f.write(email_text)
            logging.info(f"Email draft saved successfully: {output_email_path}")
            print(f"\n--- Generated Email Draft (Preview) ---")
            print(email_text)
            print("----------------------------------------\n")
            print(f"Full email draft saved to: {output_email_path}")
        except Exception as e:
            logging.error(f"Error writing email draft file {output_email_path}: {e}")
            # ... (rest of email saving error handling) ...
            print("Error: Could not save email draft file.")
            print("\n--- Generated Email Draft (Not Saved) ---"); print(email_text); print("----------------------------------------\n")

    else:
        print("Error: Failed to generate email draft.")

    logging.info("--- Job Tailor Process Finished ---")

if __name__ == "__main__":
    os.makedirs(RESUME_OUTPUT_DIR, exist_ok=True)
    os.makedirs(EMAIL_OUTPUT_DIR, exist_ok=True)
    main()