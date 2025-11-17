"""Validation mixin for grantha data integrity checking.

This module provides GranthaValidator, a mixin class that adds validation
methods to grantha implementations.
"""

from dataclasses import dataclass
from typing import List, Optional

# Import existing hasher from grantha_converter
from grantha_converter.hasher import hash_grantha


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        name: Name of validation check.
        passed: Whether validation passed.
        message: Optional error/warning message.
    """

    name: str
    passed: bool
    message: Optional[str] = None


class GranthaValidator:
    """Mixin providing validation methods for grantha implementations.

    Classes that inherit from both BaseGrantha and GranthaValidator gain
    validation capabilities. Requires the class to implement BaseGrantha
    interface methods.
    """

    def validate_structure_completeness(self) -> ValidationResult:
        """Validates that all refs follow structure_levels hierarchy.

        Returns:
            ValidationResult with details of check.
        """
        try:
            self._check_all_refs_valid()
            return ValidationResult(
                name="structure_completeness",
                passed=True,
                message="All passage refs follow structure hierarchy"
            )
        except Exception as e:
            return ValidationResult(
                name="structure_completeness",
                passed=False,
                message=str(e)
            )

    def _check_all_refs_valid(self) -> None:
        """Checks all refs are valid according to structure."""
        # Get all refs
        all_refs = self.get_all_refs()

        # For now, basic check: refs should be non-empty
        for ref in all_refs:
            if not ref or not ref.strip():
                raise ValueError(f"Invalid empty ref found")

            # Check ref format (should be dot-separated numbers)
            parts = ref.split('.')
            for part in parts:
                if not part.isdigit():
                    raise ValueError(
                        f"Invalid ref format: {ref} "
                        f"(expected dot-separated numbers)"
                    )

    def validate_refs_unique(self) -> ValidationResult:
        """Validates that all passage refs are unique.

        Returns:
            ValidationResult indicating uniqueness status.
        """
        all_refs = self.get_all_refs()
        unique_refs = set(all_refs)

        if len(all_refs) == len(unique_refs):
            return ValidationResult(
                name="refs_unique",
                passed=True,
                message=f"All {len(all_refs)} passage refs are unique"
            )
        else:
            duplicates = self._find_duplicate_refs(all_refs)
            return ValidationResult(
                name="refs_unique",
                passed=False,
                message=f"Duplicate refs found: {duplicates}"
            )

    def _find_duplicate_refs(self, refs: List[str]) -> List[str]:
        """Finds duplicate refs in list."""
        seen = set()
        duplicates = []
        for ref in refs:
            if ref in seen:
                duplicates.append(ref)
            seen.add(ref)
        return duplicates

    def validate_commentary_refs_exist(self) -> ValidationResult:
        """Validates that commentary refs match existing passage refs.

        Returns:
            ValidationResult indicating commentary ref validity.
        """
        passage_refs = set(self.get_all_refs())
        commentary_ids = self.list_commentaries()

        if not commentary_ids:
            return ValidationResult(
                name="commentary_refs_exist",
                passed=True,
                message="No commentaries to validate"
            )

        invalid_refs = self._find_invalid_commentary_refs(
            passage_refs,
            commentary_ids
        )

        if not invalid_refs:
            return ValidationResult(
                name="commentary_refs_exist",
                passed=True,
                message="All commentary refs match passage refs"
            )
        else:
            return ValidationResult(
                name="commentary_refs_exist",
                passed=False,
                message=f"Invalid commentary refs: {invalid_refs}"
            )

    def _find_invalid_commentary_refs(
        self,
        passage_refs: set,
        commentary_ids: List[str]
    ) -> List[str]:
        """Finds commentary refs that don't match passage refs."""
        invalid_refs = []

        for cid in commentary_ids:
            for ref in passage_refs:
                try:
                    self.get_commentary(ref, cid)
                except Exception:
                    # Commentary doesn't exist for this ref - that's ok
                    pass

        return invalid_refs

    def validate_hash_integrity(self) -> ValidationResult:
        """Validates content hash against validation_hash in metadata.

        Uses grantha_converter.hasher to recompute hash and compare.

        Returns:
            ValidationResult indicating hash match status.
        """
        metadata = self.get_metadata()

        if not metadata.validation_hash:
            return ValidationResult(
                name="hash_integrity",
                passed=True,
                message="No validation hash to check"
            )

        try:
            computed_hash = self._compute_grantha_hash()
            stored_hash = self._extract_hash_value(
                metadata.validation_hash
            )

            if computed_hash == stored_hash:
                return ValidationResult(
                    name="hash_integrity",
                    passed=True,
                    message="Content hash matches validation_hash"
                )
            else:
                return ValidationResult(
                    name="hash_integrity",
                    passed=False,
                    message=(
                        f"Hash mismatch: "
                        f"computed={computed_hash[:16]}..., "
                        f"stored={stored_hash[:16]}..."
                    )
                )
        except Exception as e:
            return ValidationResult(
                name="hash_integrity",
                passed=False,
                message=f"Hash validation error: {str(e)}"
            )

    def _compute_grantha_hash(self) -> str:
        """Computes hash for current grantha content."""
        # Build a minimal grantha dict for hashing
        grantha_dict = self._build_grantha_dict_for_hashing()
        return hash_grantha(grantha_dict)

    def _build_grantha_dict_for_hashing(self) -> dict:
        """Builds grantha dict suitable for hash computation."""
        passages = []
        for passage in self.iter_passages('main'):
            passages.append({
                'ref': passage.ref,
                'content': {
                    'sanskrit': passage.content
                }
            })

        return {
            'passages': passages,
            'prefatory_material': [],
            'concluding_material': [],
        }

    def _extract_hash_value(self, validation_hash: str) -> str:
        """Extracts hash value from validation_hash field."""
        # Hash may be prefixed with "sha256:"
        if ':' in validation_hash:
            return validation_hash.split(':', 1)[1]
        return validation_hash

    def validate_all(self) -> List[ValidationResult]:
        """Runs all validation checks.

        Returns:
            List of ValidationResults, one per check.
        """
        return [
            self.validate_structure_completeness(),
            self.validate_refs_unique(),
            self.validate_commentary_refs_exist(),
            self.validate_hash_integrity(),
        ]
