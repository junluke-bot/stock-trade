from .base import AgentSignal, InvestorAgent
from .warren_buffett import WarrenBuffettAgent
from .charlie_munger import CharlieMungerAgent
from .cathie_wood import CathieWoodAgent
from .ben_graham import BenGrahamAgent
from .michael_burry import MichaelBurryAgent
from .peter_lynch import PeterLynchAgent
from .technical_analyst import TechnicalAnalystAgent
from .risk_manager import RiskManagerAgent
from .portfolio_manager import PortfolioManagerAgent, PortfolioVerdict

ANALYST_AGENTS = [
    WarrenBuffettAgent,
    CharlieMungerAgent,
    CathieWoodAgent,
    BenGrahamAgent,
    MichaelBurryAgent,
    PeterLynchAgent,
    TechnicalAnalystAgent,
    RiskManagerAgent,
]

__all__ = [
    "AgentSignal",
    "InvestorAgent",
    "WarrenBuffettAgent",
    "CharlieMungerAgent",
    "CathieWoodAgent",
    "BenGrahamAgent",
    "MichaelBurryAgent",
    "PeterLynchAgent",
    "TechnicalAnalystAgent",
    "RiskManagerAgent",
    "PortfolioManagerAgent",
    "PortfolioVerdict",
    "ANALYST_AGENTS",
]
