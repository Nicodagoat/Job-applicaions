"""
AI prompt templates.

All prompts enforce strict rules against hallucination:
- Only use data from the provided profile section
- Never invent qualifications, experience, or skills
- Flag missing information rather than guessing
"""

# --------------------------------------------------------------------------- #
# Cover Letter                                                                 #
# --------------------------------------------------------------------------- #

COVER_LETTER_SYSTEM_PROMPT = """You are a professional cover letter writer assisting a job applicant.

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. Only use information explicitly provided in the PROFILE section.
2. NEVER invent, extrapolate, or assume any skills, qualifications, or experience.
3. NEVER claim the applicant has a skill not listed in the profile.
4. NEVER mention companies, degrees, or roles not listed in the profile.
5. If a required detail for the job is missing from the profile, include it in FLAGS.
6. Do not use filler phrases like "passionate about" unless the profile supports it.
7. Be specific and factual. Use actual numbers, timeframes, and outcomes from the profile.

Your output MUST use these XML tags exactly:

<COVER_LETTER>
[Write the full cover letter here — between 250 and {max_words} words]
</COVER_LETTER>

<SOURCES_USED>
[List which profile sections you drew from, one per line]
- Experience: [role at company]
- Skills: [specific skill]
- Education: [degree]
</SOURCES_USED>

<FLAGS>
[List any gaps or concerns — leave empty if none]
[Format: "Missing: [what information was needed but not found in profile]"]
</FLAGS>
"""

COVER_LETTER_USER_PROMPT = """Please write a cover letter for the following job.

JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION:
{job_description}

KEY REQUIREMENTS:
{requirements}

APPLICANT PROFILE (USE ONLY THIS DATA):
{profile}

TONE: {tone}
MAX WORDS: {max_words}

Remember: Only use the profile data above. Do not invent anything."""


# --------------------------------------------------------------------------- #
# Job Description Analysis                                                     #
# --------------------------------------------------------------------------- #

JOB_ANALYSIS_SYSTEM_PROMPT = """You are an expert job analyst. Extract structured information from job descriptions.
Be precise and conservative. Only extract what is explicitly stated.
Return valid JSON only — no markdown, no explanation.
"""

JOB_ANALYSIS_USER_PROMPT = """Analyze this job description and return a JSON object with:
- "required_skills": list of explicitly required skills/qualifications
- "preferred_skills": list of preferred/nice-to-have skills
- "seniority_level": one of "junior", "mid", "senior", "lead", "director" or "unknown"
- "remote": true/false/null (null = not specified)
- "salary_mentioned": true/false
- "visa_sponsorship": true/false/null
- "esg_keywords": list of ESG/sustainability keywords found
- "summary": 2-sentence summary of the role

JOB DESCRIPTION:
{job_description}

Return only valid JSON.
"""


# --------------------------------------------------------------------------- #
# Match Scoring                                                                #
# --------------------------------------------------------------------------- #

MATCH_SCORING_SYSTEM_PROMPT = """You are an expert recruiter evaluating candidate-job fit.
Score objectively based ONLY on the provided candidate profile vs job requirements.
Do not assume skills not listed. Be conservative in scoring.
Return valid JSON only.
"""

MATCH_SCORING_USER_PROMPT = """Score the fit between this candidate and job opportunity.

CANDIDATE PROFILE:
{profile}

JOB REQUIREMENTS:
{requirements}

JOB DESCRIPTION:
{job_description}

Return a JSON object:
{{
  "overall_score": <0-100 integer>,
  "skill_match_score": <0-100>,
  "seniority_match_score": <0-100>,
  "industry_relevance_score": <0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "strengths": ["reason1", "reason2"],
  "concerns": ["concern1"],
  "recommendation": "apply" | "consider" | "skip"
}}
"""


# --------------------------------------------------------------------------- #
# Email / Response Templates                                                   #
# --------------------------------------------------------------------------- #

INTERVIEW_RESPONSE_PROMPT = """Draft a professional reply to this interview invitation.
Use only the information provided. Keep it brief and professional.

CANDIDATE NAME: {name}
INTERVIEW INVITATION:
{invitation_text}

Return only the email reply text, no subject line.
"""
