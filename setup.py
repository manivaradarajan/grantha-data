from setuptools import setup, find_packages

setup(
    # This mapping says: 
    # 1. "Root" packages (like gemini_processor) are in tools/lib
    # 2. The "scripts" package is in tools/scripts
    package_dir={
        "": "tools/lib",
        "scripts": "tools/scripts",
    },
    # We combine the discovery from both locations
    packages=(
        find_packages(where="tools/lib") + 
        find_packages(where="tools", include=["scripts", "scripts.*"])
    ),
)
