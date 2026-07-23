#!/bin/bash -ex

# Batch update Python dependencies across multiple repositories to address
# Dependabot security findings. For each repo, this script updates dependencies,
# runs tests, and prepares commits for manual review and push.
#
# Quick start:
#   ./update-all-lambdas-dependabot.sh
#
# Configuration (optional):
#   REPO_BASE_PATH=../repos CHECK_LIBRARY=requests ./update-all-lambdas-dependabot.sh

# Base directory for repositories (defaults to parent directory)
base_repo_path="${REPO_BASE_PATH:-..}"

# Branch name for dependency updates
branch=dependency-update

# Library name to verify was updated in the dependency changes
check="${CHECK_LIBRARY:-urllib3}"

# Repositories in format "org/repo"
repos=(
    Sage-Bionetworks-IT/cfn-cr-alb-rule
    Sage-Bionetworks-IT/cfn-cr-same-region-bucket-download
    Sage-Bionetworks-IT/cfn-cr-sc-actions-provider
    Sage-Bionetworks-IT/cfn-cr-sc-bucket-policy
    Sage-Bionetworks-IT/cfn-cr-sc-product-provider
    Sage-Bionetworks-IT/cfn-cr-synapse-tagger
    Sage-Bionetworks-IT/cfn-explode-macro
    Sage-Bionetworks-IT/cfn-macro-ssm-param
    Sage-Bionetworks-IT/cfn-s3objects-macro
    Sage-Bionetworks-IT/lambda-batch-trigger
    Sage-Bionetworks-IT/lambda-budgets
    Sage-Bionetworks-IT/lambda-ebs-cleanup
    Sage-Bionetworks-IT/lambda-ec2-terminator
    Sage-Bionetworks-IT/lambda-finops-cost-rules
    Sage-Bionetworks-IT/lambda-finops-email-totals
    Sage-Bionetworks-IT/lambda-finops-floqast-sftp
    Sage-Bionetworks-IT/lambda-finops-s3-cost-report
    Sage-Bionetworks-IT/lambda-mips-api
    Sage-Bionetworks-IT/lambda-sc-bucket-cleanup
    Sage-Bionetworks-IT/lambda-send-budget-alert
    Sage-Bionetworks-IT/lambda-tag-patch-group
    Sage-Bionetworks-IT/lambda-template
    Sage-Bionetworks/s3-synapse-sync
)

# Track which repos were skipped or completed
skipped=""
completed=""

# Commit message for dependency updates
message="Update Python dependencies

Update ${check} dependency to address security vulnerabilities identified by
Dependabot. This update ensures the project uses the latest stable version
with known security fixes applied."


# Process each repository
for repo in "${repos[@]}"
do
    echo
    echo '  *****'
    echo

    # Extract repo name from org/repo format
    repo_name=$(basename "${repo}")
    repo_path="${base_repo_path}/${repo_name}"

    # Clone repo if it doesn't exist locally
    if [ ! -d "${repo_path}" ]
    then
        echo "Cloning ${repo}..."
        git clone "https://github.com/${repo}.git" "${repo_path}"
    fi

    pushd "${repo_path}"

    # Checkout and update main/master branch
    git checkout --force main || git checkout --force master

    git remote update
    git reset --hard origin/main || git reset --hard origin/master
    git checkout -B "${branch}"

    # Install fresh dependencies
    if ! (
        pipenv --rm &&
        pipenv lock --clear -d &&
        pipenv update -d
    )
    then
        # Failed to update dependencies - skip this repo
        skipped="${skipped} ${repo_name}"
        popd
        continue
    fi

    # Check if the target library was updated
    if ! (
        git diff | grep "${check}"
    )
    then
        # Library not updated - manually edit Pipfile and try again
        if ! (
            $EDITOR Pipfile &&
            pipenv --rm &&
            pipenv lock --clear -d &&
            pipenv update -d
        )
        then
            # Failed to update dependencies after edit - skip this repo
            skipped="${skipped} ${repo_name}"
            popd
            continue
        fi

        # Check again after manual edit
        if ! (
            git diff | grep "${check}"
        )
        then
            # Still no update - drop to shell for manual intervention
            echo "Library ${check} still not updated. Dropping to shell..."
            echo "Exit with non-zero status to skip this repo, or zero to continue."

            if ! $SHELL
            then
                # Shell exited with non-zero - skip this repo
                skipped="${skipped} ${repo_name}"
                popd
                continue
            fi

            # Check one more time after shell intervention
            if ! (
                git diff | grep "${check}"
            )
            then
                # Still no update after shell - skip this repo
                skipped="${skipped} ${repo_name}"
                popd
                continue
            fi
        fi
    fi

    # Run tests and commit changes
    if (
        # Not all projects list pre-commit as a dependency
        # pipenv run pre-commit run -a
        pipenv run coverage run -m pytest tests/ -svvv --log-level=DEBUG &&
        pipenv run coverage lcov && pipenv run coverage report -m &&
        git commit -am "${message}"
    )
    then
        completed="${completed} ${repo_name}"
    else
        # Tests failed or commit failed - skip this repo
        skipped="${skipped} ${repo_name}"
        popd
        continue
    fi

    # Open shell for manual verification,
    # amending commit message if needed,
    # and pushing to GitHub
    if ! $SHELL
    then
        # Shell exited with non-zero - skip this repo
        skipped="${skipped} ${repo_name}"
        popd
        continue
    fi

    popd
done

# Summary of results
echo Skipped repos: ${skipped}
echo Completed repos: ${completed}
