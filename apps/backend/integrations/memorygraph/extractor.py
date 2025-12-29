"""
Insight Extractor for MemoryGraph
==================================

Extracts structured insights from session output without requiring LLMs.
Uses simple pattern matching and heuristics.
"""

import re
from typing import ClassVar


class InsightExtractor:
    """Extract structured insights from session output."""

    # Common technology keywords for tagging
    TECH_KEYWORDS: ClassVar[dict[str, list[str]]] = {
        "python": ["python", ".py"],
        "javascript": ["javascript", "js", ".js"],
        "typescript": ["typescript", ".ts", ".tsx"],
        "fastapi": ["fastapi"],
        "pydantic": ["pydantic"],
        "pytest": ["pytest"],
        "async": ["async", "await"],
        "api": ["api", "endpoint"],
        "database": ["database", "db", "sql"],
        "auth": ["auth", "authentication", "jwt", "token"],
    }

    # Action patterns for categorization
    ACTION_PATTERNS: ClassVar[dict[str, str]] = {
        "fix": r"\b(fix|fixed|fixing|bugfix)\b",
        "refactor": r"\b(refactor|refactoring|refactored)\b",
        "add": r"\b(add|added|adding)\b",
        "update": r"\b(update|updated|updating)\b",
        "error": r"\b(error|exception|failure)\b",
    }

    # Stop words to exclude from pattern inference (3+ chars, common words)
    STOP_WORDS: ClassVar[set[str]] = {
        "the", "and", "for", "with", "that", "this", "was", "from",
        "are", "were", "been", "have", "has", "had", "does", "did",
        "will", "would", "could", "should", "may", "might", "must",
    }

    # Maximum words to include in inferred pattern descriptions
    MAX_PATTERN_WORDS: ClassVar[int] = 3

    # Default maximum length for memory titles
    DEFAULT_TITLE_MAX_LEN: ClassVar[int] = 50

    # Minimum number of successes required to infer patterns
    MIN_SUCCESSES_FOR_PATTERN: ClassVar[int] = 2

    # Minimum word length for pattern inference (excludes short words like "a", "to")
    MIN_WORD_LENGTH: ClassVar[int] = 3

    # Importance scores by memory type
    IMPORTANCE_PROBLEM: ClassVar[float] = 0.7
    IMPORTANCE_ERROR: ClassVar[float] = 0.8  # Errors are more important
    IMPORTANCE_SOLUTION: ClassVar[float] = 0.8
    IMPORTANCE_PATTERN: ClassVar[float] = 0.6

    def extract_problems(self, session_output: dict) -> list[dict]:
        """
        Extract problems from what_failed, errors, QA rejections.

        Args:
            session_output: Session output dictionary

        Returns:
            List of problem memory dicts
        """
        problems = []

        # Extract from what_failed
        for failure in session_output.get("what_failed", []):
            problems.append(
                self._create_memory("problem", failure, importance=self.IMPORTANCE_PROBLEM)
            )

        # Extract from errors - use "error" type for actual errors
        for error in session_output.get("errors", []):
            problems.append(
                self._create_memory("error", error, importance=self.IMPORTANCE_ERROR)
            )

        # Extract from QA rejections
        for rejection in session_output.get("qa_rejections", []):
            problems.append(
                self._create_memory("problem", rejection, importance=self.IMPORTANCE_PROBLEM)
            )

        return problems

    def extract_solutions(self, session_output: dict) -> list[dict]:
        """
        Extract solutions from what_worked, fixes applied.

        Args:
            session_output: Session output dictionary

        Returns:
            List of solution memory dicts
        """
        solutions = []

        # Extract from what_worked
        for success in session_output.get("what_worked", []):
            solutions.append(
                self._create_memory("solution", success, importance=self.IMPORTANCE_SOLUTION)
            )

        # Extract from fixes_applied
        for fix in session_output.get("fixes_applied", []):
            solutions.append(
                self._create_memory("solution", fix, importance=self.IMPORTANCE_SOLUTION)
            )

        return solutions

    def extract_patterns(self, session_output: dict) -> list[dict]:
        """
        Extract patterns from patterns_found or infer from repeated approaches.

        Args:
            session_output: Session output dictionary

        Returns:
            List of code_pattern memory dicts
        """
        patterns = []

        # Extract explicit patterns
        for pattern in session_output.get("patterns_found", []):
            patterns.append(
                self._create_memory("code_pattern", pattern, importance=self.IMPORTANCE_PATTERN)
            )

        # Infer patterns from repeated successes
        what_worked = session_output.get("what_worked", [])
        if what_worked:
            inferred = self._infer_patterns_from_successes(what_worked)
            patterns.extend(inferred)

        return patterns

    def _create_memory(
        self, memory_type: str, content: str, importance: float = 0.7
    ) -> dict:
        """
        Create a memory dict from content.

        Args:
            memory_type: Type of memory
            content: Memory content
            importance: Importance score

        Returns:
            Memory dict ready for storage
        """
        return {
            "type": memory_type,
            "title": self._summarize(content),
            "content": content,
            "tags": self._extract_tags(content),
            "importance": importance,
        }

    def _summarize(self, text: str, max_len: int | None = None) -> str:
        """
        Create short title from text.

        Args:
            text: Text to summarize
            max_len: Maximum length of title (defaults to DEFAULT_TITLE_MAX_LEN)

        Returns:
            Short title string
        """
        if max_len is None:
            max_len = self.DEFAULT_TITLE_MAX_LEN

        if not text:
            return "Untitled"

        # Take first sentence if available
        sentences = re.split(r"[.!?]\s+", text)
        first_sentence = sentences[0] if sentences else text

        # Truncate if too long
        if len(first_sentence) > max_len:
            return first_sentence[: max_len - 3].strip() + "..."

        return first_sentence.strip()

    def _extract_tags(self, text: str) -> list[str]:
        """
        Extract relevant tags from text (technologies, patterns, etc.).

        Args:
            text: Text to extract tags from

        Returns:
            List of tag strings
        """
        if not text:
            return []

        tags = set()
        text_lower = text.lower()

        # Extract technology tags
        for tag_name, keywords in self.TECH_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                tags.add(tag_name)

        # Extract action tags
        for tag_name, pattern in self.ACTION_PATTERNS.items():
            if re.search(pattern, text_lower):
                tags.add(tag_name)

        return sorted(tags)

    def _infer_patterns_from_successes(self, successes: list[str]) -> list[dict]:
        """
        Infer patterns from repeated successful approaches.

        Args:
            successes: List of successful approaches

        Returns:
            List of inferred pattern memory dicts
        """
        if len(successes) < self.MIN_SUCCESSES_FOR_PATTERN:
            return []

        patterns = []

        # Find common keywords across successes
        word_counts: dict[str, int] = {}
        for success in successes:
            # Extract meaningful words (MIN_WORD_LENGTH+ chars, lowercase)
            word_pattern = rf"\b[a-z]{{{self.MIN_WORD_LENGTH},}}\b"
            words = re.findall(word_pattern, success.lower())
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

        # Find words that appear in multiple successes, excluding stop words
        repeated_words = [
            word
            for word, count in word_counts.items()
            if count >= self.MIN_SUCCESSES_FOR_PATTERN and word not in self.STOP_WORDS
        ]

        # Create pattern if we found repeated themes
        if repeated_words:
            words_to_include = repeated_words[: self.MAX_PATTERN_WORDS]
            pattern_content = f"Pattern: {', '.join(words_to_include)} appeared in multiple solutions"
            patterns.append(
                self._create_memory(
                    "code_pattern", pattern_content, importance=self.IMPORTANCE_PATTERN
                )
            )

        return patterns
