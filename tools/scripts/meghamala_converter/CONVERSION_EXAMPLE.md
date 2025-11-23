# Example: Meghamala Source → Post-Cleaning → Final Grantha Markdown

## INPUT (Pre-Cleaned Source)

```markdown
**ईशावास्योपनिषत्**

**प्रथमः** **मन्त्रः**

**[****सर्वव्यापकत्वप्रतिपादनम्****]**

**ईशावास्यमिदं सर्वं यत्किञ्च जगत्यां जगत् ।**

**तेन त्यक्तेन भुञ्जीथाः मा गृधः कस्यस्विद्धनम् ।।१।।**

**प्रकाशिका**

**श्रीरङ्गरामानुजमुनिविरचिता**

**[****मङ्गलाचरणम्****]**

वन्दे वेदान्तवेद्यं च वेदान्ताचार्यमव्ययम् ।

सर्वलोकैकनाथं च श्रीरामानुजमुनिम् ।।

ईशावास्यमिदं सर्वम् इति । ईशः परमात्मा । तस्य वस्यं वासस्थानं भूतम् इदं सर्वं जगत् । यत्किञ्च – यत्किमपि । जगत्याम् – पृथिव्याम् । जगत् – जङ्गमम् ।
```

## POST-CLEANING (Sent to Gemini)

```markdown
ईशावास्योपनिषत्

प्रथमः मन्त्रः

सर्वव्यापकत्वप्रतिपादनम्

ईशावास्यमिदं सर्वं यत्किञ्च जगत्यां जगत् ।

तेन त्यक्तेन भुञ्जीथाः मा गृधः कस्यस्विद्धनम् ।।१।।

प्रकाशिका

श्रीरङ्गरामानुजमुनिविरचिता

मङ्गलाचरणम्

वन्दे वेदान्तवेद्यं च वेदान्ताचार्यमव्ययम् ।

सर्वलोकैकनाथं च श्रीरामानुजमुनिम् ।।

ईशावास्यमिदं सर्वम् इति । ईशः परमात्मा । तस्य वस्यं वासस्थानं भूतम् इदं सर्वं जगत् । यत्किञ्च – यत्किमपि । जगत्याम् – पृथिव्याम् । जगत् – जङ्गमम् ।
```

## FINAL OUTPUT (Grantha Markdown)

```markdown
---
grantha_id: ishavasya-upanishad
part_num: 1
canonical_title: ईशावास्योपनिषत्
text_type: upanishad
language: sanskrit
structure_type: mantra
commentaries_metadata:
- commentary_id: rangaramanuja-muni-prakashika
  commentary_title: प्रकाशिका
  commentator:
    devanagari: श्रीरङ्गरामानुजमुनिः
    roman: ''
  authored_colophon: श्रीरङ्गरामानुजमुनिभिः विरचिता
structure_levels:
- key: Mantra
  scriptNames:
    devanagari: मन्त्रः
    roman: mantra
hash_version: 3
validation_hash: abc123...
---

<!-- hide type:document-title -->
ईशावास्योपनिषत्
<!-- /hide -->

<!-- hide type:section-marker -->
प्रथमः मन्त्रः
<!-- /hide -->

<!-- hide type:editorial-heading -->
सर्वव्यापकत्वप्रतिपादनम्
<!-- /hide -->

# Mantra 1

<!-- sanskrit:devanagari -->
ईशावास्यमिदं सर्वं यत्किञ्च जगत्यां जगत् ।
तेन त्यक्तेन भुञ्जीथाः मा गृधः कस्यस्विद्धनम्<!-- hide type:verse-number --> ।।१।। <!-- /hide -->
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "rangaramanuja-muni-prakashika"} -->
# Commentary: 1

<!-- hide type:commentary-title -->
प्रकाशिका
<!-- /hide -->

<!-- hide type:author-note -->
श्रीरङ्गरामानुजमुनिविरचिता
<!-- /hide -->

<!-- hide type:sub-heading -->
मङ्गलाचरणम्
<!-- /hide -->

वन्दे वेदान्तवेद्यं च वेदान्ताचार्यमव्ययम् ।

सर्वलोकैकनाथं च श्रीरामानुजमुनिम् ।।

ईशावास्यमिदं सर्वम् इति । ईशः परमात्मा । तस्य वस्यं वासस्थानं भूतम् इदं सर्वं जगत् । यत्किञ्च – यत्किमपि । जगत्याम् – पृथिव्याम् । जगत् – जङ्गमम् ।
```

## KEY TRANSFORMATIONS

1. **Bold removal** (`**text**` → `text`)
   - All `**` markers removed
   - Spacing between words preserved
   - Example: `**प्रथमः** **मन्त्रः**` → `प्रथमः मन्त्रः`

2. **Structural identification**
   - Document title → `<!-- hide type:document-title -->`
   - Section markers → `<!-- hide type:section-marker -->`
   - Editorial headings → `<!-- hide type:editorial-heading -->`
   - Bold markers in meghamala (`**[****text****]**`) indicate structural elements

3. **Mantra extraction**
   - Sanskrit verse becomes `# Mantra N` with `<!-- sanskrit:devanagari -->` block
   - Verse numbers moved to `<!-- hide type:verse-number -->`

4. **Commentary structuring**
   - Commentary title/author → hidden with appropriate type
   - Sub-headings (मङ्गलाचरणम्) → hidden
   - Commentary body text remains visible
   - Linked to mantra via `<!-- commentary: {...} -->`

5. **Metadata generation**
   - YAML frontmatter with structure_levels, commentaries_metadata
   - Validation hash computed from Devanagari content only

## CRITICAL: Preserve Spacing

The post-cleaned text MUST preserve all spaces from the source:
- ✅ CORRECT: `प्रथमः मन्त्रः` (space between words)
- ❌ WRONG: `प्रथमःमन्त्रः` (space lost)

This is essential because compound word spacing (sandhi) affects meaning.
