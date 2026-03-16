import os
import subprocess
import tempfile
import logging
import sys
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader

# ==========================================
# LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
# LATEX TEMPLATE
# ==========================================
LATEX_TEMPLATE = r"""\documentclass[a4paper,10pt]{article}
\usepackage[left=0.5in, right=0.5in, top=0.5in, bottom=0.5in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{hyperref}

% Formatting sections
\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}[\titlerule]
\titlespacing*{\section}{0pt}{12pt}{6pt}

% Formatting lists
\setlist[itemize]{noitemsep, topsep=0pt, leftmargin=1.5em}

\begin{document}

% HEADER
\begin{center}
    {\Huge \textbf{INSERT_NAME_HERE}} \\ \vspace{2mm}
    INSERT_PHONE | \href{mailto:INSERT_EMAIL}{INSERT_EMAIL} | \href{INSERT_LINKEDIN_URL}{LinkedIn} | \href{INSERT_GITHUB_URL}{GitHub}
\end{center}

% SUMMARY
\section*{Professional Summary}
INSERT_OPTIMIZED_SUMMARY_HERE

% SKILLS
\section*{Technical Skills}
\begin{itemize}
    \item \textbf{Languages:} INSERT_LANGUAGES
    \item \textbf{Frameworks \& Libraries:} INSERT_FRAMEWORKS
    \item \textbf{Tools \& Platforms:} INSERT_TOOLS
    \item \textbf{Databases:} INSERT_DATABASES
\end{itemize}

% EXPERIENCE
\section*{Experience}
% REPEAT THIS BLOCK FOR EACH JOB
\noindent \textbf{INSERT_COMPANY} \hfill INSERT_LOCATION \\
\textit{INSERT_ROLE} \hfill INSERT_DATES
\begin{itemize}
    \item INSERT_BULLET_POINT_1 (Quantified Result)
    \item INSERT_BULLET_POINT_2 (Quantified Result)
    \item INSERT_BULLET_POINT_3
\end{itemize}

% PROJECTS
\section*{Projects}
% REPEAT THIS BLOCK FOR EACH PROJECT
\noindent \textbf{INSERT_PROJECT_NAME} | \textit{INSERT_TECH_STACK} \hfill \href{INSERT_PROJECT_LINK}{Link}
\begin{itemize}
    \item INSERT_PROJECT_BULLET_1
    \item INSERT_PROJECT_BULLET_2
\end{itemize}

% EDUCATION
\section*{Education}
\noindent \textbf{INSERT_UNIVERSITY} \hfill INSERT_GRAD_YEAR \\
INSERT_DEGREE \hfill GPA: INSERT_GPA

\end{document}"""

# ==========================================
# AI AGENT LOGIC
# ==========================================
class ResumeAgent:
    def __init__(self, api_key):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=api_key,
            max_retries=2
        )
        logger.info("🤖 ResumeAgent initialized with gemini-2.5-flash")

    def analyze_gaps(self, resume_text, jd_text):
        """Analyzes the resume against the JD."""
        logger.info("🔍 STARTING: Gap Analysis LLM Chain")
        template = """
        You are an expert Technical Recruiter.
        JOB DESCRIPTION: {jd}
        RESUME CONTENT: {resume}
        TASK:
        Identify the gaps. Output a concise analysis:
        1. **Missing Keywords**: List 3-5 specific hard skills/tools from JD missing in Resume.
        2. **Summary Update**: Draft a specific, 2-sentence professional summary tailored to this JD.
        3. **Experience Enhancements**: Identify 1 weak bullet point and provide a rewrite using the STAR method.
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        try:
            return chain.invoke({"jd": jd_text, "resume": resume_text})
        except Exception as e:
            logger.error(f"❌ ERROR in Gap Analysis: {e}")
            raise

    def generate_latex(self, resume_text, jd_text, analysis):
        """Generates the LaTeX code."""
        logger.info("✍️ STARTING: LaTeX Generation LLM Chain")
        system_prompt = (
            "You are a LaTeX Resume Architect. Your task is to populate the provided "
            "LaTeX template with information from the user's resume, tailoring it "
            "based on the provided job description and analysis..."
        )
        human_prompt = '''
        Please fill this LaTeX template:
        --- TEMPLATE START ---
        {latex_template}
        --- TEMPLATE END ---
        Using this information:
        --- RESUME ---
        {resume}
        --- END RESUME ---
        --- JOB DESCRIPTION ---
        {jd}
        --- END JOB DESCRIPTION ---
        --- ANALYSIS ---
        {analysis}
        --- END ANALYSIS ---
        '''
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt),
        ])
        chain = prompt | self.llm | StrOutputParser()
        try:
            return chain.invoke({
                "latex_template": LATEX_TEMPLATE,
                "resume": resume_text,
                "jd": jd_text,
                "analysis": analysis
            })
        except Exception as e:
            logger.error(f"❌ ERROR in LaTeX Generation: {e}")
            raise

# ==========================================
# API ENDPOINTS
# ==========================================
@app.get("/")
def read_root():
    return {"status": "AIV Resume Tailor API is running."}

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

    temp_dir = tempfile.mkdtemp()
    
    def cleanup():
        logger.info(f"Cleaning up temporary directory: {temp_dir}")
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    try:
        temp_path = Path(temp_dir)
        resume_path = temp_path / "original_resume.pdf"
        tex_path = temp_path / "tailored_resume.tex"
        pdf_path = temp_path / "tailored_resume.pdf"

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
        cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory=" + str(temp_path), str(tex_path)]
        
        # Run pdflatex. It often needs to be run twice.
        result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
        if Path(pdf_path).exists():
                # Run again to resolve any cross-references
                result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)

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
        return FileResponse(
            str(pdf_path),
            media_type='application/pdf',
            filename="Optimized_Resume.pdf",
            background=BackgroundTask(cleanup)
        )

    except Exception as e:
        # If any exception occurs, clean up the directory and then re-raise
        cleanup() # Clean up immediately on any error
        logger.exception("CRITICAL APP FAILURE")
        # Raise as HTTPException to be sent to the client
        raise HTTPException(status_code=500, detail=str(e))