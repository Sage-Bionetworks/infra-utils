# Scripts for Source Control Management

* [update-all-lambdas-dependabot.sh](#update-all-lambdas-dependabotsh)

## update-all-lambdas-dependabot.sh

Batch update Python dependencies across multiple GitHub repositories to address
Dependabot security findings. For each repo, this script updates dependencies,
runs tests, and prepares commits for manual review and push.

### Dependencies

* git
* pipenv
* pytest
* coverage

### Usage

Basic usage with defaults:
```bash
./update-all-lambdas-dependabot.sh
```

Custom configuration:
```bash
REPO_BASE_PATH=../repos CHECK_LIBRARY=requests ./update-all-lambdas-dependabot.sh
```

### Environment Variables

* `REPO_BASE_PATH`: Base directory for repositories (default: `..`)
* `CHECK_LIBRARY`: Library name to verify was updated (default: `urllib3`)

### Workflow

For each repository in the configured list:

1. Clone the repository if not present locally
2. Checkout and update the main/master branch
3. Create a new branch for dependency updates
4. Update Python dependencies using pipenv
5. Verify the target library was updated
6. Run tests with coverage
7. Commit changes with a standardized message
8. Open a shell for manual review and push

### Notes

* Repositories are cloned to `${REPO_BASE_PATH}/<repo-name>`
* The script will pause for manual intervention if dependency updates fail
* Tests must pass before changes are committed
* Final push to GitHub is manual to allow for review
