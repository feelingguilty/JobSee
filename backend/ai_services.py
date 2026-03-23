import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

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

class ResumeAgent:
    def __init__(self, api_key):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=api_key,
            max_retries=2
        )
        logger.info("🤖 ResumeAgent initialized with gemini-2.5-flash")

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
    def evaluate_job_match(self, resume_text, jd_text):
        """Evaluates how well the resume matches the JD (0-100 score)."""
        logger.info("🔍 STARTING: Job Qualification Match LLM Chain")
        template = """
        You are an expert Technical Recruiter evaluating a candidate's fit for a role.
        
        JOB DESCRIPTION:
        {jd}
        
        RESUME CONTENT:
        {resume}
        
        TASK:
        Rate how qualified the candidate is for this exact job description from 0 to 100.
        Be extremely honest and critical. If the JD requires 5 years of an obscure language and the candidate has 0, score them low.
        Output EXACTLY a JSON object with two keys:
        - "score": integer from 0 to 100
        - "reason": a 1-sentence explanation of why they got this score (focus on biggest strengths/weaknesses).
        
        Example Output:
        {{"score": 85, "reason": "Strong match for Python and AWS, but lacks the required Kubernetes experience."}}
        """
        from langchain_core.output_parsers import JsonOutputParser
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | JsonOutputParser()
        try:
            return chain.invoke({"jd": jd_text, "resume": resume_text})
        except Exception as e:
            logger.error(f"❌ ERROR in Job Qualification Match: {e}")
            raise e # Let tenacity retry

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
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

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
    def generate_cover_letter(self, resume_text, jd_text):
        """Generates a professional cover letter based on Resume and JD."""
        logger.info("✍️ STARTING: Cover Letter Generation LLM Chain")
        template = """
        You are an expert Career Coach and Copywriter.
        Write a professional, compelling, 3-paragraph cover letter directed at the hiring manager.
        Use details from the provided RESUME to demonstrate fitness for the JOB DESCRIPTION.
        Do not use placeholder brackets for things like [Your Name] unless you have to, try to infer it from the resume.
        Keep it concise, confident, and focused strictly on value-add.

        --- JOB DESCRIPTION ---
        {jd}
        
        --- RESUME ---
        {resume}
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        try:
            return chain.invoke({"jd": jd_text, "resume": resume_text})
        except Exception as e:
            logger.error(f"❌ ERROR in Cover Letter Generation: {e}")
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
