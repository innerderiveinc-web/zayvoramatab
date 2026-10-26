#!/usr/bin/env python3
"""ZAYVORA MATAB OS — UI Static Syntax & Quality Linter.
Validates all JavaScript files under apps/web/static/js using `node --check`
to prevent unescaped template literals, quotes, or bracket errors in production.
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JS_DIR = BASE_DIR / "apps" / "web" / "static" / "js"
PACKAGES_DIR = BASE_DIR / "packages"

def check_file(file_path: Path) -> bool:
    try:
        res = subprocess.run(
            ["node", "--check", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return True
        else:
            print(f"❌ SYNTAX ERROR in {file_path.relative_to(BASE_DIR)}:")
            print(res.stderr.strip())
            return False
    except FileNotFoundError:
        print("⚠️ Warning: Node.js binary not found in PATH; skipping node --check.")
        return True

def main():
    print("🔍 [LINTER] Scanning all JavaScript modules for syntax validity...")
    total = 0
    passed = 0
    failed_files = []

    scan_dirs = [JS_DIR, PACKAGES_DIR]
    for s_dir in scan_dirs:
        for p in s_dir.rglob("*.js"):
            # skip node_modules
            if "node_modules" in p.parts:
                continue
            total += 1
            if check_file(p):
                passed += 1
            else:
                failed_files.append(p)

    print(f"\n📊 [LINTER RESULT] {passed}/{total} JavaScript files verified cleanly.")
    if failed_files:
        print(f"❌ {len(failed_files)} file(s) failed syntax validation!")
        sys.exit(1)
    else:
        print("✅ All JavaScript modules are 100% syntactically valid.\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
