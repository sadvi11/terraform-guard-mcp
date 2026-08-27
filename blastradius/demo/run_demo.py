"""The demo. This is what runs on the laptop while a judge holds the tablet.

    python3 demo/run_demo.py

The agent has been asked to clean up an unused staging database. What it
actually proposes replaces the production one - and Terraform writes a
replacement as delete + create, which reads as routine and is not.

Nothing here talks to a cloud account. That is deliberate: a demo that
depends on the venue wifi and someone's AWS credentials is a demo that
fails on stage.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "interceptor"))

from guard import require_approval  # noqa: E402


def say(who: str, line: str, pause: float = 0.7):
    print(f"  [{who}] {line}")
    time.sleep(pause)


def main():
    with open(os.path.join(HERE, "prod_db.json")) as handle:
        plan = json.load(handle)

    print()
    say("you", 'Agent, clean up the unused staging database.')
    say("agent", "Reading the Terraform plan...")
    say("agent", f"I will run {plan['tool']}: {plan['summary']}")
    print()

    approved = require_approval(plan["tool"], plan["summary"], plan["resources"])

    print()
    if approved:
        say("agent", "Approved by a human. Applying.", 0.3)
        print("\n  APPLIED\n")
    else:
        say("agent", "A human said no. Stopping.", 0.3)
        print("\n  BLOCKED - aws_db_instance.prod-db still exists\n")

    return 0 if not approved else 0


if __name__ == "__main__":
    sys.exit(main())
