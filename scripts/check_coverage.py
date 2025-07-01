#!/usr/bin/env python3
"""Check test coverage and enforce minimum coverage threshold."""

import subprocess
import sys
import re

def get_coverage_percentage():
    """Run pytest with coverage and extract the total coverage percentage."""
    try:
        result = subprocess.run(
            ["pytest", "tests/", "--cov=src/kanban", "--cov-report=term"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Look for the TOTAL line in coverage output
        for line in result.stdout.split('\n'):
            if 'TOTAL' in line:
                # Extract percentage from line like "TOTAL    834    279    192     33  59.84%"
                match = re.search(r'(\d+\.?\d*)%', line)
                if match:
                    return float(match.group(1))
        
        print("Could not find coverage percentage in output")
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"pytest failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return None

def main():
    """Main function to check coverage."""
    min_coverage = 60.0  # Minimum required coverage percentage
    
    print("Checking test coverage...")
    coverage = get_coverage_percentage()
    
    if coverage is None:
        print("Failed to get coverage percentage")
        sys.exit(1)
    
    print(f"Current coverage: {coverage:.2f}%")
    print(f"Minimum required: {min_coverage:.2f}%")
    
    if coverage < min_coverage:
        print(f"❌ Coverage {coverage:.2f}% is below minimum {min_coverage:.2f}%")
        sys.exit(1)
    else:
        print(f"✅ Coverage {coverage:.2f}% meets minimum requirement")
        sys.exit(0)

if __name__ == "__main__":
    main()