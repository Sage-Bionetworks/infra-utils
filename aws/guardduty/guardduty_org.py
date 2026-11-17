#!/usr/bin/env python3
"""Manage GuardDuty organization settings that CloudFormation can't.

The CloudFormation stack in Sage-Bionetworks-IT/organizations-infra
(org-formation/070-guard-duty/guardduty.yaml) deploys a detector to SecurityCentralAccount in
every region in guardDutyRegions (org-formation/070-guard-duty/_tasks.yaml). The delegated
administrator designation and org membership are per region and not supported by
CloudFormation, so they are managed here. CI does not run this tool; see README.md in this
directory, and the 070-guard-duty README in organizations-infra, for when to run each
subcommand.

Subcommands:
  enable-admin       Make SecurityCentralAccount the GuardDuty delegated administrator in each
                     region. Run in the organization management account.
  configure-members  Enroll existing org accounts as members in each region and set
                     auto-enable (NEW) with protection features copied from the us-east-1
                     organization configuration. Run in SecurityCentralAccount as
                     OrganizationAccountAccessRole (the RestrictDisableGuardduty SCP blocks
                     CreateMembers for SSO roles).
  add-region         enable-admin, then configure-members, for one newly added region.
  remove-region      Suspend, disassociate and delete all members in a region, stop
                     auto-enable there, and remove the delegated administrator. Run before
                     removing the region from guardDutyRegions.

Every subcommand accepts --dry-run, which makes only read calls and prints the write calls
it would make. Regions always come from guardDutyRegions in the _tasks.yaml given by
--tasks-file (from an organizations-infra checkout), so that file stays the single source
of truth.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

import boto3
import yaml
from botocore.exceptions import BotoCoreError, ClientError

MANAGEMENT_ACCOUNT_ID = "531805629419"
SECURITY_CENTRAL_ACCOUNT_ID = "140124849929"  # GuardDuty delegated administrator

# us-east-1 is the source of truth for the member list and for protection features.
SOURCE_REGION = "us-east-1"

# CreateMembers, StopMonitoringMembers, DisassociateMembers and DeleteMembers accept at
# most 50 accounts per call.
BATCH_SIZE = 50

# Features that DescribeOrganizationConfiguration returns but UpdateOrganizationConfiguration
# can't take back:
#   EKS_RUNTIME_MONITORING: legacy form of RUNTIME_MONITORING, which supersedes it.
#   AI_ANALYST: rejected by the update API ("one or more provided feature names are invalid").
NON_UPDATABLE_FEATURES = frozenset({"EKS_RUNTIME_MONITORING", "AI_ANALYST"})

MANAGEMENT_PROFILE_HINT = "Administrator-Organization"
SECURITY_PROFILE_HINT = "OrganizationAccountAccessRole-Security-Central"


class GuardDutyOrgError(Exception):
    """An expected failure, reported to the user without a traceback."""


# --------------------------------------------------------------------------------------
# Region list from _tasks.yaml
# --------------------------------------------------------------------------------------


class _TasksLoader(yaml.SafeLoader):
    """Loads org-formation task files, which use custom tags.

    `<<: !Include ...` merges another file into Parameters. PyYAML requires merge values to
    be mappings and the included file isn't needed here, so those merge values are replaced
    with an empty mapping. Other tags (!Ref, !Sub, !CopyValue, ...) load as plain values.
    """

    def flatten_mapping(self, node):
        node.value = [
            (key, yaml.MappingNode("tag:yaml.org,2002:map", []))
            if key.tag == "tag:yaml.org,2002:merge" and value.tag == "!Include"
            else (key, value)
            for key, value in node.value
        ]
        super().flatten_mapping(node)


def _construct_tagged(loader, _suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_TasksLoader.add_multi_constructor("!", _construct_tagged)


def load_regions(path: Path) -> list[str]:
    """Return Parameters.guardDutyRegions.Default from the org-formation tasks file."""
    try:
        with open(path) as f:
            doc = yaml.load(f, Loader=_TasksLoader)
    except (OSError, yaml.YAMLError) as e:
        raise GuardDutyOrgError(f"Could not read {path}: {e}") from e
    try:
        regions = doc["Parameters"]["guardDutyRegions"]["Default"]
    except (KeyError, TypeError) as e:
        raise GuardDutyOrgError(f"Parameters.guardDutyRegions.Default not found in {path}.") from e
    if not isinstance(regions, list) or not regions or not all(isinstance(r, str) and r for r in regions):
        raise GuardDutyOrgError(
            f"Parameters.guardDutyRegions.Default in {path} must be a non-empty list of region names."
        )
    return regions


def select_regions(all_regions: Sequence[str], requested: Sequence[str] | None) -> list[str]:
    """Restrict to the requested regions, which must all be in guardDutyRegions."""
    if not requested:
        return list(all_regions)
    unknown = [r for r in requested if r not in all_regions]
    if unknown:
        raise GuardDutyOrgError(
            f"Not in guardDutyRegions in _tasks.yaml: {', '.join(unknown)}. "
            "Add the region there and merge (so CI deploys the detector) first."
        )
    return [r for r in all_regions if r in requested]


# --------------------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------------------


def batches(items: Sequence, size: int = BATCH_SIZE) -> list[list]:
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def _feature_entry(feature: dict) -> dict:
    entry = {"Name": feature["Name"], "AutoEnable": feature["AutoEnable"]}
    additional = [
        {"Name": a["Name"], "AutoEnable": a["AutoEnable"]} for a in feature.get("AdditionalConfiguration") or []
    ]
    if additional:
        entry["AdditionalConfiguration"] = additional
    return entry


def source_features(org_config: dict) -> list[dict]:
    """Features (including NONE ones) to copy from a DescribeOrganizationConfiguration
    response, in the shape UpdateOrganizationConfiguration accepts."""
    return [
        _feature_entry(f) for f in org_config.get("Features") or [] if f["Name"] not in NON_UPDATABLE_FEATURES
    ]


def features_for_region(features: list[dict], region_config: dict) -> tuple[list[dict], list[str]]:
    """Keep only the features and additional configurations a region reports.

    Not every feature is offered in every region (e.g. AI_ANALYST in ap-south-1).
    Returns (features to send, names of skipped features).
    """
    available = {
        f["Name"]: {a["Name"] for a in f.get("AdditionalConfiguration") or []}
        for f in region_config.get("Features") or []
    }
    kept, skipped = [], []
    for feature in features:
        if feature["Name"] not in available:
            skipped.append(feature["Name"])
            continue
        entry = {"Name": feature["Name"], "AutoEnable": feature["AutoEnable"]}
        additional = [
            a for a in feature.get("AdditionalConfiguration", []) if a["Name"] in available[feature["Name"]]
        ]
        if additional:
            entry["AdditionalConfiguration"] = additional
        kept.append(entry)
    return kept, skipped


def format_features(features: Iterable[dict]) -> list[str]:
    lines = []
    for f in features:
        line = f"{f['Name']}={f['AutoEnable']}"
        if f.get("AdditionalConfiguration"):
            line += " (" + ", ".join(f"{a['Name']}={a['AutoEnable']}" for a in f["AdditionalConfiguration"]) + ")"
        lines.append(line)
    return lines


def _describe_args(kwargs: dict) -> str:
    parts = []
    for key, value in kwargs.items():
        if key in ("AccountDetails", "AccountIds"):
            parts.append(f"{key}=[{len(value)} accounts]")
        elif key == "Features":
            parts.append(f"{key}=[{', '.join(format_features(value))}]")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


# --------------------------------------------------------------------------------------
# AWS helpers
# --------------------------------------------------------------------------------------


class Context:
    """Shared state for a run: dry-run mode, output, and a warning count."""

    def __init__(self, dry_run: bool, out: Callable[[str], None] = print):
        self.dry_run = dry_run
        self.out = out
        self.warnings = 0

    def warn(self, message: str) -> None:
        self.warnings += 1
        self.out(f"  WARNING: {message}")

    def write(self, client, operation: str, region: str, **kwargs) -> dict | None:
        """Make a write call, or print it in dry-run mode."""
        if self.dry_run:
            self.out(f"  DRY_RUN: {client.meta.service_model.service_name}.{operation}"
                     f"(region={region}, {_describe_args(kwargs)})")
            return None
        return getattr(client, operation)(**kwargs)

    def report_unprocessed(self, response: dict | None, action: str) -> None:
        for account in (response or {}).get("UnprocessedAccounts") or []:
            self.warn(f"{action}: {account['AccountId']} not processed: {account['Result']}")


def check_account(session, expected_account_id: str, profile_hint: str) -> None:
    actual = session.client("sts").get_caller_identity()["Account"]
    if actual != expected_account_id:
        raise GuardDutyOrgError(
            f"Running as account {actual}, expected {expected_account_id}. "
            f"Use a profile for that account (e.g. --profile {profile_hint}); "
            f"current profile: {session.profile_name or '<default>'}."
        )


def detector_id(client) -> str | None:
    ids = [d for page in client.get_paginator("list_detectors").paginate() for d in page["DetectorIds"]]
    return ids[0] if ids else None


def admin_status(client, admin_account_id: str) -> str | None:
    for page in client.get_paginator("list_organization_admin_accounts").paginate():
        for admin in page["AdminAccounts"]:
            if admin["AdminAccountId"] == admin_account_id:
                return admin["AdminStatus"]
    return None


def list_member_ids(client, detector: str, only_associated: bool, enabled_only: bool) -> list[str]:
    ids = []
    paginator = client.get_paginator("list_members")
    for page in paginator.paginate(DetectorId=detector, OnlyAssociated=str(only_associated).lower()):
        for member in page["Members"]:
            if not enabled_only or member.get("RelationshipStatus") == "Enabled":
                ids.append(member["AccountId"])
    return ids


# --------------------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------------------


def enable_admin(session, regions: Sequence[str], ctx: Context) -> None:
    ctx.out(f"Regions: {' '.join(regions)}")
    for region in regions:
        ctx.out(f"Checking GuardDuty delegated administrator in {region}...")
        gd = session.client("guardduty", region_name=region)
        if admin_status(gd, SECURITY_CENTRAL_ACCOUNT_ID) == "ENABLED":
            ctx.out("  Already enabled, skipping.")
            continue
        ctx.write(gd, "enable_organization_admin_account", region, AdminAccountId=SECURITY_CENTRAL_ACCOUNT_ID)
        ctx.out("  Done")


def configure_members(session, regions: Sequence[str], ctx: Context) -> None:
    ctx.out(f"Regions: {' '.join(regions)}")
    source = session.client("guardduty", region_name=SOURCE_REGION)
    source_detector = detector_id(source)
    if not source_detector:
        raise GuardDutyOrgError(f"No GuardDuty detector found in {SOURCE_REGION}.")

    features = source_features(source.describe_organization_configuration(DetectorId=source_detector))
    if not features:
        raise GuardDutyOrgError(f"No features found in the {SOURCE_REGION} organization configuration.")
    ctx.out(f"Features (from {SOURCE_REGION} organization configuration):")
    for line in format_features(features):
        ctx.out(f"  {line}")

    member_ids = list_member_ids(source, source_detector, only_associated=True, enabled_only=True)
    # CreateMembers requires an Email for each account, but ListMembers returns none for
    # org-managed members, so take emails from Organizations.
    emails = {
        account["Id"]: account["Email"]
        for page in session.client("organizations").get_paginator("list_accounts").paginate()
        for account in page["Accounts"]
    }
    missing = [i for i in member_ids if i not in emails]
    if missing:
        raise GuardDutyOrgError(f"{SOURCE_REGION} members not found in the organization: {', '.join(missing)}")
    members = [{"AccountId": i, "Email": emails[i]} for i in member_ids]
    ctx.out(f"Found {len(members)} Enabled members in {SOURCE_REGION}.")

    for region in regions:
        ctx.out(f"Configuring GuardDuty org membership in {region}...")
        gd = session.client("guardduty", region_name=region)
        detector = detector_id(gd)
        if not detector:
            ctx.warn(f"No detector found in {region}, skipping.")
            continue

        region_features, skipped = features_for_region(
            features, gd.describe_organization_configuration(DetectorId=detector)
        )
        if skipped:
            ctx.out(f"  Not available in {region}, skipping: {', '.join(skipped)}")

        if region != SOURCE_REGION:
            # Only enroll accounts that aren't already Enabled members here, so re-runs don't
            # depend on how CreateMembers reports existing members.
            enabled = set(list_member_ids(gd, detector, only_associated=True, enabled_only=True))
            to_enroll = [m for m in members if m["AccountId"] not in enabled]
            ctx.out(f"  {len(members) - len(to_enroll)} already Enabled members, {len(to_enroll)} to enroll.")
            for batch in batches(to_enroll):
                response = ctx.write(gd, "create_members", region, DetectorId=detector, AccountDetails=batch)
                ctx.report_unprocessed(response, "CreateMembers")

        # NEW, not ALL: ALL would re-enable every suspended account. See README.md.
        ctx.write(
            gd,
            "update_organization_configuration",
            region,
            DetectorId=detector,
            AutoEnableOrganizationMembers="NEW",
            Features=region_features,
        )
        ctx.out(f"  Done (detector: {detector})")


def remove_region(security_session, management_session, region: str, ctx: Context) -> None:
    """Undo GuardDuty org membership in one region (see README.md, Removing a region)."""
    gd = security_session.client("guardduty", region_name=region)
    detector = detector_id(gd)
    if not detector:
        ctx.warn(f"No SecurityCentral detector found in {region}; skipping member cleanup.")
    else:
        ctx.out(f"Stopping auto-enable in {region} (detector: {detector})...")
        ctx.write(gd, "update_organization_configuration", region,
                  DetectorId=detector, AutoEnableOrganizationMembers="NONE")

        member_ids = list_member_ids(gd, detector, only_associated=False, enabled_only=False)
        ctx.out(f"Found {len(member_ids)} members in {region}.")
        for batch in batches(member_ids):
            for operation, action in (
                ("stop_monitoring_members", "StopMonitoringMembers"),
                ("disassociate_members", "DisassociateMembers"),
                ("delete_members", "DeleteMembers"),
            ):
                ctx.out(f"  {action} for {len(batch)} accounts...")
                response = ctx.write(gd, operation, region, DetectorId=detector, AccountIds=batch)
                ctx.report_unprocessed(response, action)

    mgmt = management_session.client("guardduty", region_name=region)
    if admin_status(mgmt, SECURITY_CENTRAL_ACCOUNT_ID) is None:
        ctx.out(f"SecurityCentralAccount is not the delegated administrator in {region}; nothing to remove.")
    else:
        ctx.out(f"Removing the delegated administrator in {region}...")
        ctx.write(mgmt, "disable_organization_admin_account", region, AdminAccountId=SECURITY_CENTRAL_ACCOUNT_ID)

    ctx.out(
        f"Next: remove {region} from guardDutyRegions in _tasks.yaml and merge, so CI deletes the "
        "SecurityCentral detector stack there. Suspended member detectors remain in the member "
        "accounts (no GuardDuty charges); deleting those has to be done in each account."
    )


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def _session(profile: str | None):
    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def _confirm(region: str, assume_yes: bool, read: Callable[[str], str] = input) -> None:
    if assume_yes:
        return
    answer = read(
        f"This suspends GuardDuty in every member account in {region} and removes them and the "
        f"delegated administrator there. Type the region name to continue: "
    )
    if answer.strip() != region:
        raise GuardDutyOrgError("Confirmation did not match; nothing was changed.")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--tasks-file", required=True, type=Path, metavar="PATH",
                        help="org-formation/070-guard-duty/_tasks.yaml in an organizations-infra "
                             "checkout; regions are read from its guardDutyRegions parameter")
    common.add_argument("--dry-run", action="store_true",
                        help="make only read calls and print the write calls that would be made")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("enable-admin", parents=[common],
                       help="make SecurityCentralAccount the delegated administrator in each region")
    p.add_argument("--profile", help=f"management account profile (e.g. {MANAGEMENT_PROFILE_HINT}); "
                                     "default: AWS_PROFILE / default credentials")
    p.add_argument("--region", action="append", dest="regions", metavar="REGION",
                   help="limit to this region (repeatable; must be in guardDutyRegions)")

    p = sub.add_parser("configure-members", parents=[common],
                       help="enroll members and set auto-enable and features in each region")
    p.add_argument("--profile", help=f"SecurityCentralAccount profile (e.g. {SECURITY_PROFILE_HINT}); "
                                     "default: AWS_PROFILE / default credentials")
    p.add_argument("--region", action="append", dest="regions", metavar="REGION",
                   help="limit to this region (repeatable; must be in guardDutyRegions)")

    for name, help_text in (
        ("add-region", "run enable-admin, then configure-members, for one newly added region"),
        ("remove-region", "remove GuardDuty org membership from one region (run before removing it "
                          "from guardDutyRegions)"),
    ):
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.add_argument("region")
        p.add_argument("--management-profile", required=True, help=f"e.g. {MANAGEMENT_PROFILE_HINT}")
        p.add_argument("--security-profile", required=True, help=f"e.g. {SECURITY_PROFILE_HINT}")
        if name == "remove-region":
            p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Context(dry_run=args.dry_run)
    try:
        all_regions = load_regions(args.tasks_file)
        if args.command == "enable-admin":
            session = _session(args.profile)
            check_account(session, MANAGEMENT_ACCOUNT_ID, MANAGEMENT_PROFILE_HINT)
            enable_admin(session, select_regions(all_regions, args.regions), ctx)
        elif args.command == "configure-members":
            session = _session(args.profile)
            check_account(session, SECURITY_CENTRAL_ACCOUNT_ID, SECURITY_PROFILE_HINT)
            configure_members(session, select_regions(all_regions, args.regions), ctx)
        elif args.command == "add-region":
            regions = select_regions(all_regions, [args.region])
            management, security = _session(args.management_profile), _session(args.security_profile)
            check_account(management, MANAGEMENT_ACCOUNT_ID, MANAGEMENT_PROFILE_HINT)
            check_account(security, SECURITY_CENTRAL_ACCOUNT_ID, SECURITY_PROFILE_HINT)
            enable_admin(management, regions, ctx)
            configure_members(security, regions, ctx)
        elif args.command == "remove-region":
            management, security = _session(args.management_profile), _session(args.security_profile)
            check_account(management, MANAGEMENT_ACCOUNT_ID, MANAGEMENT_PROFILE_HINT)
            check_account(security, SECURITY_CENTRAL_ACCOUNT_ID, SECURITY_PROFILE_HINT)
            if args.region == SOURCE_REGION:
                raise GuardDutyOrgError(f"{SOURCE_REGION} is the source of truth for members and features; "
                                        "removing it is not supported.")
            if args.region not in all_regions:
                ctx.out(f"Note: {args.region} is not in guardDutyRegions (already removed from _tasks.yaml).")
            if not ctx.dry_run:
                _confirm(args.region, args.yes)
            remove_region(security, management, args.region, ctx)
    except GuardDutyOrgError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except (ClientError, BotoCoreError) as e:
        print(f"ERROR: AWS call failed: {e}", file=sys.stderr)
        return 1

    if ctx.warnings:
        print(f"Finished with {ctx.warnings} warning(s); see above.")
        return 2
    print("Done." if not ctx.dry_run else "Dry run complete; no changes were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
