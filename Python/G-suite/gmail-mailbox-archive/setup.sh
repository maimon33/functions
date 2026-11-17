#!/usr/bin/env bash
# Sets everything up and starts the copy in the background:
#   Google Cloud project + Gmail API + service account + key  (automatic, via gcloud)
#   Workspace domain-wide delegation                          (manual, the page is opened for you)
#   Docker image, dry run, then the real copy
#
# Safe to rerun: finished steps are skipped and the copy resumes where it stopped.
#
# Usage:
#   ./setup.sh [options] ARCHIVE_MAILBOX SOURCE_MAILBOX [SOURCE_MAILBOX...]
#   ./setup.sh [options] --sources-file FILE ARCHIVE_MAILBOX [SOURCE_MAILBOX...]
#   PROJECT_ID=my-project ./setup.sh ...     # use a specific Google Cloud project
#
#   ./setup.sh status            what is queued, copying and finished
#   ./setup.sh logs [MAILBOX]    follow the live log (Ctrl-C leaves the log, not the copy)
#   ./setup.sh stop              stop cleanly; nothing is lost
#   ./setup.sh resume [--workers N] [--parallel N]
#                                continue a stopped batch, and retry what did not finish
#
# The copy runs as a "batch" in the background, so the terminal comes straight back and
# can be closed. Starting more mailboxes while a batch is running adds them to it.
#
#   --sources-file FILE  read source mailboxes from FILE, one address per line. Blank
#                        lines and anything after a # are ignored. Addresses given on
#                        the command line are copied as well.
#   --workers N          total parallel copies, shared by all mailboxes being copied
#                        (default: 12). Gmail caps one archive mailbox at roughly 10
#                        messages/s, so more than about 16 gains nothing.
#   --parallel N         mailboxes copied at the same time, one container each
#                        (default: 3). This does not raise the total speed; it keeps
#                        small mailboxes from waiting behind big ones.
#   --skip-dry-run       skip the access check and the confirmation; start copying at
#                        once. Use it only for reruns, after a dry run has passed.
#
# Each mailbox is copied by its own container, named after the mailbox, so Docker itself
# refuses to copy the same mailbox twice at once. Logs are kept under logs/<batch>/:
# batch.log for everything, and one file per mailbox.
set -euo pipefail
START_DIR=$PWD  # a relative --sources-file is relative to where the user is, not to this script
cd "$(dirname "$0")"
SELF="$PWD/$(basename "$0")"

IMAGE=gmail-migrate
CONTAINER_PREFIX=gmail-archive
SA_NAME=gmail-migrate
KEY=secrets/sa.json
DELEGATION_URL="https://admin.google.com/ac/owl/domainwidedelegation"
BATCH=data/batch          # the current batch: its queue, settings and per-mailbox status
SHARE_FILE=data/active    # number of containers copying right now; they split --workers by it

die() { echo "ERROR: $*" >&2; exit 1; }
step() { printf '\n==> %s\n' "$*"; }
open_url() {
  if command -v open >/dev/null; then open "$1"
  elif command -v xdg-open >/dev/null; then xdg-open "$1"
  fi
  echo "    $1"
}
copy() { if command -v pbcopy >/dev/null; then printf '%s' "$1" | pbcopy; fi; }

confirm() {  # confirm "question" -> success only on an explicit yes
  local answer
  read -r -p "    $1 [y/N] " answer
  case "$answer" in y | Y | yes | YES) return 0 ;; *) return 1 ;; esac
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
put() { printf '%s\n' "$2" >"$1.tmp" && mv "$1.tmp" "$1"; }  # replace a small file in one step
key_field() { sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p" "$KEY" 2>/dev/null | head -n 1; }
is_count() { case "$1" in "" | *[!0-9]* | 0*) return 1 ;; *) return 0 ;; esac; }

usage() {
  cat >&2 <<EOF
Usage: $0 [options] ARCHIVE_MAILBOX SOURCE_MAILBOX [SOURCE_MAILBOX...]
       $0 [options] --sources-file FILE ARCHIVE_MAILBOX [SOURCE_MAILBOX...]
       $0 status | logs [MAILBOX] | stop | resume [--workers N] [--parallel N]
Options:
  --sources-file FILE  read source mailboxes from FILE, one address per line
                       (blank lines and # comments are ignored)
  --workers N          total parallel copies, shared by all mailboxes (default: 12)
  --parallel N         mailboxes copied at the same time (default: 3)
  --skip-dry-run       skip the access check and the confirmation (reruns only)
The copy runs in the background. Starting more mailboxes while it runs adds them to it.
EOF
  exit 64
}

# ---------------------------------------------------------------------------------------
# The batch: a queue of mailboxes that a background process (the runner) copies a few at
# a time, one container per mailbox.
#
#   data/batch/id, dest, workers, parallel   settings of the current batch
#   data/batch/queue                         source mailboxes, one per line, in order
#   data/batch/status/<mailbox>              queued | running | exit code of its container
#   data/batch/runner.pid                    the runner, while it is working
#   data/batch/stop                          exists while a stop has been requested
#   logs/<batch id>/batch.log                everything, live; plus one log per mailbox
# ---------------------------------------------------------------------------------------

batch_exists() { [ -f "$BATCH/id" ]; }

batch_load() {
  BATCH_ID=$(cat "$BATCH/id")
  B_DEST=$(cat "$BATCH/dest")
  B_WORKERS=$(cat "$BATCH/workers")
  B_PARALLEL=$(cat "$BATCH/parallel")
  LOG_DIR="logs/$BATCH_ID"
  BATCH_LOG="$LOG_DIR/batch.log"
  mkdir -p "$LOG_DIR" "$BATCH/status" "$BATCH/followers"
}

job_status() { cat "$BATCH/status/$(lower "$1")" 2>/dev/null || echo none; }
set_job_status() { put "$BATCH/status/$(lower "$1")" "$2"; }
# One fixed name per mailbox, so Docker itself refuses to copy a mailbox twice at once.
container_name() { printf '%s-copy-%s' "$CONTAINER_PREFIX" "$(lower "$1" | sed 's/[^a-z0-9_.-]/_/g')"; }
# Every line of the batch log starts with who wrote it: [mailbox], or [batch] for the runner itself.
log_line() {  # log_line WHO MESSAGE; the time is UTC, like the containers
  local who=$1
  shift
  printf '[%s] %s %s\n' "$who" "$(date -u +%H:%M:%S)" "$*" >>"$BATCH_LOG"
}

describe() {
  case "$1" in
    queued) echo "queued" ;;
    running) echo "copying" ;;
    0) echo "OK, verified in the archive" ;;
    1) echo "INCOMPLETE: some messages failed or could not be verified" ;;
    3) echo "NOT AUTHORISED: domain-wide delegation is missing" ;;
    4) echo "CANNOT USE: not a user, or no Gmail (see its log)" ;;
    130) echo "stopped before it finished" ;;
    *) echo "FAILED (exit code $1, see its log)" ;;
  esac
}

lock() {  # for short critical sections; a lock still there after 10 seconds was left by a crash
  local tries=0
  until mkdir "$BATCH/lock" 2>/dev/null; do
    tries=$((tries + 1))
    if [ "$tries" -ge 100 ]; then
      rmdir "$BATCH/lock" 2>/dev/null || true
      tries=0
    fi
    sleep 0.1
  done
}
unlock() { rmdir "$BATCH/lock" 2>/dev/null || true; }

runner_alive() {
  local pid
  pid=$(cat "$BATCH/runner.pid" 2>/dev/null) || return 1
  if [ -z "$pid" ]; then return 1; fi
  # After a reboot the pid could belong to something else, so check what it is.
  ps -p "$pid" -o command= 2>/dev/null | grep -q "_runner"
}

running_copies() {  # containers copying into the given archive right now
  docker ps -q --filter "label=gmail-archive.role=copy" --filter "label=gmail-archive.dest=$(lower "$1")" 2>/dev/null |
    wc -l | tr -d ' '
}

refuse_foreign_copies() {
  # A copy started by an older version of this script keeps its progress in one shared
  # file. Running next to it could copy the same messages twice.
  local names
  names=$(docker ps --no-trunc --format '{{.Names}}|{{.Command}}' 2>/dev/null | grep 'migrate\.py' |
    grep -v "^$CONTAINER_PREFIX-" | cut -d'|' -f1 | paste -sd' ' - || true)
  if [ -n "$names" ]; then
    cat >&2 <<EOF
ERROR: a copy started by an older version of this script is still running (container: $names).
  It records its progress in a different place, so starting now could copy messages twice.
  Wait for it to finish, or stop it with one Ctrl-C in its terminal, then rerun this command.
EOF
    exit 1
  fi
}

any_queued() {
  local source
  while IFS= read -r source <&3; do
    if [ "$(job_status "$source")" = queued ]; then return 0; fi
  done 3<"$BATCH/queue"
  return 1
}

batch_unfinished() {  # is there work left that this batch would do without being asked again?
  local source
  if runner_alive; then return 0; fi
  while IFS= read -r source <&3; do
    case "$(job_status "$source")" in queued | running | 130) return 0 ;; esac
  done 3<"$BATCH/queue"
  return 1
}

follow() {  # follow SOURCE CONTAINER TAIL: copy the container's output into the batch log, live
  (docker logs -f --tail "$3" "$2" 2>&1 | while IFS= read -r line; do printf '[%s] %s\n' "$1" "$line"; done >>"$BATCH_LOG") &
  put "$BATCH/followers/$(lower "$1")" "$!"
}

start_job() {
  local source=$1 name status error
  name=$(container_name "$source")
  status=$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || true)
  if [ "$status" = running ]; then
    log_line "$source" "a container is already copying this mailbox; following it"
    follow "$source" "$name" 0
  else
    if [ -n "$status" ]; then  # left behind by a run that was cut short: keep its output, then replace it
      docker logs "$name" >"$LOG_DIR/$source.leftover.txt" 2>&1 || true
      docker rm -f "$name" >/dev/null 2>&1 || true
    fi
    # Count the new container in before it starts, so the others make room straight away.
    put "$SHARE_FILE" "$(($(running_copies "$B_DEST") + 1))"
    if ! error=$(docker run -d --name "$name" \
      --label "gmail-archive.role=copy" --label "gmail-archive.dest=$(lower "$B_DEST")" \
      -v "$PWD/secrets:/secrets:ro" -v "$PWD/data:/data" "$IMAGE" \
      --source "$source" --dest "$B_DEST" --workers "$B_WORKERS" --share-file "/$SHARE_FILE" 2>&1); then
      log_line "$source" "could not be started: $error"
      set_job_status "$source" 125
      return 1
    fi
    log_line "$source" "started"
    follow "$source" "$name" all
  fi
  set_job_status "$source" running
}

finish_job() {  # finish_job SOURCE CONTAINER EXIT_CODE
  local follower
  follower=$(cat "$BATCH/followers/$(lower "$1")" 2>/dev/null || true)
  if [ -n "$follower" ]; then wait "$follower" 2>/dev/null || true; fi  # let the live log catch up
  {
    echo "---- $(date -u '+%Y-%m-%d %H:%M:%S') UTC, exit code $3 ----"
    docker logs "$2" 2>&1 || true
  } >>"$LOG_DIR/$1.log"
  docker rm "$2" >/dev/null 2>&1 || true
  set_job_status "$1" "$3"
  log_line "$1" "finished: $(describe "$3")"
}

reap_and_count() {  # record containers that have ended; set N_RUNNING and N_QUEUED
  local source name state
  N_RUNNING=0
  N_QUEUED=0
  while IFS= read -r source <&3; do
    case "$(job_status "$source")" in
      queued) N_QUEUED=$((N_QUEUED + 1)) ;;
      running)
        name=$(container_name "$source")
        state=$(docker inspect -f '{{.State.Running}} {{.State.ExitCode}}' "$name" 2>/dev/null || true)
        case "$state" in
          "true "*) N_RUNNING=$((N_RUNNING + 1)) ;;
          "false "*) finish_job "$source" "$name" "${state#false }" ;;
          *)
            set_job_status "$source" 125
            log_line "$source" "its container no longer exists; marked as failed"
            ;;
        esac
        ;;
    esac
  done 3<"$BATCH/queue"
}

write_summary() {  # appended to the batch log when the runner ends
  local source st ok=0 total=0 not_done="" copied line
  {
    echo
    if [ -e "$BATCH/stop" ]; then echo "==> batch $BATCH_ID stopped"; else echo "==> batch $BATCH_ID finished"; fi
    while IFS= read -r source <&3; do
      st=$(job_status "$source")
      total=$((total + 1))
      if [ "$st" = 0 ]; then ok=$((ok + 1)); else not_done="$not_done${not_done:+, }$source"; fi
      printf '    %-40s %s\n' "$source" "$(describe "$st")"
    done 3<"$BATCH/queue"
    copied=$(cat "$LOG_DIR"/*@*.log 2>/dev/null | sed -n 's/.*this run copied \([0-9,]*\) messages.*/\1/p' |
      tr -d , | awk '{ s += $1 } END { print s + 0 }')
    line="SUMMARY: $ok of $total mailboxes verified in the archive; $copied messages copied in this batch"
    if [ -n "$not_done" ]; then line="$line; NOT complete, do not delete: $not_done"; fi
    echo "$line"
    echo "Logs: $LOG_DIR/"
    if [ -e "$BATCH/stop" ]; then
      echo "Nothing is lost. Continue with: ./$(basename "$SELF") resume"
    elif [ -n "$not_done" ]; then
      echo "Retry what is not complete with: ./$(basename "$SELF") resume"
    else
      cat <<EOF
Once you have spot-checked the archive and are completely done, remove the access this
script created (the key can read every mailbox in the domain):
  1. Delete the Client ID $(key_field client_id) entry at $DELEGATION_URL
  2. gcloud projects delete $(key_field project_id)
  3. rm -rf secrets
EOF
    fi
  } >>"$BATCH_LOG"
}

last_summary() { awk '/^==> batch/ { block = "" } { block = block $0 "\n" } END { printf "%s", block }' "$BATCH_LOG"; }

cmd__runner() {  # the background process; started by start_runner, never by hand
  set +e  # one failed docker call must not end the batch
  local signalled="" source active
  batch_load
  # Every container needs at least one worker, so more containers than workers would exceed the budget.
  if [ "$B_PARALLEL" -gt "$B_WORKERS" ]; then B_PARALLEL=$B_WORKERS; fi
  lock
  if runner_alive; then
    unlock
    exit 0
  fi
  put "$BATCH/runner.pid" "$$"
  unlock
  trap 'touch "$BATCH/stop"' TERM INT
  log_line batch "==> batch $BATCH_ID: copying into $B_DEST, $B_WORKERS workers shared by up to $B_PARALLEL mailboxes at a time"

  while :; do
    if ! docker ps -q >/dev/null 2>&1; then
      log_line batch "Docker is not responding; waiting for it"
      sleep 15
      continue
    fi
    reap_and_count
    if [ -e "$BATCH/stop" ]; then
      if [ -z "$signalled" ]; then
        signalled=yes
        log_line batch "==> stop requested: each mailbox finishes the messages it is copying right now"
        while IFS= read -r source <&3; do
          if [ "$(job_status "$source")" = running ]; then
            docker kill --signal=TERM "$(container_name "$source")" >/dev/null 2>&1
          fi
        done 3<"$BATCH/queue"
      fi
    else
      while IFS= read -r source <&3; do
        if [ "$N_RUNNING" -ge "$B_PARALLEL" ]; then break; fi
        if [ "$(job_status "$source")" = queued ]; then
          if start_job "$source"; then N_RUNNING=$((N_RUNNING + 1)); fi
        fi
      done 3<"$BATCH/queue"
    fi
    active=$(running_copies "$B_DEST")
    if [ "$active" -lt 1 ]; then active=1; fi
    put "$SHARE_FILE" "$active"

    if [ "$N_RUNNING" -eq 0 ]; then
      # Decide under the lock, so a mailbox added at this very moment is not left behind.
      lock
      if [ -e "$BATCH/stop" ] || ! any_queued; then
        write_summary
        rm -f "$BATCH/stop" "$BATCH/runner.pid"
        unlock
        break
      fi
      unlock
    fi
    sleep 5
  done
}

start_runner() {
  local tries=0
  nohup bash "$SELF" _runner >>"$BATCH_LOG" 2>&1 </dev/null &
  # Return only once it is up, so a status or stop typed straight afterwards sees it.
  until runner_alive || [ "$tries" -ge 50 ]; do
    tries=$((tries + 1))
    sleep 0.1
  done
}

resume_batch() {  # put everything that is not verified back in the queue and start the runner
  local source waiting=0
  reap_and_count  # containers that ended while no runner was watching
  while IFS= read -r source <&3; do
    case "$(job_status "$source")" in
      0 | running) ;;
      queued) waiting=$((waiting + 1)) ;;
      *)
        set_job_status "$source" queued
        waiting=$((waiting + 1))
        ;;
    esac
  done 3<"$BATCH/queue"
  if [ "$waiting" -eq 0 ] && [ "$N_RUNNING" -eq 0 ]; then
    echo "    Nothing to do: every mailbox in batch $BATCH_ID is verified in the archive."
    return 0
  fi
  rm -f "$BATCH/stop"
  start_runner
  cat <<EOF
    Batch $BATCH_ID is copying in the background ($waiting mailbox(es) to go, into $B_DEST).
    You can close this terminal.
      $0 status    what is queued, copying and finished
      $0 logs      follow the live log
      $0 stop      stop cleanly ($0 resume continues)
EOF
}

cmd_status() {
  local source st last
  batch_exists || die "nothing has been started yet"
  batch_load
  if runner_alive; then
    echo "Batch $BATCH_ID is running: copying into $B_DEST ($B_WORKERS workers, up to $B_PARALLEL mailboxes at a time)"
  elif [ "$(running_copies "$B_DEST")" -gt 0 ]; then
    echo "Batch $BATCH_ID: the background runner is gone (killed, or the machine restarted), but mailboxes"
    echo "that had started are still copying. Take over with: $0 resume    Or stop them: $0 stop"
  elif batch_unfinished; then
    echo "Batch $BATCH_ID is stopped. Continue with: $0 resume"
  else
    echo "Batch $BATCH_ID has finished."
  fi
  while IFS= read -r source <&3; do
    st=$(job_status "$source")
    if [ "$st" != running ]; then
      printf '  %-40s %s\n' "$source" "$(describe "$st")"
    elif [ "$(docker inspect -f '{{.State.Running}}' "$(container_name "$source")" 2>/dev/null || true)" = true ]; then
      printf '  %-40s %s\n' "$source" "copying"
      last=$(docker logs --tail 1 "$(container_name "$source")" 2>&1 | cut -c1-120 || true)
      if [ -n "$last" ]; then printf '  %-40s   %s\n' "" "$last"; fi
    else
      printf '  %-40s %s\n' "$source" "ended while nothing was watching; '$0 resume' records the result"
    fi
  done 3<"$BATCH/queue"
  echo "Logs: $LOG_DIR/"
}

cmd_logs() {
  local name
  batch_exists || die "nothing has been started yet"
  batch_load
  if [ $# -eq 0 ]; then
    [ -f "$BATCH_LOG" ] || die "there is no log yet"
    echo "Following $BATCH_LOG (Ctrl-C leaves the log; the copy keeps running)"
    exec tail -n 40 -f "$BATCH_LOG"
  fi
  name=$(container_name "$1")
  if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" = true ]; then
    echo "Following $1 (Ctrl-C leaves the log; the copy keeps running)"
    exec docker logs -f --tail 40 "$name"
  elif [ -f "$LOG_DIR/$1.log" ]; then
    cat "$LOG_DIR/$1.log"
  else
    die "no log for '$1' in batch $BATCH_ID (look in $LOG_DIR/)"
  fi
}

cmd_stop() {
  local source name signalled=""
  batch_exists || die "nothing has been started yet"
  batch_load
  if runner_alive; then
    touch "$BATCH/stop"
    printf 'Stopping: each mailbox finishes the messages it is copying right now '
    while runner_alive; do
      printf '.'
      sleep 2
    done
    echo
    last_summary
    return 0
  fi
  # No runner (it was killed, or the machine restarted): stop the containers directly.
  while IFS= read -r source <&3; do
    name=$(container_name "$source")
    if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" = true ]; then
      docker kill --signal=TERM "$name" >/dev/null 2>&1 || true
      signalled=yes
    fi
  done 3<"$BATCH/queue"
  if [ -z "$signalled" ]; then
    echo "Nothing is running."
    return 0
  fi
  printf 'Stopping: each mailbox finishes the messages it is copying right now '
  while [ "$(running_copies "$B_DEST")" -gt 0 ]; do
    printf '.'
    sleep 2
  done
  echo
  echo "Stopped. Nothing is lost. Continue with: $0 resume"
}

cmd_resume() {
  local workers="" parallel=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --workers) [ $# -ge 2 ] || usage; workers=$2; shift 2 ;;
      --workers=*) workers=${1#*=}; shift ;;
      --parallel) [ $# -ge 2 ] || usage; parallel=$2; shift 2 ;;
      --parallel=*) parallel=${1#*=}; shift ;;
      *) usage ;;
    esac
  done
  batch_exists || die "nothing to resume. Start a copy with: $0 ARCHIVE_MAILBOX SOURCE_MAILBOX..."
  batch_load
  if runner_alive; then
    echo "Batch $BATCH_ID is already running. Follow it with: $0 logs"
    return 0
  fi
  docker ps -q >/dev/null 2>&1 || die "Docker is not running. Start it, then rerun."
  refuse_foreign_copies
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then docker build -q -t "$IMAGE" . >/dev/null; fi
  if [ -n "$workers" ]; then
    is_count "$workers" || die "--workers must be a positive whole number, got '$workers'"
    put "$BATCH/workers" "$workers"
  fi
  if [ -n "$parallel" ]; then
    is_count "$parallel" || die "--parallel must be a positive whole number, got '$parallel'"
    put "$BATCH/parallel" "$parallel"
  fi
  batch_load
  resume_batch
}

case "${1:-}" in
  status | logs | stop | resume | _runner)
    command=$1
    shift
    "cmd_$command" "$@"
    exit 0
    ;;
esac

WORKERS=12
PARALLEL=3
WORKERS_SET=""
PARALLEL_SET=""
SKIP_DRY_RUN=""
SOURCES_FILE=""
MAILBOXES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --workers) [ $# -ge 2 ] || usage; WORKERS=$2; WORKERS_SET=yes; shift 2 ;;
    --workers=*) WORKERS=${1#*=}; WORKERS_SET=yes; shift ;;
    --parallel) [ $# -ge 2 ] || usage; PARALLEL=$2; PARALLEL_SET=yes; shift 2 ;;
    --parallel=*) PARALLEL=${1#*=}; PARALLEL_SET=yes; shift ;;
    --sources-file) [ $# -ge 2 ] || usage; SOURCES_FILE=$2; shift 2 ;;
    --sources-file=*) SOURCES_FILE=${1#*=}; shift ;;
    --skip-dry-run) SKIP_DRY_RUN=yes; shift ;;
    -h | --help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) MAILBOXES+=("$1"); shift ;;
  esac
done
[ "${#MAILBOXES[@]}" -ge 1 ] || usage
is_count "$WORKERS" || die "--workers must be a positive whole number, got '$WORKERS'"
is_count "$PARALLEL" || die "--parallel must be a positive whole number, got '$PARALLEL'"

if [ -n "$SOURCES_FILE" ]; then
  case "$SOURCES_FILE" in /*) ;; *) SOURCES_FILE="$START_DIR/$SOURCES_FILE" ;; esac
  [ -f "$SOURCES_FILE" ] && [ -r "$SOURCES_FILE" ] || die "cannot read the sources file '$SOURCES_FILE'"
  while IFS= read -r line || [ -n "$line" ]; do  # the || keeps a last line that has no newline
    line=${line%%#*}
    line=$(printf '%s' "$line" | tr -d '[:space:]')  # also drops the \r of Windows line endings
    if [ -n "$line" ]; then MAILBOXES+=("$line"); fi
  done <"$SOURCES_FILE"
fi
[ "${#MAILBOXES[@]}" -ge 2 ] || die "no source mailboxes given (on the command line or in --sources-file)"

DEST=${MAILBOXES[0]}
case "$DEST" in *@*) ;; *) die "'$DEST' is not an email address" ;; esac
DEST_LC=$(lower "$DEST")
SOURCES=()
SOURCE_ARGS=()  # the same list as --source arguments, for the dry run
SEEN=" "
for source in "${MAILBOXES[@]:1}"; do
  case "$source" in *@*) ;; *) die "'$source' is not an email address" ;; esac
  case "$source" in *[!A-Za-z0-9@._%+-]*) die "'$source' contains characters that are not allowed in a mailbox address" ;; esac
  source_lc=$(lower "$source")
  [ "$source_lc" != "$DEST_LC" ] || die "the archive mailbox cannot also be a source"
  case "$SEEN" in *" $source_lc "*) continue ;; esac  # listed twice: copy it once
  SEEN="$SEEN$source_lc "
  SOURCES+=("$source")
  SOURCE_ARGS+=(--source "$source")
done

if [ -z "${PROJECT_ID:-}" ]; then
  # Project IDs are global, so derive one from the domain: gmail-archive-company-com
  PROJECT_ID=$(printf 'gmail-archive-%s' "${DEST#*@}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | cut -c1-30 | sed 's/-*$//')
fi
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
# Single source of truth for the scopes is migrate.py.
SCOPES=$(grep -o 'https://www.googleapis.com/auth/[a-z.]*' migrate.py | paste -sd, -)

run_dry() {  # one short container in the foreground; it reads only
  docker run --rm --name "$CONTAINER_PREFIX-dryrun-$$" -v "$PWD/secrets:/secrets:ro" -v "$PWD/data:/data" "$IMAGE" \
    "${SOURCE_ARGS[@]}" --dest "$DEST" --dry-run
}

step "1/6 Checking tools"
echo "    archive mailbox:  $DEST"
echo "    source mailboxes: ${#SOURCES[@]}"

if ! command -v gcloud >/dev/null; then
  cat <<EOF

    The Google Cloud CLI (gcloud) is not installed. It is needed to create the Google
    Cloud project, the service account and its key.
EOF
  if command -v brew >/dev/null && confirm "Install it now with Homebrew (brew install --cask gcloud-cli)?"; then
    brew install --cask gcloud-cli
    hash -r
  fi
  if ! command -v gcloud >/dev/null; then
    echo "    Install it from the page below, open a new terminal so it is on your PATH, then rerun:"
    open_url "https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
fi

if ! command -v docker >/dev/null; then
  cat <<EOF

    Docker is not installed. The copy runs inside a container, so that nothing else
    (Python, libraries) has to be installed on this machine.
EOF
  if command -v brew >/dev/null && confirm "Install Docker Desktop now with Homebrew (brew install --cask docker-desktop)?"; then
    brew install --cask docker-desktop
    hash -r
  fi
  if ! command -v docker >/dev/null; then
    echo "    Install it from the page below, then rerun:"
    open_url "https://docs.docker.com/get-started/get-docker/"
    exit 1
  fi
fi

if ! docker info >/dev/null 2>&1; then
  if [ -d /Applications/Docker.app ]; then
    echo "    Docker is installed but not running. Starting Docker Desktop (first start can take a minute,"
    echo "    and it may ask you to accept its terms in its own window)..."
    open -a Docker
    for _ in $(seq 1 60); do
      docker info >/dev/null 2>&1 && break
      sleep 3
    done
  fi
  if ! docker info >/dev/null 2>&1; then
    cat >&2 <<EOF
ERROR: Docker is installed but not running.
  macOS / Windows: start Docker Desktop and wait for it to say "Engine running".
  Linux:           sudo systemctl start docker
                   (and, to run it without sudo: sudo usermod -aG docker \$USER, then log in again)
Then rerun this script.
EOF
    exit 1
  fi
fi

ACCOUNT=$(gcloud config get-value account 2>/dev/null || true)
if [ -z "$ACCOUNT" ] || [ "$ACCOUNT" = "(unset)" ]; then
  echo "    gcloud is not signed in. A browser window will open: sign in with an account"
  echo "    that may create Google Cloud projects in your organisation."
  gcloud auth login
  ACCOUNT=$(gcloud config get-value account 2>/dev/null)
fi
echo "    Google Cloud account: $ACCOUNT"
echo "    Google Cloud project: $PROJECT_ID"
mkdir -p secrets data

step "2/6 Google Cloud project and Gmail API"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "    project already exists"
elif ! gcloud projects create "$PROJECT_ID" --name="Gmail archive"; then
  cat >&2 <<EOF

ERROR: could not create the Google Cloud project '$PROJECT_ID' as $ACCOUNT (see the message above).
  - "already exists" or "in use": project IDs are global and this one is taken, or it
    belongs to an account that $ACCOUNT cannot see. Pick another ID:
        PROJECT_ID=some-unique-id $0 ...
  - "permission denied": $ACCOUNT may not create projects. Either ask a Google Cloud
    admin for the "Project Creator" role, or reuse a project you already own:
        PROJECT_ID=existing-project-id $0 ...
  - "Terms of Service": this account has never used Google Cloud. Open the console
    once, accept the terms, then rerun:
        https://console.cloud.google.com/
  - Signed in with the wrong account? Run: gcloud auth login
EOF
  exit 1
fi
if ! gcloud services enable gmail.googleapis.com --project "$PROJECT_ID"; then
  cat >&2 <<EOF

ERROR: could not enable the Gmail API in project '$PROJECT_ID' (see the message above).
  $ACCOUNT needs the Owner or Editor role (or "Service Usage Admin") on that project.
  You can also enable it by hand, then rerun:
      https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=$PROJECT_ID
EOF
  exit 1
fi

step "3/6 Service account and key"
if gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "    service account already exists"
else
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name="Gmail mailbox archiver"
fi
if [ -s "$KEY" ]; then
  echo "    key already at $KEY"
else
  created=""
  for attempt in 1 2 3; do  # a brand-new service account can take a few seconds to appear
    if gcloud iam service-accounts keys create "$KEY" --iam-account "$SA_EMAIL" --project "$PROJECT_ID"; then
      created=yes
      break
    fi
    sleep 5
  done
  if [ -z "$created" ]; then
    rm -f "$KEY"
    echo "Could not create a key. If the error mentions 'disableServiceAccountKeyCreation'," >&2
    echo "an org policy blocks keys; turn it off for this project here, then rerun:" >&2
    open_url "https://console.cloud.google.com/iam-admin/orgpolicies/iam-disableServiceAccountKeyCreation?project=$PROJECT_ID" >&2
    exit 1
  fi
  chmod 600 "$KEY"
fi
CLIENT_ID=$(sed -n 's/.*"client_id": *"\([0-9][0-9]*\)".*/\1/p' "$KEY")
[ -n "$CLIENT_ID" ] || die "no client_id found in $KEY; delete the file and rerun"

step "4/6 Building Docker image"
docker build -q -t "$IMAGE" . >/dev/null
echo "    built $IMAGE"

step "5/6 Checking mailbox access (dry run, writes nothing)"
[ -z "$SKIP_DRY_RUN" ] || echo "    skipped (--skip-dry-run)"
shown_delegation=""
shown_users=""
while [ -z "$SKIP_DRY_RUN" ]; do
  rc=0
  run_dry || rc=$?
  [ "$rc" -eq 0 ] && break

  if [ "$rc" -eq 3 ] && [ -z "$shown_delegation" ]; then
    shown_delegation=yes
    cat <<EOF

    The service account is not yet authorised in Google Workspace. This is the one
    manual step, and it needs a Workspace super admin. Opening the page:
EOF
    open_url "$DELEGATION_URL"
    cat <<EOF

    On that page click "Add new", then fill in:
      Client ID:    $CLIENT_ID
      OAuth scopes: $SCOPES

EOF
    copy "$CLIENT_ID"
    read -r -p "    Client ID is on your clipboard. Paste it, then press Enter to get the scopes... "
    copy "$SCOPES"
    read -r -p "    Scopes are on your clipboard. Paste them, click Authorize, then press Enter... "
  elif [ "$rc" -eq 4 ]; then
    cat <<EOF

    The mailboxes marked CANNOT USE above have to be fixed in the Google Admin console
    (Directory > Users), or removed from the command:

      "no such user"      Check the spelling. It must be an active user: not a group,
                          not suspended, not deleted. A user deleted in the last 20 days
                          can be restored from the Users page (filter: recently deleted).
      "no Gmail mailbox"  Open the user and assign a Google Workspace licence (Licences
                          section), and check that Gmail is ON for their organisational
                          unit: Apps > Google Workspace > Gmail > Service status.
                          A newly licensed mailbox can take a few minutes to appear.

EOF
    if [ -z "$shown_users" ]; then
      shown_users=yes
      echo "    Opening the Users page:"
      open_url "https://admin.google.com/ac/users"
    fi
    read -r -p "    Press Enter to retry, or Ctrl-C to stop and change the mailbox list... "
  else
    cat <<EOF

    The dry run failed (see the error above).
      - "unauthorized_client": delegation is not active yet. It usually takes a few
        minutes after you click Authorize (Google allows up to 24 hours). Also check
        that the scopes in the Admin console entry are exactly:
          $SCOPES
      - "has not been used in project" / "disabled": the Gmail API was only just
        enabled; wait a minute.
      - "Invalid JWT" / "Token must be a short-lived token": this machine's clock is
        wrong; fix the date and time. If you deleted the service account key, also
        delete $KEY and rerun.
EOF
    read -r -p "    Press Enter to retry, or Ctrl-C to stop... "
  fi
done

step "6/6 Starting the copy in the background"
if [ -z "$SKIP_DRY_RUN" ] && ! confirm "Dry run passed. Start the real copy now?"; then
  echo "    Not started. Rerun this script when ready."
  exit 0
fi
refuse_foreign_copies
mkdir -p "$BATCH" logs

lock
if batch_exists && batch_unfinished; then
  # A batch is running or was stopped: these mailboxes join it.
  batch_load
  if [ "$(lower "$B_DEST")" != "$DEST_LC" ]; then
    unlock
    die "the current batch copies into $B_DEST. Let it finish (see: $0 status) before copying into $DEST."
  fi
  joined=yes
else
  # Nothing unfinished: start a new batch. Logs of earlier batches stay under logs/.
  rm -rf "$BATCH/status" "$BATCH/followers"
  rm -f "$BATCH/stop" "$BATCH/runner.pid"
  : >"$BATCH/queue"
  put "$BATCH/id" "$(date +%Y%m%d-%H%M%S)"
  put "$BATCH/dest" "$DEST"
  put "$BATCH/workers" "$WORKERS"
  put "$BATCH/parallel" "$PARALLEL"
  batch_load
  joined=""
fi
added=0
for source in "${SOURCES[@]}"; do
  case "$(job_status "$source")" in
    queued | running) echo "    $source is already in batch $BATCH_ID" ;;
    none)
      printf '%s\n' "$source" >>"$BATCH/queue"
      set_job_status "$source" queued
      added=$((added + 1))
      ;;
    *)  # finished earlier in this batch: queue it again to copy whatever is new
      set_job_status "$source" queued
      added=$((added + 1))
      ;;
  esac
done
running=""
if runner_alive; then running=yes; fi
unlock

if [ -n "$running" ]; then
  echo "    Added $added mailbox(es) to batch $BATCH_ID, which is copying in the background."
  if [ -n "$WORKERS_SET$PARALLEL_SET" ]; then
    echo "    The running batch keeps its settings ($B_WORKERS workers, $B_PARALLEL mailboxes at a time)."
    echo "    To change them: $0 stop, then $0 resume --workers N --parallel N"
  fi
  echo "    Follow it with: $0 logs      Overview: $0 status"
else
  if [ -n "$joined" ]; then
    echo "    Added $added mailbox(es) to batch $BATCH_ID, which was stopped. Resuming it."
    if [ -n "$WORKERS_SET" ]; then put "$BATCH/workers" "$WORKERS"; fi
    if [ -n "$PARALLEL_SET" ]; then put "$BATCH/parallel" "$PARALLEL"; fi
    batch_load
  fi
  resume_batch
fi
