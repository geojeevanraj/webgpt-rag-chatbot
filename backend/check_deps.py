import importlib

modules_to_check = [
    ("google.generativeai", "google-generativeai"),
    ("chromadb", "chromadb"),
    ("sentence_transformers", "sentence-transformers"),
    ("aiohttp", "aiohttp"),
    ("bs4", "beautifulsoup4"),
    ("sqlalchemy", "sqlalchemy"),
    ("aiosqlite", "aiosqlite"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic_settings", "pydantic-settings"),
    ("lxml", "lxml"),
    ("dotenv", "python-dotenv"),
]

for module_name, package_name in modules_to_check:
    try:
        importlib.import_module(module_name)
        print(f"  {package_name}: OK")
    except ImportError:
        print(f"  {package_name}: MISSING")

print("\nDependency check complete.")
