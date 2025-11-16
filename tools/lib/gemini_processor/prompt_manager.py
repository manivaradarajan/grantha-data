"""Prompt template management for Gemini API interactions.

Provides a flexible system for loading and managing prompt templates
with variable substitution support.
"""

from pathlib import Path
from typing import Dict, Optional


class PromptManager:
    """Manages prompt templates from a specified directory.

    Handles loading prompt template files and provides variable substitution
    functionality for dynamic prompt generation.

    Attributes:
        prompts_dir: Path to the directory containing prompt templates.
    """

    def __init__(self, prompts_dir: Path):
        """Initialize PromptManager with a prompts directory.

        Args:
            prompts_dir: Path to directory containing prompt template files.

        Raises:
            ValueError: If prompts_dir is not a directory.
        """
        self.prompts_dir = Path(prompts_dir)
        if not self.prompts_dir.is_dir():
            raise ValueError(f"Prompts directory does not exist: {prompts_dir}")

    def load_template(self, filename: str) -> str:
        """Load a prompt template from the prompts directory.

        Args:
            filename: Name of the prompt file (e.g., 'conversion_prompt.txt').

        Returns:
            The prompt template as a string.

        Raises:
            FileNotFoundError: If the prompt file doesn't exist.
            IOError: If there's an error reading the file.
        """
        prompt_path = self.prompts_dir / filename
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt template not found: {prompt_path}\n"
                f"Expected location: {self.prompts_dir}\n"
                f"Please ensure the prompts directory exists and contains "
                f"the required template files."
            )
        except Exception as e:
            raise IOError(f"Error reading prompt template {filename}: {e}")

    def format_template(
        self, template: str, variables: Optional[Dict[str, str]] = None
    ) -> str:
        """Format a template with variable substitution.

        Args:
            template: The template string with {variable} placeholders.
            variables: Dictionary mapping variable names to values.

        Returns:
            The formatted template with variables substituted.

        Raises:
            KeyError: If a required variable is missing from the variables dict.
        """
        if variables is None:
            variables = {}
        try:
            return template.format(**variables)
        except KeyError as e:
            raise KeyError(
                f"Missing required variable in template: {e}. "
                f"Available variables: {list(variables.keys())}"
            )

    def load_and_format(
        self, filename: str, variables: Optional[Dict[str, str]] = None
    ) -> str:
        """Load a template and format it with variables in one step.

        Args:
            filename: Name of the prompt file.
            variables: Dictionary mapping variable names to values.

        Returns:
            The formatted prompt with variables substituted.

        Raises:
            FileNotFoundError: If the prompt file doesn't exist.
            IOError: If there's an error reading the file.
            KeyError: If a required variable is missing.
        """
        template = self.load_template(filename)
        return self.format_template(template, variables)
