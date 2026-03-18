# JobSee Backend: AI Resume Tailor

This is the FastAPI backend for JobSee. It uses Google Gemini to analyze resumes and generate optimized Word documents.

## 🚀 Setup

1. **Install Python Dependencies:**
   Ensure you're using a virtual environment (e.g., `venv`).
   ```bash
   pip install fastapi uvicorn python-multipart langchain-google-genai pypdf python-docx httpx
   ```

2. **No LaTeX Needed:**
   This version of JobSee does **not** require LaTeX. It generates Word (.docx) files directly using `python-docx`.

3. **Running the Server:**
   From the `backend` directory:
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://127.0.0.1:8000`.

## 📡 API Endpoints

### `POST /tailor/`
- **Description:** Tailors a resume to a job description.
- **Parameters:**
  - `api_key`: Google Gemini API Key.
  - `jd_text`: The job description text.
  - `resume_file`: The user's original resume (PDF).
- **Returns:** A tailored `.docx` file.

## 🧪 Frontend Alternatives
- **Streamlit:** You can also run the web interface:
  ```bash
  streamlit run app.py
  ```
- **Extension:** Recommended for best experience (automatic JD detection).
