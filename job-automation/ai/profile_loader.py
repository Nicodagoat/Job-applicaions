"""
Profile loader — single source of truth for all AI operations.

The AI is ONLY allowed to use data from this module.
Any information not found here must be treated as unknown
and the system must pause and ask the user.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


_PROFILE_PATH = Path(__file__).parent.parent / "config" / "profile.yaml"


def load_profile() -> dict[str, Any]:
    """Load the user profile config. Raises FileNotFoundError if missing."""
    with open(_PROFILE_PATH) as f:
        return yaml.safe_load(f)


# Canonical profile facts —— built from the real resume.
# These are hardcoded as ground truth so the AI cannot drift.
PROFILE_FACTS = {
    "name": "Niccolò Andrea Nolli",
    "email": "niccolonolli@gmail.com",
    "phone": "+39 3896940163",
    "linkedin": "https://www.linkedin.com/in/niccolo-andrea-nolli",
    "location": "Milan, Italy",
    "open_to_relocation": True,
    "languages": [
        {"language": "Italian", "level": "Native"},
        {"language": "English", "level": "Bilingual"},
    ],
    "education": [
        {
            "degree": "MSc Political Economy of Development",
            "institution": "SOAS, University of London",
            "location": "London, United Kingdom",
            "period": "August 2020 – September 2021",
            "result": "Merit",
        },
        {
            "degree": "Bachelor in Political Science and Economics",
            "institution": "University of Milan",
            "location": "Milan, Italy",
            "period": "August 2017 – June 2020",
            "result": "99/110",
        },
        {
            "degree": "International Baccalaureate Bilingual Diploma",
            "institution": "Windermere International School",
            "location": "Windermere, United Kingdom",
            "period": "2015 – 2017",
        },
    ],
    "experience": [
        {
            "title": "Sustainability Specialist",
            "company": "Limenet",
            "location": "Lecco, Italy",
            "period": "September 2025 – Present",
            "responsibilities": [
                "Advising clients on implementing key EU sustainability regulations including CSRD and EU Taxonomy.",
                "Developing strategies for regulatory compliance and sustainability market positioning.",
                "Conducting policy and market analysis related to the green transition.",
                "Supporting grant applications and strategic sustainability planning.",
            ],
        },
        {
            "title": "ESG Specialist",
            "company": "PQE Group",
            "location": "Milan, Italy",
            "period": "September 2024 – September 2025",
            "responsibilities": [
                "Led the full process for CSRD compliance and sustainability reporting.",
                "Managed ESG data analysis and final sustainability report preparation.",
                "Coordinated internal and external stakeholders on ESG initiatives.",
                "Facilitated cross-functional sustainability working groups.",
                "Monitored ESG regulatory developments and produced policy briefings.",
            ],
        },
        {
            "title": "Consultant – Freelance",
            "company": "InnovaBeyond | ESGeo",
            "location": "Milan, Italy",
            "period": "January 2024 – July 2024",
            "responsibilities": [
                "Managed EU Taxonomy and CSRD alignment projects.",
                "Analyzed technical screening criteria and operational impacts.",
                "Supported the development of sustainability reports and ESG communications.",
            ],
        },
        {
            "title": "Junior Consultant",
            "company": "TradeLab",
            "location": None,
            "period": "April 2022 – December 2023",
            "responsibilities": [
                "Conducted market research and data analysis.",
                "Produced analytical reports and strategic insights for clients.",
            ],
        },
    ],
    "skills": {
        "tools_technical": [
            "Excel",
            "SPSS",
            "Sustainability reporting platforms",
            "Basic Python",
            "Data quality review",
            "Process improvement",
        ],
        "sustainability_reporting": [
            "CSRD implementation",
            "EU Taxonomy alignment",
            "Double materiality assessment",
            "ISSB familiarity",
            "TCFD familiarity",
            "Sustainability disclosure analysis",
        ],
        "climate_esg_data": [
            "GHG accounting",
            "Emissions reporting (Scopes 1, 2, 3)",
            "GHG Protocol",
            "ISO 14064",
            "ESG data collection",
            "Audit support",
            "KPI definition and monitoring",
        ],
        "stakeholder_governance": [
            "Stakeholder mapping",
            "Stakeholder engagement",
            "Cross-functional collaboration",
            "Policy analysis",
            "Regulatory monitoring",
            "ESG risk and materiality evaluation",
        ],
    },
    "courses": [
        "LCA Methodological Aspects and Practical Cases — Politecnico di Milano",
        "Deep Dive on Double Materiality Assessment for CSRD Reporting — Greenomy",
        "Generative AI Fundamentals — Google",
        "Introduction to Python — Sololearn",
        "E-learning Course on Green Fiscal Policy — United Nations",
    ],
    "summary": (
        "Professional with experience in EU sustainability regulation, stakeholder engagement, "
        "and environmental policy. Skilled at translating technical ESG and compliance topics "
        "into actionable insights and briefings. Strong knowledge of EU institutions and "
        "policy-making. Open to relocation and focused on environmental legislation and "
        "sustainability policy."
    ),
}


def get_all_skills() -> list[str]:
    """Return a flat list of all skills for matching."""
    skills = []
    for category in PROFILE_FACTS["skills"].values():
        skills.extend(category)
    return skills


def get_profile_as_text() -> str:
    """Return the full profile as structured plain text for AI prompts."""
    p = PROFILE_FACTS
    lines = [
        f"Name: {p['name']}",
        f"Location: {p['location']} (open to relocation)",
        f"Languages: {', '.join(l['language'] + ' (' + l['level'] + ')' for l in p['languages'])}",
        "",
        "PROFESSIONAL SUMMARY:",
        p["summary"],
        "",
        "EXPERIENCE:",
    ]
    for exp in p["experience"]:
        lines.append(f"  {exp['title']} at {exp['company']} ({exp['period']})")
        for resp in exp["responsibilities"]:
            lines.append(f"    - {resp}")
    lines.append("")
    lines.append("EDUCATION:")
    for edu in p["education"]:
        result = f" — {edu.get('result', '')}" if edu.get("result") else ""
        lines.append(f"  {edu['degree']}, {edu['institution']} ({edu['period']}){result}")
    lines.append("")
    lines.append("SKILLS:")
    for category, skill_list in p["skills"].items():
        lines.append(f"  {category.replace('_', ' ').title()}: {', '.join(skill_list)}")
    lines.append("")
    lines.append("COURSES:")
    for course in p["courses"]:
        lines.append(f"  - {course}")
    return "\n".join(lines)
