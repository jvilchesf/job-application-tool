"""
Matcher Service - LLM-based job-CV matching.

This service uses OpenAI LLM to evaluate how well qualified jobs
match the candidate's CV, providing a score from 1-5.
"""

from .cv_loader import CVLoader
from .llm_matcher import LLMMatcher, MatchResult

__all__ = ["CVLoader", "LLMMatcher", "MatchResult"]
