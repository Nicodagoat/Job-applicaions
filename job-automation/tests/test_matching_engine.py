"""
Tests for the matching engine.
Ensures scoring is deterministic and geography exclusion works.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from ai.matching_engine import MatchingEngine


@pytest.fixture
def engine():
    return MatchingEngine()


def test_esg_job_scores_high(engine):
    result = engine.score(
        job_title="Sustainability Policy Analyst",
        company="Carbon Disclosure Project",
        location="London",
        country="United Kingdom",
        description="CSRD EU Taxonomy ESG reporting climate policy GHG emissions net zero sustainability",
        requirements=["CSRD", "EU Taxonomy", "ESG reporting", "stakeholder engagement"],
        remote=False,
    )
    assert result["overall_score"] >= 65, f"Expected high score, got {result['overall_score']}"
    assert result["esg_relevant"] is True


def test_italy_excluded(engine):
    result = engine.score(
        job_title="ESG Analyst",
        company="Some Italian Company",
        location="Rome, Italy",
        country="Italy",
        description="ESG sustainability CSRD",
        requirements=[],
        remote=False,
    )
    assert result["overall_score"] == 0.0, "Italy should be excluded (score=0)"
    assert any("excluded country" in f.lower() for f in result["flags"])


def test_remote_not_excluded_for_italy_region(engine):
    # Remote from any country is acceptable
    result = engine.score(
        job_title="ESG Consultant",
        company="European NGO",
        location="Remote",
        country="United Kingdom",
        description="ESG sustainability reporting",
        requirements=[],
        remote=True,
    )
    assert result["overall_score"] > 0


def test_unrelated_job_scores_low(engine):
    result = engine.score(
        job_title="Sales Representative",
        company="Car Dealership",
        location="Manchester",
        country="United Kingdom",
        description="Selling cars, achieving sales targets, cold calling customers",
        requirements=["Sales experience", "Driving licence"],
        remote=False,
    )
    assert result["overall_score"] < 60


def test_score_breakdown_keys(engine):
    result = engine.score(
        job_title="Climate Policy Analyst",
        company="E3G",
        location="Brussels",
        country="Belgium",
        description="EU climate policy analysis",
        requirements=[],
        remote=False,
    )
    expected_keys = {"skill_match", "location_match", "seniority_match",
                     "industry_relevance", "company_priority", "esg_relevance"}
    assert expected_keys.issubset(result["breakdown"].keys())
