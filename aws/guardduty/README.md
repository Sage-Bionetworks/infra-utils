# guardduty_org.py

Manages the GuardDuty organization settings that CloudFormation can't, for the GuardDuty
setup in [organizations-infra](https://github.com/Sage-Bionetworks-IT/organizations-infra)
(`org-formation/070-guard-duty`):

* the **delegated administrator** designation (SecurityCentralAccount, 140124849929), per region
* **org membership**: existing accounts enrolled as members in each region
* **auto-enable** (`NEW`) and **protection features**, copied from the us-east-1 organization
  configuration

Both the delegated administrator and membership are per region. The CloudFormation stack only
deploys the SecurityCentral detector in each region in `guardDutyRegions`.

**CI does not run this tool.** For when to run it (adding or removing a region, changing
features, re-enabling an account), see the
[070-guard-duty README](https://github.com/Sage-Bionetworks-IT/organizations-infra/blob/master/org-formation/070-guard-duty/README.md)
in organizations-infra.

## Dependencies

Python 3.9+ and the packages in `requirements.txt` (boto3 1.34 or newer is needed for the
GuardDuty `Features` API). CI tests Python 3.10 and 3.14; 3.9 has been checked locally.

```
pip install -r requirements.txt
```

## Region list

Regions always come from the `guardDutyRegions` parameter in organizations-infra, passed with
`--tasks-file`, so that file stays the single source of truth:

```
--tasks-file ~/Documents/organizations-infra/org-formation/070-guard-duty/_tasks.yaml
```

Pull the latest organizations-infra `master` first. Use `--region` (repeatable) on
`enable-admin` and `configure-members` to limit a run to some of those regions.

## Credentials

| Subcommand | Account | Example profile |
|---|---|---|
| `enable-admin` | management (531805629419) | `Administrator-Organization` |
| `configure-members` | SecurityCentralAccount (140124849929) as `OrganizationAccountAccessRole` | `OrganizationAccountAccessRole-Security-Central` |
| `add-region`, `remove-region` | both | both, via `--management-profile` and `--security-profile` |

The `RestrictDisableGuardduty` SCP denies `CreateMembers`, `StopMonitoringMembers`,
`DisassociateMembers` and `DeleteMembers` to everything except `OrganizationAccountAccessRole`,
so SSO roles in SecurityCentralAccount can only dry-run `configure-members` and `remove-region`.
Assume the role from the management account with a profile like:

```
[profile OrganizationAccountAccessRole-Security-Central]
role_arn = arn:aws:iam::140124849929:role/OrganizationAccountAccessRole
source_profile = Administrator-Organization
```

Each subcommand checks that its credentials are for the expected account before doing anything.

## Usage

Every subcommand accepts `--dry-run`, which makes only read calls and prints the write calls it
would make. Do a dry run first.

```
export TASKS=~/Documents/organizations-infra/org-formation/070-guard-duty/_tasks.yaml
aws sso login --profile Administrator-Organization

# Make SecurityCentralAccount the delegated administrator in every region (idempotent)
./guardduty_org.py enable-admin --tasks-file $TASKS --profile Administrator-Organization --dry-run

# Enroll members and set auto-enable and features in every region (idempotent)
./guardduty_org.py configure-members --tasks-file $TASKS \
  --profile OrganizationAccountAccessRole-Security-Central --dry-run

# After adding a region to guardDutyRegions and merging (so CI deployed the detector)
./guardduty_org.py add-region eu-south-1 --tasks-file $TASKS \
  --management-profile Administrator-Organization \
  --security-profile OrganizationAccountAccessRole-Security-Central --dry-run

# Before removing a region from guardDutyRegions. Asks you to type the region name unless --yes.
./guardduty_org.py remove-region eu-south-1 --tasks-file $TASKS \
  --management-profile Administrator-Organization \
  --security-profile OrganizationAccountAccessRole-Security-Central --dry-run
```

### What each subcommand does

* **enable-admin**: in each region, calls `EnableOrganizationAdminAccount` for
  SecurityCentralAccount unless it is already the delegated administrator.
* **configure-members**: takes the `Enabled` members of the us-east-1 detector (so
  suspended and invite-based accounts are not touched), then in each other region enrolls those
  that aren't already `Enabled` members there (`CreateMembers`, 50 per call). In every region it
  sets `AutoEnableOrganizationMembers` to `NEW` (not `ALL`, which would re-enable every
  suspended account) and copies the us-east-1 protection features, skipping:
  * features `UpdateOrganizationConfiguration` doesn't accept (`EKS_RUNTIME_MONITORING`,
    `AI_ANALYST`)
  * features or additional configurations the region doesn't offer
* **add-region**: `enable-admin`, then `configure-members`, for one region. The region must
  already be in `guardDutyRegions`.
* **remove-region**: sets auto-enable to `NONE`, then suspends (`StopMonitoringMembers`),
  disassociates and deletes every member in the region, and removes the delegated administrator
  there. us-east-1 can't be removed. Afterwards, remove the region from `guardDutyRegions` and
  merge, so CI deletes the detector stack. Suspended member detectors stay in the member
  accounts, with no GuardDuty charges.

### Exit status

* `0`: success
* `1`: error (nothing further was attempted)
* `2`: finished, with warnings (e.g. accounts reported in `UnprocessedAccounts`, or a region
  with no detector)

## Tests

```
pip install -r requirements.txt
python3 -m unittest -v test_guardduty_org
```

The tests use botocore's `Stubber`, so no AWS access is needed. `testdata/_tasks.yaml` is a copy
of the organizations-infra file, used to test parsing of org-formation's YAML tags.
