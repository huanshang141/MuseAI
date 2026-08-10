#!/usr/bin/env bash
# Mock regression for pg_backup.sh. No PostgreSQL or Docker daemon is required.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/pg_backup.sh"
TEST_ROOT="$(mktemp -d)"

cleanup() {
    rm -rf -- "$TEST_ROOT"
}
trap cleanup EXIT

MOCK_BIN="${TEST_ROOT}/bin"
mkdir -p "$MOCK_BIN"

cat > "${MOCK_BIN}/docker" <<'MOCK_DOCKER'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$@" > "$MOCK_DOCKER_ARGS_FILE"
if [ "$MOCK_DOCKER_MODE" = "failure" ]; then
    printf '%s\n' '-- partial dump that must never be published'
    exit 42
fi

printf '%s\n' '-- MuseAI backup fixture' 'CREATE TABLE backup_probe (id integer);'
MOCK_DOCKER
chmod +x "${MOCK_BIN}/docker"

SUCCESS_DIR="${TEST_ROOT}/success"
SUCCESS_ARGS="${TEST_ROOT}/success-docker-args"
mkdir -p "$SUCCESS_DIR"
SUCCESS_FILE="$({
    unset PGUSER
    PATH="${MOCK_BIN}:$PATH" \
        MOCK_DOCKER_MODE=success \
        MOCK_DOCKER_ARGS_FILE="$SUCCESS_ARGS" \
        PG_CONTAINER=museai-postgres \
        DB_NAME=museai \
        BACKUP_DIR="$SUCCESS_DIR" \
        "$BACKUP_SCRIPT"
})"

case "$SUCCESS_FILE" in
    "${SUCCESS_DIR}"/museai_*.sql.gz) ;;
    *)
        printf 'unexpected backup path: %s\n' "$SUCCESS_FILE" >&2
        exit 1
        ;;
esac
test -f "$SUCCESS_FILE"
test "$(stat -c '%a' "$SUCCESS_DIR")" = 700
test "$(stat -c '%a' "$SUCCESS_FILE")" = 600
gzip -t "$SUCCESS_FILE"
test "$(gzip -dc "$SUCCESS_FILE")" = $'-- MuseAI backup fixture\nCREATE TABLE backup_probe (id integer);'
test "$(cat "$SUCCESS_ARGS")" = $'exec\nmuseai-postgres\npg_dump\n--no-owner\n-U\nmuseai\nmuseai'
SUCCESS_TEMP_FILE="$(find "$SUCCESS_DIR" -maxdepth 1 -name '.museai_*.sql.gz' -print -quit)"
test -z "$SUCCESS_TEMP_FILE"

FAILURE_DIR="${TEST_ROOT}/failure"
FAILURE_ARGS="${TEST_ROOT}/failure-docker-args"
mkdir -p "$FAILURE_DIR"
if {
    unset PGUSER
    PATH="${MOCK_BIN}:$PATH" \
        MOCK_DOCKER_MODE=failure \
        MOCK_DOCKER_ARGS_FILE="$FAILURE_ARGS" \
        PG_CONTAINER=museai-postgres \
        DB_NAME=museai \
        BACKUP_DIR="$FAILURE_DIR" \
        "$BACKUP_SCRIPT"
} >"${TEST_ROOT}/failure.stdout" 2>"${TEST_ROOT}/failure.stderr"; then
    printf 'pg_backup.sh unexpectedly succeeded after pg_dump failure\n' >&2
    exit 1
fi

test "$(cat "$FAILURE_ARGS")" = $'exec\nmuseai-postgres\npg_dump\n--no-owner\n-U\nmuseai\nmuseai'
FAILURE_FINAL_FILE="$(find "$FAILURE_DIR" -maxdepth 1 -name 'museai_*.sql.gz' -print -quit)"
FAILURE_TEMP_FILE="$(find "$FAILURE_DIR" -maxdepth 1 -name '.museai_*.sql.gz' -print -quit)"
test -z "$FAILURE_FINAL_FILE"
test -z "$FAILURE_TEMP_FILE"

printf '%s\n' 'pg_backup.sh mock regression passed'
