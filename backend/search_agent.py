import time
import threading
import queue
import logging
import json
import os
import requests
import subprocess
from pathlib import Path
from ddgs import DDGS
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database import SessionLocal, Job
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.document_loaders import PyPDFLoader

from ai_services import ResumeAgent

logger = logging.getLogger(__name__)

# Global Kill Switch & Queue
KILL_SWITCH_EVENT = threading.Event()
JOB_PROCESS_QUEUE = queue.Queue()

# Cache for extracted resume profile so we don't re-parse every cycle
_resume_profile_cache = None

BASE_RESUME_PATH = Path(__file__).parent.resolve() / "resumes" / "base_resume.pdf"


def extract_resume_profile(api_key: str):
    """Reads the base resume PDF and uses Gemini to extract a structured profile."""
    global _resume_profile_cache
    if _resume_profile_cache:
        return _resume_profile_cache

    if not BASE_RESUME_PATH.exists():
        logger.error("❌ No base_resume.pdf found! Upload it via the Settings tab.")
        return None

    logger.info("📄 Reading base_resume.pdf to build candidate profile...")
    loader = PyPDFLoader(str(BASE_RESUME_PATH))
    raw_text = "\n".join([p.page_content for p in loader.load()])

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=api_key
    )

    template = """
    You are an expert Resume Parser.
    
    Given the following resume text, extract a structured profile.
    
    RESUME TEXT:
    {resume}
    
    OUTPUT a valid JSON object with EXACTLY these keys:
    - "name": candidate's full name
    - "primary_role": their most fitting job title (e.g. "AI/ML Engineer", "Backend Developer")
    - "alternate_roles": a list of 2-3 other job titles they could apply for
    - "top_skills": a list of their 5-8 strongest technical skills (languages, frameworks, tools)
    - "experience_years": estimated total years of experience (integer)
    - "domains": list of 2-3 industry domains they have experience in (e.g. "FinTech", "Healthcare", "SaaS")
    
    Output ONLY valid JSON. No markdown, no extra text.
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm | JsonOutputParser()

    try:
        profile = chain.invoke({"resume": raw_text})
        logger.info(f"✅ Resume Profile Extracted: {profile.get('primary_role')} | Skills: {profile.get('top_skills')}")
        _resume_profile_cache = profile
        _resume_profile_cache["raw_text"] = raw_text
        time.sleep(5)  # Cooldown after profile extraction call
        return _resume_profile_cache
    except Exception as e:
        logger.error(f"❌ Failed to extract resume profile: {e}")
        return None


class JobDiscoveryAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            google_api_key=api_key
        )

    def generate_resume_queries(self, profile: dict):
        """Uses the extracted resume profile to generate highly targeted search queries."""
        logger.info("🧠 Generating resume-driven search queries...")

        template = """
        You are an expert job search strategist for the Indian job market.
        
        CANDIDATE PROFILE:
        - Primary Role: {primary_role}
        - Alternate Roles: {alternate_roles}
        - Top Skills: {top_skills}
        - Experience: {experience_years} years
        - Domains: {domains}
        
        TASK:
        Generate a JSON array of 8 highly targeted search query strings to find matching jobs.
        The candidate ONLY wants jobs in INDIA (any Indian city) or REMOTE positions.
        
        Split them as:
        - 4 queries for site:linkedin.com/jobs/view
        - 4 queries for site:naukri.com/job-listings
        
        RULES:
        - Do NOT use boolean operators (OR, AND), parentheses, or quotes.
        - Use raw space-separated keywords only.
        - Each query should target a DIFFERENT angle (different role name, different skill combo, different city).
        - Include Indian cities like Bangalore, Hyderabad, Pune, Noida, Gurgaon, Mumbai, Chennai, Remote.
        - Focus on skills the candidate ACTUALLY has. Don't invent skills.
        - Add freshness keywords like "hiring" or "urgent" or "immediate" to some queries.
        
        EXAMPLES:
        - site:linkedin.com/jobs/view machine learning engineer bangalore python tensorflow
        - site:naukri.com/job-listings backend developer remote python fastapi
        - site:linkedin.com/jobs/view ai engineer noida gurgaon langchain
        
        Output EXACTLY and ONLY a valid JSON array of 8 strings. No markdown.
        """

        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | JsonOutputParser()

        try:
            queries = chain.invoke({
                "primary_role": profile.get("primary_role", "Software Engineer"),
                "alternate_roles": ", ".join(profile.get("alternate_roles", [])),
                "top_skills": ", ".join(profile.get("top_skills", [])),
                "experience_years": profile.get("experience_years", 2),
                "domains": ", ".join(profile.get("domains", []))
            })
            if isinstance(queries, list):
                logger.info(f"📋 Generated {len(queries)} resume-driven queries.")
                return queries
            return []
        except Exception as e:
            logger.error(f"❌ ERROR generating resume-driven queries: {e}")
            # Fallback to basic queries
            role = profile.get("primary_role", "software engineer")
            skill = profile.get("top_skills", ["python"])[0] if profile.get("top_skills") else "python"
            return [
                f"site:linkedin.com/jobs/view {role} india {skill}",
                f"site:linkedin.com/jobs/view {role} remote {skill}",
                f"site:naukri.com/job-listings {role} bangalore {skill}",
                f"site:naukri.com/job-listings {role} remote {skill}",
            ]

    def execute_search(self, profile: dict):
        """Searches for jobs using resume-driven queries and queues them."""
        queries = self.generate_resume_queries(profile)
        if not queries:
            logger.warning("No queries generated. Skipping.")
            return

        db: Session = SessionLocal()
        new_count = 0
        try:
            with DDGS() as ddgs:
                for query in queries:
                    if KILL_SWITCH_EVENT.is_set():
                        break

                    logger.info(f"🔎 Resume-Driven Search: {query}")
                    try:
                        results = list(ddgs.text(query, max_results=10, timelimit='d'))
                    except Exception as e:
                        logger.warning(f"⚠️ Search failed for query: {e}")
                        continue

                    for r in results:
                        if KILL_SWITCH_EVENT.is_set():
                            break

                        title = r.get("title", "Unknown Role")
                        url = r.get("href", "")
                        body_snippet = r.get("body", "")

                        # Determine source
                        source = "Web"
                        if "linkedin.com" in url:
                            source = "LinkedIn"
                        elif "naukri.com" in url:
                            source = "Naukri"

                        # Skip duplicate URLs
                        existing = db.query(Job).filter(Job.url == url).first()
                        if existing:
                            continue

                        new_job = Job(
                            title=title,
                            company="(Pending Extraction)",
                            location="India / Remote",
                            url=url,
                            description=body_snippet,
                            source=source,
                            status="QUEUED"
                        )
                        db.add(new_job)
                        db.commit()
                        db.refresh(new_job)
                        new_count += 1

                        logger.info(f"✨ Discovered: {title} [{source}]. Queued for processing.")
                        JOB_PROCESS_QUEUE.put((new_job.id, self.api_key))

            logger.info(f"🏁 Search cycle complete. {new_count} new jobs discovered.")
        except Exception as e:
            logger.error(f"❌ Error during search: {e}")
            db.rollback()
        finally:
            db.close()


def job_processing_worker():
    """Background thread: scrapes JD, evaluates match, generates materials."""
    logger.info("👷 Background processing worker started.")
    while not KILL_SWITCH_EVENT.is_set():
        try:
            job_id, api_key = JOB_PROCESS_QUEUE.get(timeout=2)
        except queue.Empty:
            continue

        db: Session = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or not api_key:
                continue

            logger.info(f"────────────────────────────────────")
            logger.info(f"⚙️ PROCESSING JOB #{job.id}: {job.title}")

            # 1. Scrape Full JD
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                res = requests.get(job.url, headers=headers, timeout=10)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.extract()
                    job.description = soup.get_text(separator=' ', strip=True)[:12000]
            except Exception:
                pass  # Fall back to search snippet

            # 2. Get Resume Text
            if not _resume_profile_cache or "raw_text" not in _resume_profile_cache:
                logger.warning(f"No cached resume text. Skipping Job #{job.id}")
                job.status = "NO RESUME"
                db.commit()
                continue

            raw_resume = _resume_profile_cache["raw_text"]

            # 3. Evaluate Match Score
            agent = ResumeAgent(api_key)

            logger.info(f"🧠 Evaluating match score for Job #{job.id}...")
            match_result = agent.evaluate_job_match(raw_resume, job.description)
            job.match_score = match_result.get("score", 0)
            job.match_reason = match_result.get("reason", "No reason provided.")

            time.sleep(8)  # Throttle for free tier (~10 RPM)

            if job.match_score >= 70:
                logger.info(f"🟢 High Match ({job.match_score}%). Generating materials...")

                job.cover_letter = agent.generate_cover_letter(raw_resume, job.description)
                time.sleep(8)

                analysis = agent.analyze_gaps(raw_resume, job.description)
                time.sleep(8)

                latex_code = agent.generate_latex(raw_resume, job.description, analysis)
                clean_code = latex_code.replace("```latex", "").replace("```", "").strip()

                output_dir = Path(__file__).parent.resolve() / "resumes"
                tex_path = output_dir / f"tailored_resume_job_{job.id}.tex"
                pdf_path = output_dir / f"tailored_resume_job_{job.id}.pdf"

                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(clean_code)

                cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory=.", tex_path.name]
                subprocess.run(cmd, cwd=output_dir, capture_output=True, text=True)

                if Path(pdf_path).exists():
                    job.tailored_resume_path = str(pdf_path)
                    job.status = "AUTO-GENERATED"
                    logger.info(f"🎉 Complete for Job #{job.id}!")
                else:
                    job.status = "LATEX ERROR"
            else:
                logger.info(f"🔴 Low Match ({job.match_score}%). Skipped.")
                job.status = "LOW MATCH"

            db.commit()

        except Exception as e:
            logger.error(f"❌ Worker Error on Job #{job_id}: {e}")
            db.rollback()
        finally:
            db.close()
            JOB_PROCESS_QUEUE.task_done()


def discovery_loop(api_key: str, interval_minutes: int = 60):
    """Main loop: extracts profile from resume, then searches on repeat."""
    logger.info("🚀 Resume-Driven Job Discovery Agent STARTED.")
    KILL_SWITCH_EVENT.clear()

    # Step 1: Extract profile from resume (once)
    profile = extract_resume_profile(api_key)
    if not profile:
        logger.error("❌ Cannot start agent without a valid base resume. Upload one in Settings.")
        return

    logger.info(f"👤 Candidate: {profile.get('name')} | Role: {profile.get('primary_role')}")
    logger.info(f"🛠️ Skills: {profile.get('top_skills')}")

    agent = JobDiscoveryAgent(api_key)

    while not KILL_SWITCH_EVENT.is_set():
        logger.info("🕰️ Agent waking up for a search cycle...")
        agent.execute_search(profile)

        sleep_seconds = interval_minutes * 60
        for _ in range(sleep_seconds):
            if KILL_SWITCH_EVENT.is_set():
                break
            time.sleep(1)

    logger.info("🛑 Job Discovery Agent STOPPED.")


_agent_thread = None
_worker_thread = None


def start_agent_thread(api_key: str = "", interval_minutes: int = 60, **kwargs):
    """Starts the discovery + worker threads. Only needs api_key now."""
    global _agent_thread, _worker_thread, _resume_profile_cache

    if _agent_thread and _agent_thread.is_alive():
        return False

    # Clear cache so a fresh resume is re-read on restart
    _resume_profile_cache = None
    KILL_SWITCH_EVENT.clear()

    _agent_thread = threading.Thread(
        target=discovery_loop,
        args=(api_key, interval_minutes),
        daemon=True
    )
    _agent_thread.start()

    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_thread = threading.Thread(
            target=job_processing_worker,
            daemon=True
        )
        _worker_thread.start()

    return True


def kill_agent_thread():
    KILL_SWITCH_EVENT.set()
    return True
