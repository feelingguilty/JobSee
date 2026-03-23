import streamlit as st
import requests
import json
import pandas as pd
import time
import os
import base64

FASTAPI_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="JobSee Agent", page_icon="🕵️", layout="wide")

st.title("🕵️‍♂️ JobSee Personal Job Assistant")

tab1, tab2, tab3 = st.tabs(["🚀 Job Discovery (Tracker)", "📝 Application Hub", "⚙️ Settings"])

CONFIG_FILE = "jobsee_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

config = load_config()

def save_base_resume(uploaded_file):
    os.makedirs("resumes", exist_ok=True)
    with open(os.path.join("resumes", "base_resume.pdf"), "wb") as f:
        f.write(uploaded_file.getbuffer())

def fetch_jobs():
    try:
        response = requests.get(f"{FASTAPI_URL}/jobs")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

# --- TAB 3: SETTINGS ---
with tab3:
    st.header("Agent Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        target_role = st.text_input("Target Role", value=config.get('target_role', 'Software Engineer'))
        location = st.text_input("Location", value=config.get('location', 'Remote'))
    with col2:
        skills = st.text_input("Skills/Keywords", value=config.get('skills', 'Python, React'))
        interval = st.number_input("Discovery Interval (mins)", min_value=1, value=config.get('interval_minutes', 60))

    st.divider()
    api_key = st.text_input("Google Gemini API Key", type="password", value=config.get('api_key', ''))

    st.divider()
    st.write("📄 **Base Resume for Auto-Generation**")
    base_resume = st.file_uploader("Upload your master resume (PDF). The agent uses this to automatically write cover letters and tailor resumes in the background.", type=["pdf"])
    if base_resume:
        save_base_resume(base_resume)
        st.success("Base Resume saved successfully!")

    st.divider()
    if st.button("💾 Save Configuration as JSON"):
        new_config = {
            "target_role": target_role,
            "location": location,
            "skills": skills,
            "interval_minutes": interval,
            "api_key": api_key
        }
        save_config(new_config)
        st.success("Configuration saved locally as JSON! The agent will use these settings next time you start it.")
        config = new_config # Update current state

# --- TAB 1: JOB DISCOVERY ---
with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Agent Control Panel")
        st.caption("The agent reads your uploaded **Base Resume** and finds matching jobs in India/Remote automatically.")
        if st.button("▶️ START AGENT", type="primary"):
            try:
                current_config = load_config()
                payload = {
                    "interval_minutes": current_config.get("interval_minutes", 60),
                    "api_key": current_config.get("api_key", "")
                }
                res = requests.post(f"{FASTAPI_URL}/agent/start", json=payload)
                st.success(res.json().get("status", "Started"))
            except Exception as e:
                st.error(f"Failed to start. Make sure you saved your API Key in Settings: {e}")

    with col2:
        st.subheader("KILL SWITCH")
        if st.button("🛑 STOP ACTIVE SEARCH", type="secondary"):
            try:
                res = requests.post(f"{FASTAPI_URL}/agent/stop")
                st.warning(res.json().get("status", "Stopped"))
            except Exception as e:
                st.error(f"Failed to stop: {e}")
                
    st.divider()
    st.subheader("Discovered Jobs Tracker")
    
    if st.button("🔄 Refresh List"):
        st.rerun()

    jobs = fetch_jobs()
    if jobs:
        # --- METRICS ---
        total_jobs = len(jobs)
        high_matches = sum(1 for j in jobs if j.get('match_score') is not None and j.get('match_score') >= 70)
        auto_gen = sum(1 for j in jobs if j.get('status') == 'AUTO-GENERATED')
        applied = sum(1 for j in jobs if j.get('status') == 'APPLIED')
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Discovered", total_jobs)
        m2.metric("High Matches (>=70%)", high_matches)
        m3.metric("Auto-Generated Docs", auto_gen)
        m4.metric("Applied", applied)
        st.divider()
        
        # --- DATA EDITOR ---
        df = pd.DataFrame(jobs)
        # Reorder columns to make it nice
        cols = ['id', 'match_score', 'status', 'title', 'company', 'source', 'discovery_date', 'match_reason', 'url']
        df = df[[c for c in cols if c in df.columns]]
        
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    help="Update the job status",
                    options=["NEW", "QUEUED", "LOW MATCH", "AUTO-GENERATED", "APPLIED", "IGNORED"],
                    required=True
                )
            },
            disabled=["id", "match_score", "title", "company", "source", "discovery_date", "match_reason", "url"],
            key="jobs_editor"
        )
        
        # Detect and save status changes
        for index, row in edited_df.iterrows():
            orig_status = df.loc[index, 'status']
            new_status = row['status']
            if new_status != orig_status:
                try:
                    job_id = row['id']
                    res = requests.put(f"{FASTAPI_URL}/jobs/{job_id}/status", data={"status": str(new_status)})
                    if res.status_code == 200:
                        st.toast(f"✅ Updated Job {job_id} to {new_status}")
                        st.rerun() # Refresh with new DB state
                except Exception as e:
                    st.error(f"Failed to update status: {e}")
    else:
        st.info("No jobs discovered yet. Make sure the backend is running and start the Agent.")

# --- TAB 2: APPLICATION HUB ---
with tab2:
    st.header("📝 Application Generator")
    
    jobs = fetch_jobs()
    if not jobs:
        st.warning("No jobs found in the database to apply to.")
    else:
        job_options = {f"[{j['id']}] {j['title']} at {j['company']}": j for j in jobs}
        selected_job_label = st.selectbox("Select a Job to Tailor Application For", list(job_options.keys()))
        selected_job = job_options[selected_job_label]

        with st.expander("View Job Description snippet"):
            st.write(selected_job.get("description", "No description available."))
            st.markdown(f"[Go to Original Posting]({selected_job['url']})")
            
        st.divider()
        uploaded_resume = st.file_uploader("Upload Base Resume (PDF)", type=["pdf"])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✉️ Generate Cover Letter"):
                current_api_key = config.get("api_key", "")
                if not uploaded_resume or not current_api_key:
                    st.error("Please upload a resume and provide an API key in Settings (and press Save).")
                else:
                    with st.spinner("Generating Cover Letter using Gemini..."):
                        try:
                            files = {"resume_file": (uploaded_resume.name, uploaded_resume, "application/pdf")}
                            data = {"api_key": current_api_key}
                            res = requests.post(f"{FASTAPI_URL}/jobs/{selected_job['id']}/cover-letter", files=files, data=data)
                            if res.status_code == 200:
                                cover_letter = res.json().get("cover_letter", "")
                                st.session_state[f"cl_{selected_job['id']}"] = cover_letter
                                st.success("Cover Letter Generated!")
                            else:
                                st.error(f"Error: {res.text}")
                        except Exception as e:
                            st.error(f"Failed to connect: {e}")

        with col2:
            if st.button("📄 Generate Tailored Resume (PDF)"):
                current_api_key = config.get("api_key", "")
                if not uploaded_resume or not current_api_key:
                    st.error("Please upload a resume and provide an API key in Settings (and press Save).")
                else:
                    with st.spinner("Compiling LaTeX Resume with Gemini..."):
                        try:
                            # Use original endpoint for resume tailoring
                            files = {"resume_file": (uploaded_resume.name, uploaded_resume, "application/pdf")}
                            data = {"api_key": current_api_key, "jd_text": selected_job.get("description", "")}
                            res = requests.post(f"{FASTAPI_URL}/tailor/", files=files, data=data)
                            if res.status_code == 200:
                                result = res.json()
                                pdf_data = result["pdf_base64"]
                                
                                st.download_button(
                                    label="Download Tailored Resume",
                                    data=base64.b64decode(pdf_data),
                                    file_name=f"Tailored_Resume_{selected_job['id']}.pdf",
                                    mime="application/pdf"
                                )
                                st.success("Resume Generated Successfully!")
                            else:
                                st.error(f"Error: {res.text}")
                        except Exception as e:
                            st.error(f"Failed to connect: {e}")

        # Show existing or newly generated cover letter
        current_cl = st.session_state.get(f"cl_{selected_job['id']}", selected_job.get("cover_letter"))
        if current_cl:
            st.subheader("Your Cover Letter")
            st.text_area("Cover Letter Output", current_cl, height=400)
