# Blast Radius

**The "are you sure?" text message, for AI.**

You know when your bank texts you *"Did you just spend $500? YES / NO"* and
the payment does not go through until you tap one?

AI coding agents can now change real servers and real databases. Nobody is
checking them. This is the text message.

The agent asks to do something dangerous. **The tablet lights up.** A human
taps YES or NO. The agent cannot move until someone taps.

---

## Run it in 30 seconds

Two terminals, no `pip install`, no cloud account, no API key.

```bash
python3 relay/server.py      # terminal 1 - the server in the middle
python3 demo/run_demo.py     # terminal 2 - the agent
```

Then open the tablet at **`http://<laptop-ip>:8000`** — the relay serves the
page itself, so there is nothing else to start.

The agent will freeze. Tap NO on the tablet. The agent prints `BLOCKED`.

Check the whole loop still works after you change something:

```bash
python3 test_e2e.py
```

---

## The one thing to agree on first

Everything talks in this shape. Agree on it before anyone writes real code,
then all three people can build separately without waiting for each other.

```json
{
  "id": "req_1",
  "tool": "terraform_apply",
  "summary": "Clean up the unused staging database",
  "verdict": "BLOCK",
  "resources": [
    { "name": "aws_db_instance.prod-db", "action": "replace", "fatal": true },
    { "name": "aws_security_group.web",  "action": "update",  "fatal": false }
  ],
  "status": "pending"
}
```

Three endpoints, and that is the entire system:

| Endpoint | Who calls it |
| --- | --- |
| `POST /requests` | the agent asks, then hangs until an answer comes back |
| `GET /requests/pending` | the tablet asks what is waiting |
| `POST /requests/<id>/decision` | the tablet sends `approve` or `block` |

---

## Who owns what

| File | Owner | Job |
| --- | --- | --- |
| `interceptor/guard.py` | **Person 1** | make the agent stop and wait. Hardest — start here. |
| `relay/server.py` | **Person 2** | pass messages between laptop and tablet |
| `verdict.py` | **Person 2** | decide BLOCK / REVIEW / SAFE. A plain function, no AI. |
| `tablet/index.html` | **Person 3** | the screen judges will stare at |
| `demo/run_demo.py` | **Person 4** | the story, the script, the practice runs |

Person 2 finishes first. When you do, **do not start a fourth feature** —
go help whoever is behind and be the one who connects the pieces.

---

## Wiring it into a real agent

One line at the top of whatever tool the agent calls:

```python
from guard import require_approval

if not require_approval("terraform_apply", summary, resources):
    return "BLOCKED by human review"
```

`require_approval` returns `True` only if a human tapped YES. If the relay is
down it raises instead of returning `True` — an approval system that waves
things through when it breaks is not an approval system.

`SAFE` changes are not worth waking anybody for, so they pass straight
through. Only `REVIEW` and `BLOCK` reach the tablet.

---

## Three rules

1. **Make the whole thing work early, even if it is fake.** It already does —
   keep it that way. If connecting is left for the end, it will not happen.
2. **One laptop for the demo.** One person sets it up. Nobody else installs
   anything on it.
3. **Stop coding one hour before.** Practice three times. Something always
   breaks on the third run — better then than in front of judges.

---

## The demo, 90 seconds

Hand a judge the tablet. Tell the agent *"clean up the unused staging
database."* It gets it wrong and proposes replacing the **real** one. The
tablet turns red. The judge taps NO. The agent stops.

Then the line:

> Every other demo today asked you to trust their AI. This one doesn't ask.

---

## If you have time left

In this order, most valuable first:

- **Swipe instead of tap.** Buttons are reliable; swipe looks better. Add it
  last, keep the buttons underneath.
- **A countdown.** "Applying in 30s unless you say no" is a different and
  scarier product, and it demos well.
- **Show what else dies.** `prod-db` is not the whole story — the things that
  depended on it break too. Draw those.
- **Second device.** Two people must both tap YES. Very hard to argue with.

Do not add: login, history, a database, real AWS. Judges never ask.
