import re
from typing import Literal, Optional

import structlog
from pydantic import BaseModel, Field

from receipt_api.llm.client import get_llm_client

logger = structlog.get_logger(__name__)


class AcceptanceCriterion(BaseModel):
    id: str = Field(description="Unique criterion identifier, e.g. ac1, ac2")
    text: str = Field(description="Clear, testable acceptance condition description")
    testable: bool = Field(default=True, description="Whether this criterion can be validated by a code test")
    kind: Literal["bugfix", "feature", "refactor"] = Field(
        default="feature", description="Category of change"
    )


class IntentExtractionResult(BaseModel):
    summary: str = Field(description="High level summary of the intended changes")
    criteria: list[AcceptanceCriterion] = Field(
        default_factory=list, description="List of discrete acceptance criteria"
    )


INTENT_PROMPT_TEMPLATE = """You are Receipt's Acceptance Criteria Extractor.
Given a Pull Request title, description, and task context, extract a list of discrete, testable acceptance criteria.

PR Title: {title}
PR Description:
{body}

Additional Context:
{context}

Guidelines:
1. Break down complex PRs into 1 to 4 crisp criteria.
2. Mark 'testable' as True for behaviors that can be tested programmatically via unit/integration tests.
3. Classify kind as 'bugfix' (fixing a bug), 'feature' (new functionality), or 'refactor' (internal structure preservation).
4. Each criterion must be unambiguous.
"""


def extract_intent(
    title: str,
    body: str = "",
    diff_text: str = "",
    context: str = "",
) -> list[AcceptanceCriterion]:
    """Extract discrete acceptance criteria using structured LLM output with deterministic fallback."""
    llm = get_llm_client()
    prompt = INTENT_PROMPT_TEMPLATE.format(
        title=title,
        body=body or "(No description provided)",
        context=context or diff_text[:1000] or "None",
    )

    try:
        res: IntentExtractionResult = llm.chat_structured_sync(
            messages=[
                {"role": "system", "content": "You are a precise technical specifications extractor."},
                {"role": "user", "content": prompt},
            ],
            response_model=IntentExtractionResult,
            temperature=0.1,
        )
        if res.criteria:
            return res.criteria
    except Exception as e:
        logger.warning("intent_extraction_llm_failed_falling_back", error=str(e))

    # Deterministic heuristic fallback
    return fallback_extract_intent(title, body)


def fallback_extract_intent(title: str, body: str) -> list[AcceptanceCriterion]:
    """Deterministic fallback parsing for offline/test environments."""
    criteria: list[AcceptanceCriterion] = []
    title_lower = title.lower()

    default_kind: Literal["bugfix", "feature", "refactor"] = "feature"
    if title_lower.startswith("fix") or "bug" in title_lower or "hotfix" in title_lower:
        default_kind = "bugfix"
    elif title_lower.startswith("refactor") or "cleanup" in title_lower:
        default_kind = "refactor"

    # Look for bullet points or markdown check boxes in body
    bullet_pattern = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(?:\[[ xX]\]\s+)?(.+)$", re.MULTILINE)
    matches = bullet_pattern.findall(body)

    for idx, match in enumerate(matches[:4], start=1):
        clean_text = match.strip()
        if len(clean_text) > 8 and not clean_text.lower().startswith("signed-off"):
            criteria.append(
                AcceptanceCriterion(
                    id=f"ac{idx}",
                    text=clean_text,
                    testable=True,
                    kind=default_kind,
                )
            )

    # If no bullets found, derive criterion directly from the PR title
    if not criteria:
        clean_title = re.sub(r"^(?:feat|fix|refactor|test|chore)(?:\(.*?\))?:\s*", "", title, flags=re.I).strip()
        criteria.append(
            AcceptanceCriterion(
                id="ac1",
                text=clean_title or title,
                testable=True,
                kind=default_kind,
            )
        )

    return criteria
