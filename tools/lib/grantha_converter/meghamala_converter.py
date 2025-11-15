"""
Meghamala markdown to Grantha structured markdown converter.

This module parses meghamala-format markdown files and converts them to
structured Grantha Markdown format with proper YAML frontmatter, hierarchical
structure, and commentary metadata.
"""

import re
import yaml
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from grantha_converter.hasher import hash_text


class MalformedMantraError(Exception):
    """Raised when multi-line mantras are detected."""
    def __init__(self, line_num: int, line_content: str, next_line_num: int, next_line_content: str):
        self.line_num = line_num
        self.line_content = line_content
        self.next_line_num = next_line_num
        self.next_line_content = next_line_content
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return (
            f"\n❌ Multi-line mantra detected (not supported)\n\n"
            f"Line {self.line_num}: {self.line_content[:80]}...\n"
            f"Line {self.next_line_num}: {self.next_line_content[:80]}...\n\n"
            f"This appears to be a multi-line mantra where the first line (line {self.line_num}) "
            f"is bold but has no verse number, and the next line (line {self.next_line_num}) "
            f"continues the mantra and has a verse number.\n\n"
            f"Please reformat the input so each mantra is on a single bold line with its verse number.\n"
            f"Alternatively, if these should be separate mantras, ensure each has its own verse number."
        )


@dataclass
class MantraPassage:
    """Represents a mantra/verse passage."""
    text: str
    reference: str
    passage_type: str = "main"  # "main", "prefatory", or "concluding"
    label: Optional[str] = None  # For prefatory/concluding passages


@dataclass
class CommentarySection:
    """Represents a commentary section."""
    mantra_ref: str
    heading: Optional[str] = None
    text: str = ""


@dataclass
class StructureNode:
    """Represents a node in the hierarchical structure."""
    level_id: str  # e.g., "khanda", "mantra"
    level_label: str  # e.g., "खण्डः"
    number: int
    passages: List[MantraPassage] = field(default_factory=list)
    commentaries: List[CommentarySection] = field(default_factory=list)
    children: List['StructureNode'] = field(default_factory=list)


class MeghamalaParser:
    """Parser for meghamala markdown format."""

    # Patterns for identifying structure
    KHANDA_START_PATTERN = re.compile(r'\*\*(.+?)(खण्डः|वल्ली)\*\*')
    KHANDA_END_PATTERN = re.compile(r'\*\*(इति\s+.+?(खण्डः|वल्ली)\s*समाप्तः)\*\*')

    # Verse number patterns
    VERSE_NUM_PATTERN = re.compile(r'[।॥](\d+)[।॥]+\s*$')

    # Special section patterns
    SHANTI_PATTERN = re.compile(r'\*\*\[(.+?(शान्तिपाठः|शान्तिमन्त्र))\]\*\*')
    ENDING_SHANTI_PATTERN = re.compile(r'\*\*(.+?शान्तिपाठः)\*\*')
    MANGALA_PATTERN = re.compile(r'\*\*(मङ्गलाचरणम्?.*?)\*\*')

    # Commentary markers
    COMMENTARY_NAME_PATTERN = re.compile(r'\*\*(प्रकाशिका|भाष्यम्|टीका|व्याख्या)\*\*')
    COMMENTATOR_PATTERN = re.compile(r'\*\*(.+?(विरचिता?|कृत[ाः]))\*\*')

    # Section heading patterns (bold text in brackets or standalone)
    SECTION_HEADING_PATTERN = re.compile(r'\*\*([^\[\]]+?)\*\*')

    # Colophon pattern
    COLOPHON_PATTERN = re.compile(r'\*\*(इति\s+.+?)\*\*')

    def __init__(self, content: str):
        """Initialize parser with meghamala markdown content."""
        self.lines = content.split('\n')
        self.current_line = 0

        # Metadata extracted during parsing
        self.title = None
        self.commentator = None
        self.commentary_name = None

    def extract_bold(self, line: str) -> Optional[str]:
        """Extract bold text from a line."""
        match = re.search(r'\*\*(.+?)\*\*', line)
        return match.group(1) if match else None

    def remove_bold(self, text: str) -> str:
        """Remove all bold markup from text."""
        return re.sub(r'\*\*', '', text)

    def is_likely_mantra(self, line: str) -> bool:
        """Check if a line is likely a mantra (bold text with verse number)."""
        if not line.startswith('**'):
            return False
        bold_text = self.extract_bold(line)
        if not bold_text:
            return False
        # Check for verse number at end
        return bool(self.VERSE_NUM_PATTERN.search(bold_text))

    def extract_verse_number(self, text: str) -> Optional[str]:
        """Extract verse number from text."""
        match = self.VERSE_NUM_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def is_commentary_text(self, line: str) -> bool:
        """Check if line is commentary text (not bold, has Devanagari)."""
        if line.startswith('**'):
            return False
        # Check for Devanagari characters
        return bool(re.search(r'[\u0900-\u097F]', line))

    def extract_title(self) -> Optional[str]:
        """Extract Upanishad title from early lines."""
        for i in range(min(10, len(self.lines))):
            line = self.lines[i].strip()
            # Check for Upanishad title (various forms)
            if line.startswith('**') and ('पनिषत्' in line or 'पनिषद्' in line):
                title = self.extract_bold(line)
                if title and len(title) < 50:  # Reasonable title length
                    return title
        return None

    def extract_commentator_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract commentator name and commentary name from content."""
        commentator = None
        commentary_name = None

        for i, line in enumerate(self.lines[:50]):  # Check first 50 lines
            line = line.strip()

            # Check for commentary name
            if self.COMMENTARY_NAME_PATTERN.search(line):
                bold = self.extract_bold(line)
                if bold:
                    commentary_name = bold

            # Check for commentator
            if self.COMMENTATOR_PATTERN.search(line):
                bold = self.extract_bold(line)
                if bold and ('विरचित' in bold or 'कृत' in bold):
                    commentator = bold

        return commentator, commentary_name

    def validate_no_multiline_mantras(self):
        """
        Validate that there are no multi-line mantras.

        Raises MalformedMantraError if a multi-line mantra is detected.
        """
        for i in range(len(self.lines) - 1):
            line = self.lines[i].strip()
            next_line = self.lines[i + 1].strip()

            # Skip empty lines
            if not line or not next_line:
                continue

            # Check if current line is bold
            if not line.startswith('**'):
                continue

            bold_text = self.extract_bold(line)
            if not bold_text:
                continue

            # Skip special patterns that aren't mantras
            if (self.KHANDA_START_PATTERN.match(line) or
                self.KHANDA_END_PATTERN.match(line) or
                self.SHANTI_PATTERN.match(line) or
                self.ENDING_SHANTI_PATTERN.match(line) or
                self.COMMENTARY_NAME_PATTERN.search(line) or
                self.COMMENTATOR_PATTERN.search(line) or
                len(bold_text) < 10):  # Too short to be a mantra
                continue

            # Check if this bold line has Devanagari but no verse number
            has_devanagari = bool(re.search(r'[\u0900-\u097F]', bold_text))
            has_verse_num = bool(self.VERSE_NUM_PATTERN.search(bold_text))

            if not has_devanagari or has_verse_num:
                continue

            # Check if next line is also bold and has a verse number
            if next_line.startswith('**'):
                next_bold = self.extract_bold(next_line)
                if next_bold:
                    next_has_verse = bool(self.VERSE_NUM_PATTERN.search(next_bold))
                    next_has_devanagari = bool(re.search(r'[\u0900-\u097F]', next_bold))

                    if next_has_devanagari and next_has_verse:
                        # This is a multi-line mantra!
                        raise MalformedMantraError(
                            line_num=i + 1,
                            line_content=line,
                            next_line_num=i + 2,
                            next_line_content=next_line
                        )

    def parse(self) -> List[StructureNode]:
        """Parse the meghamala content into structured nodes."""
        # Extract metadata first
        self.title = self.extract_title()
        self.commentator, self.commentary_name = self.extract_commentator_info()

        # Validate no multi-line mantras
        self.validate_no_multiline_mantras()

        # Parse structure
        nodes = []
        current_khanda = None
        current_khanda_num = 0
        in_commentary = False
        commentary_buffer = []
        last_mantra_ref = None
        passage_counter = 0

        # Check if document has khanda structure
        has_khandas = any(self.KHANDA_START_PATTERN.match(line.strip())
                         for line in self.lines)

        # If no khandas, create a default node
        if not has_khandas:
            current_khanda = StructureNode(
                level_id="mantra",
                level_label="",
                number=1
            )
            current_khanda_num = 1

        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()

            # Check for khanda start
            khanda_match = self.KHANDA_START_PATTERN.match(line)
            if khanda_match:
                # Save previous khanda
                if current_khanda:
                    nodes.append(current_khanda)

                # Start new khanda
                current_khanda_num += 1
                khanda_text = khanda_match.group(1)
                level_label = khanda_match.group(2)

                current_khanda = StructureNode(
                    level_id="khanda" if "खण्डः" in level_label else "valli",
                    level_label=level_label,
                    number=current_khanda_num
                )
                passage_counter = 0
                i += 1
                continue

            # Check for khanda end
            if self.KHANDA_END_PATTERN.match(line):
                if commentary_buffer and current_khanda and last_mantra_ref:
                    # Add accumulated commentary
                    commentary = CommentarySection(
                        mantra_ref=last_mantra_ref,
                        text='\n'.join(commentary_buffer)
                    )
                    current_khanda.commentaries.append(commentary)
                    commentary_buffer = []
                i += 1
                continue

            # Check for mantra
            if self.is_likely_mantra(line):
                # Save previous commentary if any
                if commentary_buffer and current_khanda and last_mantra_ref:
                    commentary = CommentarySection(
                        mantra_ref=last_mantra_ref,
                        text='\n'.join(commentary_buffer)
                    )
                    current_khanda.commentaries.append(commentary)
                    commentary_buffer = []

                # Extract mantra text
                bold_text = self.extract_bold(line)
                if bold_text:
                    passage_counter += 1
                    mantra_ref = f"{current_khanda_num}.{passage_counter}"
                    last_mantra_ref = mantra_ref

                    # Remove verse number from text
                    mantra_text = self.VERSE_NUM_PATTERN.sub('', bold_text).strip()

                    passage = MantraPassage(
                        text=mantra_text,
                        reference=mantra_ref
                    )

                    if current_khanda:
                        current_khanda.passages.append(passage)

                i += 1
                continue

            # Check for shanti patha (prefatory/concluding)
            shanti_match = self.SHANTI_PATTERN.match(line) or self.ENDING_SHANTI_PATTERN.match(line)
            if shanti_match:
                # Collect shanti text (next bold lines)
                shanti_lines = []
                j = i + 1
                while j < len(self.lines):
                    next_line = self.lines[j].strip()
                    if next_line.startswith('**') and 'ओम्' in next_line or 'ओं' in next_line:
                        bold = self.extract_bold(next_line)
                        if bold:
                            shanti_lines.append(bold)
                        j += 1
                    elif next_line and not next_line.startswith('**'):
                        break
                    else:
                        j += 1
                        if '***' in next_line:
                            break

                if shanti_lines:
                    label = shanti_match.group(1)
                    passage_type = "prefatory" if i < 50 else "concluding"
                    passage_counter += 1
                    ref = f"{current_khanda_num if current_khanda_num > 0 else 0}.{passage_counter}"

                    passage = MantraPassage(
                        text='\n\n'.join(shanti_lines),
                        reference=ref,
                        passage_type=passage_type,
                        label=label
                    )

                    if current_khanda:
                        current_khanda.passages.insert(0, passage)
                    else:
                        # Pre-khanda content
                        nodes.insert(0, StructureNode(
                            level_id="prefatory",
                            level_label="",
                            number=0,
                            passages=[passage]
                        ))

                i = j
                continue

            # Check for commentary text
            if self.is_commentary_text(line) and current_khanda and last_mantra_ref:
                commentary_buffer.append(line)

            # Check for section headings in commentary
            elif line.startswith('**') and not self.is_likely_mantra(line):
                bold = self.extract_bold(line)
                if bold and len(bold) < 100:  # Likely a heading
                    # Add as commentary heading
                    if commentary_buffer:
                        commentary_buffer.append(f"\n**{bold}**\n")
                    else:
                        commentary_buffer.append(f"**{bold}**")

            i += 1

        # Save last khanda
        if current_khanda:
            if commentary_buffer and last_mantra_ref:
                commentary = CommentarySection(
                    mantra_ref=last_mantra_ref,
                    text='\n'.join(commentary_buffer)
                )
                current_khanda.commentaries.append(commentary)
            nodes.append(current_khanda)

        return nodes


class GranthaMarkdownGenerator:
    """Generates Grantha structured markdown from parsed nodes."""

    def __init__(self,
                 nodes: List[StructureNode],
                 grantha_id: str,
                 canonical_title: str,
                 commentary_id: Optional[str] = None,
                 commentator: Optional[str] = None,
                 part_num: int = 1,
                 remove_bold: bool = True):
        self.nodes = nodes
        self.grantha_id = grantha_id
        self.canonical_title = canonical_title
        self.commentary_id = commentary_id
        self.commentator = commentator
        self.part_num = part_num
        self.remove_bold = remove_bold

    def generate_structure_levels(self) -> Dict:
        """Generate structure_levels dictionary from nodes."""
        # Determine structure type based on node level_ids
        if any(node.level_id == "khanda" for node in self.nodes):
            return {
                "khanda": {
                    "label_devanagari": "खण्डः",
                    "label_roman": "khaṇḍa"
                },
                "mantra": {
                    "label_devanagari": "मन्त्रः",
                    "label_roman": "mantra"
                }
            }
        elif any(node.level_id == "valli" for node in self.nodes):
            return {
                "valli": {
                    "label_devanagari": "वल्ली",
                    "label_roman": "vallī"
                },
                "mantra": {
                    "label_devanagari": "मन्त्रः",
                    "label_roman": "mantra"
                }
            }
        else:
            # Default structure
            return {
                "mantra": {
                    "label_devanagari": "मन्त्रः",
                    "label_roman": "mantra"
                }
            }

    def generate_commentaries_metadata(self) -> Optional[List[Dict]]:
        """Generate commentaries_metadata if commentary exists."""
        if not self.commentary_id or not self.commentator:
            return None

        return [{
            "commentary_id": self.commentary_id,
            "commentator": self.commentator,
            "language": "sanskrit"
        }]

    def process_text(self, text: str) -> str:
        """Process text: remove bold if configured."""
        if self.remove_bold:
            return re.sub(r'\*\*', '', text)
        return text

    def generate_frontmatter(self, content_hash: str) -> str:
        """Generate YAML frontmatter."""
        metadata = {
            "grantha_id": self.grantha_id,
            "part_num": self.part_num,
            "canonical_title": self.canonical_title,
            "text_type": "upanishad",
            "language": "sanskrit",
            "structure_levels": self.generate_structure_levels(),
            "validation_hash": content_hash
        }

        commentaries = self.generate_commentaries_metadata()
        if commentaries:
            metadata["commentaries_metadata"] = commentaries

        yaml_str = yaml.dump(metadata, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return f"---\n{yaml_str}---\n\n"

    def generate_markdown_body(self) -> str:
        """Generate the markdown body content."""
        lines = []

        for node in self.nodes:
            # Generate khanda/valli header
            if node.level_id in ["khanda", "valli"]:
                lines.append(f"# {node.level_label.title()} {node.number}\n")

            # Generate passages
            for passage in node.passages:
                if passage.passage_type == "prefatory":
                    lines.append(f'# Prefatory: {passage.reference} (devanagari: "{passage.label}")\n')
                elif passage.passage_type == "concluding":
                    lines.append(f'# Concluding: {passage.reference} (devanagari: "{passage.label}")\n')
                else:
                    lines.append(f"## Mantra {passage.reference}\n")

                # Wrap in Sanskrit comment block
                processed_text = self.process_text(passage.text)
                lines.append("<!-- sanskrit:devanagari -->\n")
                lines.append(f"{processed_text}\n")
                lines.append("<!-- /sanskrit:devanagari -->\n")

            # Generate commentaries
            for commentary in node.commentaries:
                if self.commentary_id:
                    # Add commentary metadata
                    metadata_comment = f'<!-- commentary: {{"commentary_id": "{self.commentary_id}"}} -->\n'
                    lines.append(metadata_comment)
                    lines.append(f"### Commentary: {commentary.mantra_ref}\n")

                    # Commentary text
                    processed_text = self.process_text(commentary.text)
                    lines.append("<!-- sanskrit:devanagari -->\n")
                    lines.append(f"{processed_text}\n")
                    lines.append("<!-- /sanskrit:devanagari -->\n")

        return '\n'.join(lines)

    def generate(self) -> str:
        """Generate complete Grantha markdown document."""
        # Generate body first (needed for hash)
        body = self.generate_markdown_body()

        # Calculate content hash
        content_hash = hash_text(body)

        # Generate frontmatter with hash
        frontmatter = self.generate_frontmatter(content_hash)

        # Combine
        return frontmatter + body


def convert_meghamala_to_grantha(
    meghamala_content: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: Optional[str] = None,
    commentator: Optional[str] = None,
    part_num: int = 1,
    remove_bold: bool = True
) -> str:
    """
    Convert meghamala markdown to Grantha structured markdown.

    Args:
        meghamala_content: Input meghamala markdown content
        grantha_id: Grantha identifier (e.g., "kena-upanishad")
        canonical_title: Canonical Devanagari title (e.g., "केनोपनिषत्")
        commentary_id: Commentary identifier (optional)
        commentator: Commentator name in Devanagari (optional)
        part_num: Part number for multi-part texts (default: 1)
        remove_bold: Remove bold markup (default: True)

    Returns:
        Grantha structured markdown content
    """
    # Parse meghamala format
    parser = MeghamalaParser(meghamala_content)
    nodes = parser.parse()

    # Auto-extract metadata if not provided
    if not canonical_title and parser.title:
        canonical_title = parser.title

    if not commentator and parser.commentator:
        commentator = parser.commentator

    # Generate Grantha markdown
    generator = GranthaMarkdownGenerator(
        nodes=nodes,
        grantha_id=grantha_id,
        canonical_title=canonical_title,
        commentary_id=commentary_id,
        commentator=commentator,
        part_num=part_num,
        remove_bold=remove_bold
    )

    return generator.generate()
