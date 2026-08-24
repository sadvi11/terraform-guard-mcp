"""The rules, and the verdict.

The whole point of this project lives in `assess`. A model reading a plan
can say it looks fine. **This function decides**, and no wording in the
plan, no argument from the client, and no opinion from the model changes
`if change.is_stateful and change.is_destroy`.

That is the same reasoning as a refund limit in a Python function rather
than in a system prompt: a prompt instruction is a request; a comparison is
not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tfguard.plan import Change, after_values, changes

# Ports where a rule admitting the whole internet is almost never intended.
SENSITIVE_PORTS = {22: "SSH", 3389: "RDP", 3306: "MySQL", 5432: "PostgreSQL",
                   6379: "Redis", 27017: "MongoDB", 9200: "Elasticsearch"}


class Verdict(str, Enum):
    SAFE = "SAFE"       # create and update only, nothing flagged
    REVIEW = "REVIEW"   # a human should look before applying
    BLOCK = "BLOCK"     # do not apply without an explicit, recorded override


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    address: str
    detail: str


@dataclass
class Assessment:
    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    reason: str = ""

    @property
    def blocked(self) -> bool:
        return self.verdict is Verdict.BLOCK


# ---------------------------------------------------------------------------
# Rules. Each returns findings; none of them decides the verdict.
# ---------------------------------------------------------------------------
def rule_stateful_destroy(cs: list[Change]) -> list[Finding]:
    """Destroying something that holds data.

    Terraform reports a replacement as delete+create, so a database being
    replaced reads as routine in a plan summary. The data is just as gone.
    """
    out = []
    for c in cs:
        if c.is_stateful and c.is_destroy:
            out.append(Finding(
                rule="stateful_destroy",
                severity=Severity.HIGH,
                address=c.address,
                detail=(
                    f"{c.verb} of {c.type} - this holds data, and apply will not "
                    f"bring it back. Confirm a snapshot exists first."
                ),
            ))
    return out


def rule_audit_destroy(cs: list[Change]) -> list[Finding]:
    """Destroying the record of what happened."""
    return [
        Finding(
            rule="audit_destroy",
            severity=Severity.HIGH,
            address=c.address,
            detail=(
                f"{c.verb} of {c.type} - this removes audit history. That is "
                f"the window an auditor asks about."
            ),
        )
        for c in cs if c.is_audit and c.is_destroy
    ]


def rule_open_ingress(plan: dict) -> list[Finding]:
    """0.0.0.0/0 on a port that should never see the open internet."""
    out = []
    for rtype in ("aws_security_group", "aws_vpc_security_group_ingress_rule"):
        for address, after in after_values(plan, rtype):
            rules = after.get("ingress") or ([after] if "cidr_ipv4" in after or "cidr_blocks" in after else [])
            for r in rules:
                if not isinstance(r, dict):
                    continue
                cidrs = r.get("cidr_blocks") or ([r["cidr_ipv4"]] if r.get("cidr_ipv4") else [])
                if "0.0.0.0/0" not in (cidrs or []):
                    continue
                frm, to = r.get("from_port"), r.get("to_port")
                hit = [n for p, n in SENSITIVE_PORTS.items()
                       if frm is not None and to is not None and frm <= p <= to]
                # -1 or a 0-65535 range means every port, which includes all
                # of the sensitive ones.
                if frm in (-1, 0) and to in (-1, 65535):
                    hit = ["all ports"]
                if hit:
                    out.append(Finding(
                        rule="open_ingress",
                        severity=Severity.HIGH,
                        address=address,
                        detail=f"0.0.0.0/0 reaches {', '.join(hit)}",
                    ))
    return out


def rule_unencrypted_storage(plan: dict) -> list[Finding]:
    out = []
    for address, after in after_values(plan, "aws_ebs_volume"):
        if after.get("encrypted") is not True:
            out.append(Finding("unencrypted_storage", Severity.MEDIUM, address,
                               "EBS volume is not encrypted"))
    for address, after in after_values(plan, "aws_db_instance"):
        if after.get("storage_encrypted") is not True:
            out.append(Finding("unencrypted_storage", Severity.MEDIUM, address,
                               "RDS storage is not encrypted"))
    return out


def rule_public_ip(plan: dict) -> list[Finding]:
    out = []
    for rtype, key in (("aws_subnet", "map_public_ip_on_launch"),
                       ("aws_instance", "associate_public_ip_address")):
        for address, after in after_values(plan, rtype):
            if after.get(key) is True:
                out.append(Finding("public_ip", Severity.MEDIUM, address,
                                   f"{key} is true - reachable from the internet"))
    return out


def rule_no_deletion_protection(plan: dict) -> list[Finding]:
    out = []
    for address, after in after_values(plan, "aws_db_instance"):
        if after.get("deletion_protection") is not True:
            out.append(Finding("no_deletion_protection", Severity.LOW, address,
                               "database has no deletion protection"))
    return out


ALL_RULES_CHANGES = (rule_stateful_destroy, rule_audit_destroy)
ALL_RULES_PLAN = (rule_open_ingress, rule_unencrypted_storage,
                  rule_public_ip, rule_no_deletion_protection)


# ---------------------------------------------------------------------------
# The verdict. This is the guard.
# ---------------------------------------------------------------------------
def assess(plan: dict) -> Assessment:
    """SAFE, REVIEW or BLOCK - decided here, in code.

    Nothing in the plan file is an argument to this function beyond the
    facts it states. A comment saying "approved by the CTO", a resource
    named `definitely_safe_to_delete`, or a model insisting it looked fine
    do not reach these comparisons.
    """
    cs = changes(plan)

    findings: list[Finding] = []
    for rule in ALL_RULES_CHANGES:
        findings += rule(cs)
    for rule in ALL_RULES_PLAN:
        findings += rule(plan)

    counts: dict[str, int] = {}
    for c in cs:
        counts[c.verb] = counts.get(c.verb, 0) + 1

    high = [f for f in findings if f.severity is Severity.HIGH]

    if high:
        return Assessment(
            Verdict.BLOCK, findings, counts,
            f"{len(high)} high-severity finding(s): "
            + "; ".join(sorted({f.rule for f in high})),
        )

    if findings or any(c.is_destroy for c in cs):
        why = []
        destroys = sum(1 for c in cs if c.is_destroy)
        if destroys:
            why.append(f"{destroys} resource(s) destroyed or replaced")
        if findings:
            why.append(f"{len(findings)} finding(s)")
        return Assessment(Verdict.REVIEW, findings, counts, "; ".join(why))

    if not cs:
        return Assessment(Verdict.SAFE, findings, counts, "no changes")

    return Assessment(Verdict.SAFE, findings, counts,
                      "creates and updates only, nothing flagged")
