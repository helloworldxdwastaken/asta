"""Research skill - creates market research reports and saves to files."""
import re
from typing import Any
from pathlib import Path

from app.lib.skill import Skill


class ResearchSkill(Skill):
    """Skill for creating research reports and saving to files."""
    
    RESEARCH_PATTERNS = [
        r"research\s+(?:about\s+)?(?:the\s+)?(\w+\s+market)",
        r"research\s+(?:on\s+)?(\w+(?:\s+\w+)?)",
        r"(?:market\s+)?analysis\s+(?:of\s+)?(\w+)",
        r"competitor\s+analysis\s+(?:of\s+)?(\w+)",
        r"(\w+)\s+market\s+report",
        r"write\s+(?:a\s+)?research\s+(?:report\s+)?(?:on\s+)?(\w+)",
    ]
    
    def __init__(self) -> None:
        self._patterns = [re.compile(p, re.I) for p in self.RESEARCH_PATTERNS]
    
    @property
    def name(self) -> str:
        return "research"
    
    def check_eligibility(self, text: str, user_id: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        
        # Check for research-related keywords
        keywords = [
            "research", "market analysis", "competitor analysis",
            "industry report", "market report", "market research"
        ]
        
        return any(kw in text_lower for kw in keywords)

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """This skill doesn't execute directly - it provides context to the model."""
        return {}

    async def get_context_section(self, db: Any, user_id: str, extra: dict[str, Any]) -> str | None:
        return """## RESEARCH REPORT - IMMEDIATE ACTION REQUIRED

When user asks for research/market analysis:
1. AFTER 2-3 web searches, STOP searching and create the file immediately
2. Use the **files tool** to write to: /Users/tokyo/asta/workspace/research/[topic]_report.md
3. Do NOT ask permission - create the file right away

## REPORT STRUCTURE - MUST INCLUDE ALL SECTIONS:

### Executive Summary
- 2-3 paragraph overview of the market

### Market Size & Forecast
- Current market value (2024, 2025)
- Projected values (2030, 2035, 2040 if available)
- CAGR and growth drivers
- Include multiple sources with different estimates

### Competitive Landscape
- Detailed profiles of ALL major players
- Market share data
- Key financials (revenue, market cap if public)
- Strategic partnerships

### Technology Trends
- Major technological developments
- Emerging technologies
- Innovation areas

### Industry Applications
- All relevant use cases
- Industry-specific adoption

### Regional Analysis
- North America
- Europe  
- Asia-Pacific
- Other regions

### Investment & Funding
- M&A activity
- VC funding rounds
- IPOs

### Regulatory Environment
- Current regulations
- Upcoming changes
- Impact on market

### Challenges & Risks
- Technical challenges
- Market risks
- Regulatory risks

### Key Takeaways
- 5-7 bullet points summarizing critical insights

### Sources
- List ALL sources used with URLs and access dates

### References & Further Reading
- Include relevant industry reports (Gartner, Forrester, McKinsey, IDC, Statista)
- Add links to company websites, press releases, earnings calls
- Include academic papers and whitepapers
- Reference regulatory bodies and industry associations

CRITICAL: The report must be 3000+ words minimum. Be comprehensive and thorough. Include clickable URLs for all sources.
"""
