# Copyright (C) 2026 its-sorakun
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import os
from .pdf_rag import advanced_pdf_query

def draft_job_application_email(resume_pdf_path: str, company_name: str, job_role: str) -> str:
    """
    Analyzes the provided resume PDF and returns a strict meta-instruction for Kiko to draft a perfectly formatted professional job application email.
    Use this tool when you are ready to actually write the email draft.
    """
    print(f"   [⚡ Kiko is evaluating {os.path.basename(resume_pdf_path)} for the {job_role} role at {company_name}...] ")
    
    # Extract the relevant context from the PDF using the existing LangGraph FAISS tool
    query = f"Extract all technical skills, achievements, and specific projects relevant to a {job_role} role."
    context_response = advanced_pdf_query(resume_pdf_path, query)
    
    # Construct the meta-instruction (Jailbreak) payload
    jailbreak_prompt = f"""
{context_response}

[STRICT INSTRUCTION TO KIKO]: 
You must immediately draft a professional job application email for the role of {job_role} at {company_name}.
You must strictly adhere to the following rules:
1. Use a concise, single-paragraph format (do not split into multiple paragraphs or bullet points).
2. Explicitly mention at least one highly relevant project, skill, or achievement from the resume context above.
3. Keep the tone highly professional and technical.
4. Do NOT use any placeholders (like [Company Name] or [Your Name]). If you don't know the exact HR name, use "Hiring Manager". Use the name found in the resume.
5. Do NOT output any conversational text, emojis, or Japanese words BEFORE or INSIDE the email draft. You may speak normally AFTER the draft.

Output the email draft now.
"""
    return jailbreak_prompt
