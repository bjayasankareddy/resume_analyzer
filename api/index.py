import os
import fitz  # PyMuPDF
import docx
import google.generativeai as genai
import json
import requests
import re
import smtplib
import csv
import io
from email.message import EmailMessage
from flask import Flask, request, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from github import Auth, Github, GithubException

# Load environment variables from a .env file
load_dotenv()

# --- Configuration for APIs ---
try:
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    GITHUB_ACCESS_TOKEN = os.environ["GITHUB_ACCESS_TOKEN"]
    genai.configure(api_key=GOOGLE_API_KEY)
    
    auth = Auth.Token(GITHUB_ACCESS_TOKEN)
    g = Github(auth=auth)

    SMTP_SERVER = os.environ["SMTP_SERVER"]
    SMTP_PORT = os.environ["SMTP_PORT"]
    SMTP_USERNAME = os.environ["SMTP_USERNAME"]
    SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

except KeyError as e:
    print(f"FATAL: Environment variable {e} not found.")
    print("Please ensure all required API keys and SMTP variables are set in your .env file.")
    exit()

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='../templates')
CORS(app)

# Vercel's serverless environment is read-only, except for the /tmp directory.
UPLOAD_FOLDER = '/tmp/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'} # This line was missing
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_file(file_path):
    text = ""
    try:
        if file_path.lower().endswith('.pdf'):
            with fitz.open(file_path) as doc: text = "".join(page.get_text() for page in doc)
        elif file_path.lower().endswith('.docx'):
            doc = docx.Document(file_path)
            text = "\n".join(para.text for para in doc.paragraphs)
        return text
    except Exception as e:
        return f"Error parsing file: {e}"
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except OSError as e: print(f"Error removing temp file {file_path}: {e}")

def send_email_to_candidate(candidate_email, candidate_name, reasoning, match_score):
    if not candidate_email: return False, "No email address found"
    msg = EmailMessage()
    msg['Subject'] = 'Your Resume Analysis Results'
    msg['From'] = SMTP_USERNAME
    msg['To'] = candidate_email
    formatted_reasoning = "\n".join([f"  {line.strip()}" for line in reasoning.strip().split('\n') if line.strip()])
    plain_text_content = f"Dear {candidate_name or 'Candidate'},\n\nThank you for your interest. We have completed an automated analysis of your resume.\n\nYour profile received a match score of: {match_score}/100\n\nHere is a summary of our findings:\n-----------------------------------------\n{formatted_reasoning}\n-----------------------------------------\n\nBest regards,\nThe Hiring Team"
    html_content = f'<html><body><p>Dear {candidate_name or "Candidate"},</p><p>Thank you for your interest. We have completed an automated analysis of your resume.</p><p>Your profile received a match score of: <strong>{match_score}/100</strong></p><p>Here is a summary of the analysis:</p><div style="background-color:#f4f4f4; border-left: 5px solid #ccc; padding: 10px; margin: 10px 0;"><pre style="white-space: pre-wrap; font-family: monospace;">{reasoning}</pre></div><p>Best regards,<br>The Hiring Team</p></body></html>'
    msg.set_content(plain_text_content)
    msg.add_alternative(html_content, subtype='html')
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, int(SMTP_PORT)) as smtp:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True, "Email sent successfully"
    except Exception as e:
        print(f"ERROR: Could not send email to {candidate_email}. Reason: {e}")
        return False, str(e)

def analyze_resume_and_jd(resume_text, jd_text):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
You are an expert HR recruitment assistant. Analyze the provided resume and job description.
Return a single valid JSON object with the exact schema below.

--- Resume Text ---
{resume_text}

--- Job Description Text ---
{jd_text}

--- JSON SCHEMA ---
{{
  "resume_data": {{
    "contact_info": {{"name": "string", "email": "string", "phone": "string"}},
    "skills": ["string"],
    "work_experience": [{{"job_title": "string", "company": "string", "duration": "string", "responsibilities": ["string"]}}],
    "education": [{{"degree": "string", "institution": "string", "graduation_year": "string"}}],
    "projects": [{{"name": "string", "description": "string", "technologies_used": ["string"], "url": "string"}}],
    "external_links": {{"github": "string", "linkedin": "string", "portfolio": "string"}}
  }},
  "match_analysis": {{
    "match_score": "integer (0-100)",
    "summary": "string (paragraph explaining the score)",
    "reasoning": "string (A bulleted list of strengths and weaknesses based on the JD. Example: '- Strength: 5 years of Python experience.\\n- Weakness: Lacks AWS experience.')",
    "skills_possessed": ["string"],
    "skills_lacking": ["string"]
  }}
}}
- "skills_possessed": Key skills from the JD that the candidate has.
- "skills_lacking": Key skills from the JD the candidate is missing.
If a section is not found, use an empty list `[]` or null. The output must be ONLY the JSON object.
"""
    response = model.generate_content(prompt)
    return response.text

# --- Routes ---
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    if 'resumes' not in request.files or 'job_description' not in request.files:
        return "Both 'resumes' and 'job_description' files are required.", 400
    
    resume_files = request.files.getlist('resumes')
    jd_file = request.files['job_description']
    
    if not resume_files or not jd_file or jd_file.filename == '':
         return "No file selected for one or both inputs.", 400

    jd_text = parse_file(save_temp_file(jd_file))
    if "Error" in jd_text: return f"Failed to process job description: {jd_text}", 500
    
    all_results = []
    for resume_file in resume_files:
        analysis_result = {"filename": resume_file.filename}
        try:
            if not allowed_file(resume_file.filename): raise ValueError("Invalid file type")
            resume_text = parse_file(save_temp_file(resume_file))
            if "Error" in resume_text: raise ValueError(f"Failed to parse file: {resume_text}")
            
            extracted_json_str = analyze_resume_and_jd(resume_text, jd_text)
            try:
                cleaned_str = extracted_json_str.strip().replace('```json', '').replace('```', '')
                parsed_json = json.loads(cleaned_str)
            except json.JSONDecodeError:
                raise ValueError("AI model returned invalid JSON.")

            if not parsed_json.get("resume_data", {}).get("projects"):
                analysis_result.update({"status": "REJECTED", "reason": "No projects found in resume."})
                all_results.append(analysis_result)
                continue
            
            contact_info = parsed_json.get("resume_data", {}).get("contact_info", {})
            match_analysis = parsed_json.get("match_analysis", {})
            if contact_info.get("email") and match_analysis.get("reasoning"):
                sent, status = send_email_to_candidate(
                    candidate_email=contact_info.get("email"),
                    candidate_name=contact_info.get("name"),
                    reasoning=match_analysis.get("reasoning"),
                    match_score=match_analysis.get("match_score")
                )
                parsed_json["email_notification"] = {"sent": sent, "status": status}

            analysis_result["data"] = parsed_json
        except Exception as e:
            print(f"!!! ERROR processing {resume_file.filename}: {e}")
            analysis_result.update({"status": "FAILED", "reason": str(e)})
        
        all_results.append(analysis_result)

    csv_rows = []
    try:
        header = ["Name", "Email", "Score", "Skills Possessed", "Skills Lacking"]
        csv_rows.append(header)
        successful_results = [r for r in all_results if r.get("data")]
        successful_results.sort(key=lambda x: x.get("data", {}).get("match_analysis", {}).get("match_score", 0), reverse=True)
        for result in successful_results:
            data = result["data"]
            contact_info = data.get("resume_data", {}).get("contact_info", {})
            match_analysis = data.get("match_analysis", {})
            skills_possessed_str = ", ".join(match_analysis.get("skills_possessed", []))
            skills_lacking_str = ", ".join(match_analysis.get("skills_lacking", []))
            row = [
                contact_info.get("name", "N/A"),
                contact_info.get("email", "N/A"),
                match_analysis.get("match_score", "N/A"),
                skills_possessed_str,
                skills_lacking_str
            ]
            csv_rows.append(row)
    except Exception as e:
        print(f"Could not generate CSV data: {e}")
    
    all_results.sort(key=lambda x: x.get("data", {}).get("match_analysis", {}).get("match_score", 0), reverse=True)
    return render_template('results.html', detailed_results=all_results, summary_data=csv_rows)

def save_temp_file(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    return file_path

