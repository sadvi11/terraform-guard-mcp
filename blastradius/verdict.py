"""Decide how dangerous a proposed change is.

This is Person 2's file. It is deliberately a plain function with no
network, no state and no cleverness: the whole point of the project is
that the decision does not live in the model's judgement.

Three outcomes:

    BLOCK   destroys data, removes the audit trail, or opens the box to
            the internet. A human must tap NO or YES.
    REVIEW  destroys something that comes back. A human should look.
    SAFE    creates and updates only. No need to wake anybody.
"""

# Actions that make a resource go away, even briefly. Terraform writes a
# replacement as delete + create, which reads as routine and is not.
DESTRUCTIVE = {"delete", "destroy", "replace"}

# Resources that hold something you cannot get back by re-running apply.
STATEFUL = (
    "db_instance",
    "rds_cluster",
    "s3_bucket",
    "dynamodb_table",
    "efs_file_system",
    "elasticache",
)

# Losing these means losing the record of what happened.
AUDIT = ("cloudtrail", "config_recorder", "flow_log", "log_group")


def _kind(name: str) -> str:
    return name.split(".", 1)[0].lower()


def is_fatal(resource: dict) -> bool:
    """True if this one resource is reason enough to stop and ask."""
    action = str(resource.get("action", "")).lower()
    kind = _kind(str(resource.get("name", "")))

    if action in DESTRUCTIVE:
        if any(word in kind for word in STATEFUL):
            return True
        if any(word in kind for word in AUDIT):
            return True

    # An update is enough here: opening SSH to the world needs no destroy.
    if resource.get("opens_to_world"):
        return True

    return False


def assess(resources: list[dict]) -> str:
    """BLOCK, REVIEW or SAFE for a whole proposed change."""
    if any(is_fatal(r) for r in resources):
        return "BLOCK"
    if any(str(r.get("action", "")).lower() in DESTRUCTIVE for r in resources):
        return "REVIEW"
    return "SAFE"


def annotate(resources: list[dict]) -> list[dict]:
    """Copy of the resources with `fatal` filled in, for the tablet to colour."""
    return [{**r, "fatal": is_fatal(r)} for r in resources]
