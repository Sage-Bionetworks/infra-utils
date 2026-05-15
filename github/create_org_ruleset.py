#!/usr/bin/env python3
"""
create_org_ruleset.py

Creates an organization-level ruleset in GitHub that applies branch protection
rules across multiple repositories at once.

Usage:
    python create_org_ruleset.py

Requirements:
    pip install requests

Environment variables:
    GITHUB_TOKEN  - Personal access token with admin:org and repo scope
    GITHUB_ORG    - Organization name (or set ORG constant below)
"""

import os
import json
import requests

# ── Configuration ────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "YOUR_TOKEN_HERE")
ORG = os.environ.get("GITHUB_ORG", "your-org-name")

# Which repositories to target.
# Options:
#   {"type": "all"}                          — every repo in the org
#   {"type": "named", "names": ["repo-a"]}  — specific repos by name
#   {"type": "pattern", "patterns": ["*"]}  — glob patterns
REPO_TARGET = {"type": "all"}

# Branch patterns this ruleset will protect
INCLUDE_BRANCH_PATTERNS = [
    "refs/heads/main",
    "refs/heads/master",
    "refs/heads/prod",
    "refs/heads/release/*",
]
EXCLUDE_BRANCH_PATTERNS = [
    "refs/heads/dev",
]

# ── Ruleset definition ────────────────────────────────────────────────────────

RULESET = {
    "name": "Sage Default Branch Protection",
    # "active" enforces the ruleset; "evaluate" runs in audit/report mode only
    "enforcement": "active",
    "target": "branch",

    # Who is allowed to bypass these rules?
    # Remove entries or leave empty to allow no bypasses.
    "bypass_actors": [
        # Allow org admins to bypass
        {"actor_id": 1, "actor_type": "OrganizationAdmin", "bypass_mode": "always"}
    ],

    # Which repos & branches this ruleset applies to
    "conditions": {
        "ref_name": {
            "include": INCLUDE_BRANCH_PATTERNS,
            "exclude": EXCLUDE_BRANCH_PATTERNS,          # e.g. ["refs/heads/dev"] to exempt dev branch
        },
        "repository_name": {
            "include": ["~ALL"],    # ~ALL = every repo; or list specific names/globs
            "exclude": [],          # e.g. ["sandbox-*"] to skip sandbox repos
            "protected": False,
        },
    },

    # The actual protection rules
    "rules": [
        # Require an approved pull request before merging
        {
            "type": "pull_request",
            "parameters": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "allowed_merge_methods": ["merge", "squash", "rebase"],
            },
        },
        # Block force pushes
        {"type": "non_fast_forward"},
        # Block branch deletion
        {"type": "deletion"},
        # Require linear history (no merge commits)
        # {"type": "required_linear_history"},
        # Require signed commits
        # {"type": "required_signatures"},
    ],
}

# ── API helpers ───────────────────────────────────────────────────────────────

BASE_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def list_existing_rulesets(org: str) -> list[dict]:
    """Return all rulesets currently defined for the org."""
    url = f"{BASE_URL}/orgs/{org}/rulesets"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def create_ruleset(org: str, ruleset: dict) -> dict:
    """POST a new ruleset to the org and return the created object."""
    url = f"{BASE_URL}/orgs/{org}/rulesets"
    resp = requests.post(url, headers=HEADERS, json=ruleset)
    resp.raise_for_status()
    return resp.json()


def update_ruleset(org: str, ruleset_id: int, ruleset: dict) -> dict:
    """PUT (full replace) an existing ruleset."""
    url = f"{BASE_URL}/orgs/{org}/rulesets/{ruleset_id}"
    resp = requests.put(url, headers=HEADERS, json=ruleset)
    resp.raise_for_status()
    return resp.json()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Organization : {ORG}")
    print(f"Ruleset name : {RULESET['name']}")
    print(f"Enforcement  : {RULESET['enforcement']}")
    print(f"Included branches: {INCLUDE_BRANCH_PATTERNS}\n")
    print(f"Excluded branches: {EXCLUDE_BRANCH_PATTERNS}\n")

    # Check for an existing ruleset with the same name to avoid duplicates
    print("Fetching existing rulesets …")
    existing = list_existing_rulesets(ORG)
    match = next((r for r in existing if r["name"] == RULESET["name"]), None)

    if match:
        print(f"  Found existing ruleset id={match['id']} — updating it.")
        result = update_ruleset(ORG, match["id"], RULESET)
        action = "Updated"
    else:
        print("  No existing ruleset found — creating a new one.")
        result = create_ruleset(ORG, RULESET)
        action = "Created"

    print(f"\n {action} ruleset successfully!")
    print(f"  ID          : {result['id']}")
    print(f"  Name        : {result['name']}")
    print(f"  Enforcement : {result['enforcement']}")
    print(f"  Node ID     : {result.get('node_id', 'n/a')}")
    print(f"\nFull response:\n{json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
