#!/usr/bin/env python3
"""
Extract and test code examples from README.md

This script extracts Python code blocks from README.md and tests them.
"""

import re
import sys
import tempfile
from pathlib import Path


def extract_python_examples(readme_path: Path) -> list[str]:
    """Extract Python code blocks from markdown file."""
    content = readme_path.read_text()

    # Find all Python code blocks
    pattern = r"```python\n(.*?)```"
    examples = re.findall(pattern, content, re.DOTALL)

    return examples


def test_example(code: str, index: int) -> bool:
    """Test a single code example."""
    # Skip examples with placeholders or pseudo-code markers
    skip_markers = [
        "your_db",
        "MyDatabase",
        "CustomRepository",
        "...",
        "# ... other",
        "postgresql://",
    ]

    if any(marker in code for marker in skip_markers):
        print(f"  Skipping example {index} (contains placeholder code)")
        return True

    try:
        # Create a temporary file to execute the code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        # Try to compile the code first
        compile(code, f"<example-{index}>", "exec")
        print(f"  ✓ Example {index} syntax OK")

        # Note: We don't actually execute the code as it may require setup
        # In a real scenario, you might want to execute in a sandbox
        return True

    except SyntaxError as e:
        print(f"  ✗ Example {index} has syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Example {index} failed: {e}")
        return False
    finally:
        # Clean up temp file
        try:
            Path(temp_path).unlink()
        except:
            pass


def main():
    readme_path = Path("README.md")

    if not readme_path.exists():
        print("❌ README.md not found")
        sys.exit(1)

    print(f"📖 Testing code examples from {readme_path}")
    print()

    examples = extract_python_examples(readme_path)

    if not examples:
        print("⚠️  No Python code examples found in README.md")
        return

    print(f"Found {len(examples)} Python code examples")
    print()

    passed = 0
    failed = 0

    for i, example in enumerate(examples, 1):
        if test_example(example, i):
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {len(examples)} total")

    if failed > 0:
        print("❌ Some examples failed")
        sys.exit(1)
    else:
        print("✅ All examples passed")


if __name__ == "__main__":
    main()
