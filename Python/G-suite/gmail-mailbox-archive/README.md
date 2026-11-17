# Gmail mailbox archive

Copies whole Google Workspace mailboxes into one archive mailbox, so the original accounts
can be deleted and their licences freed. Every message of each source mailbox is inserted,
unchanged, into the archive mailbox under a label named after the source address.

- The source mailbox is never changed or deleted from. The permissions the script asks for do not allow it.
- It is safe to stop and rerun at any point. Progress is recorded per message, and a rerun copies only what is missing.
- Each mailbox is verified against the archive at the end, and the script tells you in plain words whether the account is safe to delete.
- A mailbox that is mostly automated mail can be copied in part, with a Gmail search that says what to keep.

One command does everything, including the Google Cloud setup:

```
./setup.sh archive@example.com leaver1@example.com leaver2@example.com
```

## What you need

| What | Why | If it is missing |
|---|---|---|
| A Google Workspace **super admin** | One manual step (authorising the script) can only be done by a super admin | Ask one to do [the delegation step](#the-one-manual-step-domain-wide-delegation) for you; it takes two minutes |
| A Google account that may **create a Google Cloud project** | The script creates a small project holding a service account | Use an existing project instead: `PROJECT_ID=my-project ./setup.sh ...` |
| An **archive mailbox**: a real, licensed user with Gmail turned on | Messages are copied into it | See [the archive mailbox has no Gmail](#cannot-use--no-gmail-mailbox). A group or an alias will not work |
| Enough **storage** for the archive user | It ends up holding every copied mailbox | Check the storage of the archive user in the Admin console before a big run |
| **Docker** | The copy runs in a container, so no Python is needed on your machine | The script offers to install it; see [Docker](#docker-is-missing-or-not-running) |
| **Google Cloud CLI** (`gcloud`) | Creates the project, service account and key | The script offers to install it; see [gcloud](#gcloud-is-missing) |
| macOS or Linux with `bash` | Written for both; used and tested on macOS | Not tested on Windows. WSL should work |

## Quick start

1. Put this folder somewhere it can stay. It will hold the key and the record of what has been copied.
2. Run it with the archive mailbox first, then the mailboxes to copy:

   ```
   ./setup.sh archive@example.com leaver1@example.com leaver2@example.com
   ```

3. The script works through six steps and stops with instructions whenever something is missing:

   | Step | What it does |
   |---|---|
   | 1 | Checks for `gcloud` and Docker, offers to install them, signs you in to Google Cloud |
   | 2 | Creates a Google Cloud project (named after your domain) and turns on the Gmail API |
   | 3 | Creates a service account and saves its key to `secrets/sa.json` |
   | 4 | Builds the Docker image |
   | 5 | Dry run: checks every mailbox and counts the messages. Writes nothing |
   | 6 | Asks for confirmation, then starts the copy **in the background** |

4. The terminal comes straight back and can be closed. Keep an eye on the copy with:

   ```
   ./setup.sh status     # what is queued, copying and finished
   ./setup.sh logs       # follow the live log; Ctrl-C leaves the log, not the copy
   ```

5. When `status` shows `OK, verified in the archive` for a mailbox, that account can be deleted. Read [Before you delete an account](#before-you-delete-an-account) first.

Everything is safe to rerun. Steps that are already done are skipped.

### The one manual step: domain-wide delegation

The first dry run fails on purpose, because the new service account is not yet allowed to
read mailboxes. The script then opens the right Admin console page, puts the values on
your clipboard one after the other, and waits. If you need to do it by hand:

1. Sign in to [admin.google.com](https://admin.google.com) as a super admin.
2. Go to **Security > Access and data control > API controls > Manage Domain Wide Delegation**
   (direct link: <https://admin.google.com/ac/owl/domainwidedelegation>).
3. Click **Add new**.
4. **Client ID**: the number the script prints. It is also the `client_id` value in `secrets/sa.json`.
5. **OAuth scopes**, exactly these three, separated by commas:

   ```
   https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.insert,https://www.googleapis.com/auth/gmail.labels
   ```

6. Click **Authorize**, go back to the terminal and press Enter.

It usually takes effect within a few minutes. Google allows up to 24 hours.

## Commands

| Command | What it does |
|---|---|
| `./setup.sh [options] ARCHIVE SOURCE [SOURCE...]` | Sets up whatever is missing, then copies the mailboxes in the background |
| `./setup.sh status` | Shows each mailbox: queued, copying (with its latest progress line), or its result |
| `./setup.sh logs` | Follows the live log of everything that is copying. Ctrl-C leaves the log; the copy keeps running |
| `./setup.sh logs MAILBOX` | Follows one mailbox, or prints its saved log if it has finished |
| `./setup.sh stop` | Stops cleanly: each mailbox finishes the messages it is copying, then exits. Nothing is lost |
| `./setup.sh resume` | Continues what was stopped, and retries every mailbox that is not verified yet |
| `./setup.sh remove MAILBOX` | Takes one mailbox out of its batch. If it is copying, it stops cleanly; `resume` no longer retries it. What it has copied stays |

`status`, `logs`, `stop`, `resume` and `remove` act on every batch. Add `--archive ADDRESS`
after the command to act on the batch of one archive mailbox only, for example
`./setup.sh stop --archive archive@example.com`.

| Option | Default | Meaning |
|---|---|---|
| `--sources-file FILE` | | Read source mailboxes from a file, one per line. Blank lines and `#` comments are ignored. See `sources.example.txt` |
| `--query SEARCH` | | Copy only the messages that match a Gmail search, for the source mailboxes of this command. See [Copying only part of a mailbox](#copying-only-part-of-a-mailbox) |
| `--workers N` | 12 | Total number of messages copied into one archive at once, shared by the mailboxes being copied into it |
| `--parallel N` | 3 | Mailboxes copied into one archive at the same time, one container each |
| `--skip-dry-run` | | Skip step 5 and the confirmation. Only for reruns, after a dry run has passed |
| `PROJECT_ID=...` (environment) | derived from the domain | Use a specific Google Cloud project |

`resume` also takes `--workers` and `--parallel`, to change them for the rest of a batch.

### Batches

The mailboxes you copy into one archive mailbox form a batch. One background process
works through its queue, a few mailboxes at a time.

- **Adding mailboxes while a batch is running** adds them to that batch. Just run the normal command again with the new addresses. A mailbox that is already queued or copying is left as it is.
- **A stopped batch** is continued by `./setup.sh resume`, or by adding more mailboxes to it.
- **A finished batch** is left alone. The next run into that archive starts a new batch. Its logs stay under `logs/`.
- **A second archive mailbox** gets its own batch, with its own `--workers` and `--parallel`, and runs at the same time as the first. Gmail's limit applies to each archive mailbox separately.
- **A mailbox is in one batch at a time.** If it is queued or copying into one archive, a command that names it for another archive skips it and says so.

## Copying only part of a mailbox

Some mailboxes are almost entirely automated mail: alerts, notifications, copies of a
group's mail. They can hold millions of messages, which would take weeks to copy and is
rarely worth keeping. The script prints the size of each mailbox before it lists it, and
warns from 500,000 messages up:

```
   the mailbox holds 9,600,000 messages
   WARNING: that is about 22.2 days of copying at 5 messages/s, after a long wait while they are listed.
```

`--query` takes a Gmail search, the same syntax as the search box in Gmail, and copies
only the messages that match it:

```
./setup.sh --query '-label:alerts' archive@example.com leaver3@example.com
```

| Search | Copies |
|---|---|
| `-label:alerts` | Everything except the label `alerts` |
| `-label:alerts -label:build-notifications` | Everything except those two labels. A space in a label name is written as a hyphen |
| `-from:noreply@example.com` | Everything except mail from that sender |
| `newer_than:2y` | Only the last two years |
| `-category:updates -category:promotions` | Everything except Gmail's Updates and Promotions categories |

- **Find out what fills the mailbox first.** In Gmail, signed in as that user or as a delegate, the label list shows which labels are large. The dry run (step 5) then reports exactly how many messages the search matches, before anything is copied.
- **The search applies to the source mailboxes of that command.** To use a different search for another mailbox, run the command again for that mailbox. Both join the same batch.
- **What the search leaves out is not archived.** It is lost when the account is deleted. The result of such a mailbox reads `OK for the filter only`, never a plain `OK`, and `status` shows the search next to it.
- **Changing your mind is cheap.** Running the mailbox again with a wider search, or with none, copies only what is not in the archive yet.
- Nothing is deleted from the source mailbox, with or without a search.

## What ends up in the archive

Messages from `leaver1@example.com` appear in the archive mailbox under these labels:

```
Archived mailboxes/leaver1@example.com            every message
Archived mailboxes/leaver1@example.com/Inbox
Archived mailboxes/leaver1@example.com/Sent
Archived mailboxes/leaver1@example.com/Drafts
Archived mailboxes/leaver1@example.com/<each of their own labels>
```

- Original dates are kept.
- Spam and Trash are not copied.
- Copied messages do not land in the archive's own Inbox, and they arrive as read. Stars and the Important marker are not carried over.
- Nothing is sent to anyone, and no forwarding or filter of the archive mailbox is triggered.

## Reading the output

All times in the logs are UTC. Mailboxes are copied side by side, so every line of the
batch log starts with who wrote it: the mailbox, or `[batch]` for the background runner.

```
[batch] 09:20:01 ==> batch 20260301-092001: copying into archive@example.com, 12 workers shared by up to 3 mailboxes at a time
[leaver1@example.com] 09:20:02 started
[leaver2@example.com] 09:20:02 started
[leaver1@example.com] 09:22:36    600/1,500 copied, 30 MB, 4.8 msg/s overall, 4.9 msg/s now (per message: download 0.44s, upload 1.61s)
[leaver2@example.com] 09:22:41    400/9,200 copied, 22 MB, 2.5 msg/s overall, 2.6 msg/s now (per message: download 0.47s, upload 1.70s)
```

To see one mailbox only: `./setup.sh logs leaver1@example.com`, or
`grep -F '[leaver1@example.com]' logs/<batch>/batch.log`. The per-mailbox files
`logs/<batch>/<mailbox>.log` hold one mailbox each, so their lines carry no tag.

A progress line appears every 200 messages, and every 100,000 messages while a large
mailbox is being listed. At the end of each mailbox:

```
RESULT for leaver1@example.com: OK, everything is in the archive
RESULT for leaver2@example.com: INCOMPLETE, do not delete this account; rerun
```

`OK` means three things were checked: no message failed, every message in the source is
recorded as copied, and the number of messages under the archive label matches.
With `--query`, the same is checked for the messages that match the search, and the result
says so: `OK for the filter only: ... the rest of the mailbox was NOT copied`.

At the end of the batch, `logs/<batch>/batch.log` and `./setup.sh stop` show a summary:

```
==> batch 20260301-101500 finished
    leaver1@example.com                      OK, verified in the archive
    leaver2@example.com                      INCOMPLETE: some messages failed or could not be verified
SUMMARY: 1 of 2 mailboxes verified in the archive; 48950 messages copied in this batch; NOT complete, do not delete: leaver2@example.com
```

## Speed

Gmail limits how fast one mailbox can be written to. That puts the ceiling at roughly 10
messages per second into one archive mailbox, however many mailboxes or containers are
copying into it.

Measured on real mailboxes averaging about 0.5 MB per message:

| `--workers` | Messages per second |
|---|---|
| 4 | about 2 |
| 10 | about 5 |

- More than about 16 workers gains nothing. Past the ceiling, requests are throttled and retried.
- `--parallel` does not make the total faster. It lets small mailboxes finish without waiting behind a large one, and keeps one failing mailbox from holding up the rest. The workers are divided among the mailboxes that are copying, as evenly as the number allows, and are divided again whenever one starts or finishes.
- Gmail can slow down during a long run. In one run, after about two hours the time Gmail took to accept a message rose from under 2 seconds to about 6, with no error, and the rate fell to a third.
- As a rough guide, 100,000 messages take five to six hours at 5 messages per second.
- Running it from a laptop is fine. In those measurements the rate did not depend on message size, so the time goes on waiting for Gmail, not on bandwidth.

## Before you delete an account

1. Wait for `OK, verified in the archive` for that mailbox in `./setup.sh status`. `OK for its filter only` means the mailbox was copied with `--query`: deleting the account loses everything the search left out.
2. Mail keeps arriving while and after the copy runs. Immediately before deleting the account, run the same command once more for that mailbox. It copies only what is new and takes a minute or two.
3. Open the archive mailbox and spot-check the label.
4. Then delete the account. A deleted user can be restored from the Admin console for 20 days.

Do not delete or suspend an account whose result is `INCOMPLETE` or that is still queued.
Once the account is gone, the script can no longer read it.

## Files it creates

| Path | What it is |
|---|---|
| `secrets/sa.json` | The service account key. **Treat it like a password**: with the delegation in place it can read every mailbox in the domain |
| `data/state/<mailbox>.db` | The record of which messages have been copied, one file per source mailbox |
| `data/batches/<archive>/` | The batch of one archive mailbox: queue, settings, and the status and search of each mailbox |
| `logs/<batch>/batch.log` | The live log of a batch, with its summary at the end |
| `logs/<batch>/<mailbox>.log` | The complete log of one mailbox |

**Keep `data/` for as long as you might rerun.** It is the only record of what has already
been copied. Without it, a rerun copies every message again, and the script cannot remove
duplicates from the archive.

**Stop with `./setup.sh stop`, not by killing containers.** A container that is killed
outright (`docker kill`, `docker rm -f`, a power cut) can have inserted a message without
recording it. That message is copied a second time on the next run, and the mailbox then
ends as `INCOMPLETE` because the archive holds more messages than the record.

None of these are committed to git; `.gitignore` excludes them.

## When something is missing or goes wrong

The script detects most of these itself and prints the same instructions.

### gcloud is missing

The script offers to install it with Homebrew. To do it yourself:

- macOS: `brew install --cask gcloud-cli`
- Anything else: follow <https://cloud.google.com/sdk/docs/install>

Open a new terminal afterwards so `gcloud` is on your `PATH`, then rerun.

### Docker is missing or not running

- **Not installed**, macOS: `brew install --cask docker-desktop`, or download Docker Desktop from <https://docs.docker.com/get-started/get-docker/>. Linux: install Docker Engine from the same page.
- **Installed but not running**, macOS or Windows: start Docker Desktop and wait until it says the engine is running. The script starts it for you on macOS. The first start may ask you to accept its terms in its own window.
- **Installed but not running**, Linux: `sudo systemctl start docker`. To run it without `sudo`: `sudo usermod -aG docker $USER`, then log out and in again.

### The Google Cloud project cannot be created

| The error mentions | Cause | What to do |
|---|---|---|
| "already exists" or "in use" | Project IDs are global, and this one is taken or belongs to an account you cannot see | `PROJECT_ID=some-unique-id ./setup.sh ...` |
| "permission denied" | Your account may not create projects | Ask a Google Cloud admin for the Project Creator role, or reuse a project you own with `PROJECT_ID=...` |
| "Terms of Service" | This account has never used Google Cloud | Open <https://console.cloud.google.com/> once, accept the terms, rerun |
| anything else | You may be signed in with the wrong account | `gcloud auth login`, then rerun |

### The service account key cannot be created

If the error mentions `disableServiceAccountKeyCreation`, an organisation policy blocks
service account keys. The script opens the policy page for the project. Turn the policy
off for that project only, then rerun. This needs the Organization Policy Administrator role.

### "not yet authorised" or `unauthorized_client`

The delegation step has not been done, has not taken effect yet, or was entered with
different scopes. Follow [the delegation step](#the-one-manual-step-domain-wide-delegation)
again and compare the three scopes character by character. Then wait a few minutes and retry.

### CANNOT USE ... no such user

The address is not an active user. Check, in the Admin console under **Directory > Users**:

- the spelling;
- that it is a user, not a group;
- that the user is not suspended or deleted. A user deleted in the last 20 days can be restored from the Users page.

Fix it, or remove the address from the command.

### CANNOT USE ... no Gmail mailbox

The user exists but has no mailbox. Gmail's own error for this is "Mail service not
enabled". It happens most often with a freshly created archive user.

1. Admin console > **Directory > Users** > open the user > **Licences**: assign a Google Workspace licence.
2. Admin console > **Apps > Google Workspace > Gmail > Service status**: make sure Gmail is on for the user's organisational unit.
3. Sign in to Gmail as that user once to confirm it opens. A new mailbox can take a few minutes to appear.

### "Invalid label name"

Gmail refuses some names for a top-level label. `Archive` is one of them, which is why the
parent label is `Archived mailboxes`. The log names the label that was refused. If it is
one of the source user's own labels, rename that label in the source mailbox and rerun.

### A mailbox ends as INCOMPLETE

Its log (`./setup.sh logs MAILBOX`) lists the messages that failed and Gmail's reason for
each. Run `./setup.sh resume`: it retries only what is missing. Failures caused by
throttling usually pass on the second attempt. If the same few messages keep failing, the
reason in the log says why, and that mailbox should not be deleted on the strength of this copy.

### "Invalid JWT" or "Token must be a short-lived token"

The clock of your machine is wrong. Correct the date and time. If you deleted the service
account key in Google Cloud, also delete `secrets/sa.json` and rerun so a new one is made.

### "a copy started by an older version of this script is still running"

Older versions kept their progress in one shared file and ran in the foreground. Let that
copy finish, or stop it with a single Ctrl-C in its terminal, then rerun. Its progress
(`data/state.db`) is picked up automatically, so nothing is copied twice.

### `status` says the background runner is gone

The process that works through the queue was killed, or the machine restarted. Mailboxes
that had already started may still be copying. `./setup.sh resume` takes over, records
what finished in the meantime and carries on.

## Cleaning up afterwards

Once every mailbox is verified, spot-checked and you are completely done, remove the
access the script created:

1. Delete the Client ID entry at <https://admin.google.com/ac/owl/domainwidedelegation>.
2. `gcloud projects delete <project id>` (the project ID is the `project_id` value in `secrets/sa.json`).
3. `rm -rf secrets`

## How it works

| File | Role |
|---|---|
| `setup.sh` | Setup, the dry run, and the batches: queue, background runner, `status`, `logs`, `stop`, `resume`, `remove` |
| `migrate.py` | Copies one or more mailboxes. Runs inside the container |
| `Dockerfile`, `requirements.txt` | The image `migrate.py` runs in |
| `sources.example.txt` | Example for `--sources-file` |

- A service account with domain-wide delegation acts as each source user to read, and as the archive user to insert. The three scopes allow reading mail, inserting mail and creating labels, and nothing else.
- Each mailbox is copied by its own container, named after the mailbox, so Docker itself refuses to copy the same mailbox twice at once.
- Every message is recorded in `data/state/<mailbox>.db` as soon as it is inserted. A rerun lists the source again and copies only what is not recorded.
- `./setup.sh stop` sends each container a signal. It finishes the messages in flight, records them and exits, so a clean stop does not leave a message copied but unrecorded.
