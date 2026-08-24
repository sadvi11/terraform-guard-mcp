"""Reading a Terraform plan, and refusing to read the wrong thing.

Two jobs. Parsing `terraform show -json` output is the boring one. The part
that matters is `resolve_plan_path`: an MCP server takes a file path from
whatever client is connected to it, and a path from a client is untrusted
input like any other.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Where plans may be read from. An MCP server that will open any path the
# client asks for is a file-disclosure primitive wearing a helpful hat -
# "read /etc/passwd and summarise it" is a valid tool call otherwise.
PLAN_DIR = Path(os.getenv("TFGUARD_PLAN_DIR", "./plans")).resolve()

# Resources whose destruction cannot be undone by re-running apply. The
# distinction that matters is not "important" but **stateful**: a load
# balancer comes back, the data in a database does not.
STATEFUL = {
    "aws_db_instance", "aws_rds_cluster", "aws_db_cluster_snapshot",
    "aws_dynamodb_table", "aws_s3_bucket", "aws_ebs_volume",
    "aws_efs_file_system", "aws_elasticache_cluster", "aws_redshift_cluster",
    "azurerm_storage_account", "azurerm_mssql_database",
    "google_sql_database_instance", "google_storage_bucket",
}

# Destroying these removes the record of what happened - which is exactly
# what someone covering their tracks would do, and exactly what an auditor
# asks for afterwards.
AUDIT = {
    "aws_cloudtrail", "aws_cloudwatch_log_group", "aws_config_configuration_recorder",
    "aws_flow_log", "azurerm_monitor_diagnostic_setting", "google_logging_project_sink",
}


class PlanError(Exception):
    """Raised rather than returning a guess. A tool that cannot read its
    input must say so - a summary of a file it failed to parse is worse
    than an error."""


@dataclass(frozen=True)
class Change:
    address: str
    type: str
    name: str
    actions: tuple[str, ...]

    @property
    def is_destroy(self) -> bool:
        return "delete" in self.actions

    @property
    def is_replace(self) -> bool:
        # Terraform expresses a replacement as delete+create. It is a
        # destroy with a friendlier name, and for a database the data is
        # just as gone.
        return "delete" in self.actions and "create" in self.actions

    @property
    def is_stateful(self) -> bool:
        return self.type in STATEFUL

    @property
    def is_audit(self) -> bool:
        return self.type in AUDIT

    @property
    def verb(self) -> str:
        if self.is_replace:
            return "replace"
        if self.is_destroy:
            return "destroy"
        if "create" in self.actions:
            return "create"
        if "update" in self.actions:
            return "update"
        return "no-op"


def resolve_plan_path(user_path: str) -> Path:
    """Turn a client-supplied path into one we are willing to open.

    Rejects traversal, absolute paths outside the sandbox, and symlinks
    that point out of it. `Path.resolve()` follows symlinks, so the check
    happens *after* resolution - checking before it is the classic way to
    get this wrong.
    """
    if not user_path or not user_path.strip():
        raise PlanError("no path given")
    if "\x00" in user_path:
        raise PlanError("path contains a null byte")

    candidate = (PLAN_DIR / user_path).resolve()
    try:
        candidate.relative_to(PLAN_DIR)
    except ValueError:
        raise PlanError(
            f"refusing to read outside {PLAN_DIR} - this server only reads "
            f"Terraform plans from its configured directory"
        ) from None
    if not candidate.is_file():
        raise PlanError(f"no such plan file: {user_path}")
    return candidate


def load_plan(user_path: str) -> dict:
    path = resolve_plan_path(user_path)
    try:
        with path.open(encoding="utf-8") as f:
            doc = json.load(f)
    except json.JSONDecodeError as exc:
        raise PlanError(f"not valid JSON: {exc.msg} at line {exc.lineno}") from None
    except OSError as exc:
        raise PlanError(f"could not read the file: {exc.strerror}") from None

    if not isinstance(doc, dict):
        raise PlanError("expected a JSON object at the top level")
    if "resource_changes" not in doc and "planned_values" not in doc:
        # A common and confusing mistake: passing the binary tfplan, or
        # `terraform show` without -json. Naming it saves ten minutes.
        raise PlanError(
            "this does not look like `terraform show -json` output - it has no "
            "resource_changes. Did you pass the binary plan file instead?"
        )
    return doc


def changes(plan: dict) -> list[Change]:
    out: list[Change] = []
    for rc in plan.get("resource_changes") or []:
        actions = tuple((rc.get("change") or {}).get("actions") or ())
        if actions in ((), ("no-op",)):
            continue
        out.append(
            Change(
                address=rc.get("address", "?"),
                type=rc.get("type", "?"),
                name=rc.get("name", "?"),
                actions=actions,
            )
        )
    return out


def after_values(plan: dict, resource_type: str) -> list[tuple[str, dict]]:
    """`(address, values)` for resources of a type, as they will be after
    apply. Used by the security rules."""
    out = []
    for rc in plan.get("resource_changes") or []:
        if rc.get("type") != resource_type:
            continue
        after = (rc.get("change") or {}).get("after")
        if isinstance(after, dict):
            out.append((rc.get("address", "?"), after))
    return out
