import argparse
from pathlib import Path
import json
import jsonschema

from grantha_data import JsonGrantha
from grantha_data import MarkdownWriter

# Import for hashing


def main():
    """
    Take a json file on the command line, specified by "-i" validate its schema against grantha.schema.json,
    and convert it to structured markdown to a file specified by "-o".
    """
    parser = argparse.ArgumentParser(
        description="Convert existing JSON grantha to structured markdown",
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Path to the input JSON grantha file."
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to the output structured markdown file.",
    )
    parser.add_argument(
        "-s",
        "--schema",
        default="formats/schemas/grantha.schema.json",
        help="Path to the JSON schema file for validation.",
    )

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output
    schema_path = args.schema

    print(
        f"Converting JSON grantha from {input_path} to structured markdown at {output_path}."
    )

    # Load the schema
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Load the input JSON data
    with open(input_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Validate the input JSON against the schema
    try:
        jsonschema.validate(instance=json_data, schema=schema)
        print(
            f"Input JSON file '{input_path}' validated successfully against '{schema_path}'."
        )
    except jsonschema.ValidationError as e:
        print(f"Validation Error: {e.message}")
        print(f"Path: {e.path}")
        print(f"Validator: {e.validator} = {e.validator_value}")
        exit(1)

    json_grantha = JsonGrantha(Path(input_path))
    json_grantha.validate_all()

    # Use MarkdownWriter to convert the json grantha to structured markdown.
    writer = MarkdownWriter()
    writer.write(json_grantha, Path(output_path))


if __name__ == "__main__":
    main()
