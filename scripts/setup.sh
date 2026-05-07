#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DB_NAME="${DB_NAME:-leaderboard}"
DB_USER="${DB_USER:-$(whoami)}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env}"
if [[ "${ENV_FILE}" != /* ]]; then
  ENV_FILE="${PROJECT_ROOT}/${ENV_FILE}"
fi
DATABASE_URL_VALUE="${DATABASE_URL:-postgresql:///${DB_NAME}}"
FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-}"

log() {
  printf '\n==> %s\n' "$1"
}

warn() {
  printf '\nWARNING: %s\n' "$1" >&2
}

fail() {
  printf '\nERROR: %s\n' "$1" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ensure_command() {
  command_exists "$1" || fail "Required command '$1' was not found. Please install it and rerun this script."
}

get_firebase_project_id() {
  if [[ -n "$FIREBASE_PROJECT_ID" ]]; then
    printf '%s\n' "$FIREBASE_PROJECT_ID"
    return
  fi

  python3 - "${PROJECT_ROOT}/.firebaserc" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    sys.exit(1)

project_id = json.loads(path.read_text()).get("projects", {}).get("default")
if not project_id:
    sys.exit(1)
print(project_id)
PY
}

upsert_env_var() {
  local key="$1"
  local value="$2"

  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
path.parent.mkdir(parents=True, exist_ok=True)
lines = path.read_text().splitlines() if path.exists() else []
updated = []
replaced = False
prefix = f"{key}="
for line in lines:
    if line.startswith(prefix):
        if not replaced:
            updated.append(f"{key}={value}")
            replaced = True
        continue
    updated.append(line)
if not replaced:
    updated.append(f"{key}={value}")
path.write_text("\n".join(updated) + "\n")
PY
}

postgres_is_ready() {
  pg_isready >/dev/null 2>&1
}

start_postgres_macos() {
  ensure_command brew

  local formula=""
  if brew list --formula postgresql >/dev/null 2>&1; then
    formula="postgresql"
  else
    formula="$(brew list --formula 2>/dev/null | grep -E '^postgresql@[0-9]+$' | sort -Vr | head -n 1 || true)"
  fi

  if [[ -z "$formula" ]]; then
    fail "PostgreSQL does not appear to be installed with Homebrew. Try: brew install postgresql"
  fi

  log "Starting PostgreSQL with Homebrew ($formula)"
  brew services start "$formula" >/dev/null
}

start_postgres_linux() {
  if command_exists systemctl; then
    if systemctl list-unit-files postgresql.service >/dev/null 2>&1; then
      log "Starting PostgreSQL with systemctl"
      if sudo systemctl start postgresql; then
        return
      fi
      warn "systemctl could not start postgresql; trying other startup methods."
    fi
  fi

  if command_exists pg_ctlcluster; then
    local cluster
    cluster="$(pg_lsclusters --no-header 2>/dev/null | awk 'NR == 1 {print $1 " " $2}' || true)"
    if [[ -n "$cluster" ]]; then
      log "Starting PostgreSQL cluster with pg_ctlcluster"
      # shellcheck disable=SC2086
      sudo pg_ctlcluster $cluster start || true
      return
    fi
  fi

  warn "Could not automatically start PostgreSQL on Linux. Please start it manually, then rerun this script."
}

ensure_postgres_running() {
  ensure_command pg_isready

  if postgres_is_ready; then
    log "PostgreSQL is already running"
    return
  fi

  case "$(uname -s)" in
    Darwin)
      start_postgres_macos
      ;;
    Linux)
      start_postgres_linux
      ;;
    *)
      warn "Unsupported OS for automatic PostgreSQL startup: $(uname -s). Please start PostgreSQL manually."
      ;;
  esac

  for _ in {1..10}; do
    if postgres_is_ready; then
      log "PostgreSQL is running"
      return
    fi
    sleep 1
  done

  fail "PostgreSQL is not accepting connections. Check that the server is running and listening locally."
}

role_exists() {
  psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}'" 2>/dev/null | grep -q 1
}

ensure_database_role() {
  if role_exists; then
    log "PostgreSQL role '${DB_USER}' already exists"
    return
  fi

  if command_exists sudo; then
    log "Creating PostgreSQL role '${DB_USER}'"
    sudo -u postgres createuser --createdb "$DB_USER" || warn "Could not create PostgreSQL role '${DB_USER}'. Continuing in case it is not needed."
  else
    warn "Could not verify or create PostgreSQL role '${DB_USER}' because sudo is unavailable."
  fi
}

database_exists() {
  psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" 2>/dev/null | grep -q 1
}

create_database() {
  ensure_command createdb
  ensure_command psql

  if database_exists; then
    log "Database '${DB_NAME}' already exists"
    return
  fi

  log "Creating database '${DB_NAME}'"
  if createdb "$DB_NAME" 2>/dev/null; then
    return
  fi

  if command_exists sudo; then
    warn "createdb failed as the current user; trying as the postgres system user"
    sudo -u postgres createdb "$DB_NAME" || fail "Could not create database '${DB_NAME}'."
  else
    fail "Could not create database '${DB_NAME}'."
  fi
}

write_env_file() {
  log "Writing ${ENV_FILE}"
  upsert_env_var "DATABASE_URL" "$DATABASE_URL_VALUE"
  upsert_env_var "GOOGLE_CLOUD_PROJECT" "$(get_firebase_project_id)"
}

install_python_dependencies() {
  ensure_command python3

  if command_exists pip3; then
    log "Installing Python dependencies"
    pip3 install -r "${PROJECT_ROOT}/requirements.txt"
  else
    log "Installing Python dependencies with python3 -m pip"
    python3 -m pip install -r "${PROJECT_ROOT}/requirements.txt"
  fi
}

reset_database_schema() {
  log "Resetting database schema"
  (cd "${PROJECT_ROOT}" && python3 -m scripts.reset_database)
}

login_application_default_credentials() {
  if gcloud auth application-default login; then
    return
  fi

  warn "Browser-based authentication failed; retrying with --no-browser."
  gcloud auth application-default login --no-browser
}

setup_google_application_credentials() {
  local project_id
  project_id="$(get_firebase_project_id)" || fail "Could not determine Firebase project ID. Set FIREBASE_PROJECT_ID or add a default project to .firebaserc."

  ensure_command gcloud

  log "Configuring gcloud project '${project_id}'"
  gcloud config set project "$project_id" >/dev/null

  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    log "Authenticating Google Application Default Credentials"
    login_application_default_credentials
  else
    log "Google Application Default Credentials are already configured"
  fi

  log "Setting Application Default Credentials quota project '${project_id}'"
  gcloud auth application-default set-quota-project "$project_id" >/dev/null
}

install_python_dependencies
setup_google_application_credentials
ensure_postgres_running
ensure_database_role
create_database
write_env_file
reset_database_schema

log "Setup complete"
printf 'DATABASE_URL=%s\n' "$DATABASE_URL_VALUE"
printf 'GOOGLE_CLOUD_PROJECT=%s\n' "$(get_firebase_project_id)"
