"""JSON grantha writer.

This module provides JsonWriter for serializing grantha content to JSON format.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from grantha_data.base import BaseGrantha
from grantha_data.writers.base_writer import BaseWriter


class JsonWriter(BaseWriter):
    """Serializes grantha to JSON format.

    Produces JSON conforming to grantha.schema.json.
    """

    def write(
        self,
        grantha: BaseGrantha,
        output_path: Path,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        indent: int = 2,
        **_options
    ) -> None:
        """Writes grantha to JSON file.

        Args:
            grantha: Grantha to serialize.
            output_path: Output JSON file path.
            scripts: Scripts to include (None = all).
            commentaries: Commentary IDs to include (None = all).
            indent: JSON indentation level.
            **_options: Additional options (ignored).
        """
        json_string = self.write_to_string(
            grantha,
            scripts,
            commentaries,
            indent=indent
        )
        self._write_string_to_file(json_string, output_path)

    def _write_string_to_file(
        self,
        content: str,
        output_path: Path
    ) -> None:
        """Writes string content to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            f.write(content)

    def write_to_string(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        indent: int = 2,
        **_options
    ) -> str:
        """Serializes grantha to JSON string.

        Args:
            grantha: Grantha to serialize.
            scripts: Scripts to include (None = all).
            commentaries: Commentary IDs to include (None = all).
            indent: JSON indentation level.
            **_options: Additional options (ignored).

        Returns:
            JSON string representation.
        """
        grantha_dict = self._grantha_to_dict(grantha, scripts, commentaries)
        return json.dumps(
            grantha_dict,
            ensure_ascii=False,
            indent=indent
        )

    def _grantha_to_dict(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]],
        commentaries: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Converts grantha to dictionary."""
        result: Dict[str, Any] = {}
        self._add_metadata_to_dict(result, grantha)
        self._add_passages_to_dict(result, grantha, scripts)
        self._add_prefatory_material_to_dict(result, grantha, scripts)
        self._add_concluding_material_to_dict(result, grantha, scripts)
        self._add_commentaries_to_dict(result, grantha, commentaries, scripts)
        return result

    def _add_metadata_to_dict(
        self,
        result: Dict[str, Any],
        grantha: BaseGrantha
    ) -> None:
        """Adds metadata fields to result dictionary."""
        metadata = grantha.get_metadata()
        result['grantha_id'] = metadata.grantha_id
        result['part_num'] = metadata.part_num
        result['canonical_title'] = metadata.get_title('devanagari')
        result['text_type'] = metadata.text_type
        result['language'] = metadata.language
        result['structure_levels'] = metadata.structure.levels

    def _add_passages_to_dict(
        self,
        result: Dict[str, Any],
        grantha: BaseGrantha,
        scripts: Optional[List[str]]
    ) -> None:
        """Adds main passages to result dictionary."""
        passages = []
        for passage in grantha.iter_passages('main'):
            passage_dict = self._passage_to_dict(passage, scripts)
            passages.append(passage_dict)
        result['passages'] = passages

    def _passage_to_dict(
        self,
        passage,
        scripts: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Converts single passage to dictionary."""
        content = passage.get_content(scripts)
        passage_dict = {
            'ref': passage.ref,
            'passage_type': passage.passage_type,
            'content': {'sanskrit': content}
        }

        if passage.has_label:
            passage_dict['label'] = passage.label

        return passage_dict

    def _add_prefatory_material_to_dict(
        self,
        result: Dict[str, Any],
        grantha: BaseGrantha,
        scripts: Optional[List[str]]
    ) -> None:
        """Adds prefatory material to result dictionary."""
        prefatory = grantha.get_prefatory_material(scripts)
        if prefatory:
            result['prefatory_material'] = [
                self._passage_to_dict(p, scripts) for p in prefatory
            ]

    def _add_concluding_material_to_dict(
        self,
        result: Dict[str, Any],
        grantha: BaseGrantha,
        scripts: Optional[List[str]]
    ) -> None:
        """Adds concluding material to result dictionary."""
        concluding = grantha.get_concluding_material(scripts)
        if concluding:
            result['concluding_material'] = [
                self._passage_to_dict(p, scripts) for p in concluding
            ]

    def _add_commentaries_to_dict(
        self,
        result: Dict[str, Any],
        grantha: BaseGrantha,
        commentaries: Optional[List[str]],
        scripts: Optional[List[str]]
    ) -> None:
        """Adds commentaries to result dictionary."""
        commentary_ids = self._determine_commentary_ids(
            grantha,
            commentaries
        )

        if not commentary_ids:
            return

        result['commentaries'] = [
            self._commentary_to_dict(grantha, cid, scripts)
            for cid in commentary_ids
        ]

    def _determine_commentary_ids(
        self,
        grantha: BaseGrantha,
        commentaries: Optional[List[str]]
    ) -> List[str]:
        """Determines which commentary IDs to include."""
        if commentaries is None:
            return grantha.list_commentaries()
        return commentaries

    def _commentary_to_dict(
        self,
        grantha: BaseGrantha,
        commentary_id: str,
        scripts: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Converts commentary to dictionary."""
        metadata = grantha.get_commentary_metadata(commentary_id)

        commentary_dict = {
            'commentary_id': commentary_id,
            'commentary_title': metadata.get('commentary_title'),
            'commentator': metadata.get('commentator'),
            'passages': self._get_commentary_passages(
                grantha,
                commentary_id,
                scripts
            )
        }

        return commentary_dict

    def _get_commentary_passages(
        self,
        grantha: BaseGrantha,
        commentary_id: str,
        scripts: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Gets all passages for a commentary."""
        passages = []
        for ref in grantha.get_all_refs():
            try:
                commentary = grantha.get_commentary(
                    ref,
                    commentary_id,
                    scripts
                )
                passage_dict = self._commentary_passage_to_dict(
                    commentary,
                    scripts
                )
                passages.append(passage_dict)
            except Exception:
                # Commentary may not exist for all refs
                continue

        return passages

    def _commentary_passage_to_dict(
        self,
        commentary,
        scripts: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Converts commentary passage to dictionary."""
        content = commentary.get_content(scripts)
        passage_dict = {
            'ref': commentary.ref,
            'content': {'sanskrit': content}
        }

        if commentary.has_prefatory_material:
            passage_dict['prefatory_material'] = (
                commentary.prefatory_material
            )

        return passage_dict

    def write_envelope(
        self,
        grantha_id: str,
        canonical_title: str,
        text_type: str,
        language: str,
        structure_levels: List[Dict[str, Any]],
        part_files: List[str],
        output_path: Path
    ) -> None:
        """Writes envelope.json for multi-part grantha.

        Args:
            grantha_id: Grantha identifier.
            canonical_title: Title in Devanagari.
            text_type: Type of text.
            language: Primary language.
            structure_levels: Hierarchical structure.
            part_files: List of part filenames.
            output_path: Output envelope.json path.
        """
        envelope = {
            'grantha_id': grantha_id,
            'canonical_title': canonical_title,
            'text_type': text_type,
            'language': language,
            'structure_levels': structure_levels,
            'parts': part_files
        }

        envelope_json = json.dumps(envelope, ensure_ascii=False, indent=2)
        self._write_string_to_file(envelope_json, output_path)
