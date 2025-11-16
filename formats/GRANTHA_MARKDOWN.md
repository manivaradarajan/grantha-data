# Grantha Markdown Specification

This document outlines the official specification for authoring grantha content in Markdown for the Grantha Explorer project. Adhering to this format is crucial for the data pipeline to correctly parse the content and convert it into the required JSON format.

## 1. File Structure

Each Markdown file represents a "part" of a grantha. For a simple, single-part grantha, there will be one file. For a large, multi-part grantha (like the Brihadaranyaka Upanishad), there will be multiple files, each corresponding to a chapter or section.

- **File Naming:** Files should be named descriptively, e.g., `03-01.converted.md`. The conversion pipeline processes these files in alphabetical order.
- **Character Encoding:** All files must be saved with UTF-8 encoding.

## 2. YAML Frontmatter

Every file **must** begin with a YAML frontmatter block, enclosed by `---`.

```yaml
---
grantha_id: brihadaranyaka-upanishad
part_num: 1
part_title: "Adhyaya 3, Brahmana 1"
canonical_title: बृहदारण्यकोपनिषत्
text_type: upanishad
language: sanskrit
structure_levels:
  - key: Adhyaya
    scriptNames:
      devanagari: अध्यायः
    children:
      - key: Brahmana
        scriptNames:
          devanagari: ब्राह्मणम्
        children:
          - key: Mantra
            scriptNames:
              devanagari: मन्त्रः
commentaries_metadata:
  ranga-ramanujamuni-prakashika:
    commentary_title: "प्रकाशिका"
    commentator:
      devanagari: "रङ्गरामानुजमुनिः"
hash_version: 1
validation_hash: sha256:abc123def456...
---
```

### Required Fields

| Field                   | Type    | Description                                                                                      |
| ----------------------- | ------- | ------------------------------------------------------------------------------------------------ |
| `grantha_id`            | String  | The unique, machine-readable identifier for the grantha (e.g., `brihadaranyaka-upanishad`).      |
| `part_num`              | Integer | The sequential number of this part within the grantha. **Must be `1` for single-part granthas.** |
| `canonical_title`       | String  | The full, canonical title of the grantha in Devanagari.                                          |
| `text_type`             | String  | The type of text. Must be `upanishad` or `commentary`.                                           |
| `language`              | String  | The primary language of the text. Must be `sanskrit` or `english`.                               |
| `structure_levels`      | Array   | Defines the hierarchical structure of the text (e.g., Adhyaya, Brahmana, Mantra).                |
| `commentaries_metadata` | Object  | Metadata for the commentaries included in this file. The key is the `commentary_id`.             |

### Optional Fields

| Field                | Type    | Description                                                                |
| -------------------- | ------- | -------------------------------------------------------------------------- |
| `part_title`         | String  | A human-readable title for this specific part.                             |
| `aliases`            | Array   | An array of alternate names for the grantha.                               |
| `variants_available` | Array   | An array of available text variants.                                       |
| `metadata`           | Object  | Contains metadata related to file processing and quality control.          |

### Validation Fields

These fields are automatically generated and used for content integrity verification:

| Field              | Type    | Description                                                                                                                                                |
| ------------------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hash_version`     | Integer | The version of the hashing algorithm used to generate `validation_hash`. Current version is `1`. This must match the current algorithm version for validation to succeed. |
| `validation_hash`  | String  | SHA256 hash of the Devanagari content extracted from the file. Prefixed with `sha256:`. Used to verify content integrity during round-trip conversion.    |

## 3. Content Blocks

The body of the Markdown contains the textual content, structured into passages and commentaries.

### 3.1. Passage Headings

There are three types of passages, each identified by a unique heading format. The `<ref>` is a dot-separated hierarchical identifier (e.g., `1.1`, `3.2.1`).

#### **Main Passages (Mantras)**

Used for the primary verses of the text.

**Format:** `# Mantra <ref>`

**Example:**

```markdown
# Mantra 3.1.1
```

#### **Prefatory Material**

Used for invocations, introductions, or other material that precedes a main section (e.g., a Shanti Patha).

**Format:** `# Prefatory: <ref> (devanagari: "<label>")`

**Example:**

```markdown
# Prefatory: 3.1.0 (devanagari: "शान्तिपाठः")
```

#### **Concluding Material**

Used for benedictions or other material that follows a main section.

**Format:** `# Concluding: <ref> (devanagari: "<label>")`

**Example:**

```markdown
# Concluding: 3.1.8 (devanagari: "समापनम्")
```

### 3.2. Sanskrit Content

Sanskrit text for any passage type **must** be enclosed in a script block.

**Format:**

```markdown
<!-- sanskrit:devanagari -->

...Sanskrit text goes here...

<!-- /sanskrit:devanagari -->
```

### 3.3. Commentaries

Commentaries are linked to a specific passage (`Mantra`, `Prefatory`, or `Concluding`) via a mandatory metadata comment.

**Format:**
1.  A required HTML comment containing the `commentary_id`.
2.  A standard Level 1 heading with the `<ref>`.

```markdown
<!-- commentary: {"commentary_id": "ranga-ramanujamuni-prakashika"} -->
# Commentary: 3.1.1
```

The `<ref>` in the heading provides the `passage_ref`. It can be a single reference (e.g., `3.1.1`) or a range (e.g., `3.1.1-5`) if the commentary applies to multiple passages. The `commentary_id` in the metadata comment must correspond to an entry in the `commentaries_metadata` section of the YAML frontmatter.

*Note: For backwards compatibility, the parser will tolerate older files that contain additional keys like `passage_ref` within the metadata comment, but these keys are now considered redundant.*

A commentary block must be followed by a Sanskrit content block.

### 3.4. Content Hiding

To control the visibility or processing of certain parts of the text, such as editorial notes or headings not intended for final output, you can enclose the content within `<!-- hide -->` and `<!-- /hide -->` tags.

**Format:**

```markdown
<!-- hide -->

...Content to be hidden goes here...

<!-- /hide -->
```

---

## 4. Complete Examples

### Example 1: A Single Part File

This example shows a file that contains prefatory material, a main mantra, and a concluding passage, each with an associated commentary.

```markdown
---
grantha_id: brihadaranyaka-upanishad
part_num: 1
part_title: "Adhyaya 3, Brahmana 1"
canonical_title: बृहदारण्यकोपनिषत्
text_type: upanishad
language: sanskrit
structure_levels:
  - key: Mantra
    scriptNames:
      devanagari: मन्त्रः
commentaries_metadata:
  ranga-ramanujamuni-prakashika:
    commentary_title: "प्रकाशिका"
    commentator:
      devanagari: "रङ्गरामानुजमुनिः"
---

# Prefatory: 3.1.0 (devanagari: "शान्तिपाठः")

<!-- sanskrit:devanagari -->

हरिः ओम् पूर्णमदः पूर्णमिदं पूर्णात् पूर्णमुदच्यते ।

<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "ranga-ramanujamuni-prakashika"} -->
# Commentary: 3.1.0

<!-- sanskrit:devanagari -->

Commentary on the Shanti Patha.

<!-- /sanskrit:devanagari -->

# Mantra 3.1.1

<!-- sanskrit:devanagari -->

उषा वा अश्वस्य मध्यस्य शिरः ।

<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "ranga-ramanujamuni-prakashika"} -->
# Commentary: 3.1.1

<!-- sanskrit:devanagari -->

Commentary on Mantra 3.1.1.

<!-- /sanskrit:devanagari -->

# Concluding: 3.1.2 (devanagari: "फलश्रुतिः")

<!-- sanskrit:devanagari -->

Concluding text.

<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "ranga-ramanujamuni-prakashika"} -->
# Commentary: 3.1.2

<!-- sanskrit:devanagari -->

Commentary on the concluding passage.

<!-- /sanskrit:devanagari -->
```

## 5. Validation

To ensure that your Markdown files adhere to this specification, you can use the `grantha_markdown_validator.py` script located in the `scripts/` directory. This validator performs checks on both the YAML frontmatter and the content blocks to catch common errors and ensure consistency.

### How to Use the Validator

To validate a single Markdown file, run the script from the project root:

```bash
python scripts/grantha_markdown_validator.py <path/to/your/file.md>
```

- If the file is valid, the script will exit with a success message.
- If validation fails, the script will print detailed error messages to `stderr` and exit with a non-zero status code.

### Automated Testing

The validator is also integrated into the project's `pytest` suite. Any changes to Markdown files that are part of the automated build process will be automatically validated, ensuring continuous compliance with this specification.

---

## 6. Tooling and Scripts

The project includes several Python scripts to manage the conversion and validation of Grantha Markdown files.

### `scripts/convert_granthas.py`

This is the main script for converting a single `.converted.md` file into its corresponding `part_*.json` file. It reads the `part_num` from the frontmatter to determine the output filename.

**Usage:**

```bash
python scripts/convert_granthas.py <path/to/your/file.converted.md> <output/directory/>
```

### `scripts/grantha_markdown_validator.py`

As described in the "Validation" section, this script validates a Markdown file against the specification.

**Usage:**

```bash
python scripts/grantha_markdown_validator.py <path/to/your/file.md>
```

### Core Conversion Modules

-   **`tools/grantha_converter/md_to_json.py`**: This module contains the core logic for parsing a Markdown file and converting it into the final JSON structure. It uses a robust, single-pass strategy based on the explicit headings defined in this specification.
-   **`tools/grantha_converter/json_to_md.py`**: This module handles the reverse process of converting a `part_*.json` file back into a Markdown file. This is primarily used for round-trip testing to ensure data integrity.
