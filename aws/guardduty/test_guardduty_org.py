"""Unit tests for guardduty_org.py. No AWS access needed.

Run from this directory:  python3 -m unittest -v test_guardduty_org

testdata/_tasks.yaml is a copy of org-formation/070-guard-duty/_tasks.yaml from
Sage-Bionetworks-IT/organizations-infra, so the loader is tested against the real format.
"""

import tempfile
import unittest
from pathlib import Path

import boto3
from botocore.stub import Stubber

import guardduty_org as g

SECURITY = g.SECURITY_CENTRAL_ACCOUNT_ID
FIXTURE_TASKS_FILE = Path(__file__).resolve().parent / "testdata" / "_tasks.yaml"


class FakeSession:
    """Returns one stubbed client per (service, region); Stubber fails on any unexpected call."""

    def __init__(self, account_id=None):
        self._real = boto3.Session(aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
        self._clients = {}
        self.stubbers = []
        self.profile_name = "test"
        if account_id:  # only for tests that call check_account
            self.stub("sts").add_response("get_caller_identity",
                                          {"Account": account_id, "UserId": "u", "Arn": "arn:aws:iam::0:user/u"})

    def stub(self, service, region="us-east-1"):
        client = self._real.client(service, region_name=region)
        stubber = Stubber(client)
        stubber.activate()
        self._clients[(service, region)] = client
        self.stubbers.append(stubber)
        return stubber

    def client(self, service, region_name="us-east-1"):
        return self._clients[(service, region_name)]

    def assert_done(self):
        for s in self.stubbers:
            s.assert_no_pending_responses()


def quiet():
    lines = []
    return lines, g.Context(dry_run=False, out=lines.append)


SOURCE_CONFIG = {
    "AutoEnableOrganizationMembers": "NEW",
    "MemberAccountLimitReached": False,
    "Features": [
        {"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL"},
        {"Name": "EKS_RUNTIME_MONITORING", "AutoEnable": "NONE",
         "AdditionalConfiguration": [{"Name": "EKS_ADDON_MANAGEMENT", "AutoEnable": "NONE"}]},
        {"Name": "RUNTIME_MONITORING", "AutoEnable": "ALL",
         "AdditionalConfiguration": [{"Name": "EC2_AGENT_MANAGEMENT", "AutoEnable": "ALL"},
                                     {"Name": "EKS_ADDON_MANAGEMENT", "AutoEnable": "NONE"}]},
        {"Name": "AI_ANALYST", "AutoEnable": "NONE"},
        {"Name": "AI_PROTECTION", "AutoEnable": "NONE"},
    ],
}
SOURCE_FEATURES = [
    {"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL"},
    {"Name": "RUNTIME_MONITORING", "AutoEnable": "ALL",
     "AdditionalConfiguration": [{"Name": "EC2_AGENT_MANAGEMENT", "AutoEnable": "ALL"},
                                 {"Name": "EKS_ADDON_MANAGEMENT", "AutoEnable": "NONE"}]},
    {"Name": "AI_PROTECTION", "AutoEnable": "NONE"},
]
# A region without AI_PROTECTION and without EC2 agent management.
REGION_CONFIG = {
    "AutoEnableOrganizationMembers": "NEW",
    "MemberAccountLimitReached": False,
    "Features": [
        {"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL"},
        {"Name": "RUNTIME_MONITORING", "AutoEnable": "ALL",
         "AdditionalConfiguration": [{"Name": "EKS_ADDON_MANAGEMENT", "AutoEnable": "NONE"}]},
    ],
}
REGION_FEATURES = [
    {"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL"},
    {"Name": "RUNTIME_MONITORING", "AutoEnable": "ALL",
     "AdditionalConfiguration": [{"Name": "EKS_ADDON_MANAGEMENT", "AutoEnable": "NONE"}]},
]


class LoadRegionsTest(unittest.TestCase):
    def write(self, text):
        d = tempfile.mkdtemp()
        (Path(d) / "_parameters.yaml").write_text("resourcePrefix: x\n")
        path = Path(d) / "_tasks.yaml"
        path.write_text(text)
        return path

    def test_organizations_infra_tasks_file(self):
        regions = g.load_regions(FIXTURE_TASKS_FILE)
        self.assertEqual(regions[0], "us-east-1")
        self.assertEqual(len(regions), len(set(regions)))
        self.assertGreater(len(regions), 1)

    def test_org_formation_tags(self):
        path = self.write(
            "Parameters:\n"
            "  <<: !Include '../_parameters.yaml'\n"
            "  accountId:\n"
            "    Default: !Ref SecurityCentralAccount\n"
            "  guardDutyRegions:\n"
            "    Type: List<String>\n"
            "    Default: [us-east-1, eu-west-1]\n"
            "Stack:\n"
            "  StackName: !Sub '${resourcePrefix}-x'\n"
        )
        self.assertEqual(g.load_regions(path), ["us-east-1", "eu-west-1"])

    def test_missing_key(self):
        path = self.write("Parameters:\n  other: !Ref x\n")
        with self.assertRaisesRegex(g.GuardDutyOrgError, "guardDutyRegions.Default not found"):
            g.load_regions(path)

    def test_empty_list(self):
        path = self.write("Parameters:\n  guardDutyRegions:\n    Default: []\n")
        with self.assertRaisesRegex(g.GuardDutyOrgError, "non-empty list"):
            g.load_regions(path)

    def test_select_regions(self):
        regions = ["us-east-1", "us-west-2", "eu-west-1"]
        self.assertEqual(g.select_regions(regions, None), regions)
        self.assertEqual(g.select_regions(regions, ["eu-west-1", "us-east-1"]), ["us-east-1", "eu-west-1"])
        with self.assertRaisesRegex(g.GuardDutyOrgError, "ap-east-1"):
            g.select_regions(regions, ["ap-east-1"])


class HelpersTest(unittest.TestCase):
    def test_batches(self):
        self.assertEqual([len(b) for b in g.batches(list(range(120)))], [50, 50, 20])
        self.assertEqual(g.batches([]), [])

    def test_source_features_skips_non_updatable_and_keeps_none(self):
        self.assertEqual(g.source_features(SOURCE_CONFIG), SOURCE_FEATURES)

    def test_source_features_strips_extra_keys(self):
        config = {"Features": [{"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL", "Extra": 1,
                                "AdditionalConfiguration": []}]}
        self.assertEqual(g.source_features(config), [{"Name": "S3_DATA_EVENTS", "AutoEnable": "ALL"}])

    def test_features_for_region(self):
        kept, skipped = g.features_for_region(SOURCE_FEATURES, REGION_CONFIG)
        self.assertEqual(kept, REGION_FEATURES)
        self.assertEqual(skipped, ["AI_PROTECTION"])

    def test_features_for_region_drops_emptied_additional_configuration(self):
        config = {"Features": [{"Name": "RUNTIME_MONITORING", "AutoEnable": "NONE"}]}
        kept, _ = g.features_for_region(SOURCE_FEATURES, config)
        self.assertEqual(kept, [{"Name": "RUNTIME_MONITORING", "AutoEnable": "ALL"}])


def member(i, status="Enabled"):
    return {"AccountId": f"{i:012d}", "MasterId": SECURITY, "Email": "unused@example.org", "RelationshipStatus": status,
            "UpdatedAt": "2026-01-01"}


def org_account(i):
    return {"Id": f"{i:012d}", "Email": f"aws{i}@example.org"}


class ConfigureMembersTest(unittest.TestCase):
    """us-east-1 has 52 Enabled members (plus one Removed); us-west-1 already has 1 of them."""

    def setUp(self):
        self.session = FakeSession()
        self.east = self.session.stub("guardduty", "us-east-1")
        self.west = self.session.stub("guardduty", "us-west-1")
        orgs = self.session.stub("organizations")

        source_members = [member(i) for i in range(52)] + [member(99, "Removed")]
        self.east.add_response("list_detectors", {"DetectorIds": ["east"]})
        self.east.add_response("describe_organization_configuration", SOURCE_CONFIG, {"DetectorId": "east"})
        self.east.add_response("list_members", {"Members": source_members},
                               {"DetectorId": "east", "OnlyAssociated": "true"})
        orgs.add_response("list_accounts", {"Accounts": [org_account(i) for i in list(range(52)) + [99]]})

        # Loop: us-east-1 (source) gets no CreateMembers.
        self.east.add_response("list_detectors", {"DetectorIds": ["east"]})
        self.east.add_response("describe_organization_configuration", SOURCE_CONFIG, {"DetectorId": "east"})

        self.west.add_response("list_detectors", {"DetectorIds": ["west"]})
        self.west.add_response("describe_organization_configuration", REGION_CONFIG, {"DetectorId": "west"})
        self.west.add_response("list_members", {"Members": [member(0)]},
                               {"DetectorId": "west", "OnlyAssociated": "true"})

    def test_enrolls_missing_members_in_batches_and_sets_features(self):
        self.east.add_response("update_organization_configuration", {},
                               {"DetectorId": "east", "AutoEnableOrganizationMembers": "NEW",
                                "Features": SOURCE_FEATURES})
        to_enroll = [{"AccountId": f"{i:012d}", "Email": f"aws{i}@example.org"} for i in range(1, 52)]
        self.west.add_response("create_members", {"UnprocessedAccounts": []},
                               {"DetectorId": "west", "AccountDetails": to_enroll[:50]})
        self.west.add_response("create_members",
                               {"UnprocessedAccounts": [{"AccountId": to_enroll[50]["AccountId"], "Result": "nope"}]},
                               {"DetectorId": "west", "AccountDetails": to_enroll[50:]})
        self.west.add_response("update_organization_configuration", {},
                               {"DetectorId": "west", "AutoEnableOrganizationMembers": "NEW",
                                "Features": REGION_FEATURES})

        lines, ctx = quiet()
        g.configure_members(self.session, ["us-east-1", "us-west-1"], ctx)

        self.session.assert_done()
        self.assertEqual(ctx.warnings, 1)  # the unprocessed account is reported
        self.assertIn("Found 52 Enabled members in us-east-1.", lines)
        self.assertIn("  1 already Enabled members, 51 to enroll.", lines)
        self.assertIn("  Not available in us-west-1, skipping: AI_PROTECTION", lines)

    def test_dry_run_makes_no_writes(self):
        lines = []
        ctx = g.Context(dry_run=True, out=lines.append)
        g.configure_members(self.session, ["us-east-1", "us-west-1"], ctx)  # Stubber fails on any write
        self.session.assert_done()
        dry = [line for line in lines if "DRY_RUN" in line]
        self.assertEqual(len(dry), 4)  # 2 x update_organization_configuration, 2 x create_members
        self.assertIn("AccountDetails=[50 accounts]", dry[1])

    def test_member_missing_from_organization(self):
        session = FakeSession()
        east = session.stub("guardduty", "us-east-1")
        session.stub("organizations").add_response("list_accounts", {"Accounts": []})
        east.add_response("list_detectors", {"DetectorIds": ["east"]})
        east.add_response("describe_organization_configuration", SOURCE_CONFIG, {"DetectorId": "east"})
        east.add_response("list_members", {"Members": [member(1)]}, {"DetectorId": "east", "OnlyAssociated": "true"})
        with self.assertRaisesRegex(g.GuardDutyOrgError, "not found in the organization"):
            g.configure_members(session, ["us-east-1"], quiet()[1])


class EnableAdminTest(unittest.TestCase):
    def test_enables_only_where_missing(self):
        session = FakeSession()
        east = session.stub("guardduty", "us-east-1")
        west = session.stub("guardduty", "us-west-2")
        east.add_response("list_organization_admin_accounts",
                          {"AdminAccounts": [{"AdminAccountId": SECURITY, "AdminStatus": "ENABLED"}]})
        west.add_response("list_organization_admin_accounts", {"AdminAccounts": []})
        west.add_response("enable_organization_admin_account", {}, {"AdminAccountId": SECURITY})

        lines, ctx = quiet()
        g.enable_admin(session, ["us-east-1", "us-west-2"], ctx)
        session.assert_done()
        self.assertIn("  Already enabled, skipping.", lines)


class RemoveRegionTest(unittest.TestCase):
    def test_removes_members_then_admin(self):
        security, management = FakeSession(), FakeSession()
        gd = security.stub("guardduty", "eu-west-1")
        mgmt = management.stub("guardduty", "eu-west-1")
        ids = [f"{i:012d}" for i in range(51)]

        gd.add_response("list_detectors", {"DetectorIds": ["d"]})
        gd.add_response("update_organization_configuration", {},
                        {"DetectorId": "d", "AutoEnableOrganizationMembers": "NONE"})
        gd.add_response("list_members", {"Members": [member(i, "Removed" if i % 2 else "Enabled") for i in range(51)]},
                        {"DetectorId": "d", "OnlyAssociated": "false"})
        for batch in (ids[:50], ids[50:]):
            for op in ("stop_monitoring_members", "disassociate_members", "delete_members"):
                gd.add_response(op, {"UnprocessedAccounts": []}, {"DetectorId": "d", "AccountIds": batch})
        mgmt.add_response("list_organization_admin_accounts",
                          {"AdminAccounts": [{"AdminAccountId": SECURITY, "AdminStatus": "ENABLED"}]})
        mgmt.add_response("disable_organization_admin_account", {}, {"AdminAccountId": SECURITY})

        lines, ctx = quiet()
        g.remove_region(security, management, "eu-west-1", ctx)
        security.assert_done()
        management.assert_done()
        self.assertEqual(ctx.warnings, 0)


class CliTest(unittest.TestCase):
    def test_check_account_mismatch(self):
        with self.assertRaisesRegex(g.GuardDutyOrgError, "expected 140124849929"):
            g.check_account(FakeSession("111111111111"), SECURITY, g.SECURITY_PROFILE_HINT)

    def test_confirm(self):
        g._confirm("eu-west-1", assume_yes=False, read=lambda _: "eu-west-1\n")
        g._confirm("eu-west-1", assume_yes=True, read=lambda _: self.fail("should not prompt"))
        with self.assertRaisesRegex(g.GuardDutyOrgError, "nothing was changed"):
            g._confirm("eu-west-1", assume_yes=False, read=lambda _: "y")

    def test_two_account_commands_require_both_profiles(self):
        with self.assertRaises(SystemExit):
            g.build_parser().parse_args(["remove-region", "eu-west-1", "--tasks-file", "t.yaml",
                                         "--security-profile", "x"])

    def test_tasks_file_required(self):
        with self.assertRaises(SystemExit):
            g.build_parser().parse_args(["configure-members", "--dry-run"])

    def test_parse(self):
        args = g.build_parser().parse_args(["configure-members", "--tasks-file", "t.yaml", "--dry-run",
                                            "--region", "us-east-1"])
        self.assertEqual((args.command, args.dry_run, args.regions, args.tasks_file),
                         ("configure-members", True, ["us-east-1"], Path("t.yaml")))


if __name__ == "__main__":
    unittest.main()
