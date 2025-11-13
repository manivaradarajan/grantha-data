# Tools Directory

This directory contains all the Python-based tools and libraries for the Grantha project. It is structured to keep the codebase organized, separating the core, installable library code from standalone scripts.

## Project Structure

The key directories are:

-   `tools/lib`: Contains all installable Python packages. Each subdirectory is a separate package that can be imported by any script in the project.
-   `tools/scripts`: A place for standalone scripts that are not part of an installable package.

## Maintenance and Development

This project is managed as an "editable" Python package. The configuration in the root `pyproject.toml` file allows any script in this repository to import the libraries located in `tools/lib`.

### Important: The Golden Rule

**After creating a new library or adding a new script with a command-line entry point, you MUST re-run the installation command from the project's root directory:**

```bash
pip install -e .
```

This command updates the Python environment to recognize the new files and command-line entry points.

---

### How to Use an Existing Library

Once the project is installed, you can import any library from `tools/lib` in any Python script within this repository, just like you would with a regular `pip` installed package.

**Example:**

```python
# In a script located anywhere in the project:
# e.g., /tools/scripts/md2md_converter/md2md_converter.py

from grantha_converter import cli

# Now you can use functions and classes from the library
cli.main()
```

---

### How to Create a New Library

Follow these steps to add a new, importable Python library:

1.  **Create a Directory:** Create a new directory for your library inside `tools/lib`. The name of this directory will be the package name you use in `import` statements.

    ```bash
    mkdir tools/lib/my_new_library
    ```

2.  **Add an `__init__.py`:** Create an empty `__init__.py` file inside your new library's directory. This file tells Python to treat the directory as a package.

    ```bash
    touch tools/lib/my_new_library/__init__.py
    ```

3.  **Add Your Code:** Add your Python modules (`.py` files) to the `tools/lib/my_new_library` directory.

4.  **Re-install the Project:** Go to the project's root directory and run the installation command.

    ```bash
    pip install -e .
    ```

Your new library is now ready to be imported anywhere in the project.

---

### How to Add a New Script with a Command-Line Entry Point

If you want to create a script that can be run directly from the command line (like the `grantha-converter` command), follow these steps:

1.  **Place Your Script:** It's recommended to place the script's code within a library in `tools/lib`. For example, if you have a script that processes images, you might create a `image_processor` library and have a `cli.py` file inside it.

2.  **Create a `main` Function:** Your script should have a clear entry point function. By convention, this is often called `main()`.

    **Example: `tools/lib/image_processor/cli.py`**
    ```python
    def main():
        print("Processing images...")
        # Your script's logic here

    if __name__ == "__main__":
        main()
    ```

3.  **Edit `pyproject.toml`:** Open the `pyproject.toml` file in the project's root directory. Add your new command to the `[project.scripts]` section.

    The format is `command-name = "path.to.module:function_name"`.

    ```toml
    [project.scripts]
    grantha-converter = "grantha_converter.cli:main"
    # Add your new script here
    process-images = "image_processor.cli:main"
    ```

4.  **Re-install the Project:** Go to the project's root directory and run the installation command.

    ```bash
pip install -e .
```

You can now run your new script from anywhere by typing `process-images` in your terminal.

---

### Where to Place Tests

For maintaining code quality and ease of development, tests should generally live alongside the code they test.

1.  **For Libraries (e.g., `grantha_converter` in `tools/lib`):**
    *   Tests should reside **inside the library's package directory**.
    *   It is recommended to place test files directly in the library's root, following the pattern `tools/lib/your_library/test_*.py`.

    **Example:**
    ```
    tools/lib/grantha_converter/
    ├── __init__.py
    ├── cli.py
    ├── test_cli.py  <-- Test file for cli.py
    └── test_parser.py <-- Test file for parser logic
    ```

    To run these tests from the project root:
    ```bash
    pytest tools/lib/grantha_converter/
    ```

2.  **For Standalone Scripts (e.g., in `tools/scripts/`):**
    *   If a standalone script contains significant logic that warrants testing, create a top-level `tests` directory in the project root (`/Users/maniv/github/grantha-data/tests/`).
    *   Within this `tests` directory, mirror the structure of your scripts.

    **Example:**
    ```
    /Users/maniv/github/grantha-data/
    ├── tools/scripts/
    │   └── my_utility_script.py
    └── tests/
        └── tools/scripts/
            └── test_my_utility_script.py
    ```

