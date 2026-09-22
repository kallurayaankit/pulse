from pathlib import Path

root = Path(r"C:\Users\user\projects\pulse")

# ---- Fix 1: .gitignore should only ignore top-level reports/, not examples/reports/ ----
gitignore = root / ".gitignore"
text = gitignore.read_text(encoding="utf-8")
text = text.replace("reports/\n", "/reports/\n")  # anchor to repo root
gitignore.write_text(text, encoding="utf-8")
print("Fixed .gitignore: reports/ -> /reports/ (root-only)")

# ---- Fix 2: tell pytest not to collect classes starting with Test ----
pyproject = root / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")

old = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'
new = (
    '[tool.pytest.ini_options]\n'
    'testpaths = ["tests"]\n'
    'pythonpath = ["src"]\n'
    'python_classes = []\n'
    'filterwarnings = ["ignore::pytest.PytestCollectionWarning"]\n'
)

if old in text:
    text = text.replace(old, new)
    pyproject.write_text(text, encoding="utf-8")
    print("Fixed pyproject.toml: disabled class-based test collection")
else:
    print("WARNING: could not find pytest config block")

# ---- Verify examples/reports still exists locally ----
reports = root / "examples" / "reports"
files = sorted(reports.glob("*.xml"))
print()
print("Sample XML files present: " + str(len(files)))
for f in files[:3]:
    print("  " + f.name)
if len(files) > 3:
    print("  ... and " + str(len(files) - 3) + " more")

# ---- Check whether git is currently ignoring them ----
print()
print("Next steps:")
print("  1. git rm -r --cached examples/reports  (to un-ignore if already added)")
print("  2. git add .")
print("  3. git status  -- examples/reports should now appear")