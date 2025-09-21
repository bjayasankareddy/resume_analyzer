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
from flask import Flask, request, jsonify
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
    print("Please ensure GOOGLE_API_KEY, GITHUB_ACCESS_TOKEN, and all SMTP variables are set in your .env file.")
    exit()

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_file(file_path):
    text = ""
    try:
        if file_path.lower().endswith('.pdf'):
            with fitz.open(file_path) as doc:
                text = "".join(page.get_text() for page in doc)
        elif file_path.lower().endswith('.docx'):
            doc = docx.Document(file_path)
            text = "\n".join(para.text for para in doc.paragraphs)
        return text
    except Exception as e:
        return f"Error parsing file: {e}"
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                print(f"Error removing temporary file {file_path}: {e}")

def send_email_to_candidate(candidate_email, candidate_name, reasoning, match_score):
    if not candidate_email:
        return False, "No email address found"
    
    msg = EmailMessage()
    msg['Subject'] = 'Your Resume Analysis Results'
    msg['From'] = SMTP_USERNAME
    msg['To'] = candidate_email

    formatted_reasoning = "\n".join([f"  {line.strip()}" for line in reasoning.strip().split('\n') if line.strip()])
    
    plain_text_content = f"""
Dear {candidate_name or 'Candidate'},

Thank you for your interest. We have completed an automated analysis of your resume.
Your profile received a match score of: {match_score}/100

Here is a summary of our findings:
-----------------------------------------
{formatted_reasoning}
-----------------------------------------

Best regards,
The Hiring Team
"""
    html_content = f"""
    <html><body>
    <p>Dear {candidate_name or 'Candidate'},</p>
    <p>Thank you for your interest. We have completed an automated analysis of your resume.</p>
    <p>Your profile received a match score of: <strong>{match_score}/100</strong></p>
    <p>Here is a summary of the analysis:</p>
    <div style="background-color:#f4f4f4; border-left: 5px solid #ccc; padding: 10px; margin: 10px 0;">
      <pre style="white-space: pre-wrap; font-family: monospace;">{reasoning}</pre>
    </div>
    <p>Best regards,<br>The Hiring Team</p>
    </body></html>
    """
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

def verify_external_links(links_dict):
    verification_results = {}
    if not isinstance(links_dict, dict): return {"error": "Invalid links format"}
    for link_type, url in links_dict.items():
        if url and isinstance(url, str) and url.startswith('http'):
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                verification_results[link_type] = "OK" if 200 <= response.status_code < 300 else f"Broken (Status: {response.status_code})"
            except requests.RequestException as e:
                verification_results[link_type] = f"Unreachable ({type(e).__name__})"
        else:
            verification_results[link_type] = "Not Provided"
    return verification_results

def analyze_github_profile(github_url):
    if not github_url or "github.com" not in github_url: return {"status": "Not a valid GitHub URL"}
    match = re.search(r"github\.com/([a-zA-Z0-9_-]+)", github_url)
    if not match: return {"status": "Could not extract username"}
    username = match.group(1)
    try:
        user = g.get_user(username)
        repos = user.get_repos(sort="pushed", direction="desc")
        repo_analysis = [{"name": repo.name, "url": repo.html_url, "description": repo.description or "", "languages": list(repo.get_languages().keys())} for repo in repos[:5]]
        return {"status": "Analysis Complete", "username": username, "total_public_repos": user.public_repos, "repositories": repo_analysis}
    except Exception as e:
        return {"status": f"Error accessing GitHub profile: {str(e)}"}

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

@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    if 'resumes' not in request.files or 'job_description' not in request.files:
        return jsonify({"error": "Both 'resumes' and 'job_description' files are required."}), 400
    
    resume_files = request.files.getlist('resumes')
    jd_file = request.files['job_description']
    
    if not resume_files or not jd_file or jd_file.filename == '':
        return jsonify({"error": "No file selected for one or both inputs."}), 400

    jd_text = parse_file(save_temp_file(jd_file))
    if "Error" in jd_text: return jsonify({"error": f"Failed to process job description: {jd_text}"}), 500
    
    all_results = []
    for resume_file in resume_files:
        analysis_result = {"filename": resume_file.filename}
        
        try:
            if not allowed_file(resume_file.filename):
                raise ValueError("Invalid file type")

            resume_text = parse_file(save_temp_file(resume_file))
            if "Error" in resume_text:
                raise ValueError(f"Failed to parse file: {resume_text}")

            extracted_json_str = analyze_resume_and_jd(resume_text, jd_text)
            
            try:
                cleaned_str = extracted_json_str.strip().replace('```json', '').replace('```', '')
                parsed_json = json.loads(cleaned_str)
                
            except json.JSONDecodeError:
                print(f"!!! FAILED TO PARSE JSON for {resume_file.filename} !!!")
                print("--- RAW RESPONSE FROM AI ---")
                print(extracted_json_str)
                print("----------------------------")
                raise ValueError("AI model returned invalid JSON.")

            if not parsed_json.get("resume_data", {}).get("projects"):
                analysis_result.update({"status": "REJECTED", "reason": "No projects found in resume."})
                all_results.append(analysis_result)
                continue

            links = parsed_json.get("resume_data", {}).get("external_links", {})
            parsed_json["link_verification"] = verify_external_links(links)
            
            github_url = links.get("github")
            if github_url and parsed_json["link_verification"].get("github") == "OK":
                parsed_json["github_analysis"] = analyze_github_profile(github_url)
            
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
                print(f"--- EMAIL STATUS for {contact_info.get('email')}: {status} ---")

            analysis_result["data"] = parsed_json

        except Exception as e:
            print(f"!!! ERROR processing {resume_file.filename}: {e}")
            analysis_result.update({"status": "FAILED", "reason": str(e)})
        
        all_results.append(analysis_result)

    # --- GENERATE CSV SUMMARY ---
    csv_output = ""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        header = ["Name", "Email", "Phone", "Score", "Skills Possessed", "Skills Lacking"]
        writer.writerow(header)
        
        for result in all_results:
            if result.get("data"):
                data = result["data"]
                contact_info = data.get("resume_data", {}).get("contact_info", {})
                match_analysis = data.get("match_analysis", {})
                
                skills_possessed_str = ", ".join(match_analysis.get("skills_possessed", []))
                skills_lacking_str = ", ".join(match_analysis.get("skills_lacking", []))
                
                row = [
                    contact_info.get("name", "N/A"),
                    contact_info.get("email", "N/A"),
                    contact_info.get("phone", "N/A"),
                    match_analysis.get("match_score", "N/A"),
                    skills_possessed_str,
                    skills_lacking_str
                ]
                writer.writerow(row)
        
        csv_output = output.getvalue()
        
        print("\n\n--- CANDIDATE ANALYSIS SUMMARY (CSV) ---")
        print(csv_output)
        print("----------------------------------------\n")

    except Exception as e:
        print(f"\n!!! Could not generate CSV summary. Reason: {e} !!!\n")

    # --- RETURN BOTH DETAILED RESULTS AND CSV SUMMARY ---
    return jsonify({
        "detailed_results": all_results,
        "csv_summary": csv_output
    }), 200

def save_temp_file(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    return file_path

if __name__ == '__main__':
    app.run(debug=True)

