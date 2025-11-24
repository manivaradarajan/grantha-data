import os


# Add project root to sys.path to allow imports
from grantha_converter.md_to_json import convert_to_json


def test_full_conversion_with_prefatory_material():
    """
    Tests the full Markdown to JSON conversion logic with a file
    that includes prefatory, main, and concluding passages,
    as well as commentaries on them.
    """
    test_file_path = os.path.join(os.path.dirname(__file__), "test_data", "test_prefatory_material.md")

    with open(test_file_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    data = convert_to_json(markdown_content)

    # 1. Validate Prefatory Material
    assert len(data['prefatory_material']) == 1
    prefatory = data['prefatory_material'][0]
    assert prefatory['ref'] == '0.1'
    assert prefatory['passage_type'] == 'prefatory'
    assert prefatory['label'] == {'devanagari': 'Test Prefatory'}
    assert prefatory['content']['sanskrit']['devanagari'] == 'Prefatory text.'

    # 2. Validate Main Passage
    assert len(data['passages']) == 1
    passage = data['passages'][0]
    assert passage['ref'] == '1.1'
    assert passage['passage_type'] == 'main'
    assert passage['content']['sanskrit']['devanagari'] == 'Mantra text.'

    # 3. Validate Concluding Material
    assert len(data['concluding_material']) == 1
    concluding = data['concluding_material'][0]
    assert concluding['ref'] == '1.2'
    assert concluding['passage_type'] == 'concluding'
    assert concluding['label'] == {'devanagari': 'Test Concluding'}
    assert concluding['content']['sanskrit']['devanagari'] == 'Concluding text.'

    # 4. Validate Commentaries
    # commentaries is a dict keyed by commentary_id, not a list
    assert len(data['commentaries']) == 1
    assert 'test-commentator' in data['commentaries']
    commentary = data['commentaries']['test-commentator']
    assert commentary['commentary_id'] == 'test-commentator'

    assert len(commentary['passages']) == 2

    # Commentary on Prefatory
    commentary_pref = commentary['passages'][0]
    assert commentary_pref['ref'] == '0.1'
    assert commentary_pref['content']['sanskrit']['devanagari'] == 'Commentary on prefatory.'

    # Commentary on Main Passage
    commentary_main = commentary['passages'][1]
    assert commentary_main['ref'] == '1.1'
    assert commentary_main['content']['sanskrit']['devanagari'] == 'Commentary on mantra 1.1.'
