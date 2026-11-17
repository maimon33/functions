#!/usr/bin/env python3
"""Copy entire Google Workspace mailboxes into an archive mailbox under a label.

Every message from each --source mailbox is inserted, unchanged, into the
--dest mailbox and labelled "<prefix>/<source address>". The source user's
Inbox, Sent, Drafts and own labels become sub-labels of that label.
With --query, only the messages that match a Gmail search are copied.

Nothing is ever deleted or modified in the source mailbox: the OAuth scopes
requested below do not permit it.
"""

import argparse
import base64
import io
import os
import signal
import sqlite3
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from google.auth.exceptions import RefreshError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # read source, count destination
    "https://www.googleapis.com/auth/gmail.insert",  # add messages to destination
    "https://www.googleapis.com/auth/gmail.labels",  # create labels in destination
]

# Source system labels that are kept, as sub-labels of the archive label.
# Spam and Trash are not copied at all.
SYSTEM_LABELS = {"INBOX": "Inbox", "SENT": "Sent", "DRAFT": "Drafts"}

RETRIES = 8  # exponential backoff on rate limits and server errors
LIST_PROGRESS_EVERY = 100_000  # while listing a mailbox, say how far it is this often
LARGE_MAILBOX = 500_000  # messages; from here on, warn how long the copy will take
TYPICAL_RATE = 5  # messages/s that a copy usually reaches; Gmail's ceiling is about 10

# Exit codes that setup.sh turns into step-by-step guidance.
EXIT_NOT_AUTHORISED = 3  # domain-wide delegation is missing or has the wrong scopes
EXIT_BAD_MAILBOX = 4  # a mailbox address is not a user, or the user has no Gmail


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


class Clients:
    """One Gmail API client per (thread, user); the underlying HTTP client is not thread-safe."""

    def __init__(self, key_file):
        self.key_file = key_file
        self.local = threading.local()

    def svc(self, user):
        cache = self.local.__dict__.setdefault("cache", {})
        if user not in cache:
            creds = service_account.Credentials.from_service_account_file(
                self.key_file, scopes=SCOPES, subject=user
            )
            cache[user] = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return cache[user]


class WorkerShare:
    """How many messages this process may copy at once.

    Gmail limits writes per archive mailbox, not per process, so containers that copy
    different mailboxes into the same archive have to share one worker budget.
    setup.sh divides that budget among the mailboxes being copied and keeps the result
    in a small file, one "mailbox workers" line each. Each container re-reads the file
    and takes its own line, so the total stays at the budget as containers start and
    finish. Without a file, this process uses the whole budget.
    """

    RECHECK_SECONDS = 10

    def __init__(self, budget, share_file=None):
        self.budget = budget
        self.share_file = share_file
        self.current = None
        self.checked = None

    def limit(self, mailbox):
        now = time.monotonic()
        if self.current is None or (self.share_file and now - self.checked >= self.RECHECK_SECONDS):
            self.checked = now
            share, active = self.read(mailbox)
            if share != self.current:
                if active > 1:
                    log(f"   using {share} of {self.budget} workers ({active} mailboxes are being copied)")
                else:
                    log(f"   using {share} parallel workers")
                self.current = share
        return self.current

    def read(self, mailbox):
        """Return (workers for this mailbox, number of mailboxes being copied)."""
        if not self.share_file:
            return self.budget, 1
        try:
            with open(self.share_file) as handle:
                lines = [line.split() for line in handle if line.strip()]
        except OSError:
            lines = []
        for fields in lines:
            if len(fields) == 2 and fields[0] == mailbox.lower() and fields[1].isdigit():
                return max(1, int(fields[1])), len(lines)
        if len(lines) == 1 and len(lines[0]) == 1 and lines[0][0].isdigit():
            # Only a number: how many mailboxes are being copied, as written by a batch
            # that an older setup.sh started. Take an equal share.
            active = max(1, int(lines[0][0]))
            return max(1, self.budget // active), active
        # Not listed (yet). Keep the last share; a mailbox that never had one takes a
        # single worker, so the budget cannot be exceeded.
        return self.current or 1, len(lines) + 1


STATE_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS copied ("
    "source TEXT, dest TEXT, src_id TEXT, dest_id TEXT, "
    "PRIMARY KEY (source, dest, src_id))"
)


def open_state(state_dir, source, read_only=False):
    """Open the progress file of one source mailbox.

    Each mailbox has its own file (<state_dir>/state/<address>.db) so that containers
    running in parallel never write to the same SQLite file. Older versions kept one
    shared <state_dir>/state.db; the first time a mailbox is copied by this version
    its rows are carried over, so nothing already archived is copied twice. The old
    file is only ever read.

    A dry run (read_only) creates nothing: it reads whichever file exists.
    """
    path = os.path.join(state_dir, "state", f"{source.lower()}.db")
    legacy = os.path.join(state_dir, "state.db")
    if not os.path.exists(path):
        if read_only:
            if os.path.exists(legacy):
                return sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
            db = sqlite3.connect(":memory:")
            db.execute(STATE_SCHEMA)
            return db
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Build the file under a temporary name: a half-filled progress file would
        # look like "these messages were never copied" and cause duplicates.
        building = f"{path}.building"
        if os.path.exists(building):
            os.remove(building)
        db = sqlite3.connect(building)
        db.execute(STATE_SCHEMA)
        if os.path.exists(legacy):
            db.execute("ATTACH DATABASE ? AS old", (legacy,))
            carried = db.execute(
                "INSERT OR REPLACE INTO copied SELECT source, dest, src_id, dest_id "
                "FROM old.copied WHERE lower(source) = ?",
                (source.lower(),),
            ).rowcount
            db.commit()
            db.execute("DETACH DATABASE old")
            if carried:
                log(f"   carried over {carried:,} progress records for {source} from state.db")
        db.commit()
        db.close()
        os.replace(building, path)
    return sqlite3.connect(path)


def copied_ids(db, source, dest):
    """Source message ids already in the archive. Addresses are compared without case."""
    rows = db.execute(
        "SELECT src_id FROM copied WHERE lower(source) = ? AND lower(dest) = ?",
        (source.lower(), dest.lower()),
    )
    return {row[0] for row in rows}


def check_mailboxes(clients, addresses):
    """Return {address: problem} for every mailbox that cannot be used.

    Runs before anything is copied, so a typo in the last mailbox of a long list is
    reported in seconds instead of hours. A missing delegation is not a mailbox
    problem: that RefreshError is left for the caller.
    """
    problems = {}
    for address in addresses:
        try:
            clients.svc(address).users().getProfile(userId="me").execute(num_retries=RETRIES)
        except RefreshError as exc:
            if "Invalid email or User ID" not in str(exc):
                raise
            problems[address] = "no such user (misspelt, suspended or deleted; a group is not a mailbox)"
        except HttpError as exc:
            if "Mail service not enabled" not in str(exc):
                raise
            problems[address] = "no Gmail mailbox (no Google Workspace licence, or Gmail is off for this user)"
    return problems


def list_ids(svc, label_id=None, query=None, what=None):
    """Ids of the messages in a mailbox (never Spam or Trash).

    `label_id` and `query` (a Gmail search) narrow the list. `what` names the list in a
    progress line, printed every LIST_PROGRESS_EVERY messages, so that a very large
    mailbox does not look stuck.
    """
    params = {"userId": "me", "maxResults": 500}
    if label_id:
        params["labelIds"] = [label_id]
    if query:
        params["q"] = query
    ids = []
    reported = 0
    while True:
        resp = svc.users().messages().list(**params).execute(num_retries=RETRIES)
        ids.extend(m["id"] for m in resp.get("messages", []))
        if what and len(ids) - reported >= LIST_PROGRESS_EVERY:
            reported = len(ids)
            log(f"   listing {what}: {len(ids):,} so far")
        if "nextPageToken" not in resp:
            return ids
        params["pageToken"] = resp["nextPageToken"]


def list_labels(svc):
    return svc.users().labels().list(userId="me").execute(num_retries=RETRIES).get("labels", [])


def ensure_labels(svc, names):
    """Create any missing labels (and their parents) and return {name: id}."""
    existing = {label["name"].lower(): label["id"] for label in list_labels(svc)}
    for name in names:
        parts = name.split("/")
        for depth in range(1, len(parts) + 1):
            path = "/".join(parts[:depth])
            if path.lower() not in existing:
                body = {
                    "name": path,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                }
                try:
                    created = svc.users().labels().create(userId="me", body=body).execute(num_retries=RETRIES)
                    existing[path.lower()] = created["id"]
                except HttpError:
                    # Another container may have created the same parent label a moment
                    # ago. Look again before treating this as a real refusal.
                    existing.update({label["name"].lower(): label["id"] for label in list_labels(svc)})
                    if path.lower() not in existing:
                        log(f"   Gmail refused to create the label {path!r}")
                        raise
    return {name: existing[name.lower()] for name in names}


def copy_one(clients, source, dest, msg_id, label_map, root_id):
    """Copy one message. Returns (destination id, bytes, download seconds, upload seconds)."""
    t_start = time.monotonic()
    msg = (
        clients.svc(source)
        .users()
        .messages()
        .get(userId="me", id=msg_id, format="raw")
        .execute(num_retries=RETRIES)
    )
    t_downloaded = time.monotonic()
    encoded = msg["raw"]
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    label_ids = [root_id] + [label_map[i] for i in msg.get("labelIds", []) if i in label_map]
    media = MediaIoBaseUpload(io.BytesIO(raw), mimetype="message/rfc822", resumable=True)
    inserted = (
        clients.svc(dest)
        .users()
        .messages()
        .insert(
            userId="me",
            body={"labelIds": label_ids},
            internalDateSource="dateHeader",  # keep the original date, not today's
            media_body=media,
        )
        .execute(num_retries=RETRIES)
    )
    t_uploaded = time.monotonic()
    return inserted["id"], len(raw), t_downloaded - t_start, t_uploaded - t_downloaded


def migrate(clients, db, source, dest, prefix, query, share, dry_run, totals):
    """Copy one mailbox. Returns True only if everything is verified in the destination.

    `query` is a Gmail search; if given, only the messages that match it are copied.
    `share` says how many messages may be copied at once; it can change during the run.
    `totals` is updated as messages are copied, so the end-of-run summary is right
    even when the run is interrupted part-way through a mailbox.
    """
    src, dst = clients.svc(source), clients.svc(dest)
    root = f"{prefix}/{source}"
    log(f"== {source} -> {dest}, label '{root}'")
    size = src.users().getProfile(userId="me").execute(num_retries=RETRIES)["messagesTotal"]
    if query:
        log(f"   filter: copying only the messages that match: {query}")
        log(f"   the mailbox holds {size:,} messages in all; what the filter leaves out is NOT archived")
    else:
        log(f"   the mailbox holds {size:,} messages")
        if size >= LARGE_MAILBOX:
            log(
                f"   WARNING: that is about {size / TYPICAL_RATE / 86400:,.1f} days of copying at "
                f"{TYPICAL_RATE} messages/s, after a long wait while they are listed."
            )
            log("   If most of it is automated mail, stop, and copy only what matters with --query.")

    label_names = {}  # source label id -> destination label name
    for label in list_labels(src):
        if label["id"] in SYSTEM_LABELS:
            label_names[label["id"]] = f"{root}/{SYSTEM_LABELS[label['id']]}"
        elif label.get("type") == "user":
            label_names[label["id"]] = f"{root}/{label['name']}"

    source_ids = list_ids(src, query=query, what="source messages")
    done = copied_ids(db, source, dest)
    todo = [i for i in source_ids if i not in done]
    found = "messages in source match the filter" if query else "messages in source"
    log(f"   {len(source_ids):,} {found}, {len(source_ids) - len(todo):,} already copied, {len(todo):,} to copy")

    if dry_run:
        have = {label["name"].lower() for label in list_labels(dst)}
        missing = sorted({n for n in [root, *label_names.values()] if n.lower() not in have})
        log(f"   dry run: would create {len(missing)} labels and copy {len(todo):,} messages")
        totals["to_copy"] += len(todo)
        return True

    label_ids = ensure_labels(dst, [root, *label_names.values()])
    root_id = label_ids[root]
    label_map = {src_id: label_ids[name] for src_id, name in label_names.items()}

    failures = []
    stats = {"copied": 0, "bytes": 0, "download_s": 0.0, "upload_s": 0.0}
    started = time.time()
    stats["window_start"] = started

    # Messages are handed to the pool only as fast as the current share allows, so the
    # number in flight follows the share when other containers start or finish.
    pool = ThreadPoolExecutor(max_workers=share.budget)
    waiting = iter(todo)
    in_flight = {}  # future -> source message id; an entry stays until it is recorded

    def record(future):
        msg_id = in_flight[future]
        try:
            dest_id, size, download_s, upload_s = future.result()
        except Exception as exc:  # one bad message must not stop the mailbox
            failures.append((msg_id, str(exc)))
            totals["failed"] += 1
        else:
            db.execute("INSERT OR REPLACE INTO copied VALUES (?, ?, ?, ?)", (source, dest, msg_id, dest_id))
            db.commit()
            stats["copied"] += 1
            stats["bytes"] += size
            totals["copied"] += 1
            totals["bytes"] += size
            stats["download_s"] += download_s
            stats["upload_s"] += upload_s
            if stats["copied"] % 200 == 0:
                now = time.time()
                rate = stats["copied"] / (now - started)
                recent = 200 / (now - stats["window_start"])
                # Per-message averages over the last 200. If upload time grows as workers
                # are added, Gmail is queueing writes to the archive mailbox.
                log(
                    f"   {stats['copied']:,}/{len(todo):,} copied, {stats['bytes'] / 1e6:,.0f} MB, "
                    f"{rate:.1f} msg/s overall, {recent:.1f} msg/s now "
                    f"(per message: download {stats['download_s'] / 200:.2f}s, upload {stats['upload_s'] / 200:.2f}s)"
                )
                stats["download_s"] = stats["upload_s"] = 0.0
                stats["window_start"] = now
        del in_flight[future]

    try:
        more = True
        while more or in_flight:
            while more and len(in_flight) < share.limit(source):
                msg_id = next(waiting, None)
                if msg_id is None:
                    more = False
                else:
                    in_flight[pool.submit(copy_one, clients, source, dest, msg_id, label_map, root_id)] = msg_id
            if not in_flight:
                break
            # The timeout makes the loop re-read the share even while nothing finishes.
            finished, _ = wait(list(in_flight), timeout=5, return_when=FIRST_COMPLETED)
            for future in finished:
                record(future)
    except KeyboardInterrupt:
        log("   interrupted: finishing in-flight messages, then stopping. Rerun to resume.")
        pool.shutdown(wait=True)
        for future in list(in_flight):  # all finished now; recording twice is harmless
            record(future)
        raise
    pool.shutdown()

    # Verify against the destination itself, not just our own bookkeeping.
    recorded = copied_ids(db, source, dest)
    not_copied = [i for i in source_ids if i not in recorded]
    in_archive = len(list_ids(dst, root_id, what="archive messages"))
    ok = not failures and not not_copied and in_archive == len(recorded)

    log(f"   copied this run:           {stats['copied']:,} ({stats['bytes'] / 1e6:,.0f} MB)")
    log(f"   failed this run:           {len(failures):,}")
    log(f"   source messages{' matching the filter' if query else ''}:           {len(source_ids):,}")
    log(f"   source messages not copied: {len(not_copied):,}")
    log(f"   recorded as copied (all runs): {len(recorded):,}")
    log(f"   messages under archive label:  {in_archive:,}")
    for msg_id, error in failures[:20]:
        log(f"   FAILED {msg_id}: {error}")
    if len(failures) > 20:
        log(f"   ... and {len(failures) - 20} more failures")
    if not ok:
        result = "INCOMPLETE, do not delete this account; rerun"
    elif query:
        result = "OK for the filter only: every message that matches it is in the archive; the rest of the mailbox was NOT copied"
    else:
        result = "OK, everything is in the archive"
    log(f"   RESULT for {source}: {result}")
    return ok


def log_summary(sources, outcomes, totals, started, dry_run, query):
    """One closing line for the whole run, printed however the run ended."""
    done = [s for s in sources if outcomes.get(s)]
    not_done = [s for s in sources if not outcomes.get(s)]  # incomplete, interrupted or never reached
    elapsed = int(time.time() - started)
    took = f"{elapsed // 3600}h {elapsed % 3600 // 60:02d}m {elapsed % 60:02d}s"
    if dry_run:
        line = (
            f"SUMMARY: dry run, {len(done)} of {len(sources)} mailboxes checked, "
            f"{totals['to_copy']:,} messages to copy, took {took}"
        )
        if not_done:
            line += f"; NOT checked: {', '.join(not_done)}"
    else:
        line = (
            f"SUMMARY: {len(done)} of {len(sources)} mailboxes verified in the archive; "
            f"this run copied {totals['copied']:,} messages ({totals['bytes'] / 1e9:,.2f} GB), "
            f"{totals['failed']:,} failed, took {took}"
        )
        if not_done:
            line += f"; NOT complete, do not delete: {', '.join(not_done)}"
    if query:
        line += "; a filter was used, so only the messages matching it are covered"
    log(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", required=True, help="mailbox to copy from (repeatable)")
    parser.add_argument("--dest", required=True, help="archive mailbox to copy into")
    # Not "Archive": Gmail rejects that as a top-level label name.
    parser.add_argument(
        "--label-prefix",
        default="Archived mailboxes",
        help="parent label in the archive (default: Archived mailboxes)",
    )
    parser.add_argument("--key", default="/secrets/sa.json", help="service account key file")
    parser.add_argument(
        "--state-dir",
        default="/data",
        help="directory for progress files, one per source mailbox; keep it between runs (default: /data)",
    )
    parser.add_argument(
        "--query",
        help="copy only the messages that match this Gmail search, for example "
        "'-label:alerts newer_than:2y' (default: every message except Spam and Trash)",
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel copies (default: 4)")
    parser.add_argument(
        "--share-file",
        help="file with one 'mailbox workers' line per mailbox being copied into this archive: "
        "this mailbox's part of --workers (written by setup.sh)",
    )
    parser.add_argument("--dry-run", action="store_true", help="count and check access; write nothing")
    args = parser.parse_args()

    prefix = args.label_prefix.strip("/")
    if not prefix:
        parser.error("--label-prefix must not be empty")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.dest.lower() in (source.lower() for source in args.source):
        parser.error("--dest must not also be a --source")

    def terminate(*_):  # make `docker stop` behave like Ctrl-C
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)

    query = (args.query or "").strip() or None
    clients = Clients(args.key)
    share = WorkerShare(args.workers, args.share_file)
    outcomes = {}  # source -> True once verified (or, in a dry run, checked)
    totals = {"copied": 0, "bytes": 0, "failed": 0, "to_copy": 0}
    started = time.time()
    try:
        problems = check_mailboxes(clients, [args.dest, *args.source])
        for address, problem in problems.items():
            log(f"CANNOT USE {address}: {problem}")
        if problems:
            log("Nothing was copied. Fix or remove the mailboxes above, then rerun.")
            sys.exit(EXIT_BAD_MAILBOX)
        for source in args.source:
            db = open_state(args.state_dir, source, read_only=args.dry_run)
            try:
                outcomes[source] = migrate(clients, db, source, args.dest, prefix, query, share, args.dry_run, totals)
            finally:
                db.close()
    except RefreshError as exc:
        log(f"Authorisation failed: {exc}")
        log("Check that the service account's client ID has domain-wide delegation for exactly these scopes:")
        for scope in SCOPES:
            log(f"  {scope}")
        sys.exit(EXIT_NOT_AUTHORISED)
    except KeyboardInterrupt:
        sys.exit(130)
    finally:
        log_summary(args.source, outcomes, totals, started, args.dry_run, query)
    sys.exit(0 if all(outcomes.values()) else 1)


if __name__ == "__main__":
    main()
