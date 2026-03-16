
import streamlit as st
import httpx
import os

st.set_page_config(
    page_title="AIV Resume Tailor",
    page_icon="📄",
    layout="wide"
)

st.title("📄 AIV Resume Tailor")
st.markdown("---")

st.info(
    "**How it works:** This tool uses an AI agent to analyze your resume against a job description. "
    "It identifies gaps, rewrites sections, and generates a new, optimized resume in LaTeX format, "
    "which is then compiled into a professional-looking PDF."
)
st.markdown("---")


col1, col2 = st.columns(2)

with col1:
    st.subheader("Your Information")
    api_key = st.text_input("Enter your Google Gemini API Key", type="password", help="Your API key is sent securely and is not stored.")
    resume_file = st.file_uploader("Upload your Resume (PDF only)", type="pdf")

with col2:
    st.subheader("Target Job")
    jd_text = st.text_area("Paste the Job Description here", height=250)


if st.button("✨ Tailor My Resume"):
    if not api_key:
        st.error("Please enter your API key.")
    elif not jd_text:
        st.error("Please paste the job description.")
    elif not resume_file:
        st.error("Please upload your resume.")
    else:
        with st.spinner("Writing and compiling your new resume... This may take up to a minute."):
            files = {'resume_file': (resume_file.name, resume_file.getvalue(), resume_file.type)}
            data = {'api_key': api_key, 'jd_text': jd_text}
            
            # FastAPI endpoint URL
            url = "http://127.0.0.1:8000/tailor/"

            try:
                # Using httpx to send the request
                with httpx.Client(timeout=300) as client:
                    response = client.post(url, files=files, data=data)

                if response.status_code == 200:
                    st.success("Your tailored resume is ready!")
                    st.download_button(
                        label="Download Your Optimized Resume (PDF)",
                        data=response.content,
                        file_name="Optimized_Resume.pdf",
                        mime="application/pdf",
                    )
                else:
                    try:
                        # Try to parse the JSON error detail
                        error_detail = response.json().get("detail", "No detail provided.")
                    except Exception:
                        # Fallback to raw text if JSON parsing fails
                        error_detail = response.text
                    st.error(f"An error occurred: {response.status_code}")
                    st.error(f"Details: {error_detail}")

            except httpx.ConnectError:
                st.error("Connection Error: Could not connect to the backend service. Please ensure the FastAPI server is running.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
