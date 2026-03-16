# AIV Resume Tailor

This project uses a FastAPI backend and a Streamlit frontend to tailor a resume to a specific job description using the Google Gemini API.

## Setup

1.  **Install dependencies:**
    Make sure you have Python 3.8+ installed. It's recommended to use a virtual environment.

    ```bash
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`

    # Install the required packages
    pip install -r requirements.txt
    ```
    *If a `requirements.txt` file is not available, you can install the packages from the imported libraries in `main.py` and `app.py`: `fastapi`, `uvicorn`, `python-multipart`, `langchain-google-genai`, `langchain`, `pypdf`, `streamlit`, `httpx` and a LaTeX distribution like MiKTeX or TeX Live.*

2.  **LaTeX Installation:**
    This application requires a LaTeX distribution to be installed on your system to compile the `.tex` files into PDFs. Ensure that the `pdflatex` command is available in your system's PATH.
    *   **Windows:** Install [MiKTeX](https://miktex.org/download).
    *   **macOS:** Install [MacTeX](https://www.tug.org/mactex/).
    *   **Linux (Ubuntu/Debian):** `sudo apt-get install texlive-full`

## Running the Application

You need to run two processes in separate terminals from the `backend` directory.

1.  **Start the FastAPI Backend:**
    The backend server handles the logic of resume processing and PDF generation.

    ```bash
    uvicorn main:app --reload
    ```
    The server will be available at `http://127.0.0.1:8000`.

2.  **Start the Streamlit Frontend:**
    The frontend provides the user interface to interact with the application.

    ```bash
    streamlit run app.py
    ```
    The Streamlit app will open in your browser, usually at `http://localhost:8501`.

## How to Use

1.  Open the Streamlit app in your browser.
2.  Enter your Google Gemini API Key.
3.  Upload your current resume in PDF format.
4.  Paste the job description for the role you are applying for.
5.  Click the "Tailor My Resume" button.
6.  If successful, a download button will appear for you to download your new, tailored resume.
