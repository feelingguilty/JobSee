import re
import os
from collections import Counter
# import PyPDF2 # Option 1 for PDF
import pdfplumber # Option 2 for PDF (often better)
# from docx import Document
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import subprocess
import sys
import nltk
# import exceptions
# Ensure NLTK data is available
def ensure_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)

    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)

# --- Text Extraction Functions ---
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        # Using pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: # Ensure text was extracted
                    text += page_text + "\n"
        # # Alternative: Using PyPDF2
        # with open(pdf_path, 'rb') as file:
        #     reader = PyPDF2.PdfReader(file)
        #     for page_num in range(len(reader.pages)):
        #         page = reader.pages[page_num]
        #         text += page.extract_text()
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

# def extract_text_from_docx(docx_path):
#     text = ""
#     try:
#         doc = Document(docx_path)
#         for para in doc.paragraphs:
#             text += para.text + "\n"
#     except Exception as e:
#         print(f"Error reading DOCX {docx_path}: {e}")
#     return text

def extract_text_from_txt(txt_path):
    text = ""
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            text = file.read()
    except Exception as e:
        print(f"Error reading TXT {txt_path}: {e}")
    return text

def get_text_from_file(file_path):
    _, extension = os.path.splitext(file_path.lower())
    if extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif extension == '.txt':
        return extract_text_from_txt(file_path)
    else:
        print(f"Unsupported file format: {extension}")
        return ""

# --- Information Extraction Functions ---
def extract_emails(text):
    # Basic email regex
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return list(set(emails)) # Unique emails

def extract_phones(text):
    # Basic phone regex (adjust for different formats if needed)
    # This regex is quite broad
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    return list(set(phones))

# Example skill list (can be expanded significantly)
PREDEFINED_SKILLS = [
    'python', 'java', 'c++', 'javascript', 'html', 'css', 'sql', 'nosql', 'mongodb',
    'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring',
    'machine learning', 'deep learning', 'data science', 'data analysis',
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'jira', 'agile',
    'communication', 'teamwork', 'problem solving', 'leadership', 'project management'
]

def extract_skills(text, skill_list=PREDEFINED_SKILLS):
    found_skills = set()
    text_lower = text.lower()
    for skill in skill_list:
        # Use word boundaries for more precise matching
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.add(skill.capitalize()) # Capitalize for display
    return list(found_skills)

def extract_keywords(text, num_keywords=10):
    if not text:
        return []
    tokens = word_tokenize(text.lower())
    # Filter out stopwords and non-alphabetic tokens
    filtered_tokens = [word for word in tokens if word.isalpha() and word not in stop_words]
    counts = Counter(filtered_tokens)
    return [item[0] for item in counts.most_common(num_keywords)]

# --- Resume Analysis Function ---
def analyze_resume_text(resume_text):
    if not resume_text:
        return {"error": "Could not extract text from resume."}

    analysis = {}
    analysis['emails'] = extract_emails(resume_text)
    analysis['phones'] = extract_phones(resume_text)
    analysis['skills'] = extract_skills(resume_text)
    analysis['keywords'] = extract_keywords(resume_text, 15)
    analysis['full_text_preview'] = resume_text[:500] + "..." # Preview

    return analysis

# --- Job Description Matching ---
def calculate_similarity(resume_text, jd_text):
    if not resume_text or not jd_text:
        return 0.0

    corpus = [resume_text, jd_text]
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)
        # cosine_similarity returns a matrix, we need the similarity between the 2 docs
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return round(similarity * 100, 2) # As percentage
    except ValueError: # Handle empty vocabulary case
        return 0.0
    except Exception as e:
        print(f"Error in TF-IDF calculation: {e}")
        return 0.0

if __name__ == '__main__':
    # --- Test the parser functions (run this file directly) ---
    # Create dummy files for testing or use your own
    # Dummy TXT
    ensure_nltk_data()
    with open("dummy_resume.txt", "w") as f:
        f.write("John Doe\nEmail: john.doe@example.com\nPhone: (123) 456-7890\nSkills: Python, Java, SQL.\nExperience in data analysis.")

    # Dummy DOCX (you'd need to create this manually or via code if you want to automate it)
    # For now, assume it exists or test with a real one.
    # from docx import Document as DocxDoc
    # doc = DocxDoc()
    # doc.add_paragraph("Jane Smith\nContact: jane.smith@email.net, 555-123-4567\nExpert in Machine Learning and Python.")
    # doc.save("dummy_resume.docx")

    # Dummy PDF (same, create manually or via code)
    # For now, assume it exists or test with a real one.

    print("--- Testing TXT Resume ---")
    txt_file = "dummy_resume.txt"
    if os.path.exists(txt_file):
        resume_text_txt = get_text_from_file(txt_file)
        analysis_txt = analyze_resume_text(resume_text_txt)
        print(analysis_txt)
    else:
        print(f"{txt_file} not found for testing.")

    # print("\n--- Testing DOCX Resume ---")
    # docx_file = "dummy_resume.docx" # Replace with your DOCX file
    # if os.path.exists(docx_file):
    #     resume_text_docx = get_text_from_file(docx_file)
    #     analysis_docx = analyze_resume_text(resume_text_docx)
    #     print(analysis_docx)
    # else:
    #     print(f"{docx_file} not found. Please create or provide one for testing.")

    # print("\n--- Testing PDF Resume ---")
    # pdf_file = "your_resume.pdf" # Replace with your PDF file
    # if os.path.exists(pdf_file):
    #     resume_text_pdf = get_text_from_file(pdf_file)
    #     analysis_pdf = analyze_resume_text(resume_text_pdf)
    #     print(analysis_pdf)
    # else:
    #     print(f"{pdf_file} not found. Please create or provide one for testing.")
    
    print("\n--- Testing Similarity ---")
    resume_sample = "Experienced Python developer with skills in machine learning, data analysis, and web development using Django."
    jd_sample = "Looking for a Python developer with machine learning knowledge. Experience with Django is a plus. Strong data analysis skills required."
    similarity_score = calculate_similarity(resume_sample, jd_sample)
    print(f"Similarity Score: {similarity_score}%")

    jd_sample_diff = "Seeking a graphic designer with Adobe Photoshop skills."
    similarity_score_diff = calculate_similarity(resume_sample, jd_sample_diff)
    print(f"Similarity Score (different JD): {similarity_score_diff}%")