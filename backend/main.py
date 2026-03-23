import os
import subprocess
import tempfile
import logging
import sys
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
import base64
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask

from database import engine, get_db, Base, Job
from sqlalchemy.orm import Session
from fastapi import Depends
from pydantic import BaseModel
from search_agent import start_agent_thread, kill_agent_thread

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv

# Get the absolute path to the directory of the current script
script_dir = Path(__file__).parent.resolve()


# ==========================================
# LOGGING SETUP
# ==========================================
# --- SETUP CENTRALIZED LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler(script_dir / "jobsee.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load fallback environment variables
load_dotenv()

# ==========================================
# FASTAPI APP SETUP
# ==========================================
app = FastAPI()

# Allow requests from browser extensions (typically null origin) and any other origin
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# LATEX AND PDF CHECK
# ==========================================
def check_pdflatex():
    """Checks if pdflatex is installed and logs the result."""
    if shutil.which("pdflatex"):
        logger.info("✅ PDFLaTeX check passed.")
        return True
    logger.error("❌ PDFLaTeX binary not found. Please install a TeX distribution (MiKTeX, TeX Live).")
    return False

LATEX_INSTALLED = check_pdflatex()

# ==========================================
# IMPORT AI SERVICES
# ==========================================
from ai_services import ResumeAgent, LATEX_TEMPLATE

# ==========================================
# API ENDPOINTS
# ==========================================
@app.get("/")
def read_root():
    return {"status": "Job Assistant API is running."}

class AgentSettings(BaseModel):
    interval_minutes: int = 60
    api_key: str = ""

@app.post("/agent/start")
def start_agent(settings: AgentSettings):
    if not settings.api_key:
        return {"status": "Error: API Key is required to start the agent."}

    started = start_agent_thread(
        api_key=settings.api_key,
        interval_minutes=settings.interval_minutes
    )
    if started:
        return {"status": "Resume-Driven Job Discovery Agent started! Reading your resume..."}
    return {"status": "Agent is already running."}

@app.post("/agent/stop")
def stop_agent():
    kill_agent_thread()
    return {"status": "Kill Switch Activated. Agent stopping."}

@app.get("/jobs")
async def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.discovery_date.desc()).all()
    return jobs

@app.put("/jobs/{job_id}/status")
async def update_job_status(job_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = status
    db.commit()
    return {"status": "success", "new_status": job.status}

@app.post("/jobs/{job_id}/cover-letter")
async def generate_cover_letter_for_job(
    job_id: int,
    api_key: str = Form(...),
    resume_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in database.")
        
    if not job.description:
        raise HTTPException(status_code=400, detail="Job description is empty. Cannot generate cover letter.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(resume_file.file, tmp)
            tmp_path = tmp.name

        loader = PyPDFLoader(tmp_path)
        raw_text = "\n".join([p.page_content for p in loader.load()])
        
        try:
            os.remove(tmp_path)
        except:
            pass

        agent = ResumeAgent(api_key)
        cover_letter_text = agent.generate_cover_letter(raw_text, job.description)

        job.cover_letter = cover_letter_text
        db.commit()

        return {"status": "success", "cover_letter": cover_letter_text}
    except Exception as e:
        logger.exception("Failed to generate cover letter")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tailor/")
async def tailor_resume(
    api_key: str = Form(...),
    jd_text: str = Form(...),
    resume_file: UploadFile = File(...)
):
    if not LATEX_INSTALLED:
        raise HTTPException(status_code=500, detail="PDFLaTeX is not installed on the server.")
    if not api_key:
        raise HTTPException(status_code=400, detail="Google Gemini API Key is required.")

    output_dir = script_dir / "resumes"
    os.makedirs(output_dir, exist_ok=True)
    try:
        output_path = Path(output_dir)
        resume_path = output_path / "original_resume.pdf"
        tex_path = output_path / "tailored_resume.tex"
        pdf_path = output_path / "tailored_resume.pdf"

        # Save uploaded resume to a temporary file
        with open(resume_path, "wb") as buffer:
            shutil.copyfileobj(resume_file.file, buffer)
        
        # Initialize agent
        agent = ResumeAgent(api_key)

        # 1. Extraction
        logger.info("Step 1: Extracting text from PDF...")
        loader = PyPDFLoader(str(resume_path))
        raw_text = "\n".join([p.page_content for p in loader.load()])
        
        # 2. Analysis
        logger.info("Step 2: Calling Analyst Agent...")
        analysis = agent.analyze_gaps(raw_text, jd_text)
        
        # 3. Code Generation
        logger.info("Step 3: Calling Architect Agent...")
        latex_code = agent.generate_latex(raw_text, jd_text, analysis)
        clean_code = latex_code.replace("```latex", "").replace("```", "").strip()
        
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(clean_code)
        
        # 4. Compilation
        logger.info("Step 4: Compiling with pdflatex...")
        cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory=.", tex_path.name]
        
        # Run pdflatex. It often needs to be run twice.
        result = subprocess.run(cmd, cwd=output_dir, capture_output=True, text=True)
        if Path(pdf_path).exists():
                # Run again to resolve any cross-references
                result = subprocess.run(cmd, cwd=output_dir, capture_output=True, text=True)

        # Final check for PDF existence and compilation success
        if result.returncode != 0 or not Path(pdf_path).exists():
            logger.error("❌ PDF generation failed after pdflatex run(s).")
            
            log_file_path = tex_path.with_suffix('.log')
            log_content = "Log file not found."
            if log_file_path.exists():
                try:
                    log_content = log_file_path.read_text(encoding='utf-8')
                except Exception as e:
                    log_content = f"Error reading log file: {e}"

            # Combine all info for a detailed error message
            error_details = (
                f"PDF compilation failed.\n"
                f"pdflatex return code: {result.returncode}\n\n"
                f"--- STDOUT ---\n{result.stdout}\n\n"
                f"--- STDERR ---\n{result.stderr}\n\n"
                f"--- LATEX LOG (from {log_file_path}) ---\n{log_content[-2000:]}" # Log last 2000 chars
            )
            logger.error(error_details)
            # This exception will be caught by the outer `except` and trigger cleanup
            raise Exception("PDF compilation failed. The LaTeX code generated by the AI may be invalid. Check server logs for details.")

        logger.info("✅ PDF successfully created.")

        # Read the generated PDF and encode it in base64
        with open(pdf_path, "rb") as pdf_file:
            pdf_base64 = base64.b64encode(pdf_file.read()).decode("utf-8")

        return JSONResponse(content={
            "analysis": analysis,
            "pdf_base64": pdf_base64,
            "filename": "Optimized_Resume.pdf"
        })

    except Exception as e:
        # If any exception occurs, clean up the directory and then re-raise
        logger.exception("CRITICAL APP FAILURE")
        # Raise as HTTPException to be sent to the client
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)