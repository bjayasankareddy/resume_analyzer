# **VeriSkill \- AI-Powered Resume Analyzer**

VeriSkill is an intelligent, full-stack application designed to automate and enhance the initial stages of the recruitment process. It leverages the power of Generative AI to parse, analyze, and score candidate resumes against a given job description, providing recruiters with actionable insights and a ranked list of candidates.

## **Table of Contents**

* [About The Project](https://www.google.com/search?q=%23about-the-project)  
* [Key Features](https://www.google.com/search?q=%23key-features)  
* [How It Works](https://www.google.com/search?q=%23how-it-works)  
* [Getting Started](https://www.google.com/search?q=%23getting-started)  
  * [Prerequisites](https://www.google.com/search?q=%23prerequisites)  
  * [Installation & Setup](https://www.google.com/search?q=%23installation--setup)  
* [Usage](https://www.google.com/search?q=%23usage)  
* [Technology Stack](https://www.google.com/search?q=%23technology-stack)  
* [Project Roadmap (Future Enhancements)](https://www.google.com/search?q=%23project-roadmap-future-enhancements)

## **About The Project**

In today's competitive job market, recruiters are often inundated with hundreds of resumes for a single position. Manually screening these documents is time-consuming, prone to bias, and inefficient.

VeriSkill addresses this challenge by providing an automated solution that not only matches keywords but also attempts to verify a candidate's skills and experience. It intelligently extracts information, analyzes a candidate's projects and online presence (like GitHub), and provides a holistic score, allowing recruiters to focus their time on the most promising candidates.

## **Key Features**

* **AI-Powered Analysis:** Uses Google's Gemini Pro model to understand the context of both the resume and the job description.  
* **Multi-Resume Processing:** Upload and analyze multiple resumes against a single job description in one batch.  
* **Skill Gap Identification:** Automatically identifies which required skills the candidate possesses and which they are lacking.  
* **GitHub Verification:** If a GitHub profile is provided, the application analyzes the candidate's public repositories to verify programming languages and project activity.  
* **Automated Email Notifications:** Sends a personalized email to each candidate with a summary of their analysis, including their match score and a breakdown of strengths and weaknesses.  
* **Summarized Reporting:** Generates a clean, tabular summary of all candidates, ranked by their match score, for a quick overview.  
* **Professional UI:** A clean, modern, and responsive user interface for a seamless user experience.

## **How It Works**

1. **Upload:** The recruiter uploads a job description and one or more candidate resumes via the web interface.  
2. **Parse:** The Python backend parses the PDF or DOCX files to extract raw text.  
3. **Analyze:** The extracted text is sent to the Gemini AI model with a detailed prompt, instructing it to return a structured JSON object containing the candidate's details, match score, and skill analysis.  
4. **Verify:** If a GitHub link is present, the backend uses the GitHub API to fetch and analyze repository data.  
5. **Notify:** An email is automatically sent to the candidate with their results.  
6. **Summarize:** A CSV summary of all candidates is generated.  
7. **Display:** The final results, including a summary table and detailed cards for each candidate, are sent back to the frontend and displayed on the dashboard.

## **Getting Started**

Follow these instructions to get a copy of the project up and running on your local machine.

### **Prerequisites**

* Python 3.8+  
* pip (Python package installer)  
* A web browser

### **Installation & Setup**

1. **Clone the Repository**  
   git clone \[https://github.com/your-username/veriskill.git\](https://github.com/your-username/veriskill.git)  
   cd veriskill

2. **Install Python Packages**  
   pip install \-r requirements.txt

   *(Note: You will need to create a requirements.txt file containing all the necessary libraries: Flask, PyMuPDF, python-docx, google-generativeai, requests, python-dotenv, PyGithub, Flask-Cors)*  
3. **Set Up Environment Variables**  
   Create a file named .env in the root of your project directory and add the following, replacing the placeholder values with your actual credentials:  
   \# Google AI API Key for Gemini  
   GOOGLE\_API\_KEY="your-google-api-key-here"

   \# GitHub Personal Access Token (for reading public repos)  
   GITHUB\_ACCESS\_TOKEN="your-github-personal-access-token-here"

   \# \--- SMTP Email Configuration (Example for Gmail) \---  
   \# NOTE: For Gmail, use an "App Password", not your regular password.  
   SMTP\_SERVER="smtp.gmail.com"  
   SMTP\_PORT="465"  
   SMTP\_USERNAME="your-email@gmail.com"  
   SMTP\_PASSWORD="your-gmail-app-password-here"

## **Usage**

1. Run the Backend Server  
   Open your terminal in the project directory and run:  
   python app.py  

# resume_analyzer
this project analysis the resume and give the score to it and sends to the analysis report to the job seeker. This project is mainly  for the job hirer so they can save time 
