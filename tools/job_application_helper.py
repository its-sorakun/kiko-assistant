import os
from google import genai
from .pdf_rag import advanced_pdf_query
from .clipboard import copy_to_clipboard

def draft_and_copy_job_email(company_name: str, job_description: str, resume_pdf_path: str) -> str:
    """
    Dedicated orchestration tool to draft a professional job application email based on a resume and 
    copy it directly to the Windows clipboard. This bypasses Kiko's anime persona for the email body.
    """
    print(f"   [⚡ Kiko is evaluating {os.path.basename(resume_pdf_path)} for the {job_description} role at {company_name}...] ")
    
    # 1. Extract context from the resume
    query = f"Extract all technical skills, achievements, and specific projects relevant to a {job_description} role."
    context_response = advanced_pdf_query(resume_pdf_path, query)
    
    # 2. Setup the strict prompt for the isolated LLM call
    prompt = f"""
Resume Context:
{context_response}

You are an expert technical recruiter and professional copywriter.
Draft a highly professional, concise, single-paragraph job application email for the role of {job_description} at {company_name}.

Rules:
1. Use a single paragraph format (do not split into multiple paragraphs or bullet points).
2. Explicitly mention at least one highly relevant project, skill, or achievement from the resume context above.
3. Keep the tone highly professional and technical.
4. Do NOT use any placeholders (like [Company Name] or [Your Name]). If you don't know the exact HR name, use "Hiring Manager". Use the applicant's name found in the resume.
5. Do NOT include any conversational filler, subject lines, or introductory/concluding remarks outside of the email body itself. The output must ONLY be the email content.
"""
    
    try:
        # 3. Generate the email using a raw Google GenAI API call
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "Failed to draft email: GEMINI_API_KEY is not set in the environment."
            
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt
        )
        
        drafted_email = response.text.strip()
        
        # 4. Copy to clipboard
        clipboard_status = copy_to_clipboard(drafted_email)
        
        # 5. Return status to Kiko
        return f"Successfully drafted the email and copied it to the clipboard!\n\nClipboard Status: {clipboard_status}\n\nDrafted Email:\n{drafted_email}"
        
    except Exception as e:
        return f"Failed to draft the email: {e}"
