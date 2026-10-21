#!/usr/bin/env python3
"""Check repository documentation completeness.

Validates that:
1. README.md exists with an H1 title and the required sections
   (installation/quickstart, usage/examples, license), matched by heading
2. All relative links in markdown files resolve to existing files
3. All referenced files (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md) exist
4. Hugo-style absolute paths (e.g. /games/...) are web URLs, not file links
"""

import os
import re
import sys
from pathlib import Path

# Each entry maps a required README concept to the heading synonyms that
# satisfy it. Synonyms follow docs/repository-documentation-standard.md, which
# names the install/run section "Quickstart" and the walkthrough "Examples".
REQUIRED_README_SECTIONS = {
    "installation": r"(install|quick\s*start|getting started|setup|prerequisite)",
    "usage": r"(usage|example|quick\s*start|pattern|how to use|what's inside)",
    "license": r"licen[cs]e",
}

HEADING_PATTERN = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)

LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
BADGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def check_readme(repo_path):
    """Check README.md exists and has required sections."""
    issues = []
    readme_path = repo_path / "README.md"
    
    if not readme_path.exists():
        issues.append("Missing README.md")
        return issues
    
    content = readme_path.read_text(encoding="utf-8")
    
    # Check for required sections. Matching is anchored to markdown headings so
    # that an incidental mention in prose or a URL cannot satisfy the check;
    # the license concept may also be asserted in prose.
    headings = "\n".join(HEADING_PATTERN.findall(content))
    for section, pattern in REQUIRED_README_SECTIONS.items():
        haystack = content if section == "license" else headings
        if not re.search(pattern, haystack, re.IGNORECASE):
            issues.append(f"README.md missing section: {section}")
    
    # Check for title
    if not re.search(r"^# .+", content, re.MULTILINE):
        issues.append("README.md missing title (H1 heading)")
    
    return issues


def check_links(repo_path):
    """Check all relative links in markdown files resolve to existing files."""
    issues = []
    checked_links = set()
    
    for md_file in repo_path.rglob("*.md"):
        # Skip .git directory
        if ".git" in md_file.parts:
            continue
        
        content = md_file.read_text(encoding="utf-8")
        
        for match in LINK_PATTERN.finditer(content):
            link_text = match.group(1)
            link_target = match.group(2)
            
            # Skip external links, anchors, mailto, and Hugo absolute paths
            if link_target.startswith(("http://", "https://", "#", "mailto:", "/")):
                continue
            
            # Skip already-checked links
            cache_key = (str(md_file), link_target)
            if cache_key in checked_links:
                continue
            checked_links.add(cache_key)
            
            # Resolve relative to the markdown file's directory
            resolved = (md_file.parent / link_target).resolve()
            
            # Also check repo root (for links from docs/ to root files)
            repo_root_resolved = (repo_path / link_target).resolve()
            
            if not resolved.exists() and not repo_root_resolved.exists():
                rel_path = md_file.relative_to(repo_path)
                issues.append(f"{rel_path}: broken link [{link_text}]({link_target})")
    
    return issues


def check_referenced_files(repo_path):
    """Check that commonly referenced files exist."""
    issues = []
    
    # Check for LICENSE file
    license_files = list(repo_path.glob("LICENSE*")) + list(repo_path.glob("COPYING*"))
    if not license_files:
        issues.append("Missing LICENSE file")
    
    # Check for CONTRIBUTING.md
    if not (repo_path / "CONTRIBUTING.md").exists():
        issues.append("Missing CONTRIBUTING.md")
    
    # Check for CODE_OF_CONDUCT.md
    if not (repo_path / "CODE_OF_CONDUCT.md").exists():
        issues.append("Missing CODE_OF_CONDUCT.md")
    
    return issues


def main():
    repo_path = Path.cwd()
    
    issues = []
    issues.extend(check_readme(repo_path))
    issues.extend(check_links(repo_path))
    issues.extend(check_referenced_files(repo_path))
    
    if issues:
        print("Documentation check FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("Documentation check PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
