#!/usr/bin/env bash
#
# Fresh-machine bootstrap for the Wikipedia Edit-Triage Agent.
#
# Clones the repo (if needed) and runs ./start.sh. Designed for a one-liner:
#
#   curl -fsSL https://raw.githubusercontent.com/takabayashi/agentic-rd/main/install.sh | bash
#
# Knobs (optional):
#   AGENTIC_DIR=~/agentic-rd     where to clone (default: ./agentic-rd)
#   AGENTIC_REF=main             branch/tag to check out
#   AGENTIC_REPO=<git url>       override the source repo

set -euo pipefail

REPO="${AGENTIC_REPO:-https://github.com/takabayashi/agentic-rd.git}"
REF="${AGENTIC_REF:-main}"
DIR="${AGENTIC_DIR:-agentic-rd}"

if [ -t 1 ]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
  BOLD=""; GREEN=""; RED=""; CYAN=""; RESET=""
fi
info() { printf '%s\n' "${CYAN}==>${RESET} $*"; }
ok()   { printf '%s\n' "${GREEN}  ok${RESET} $*"; }
die()  { printf '%s\n' "${RED}error:${RESET} $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required. Install git and re-run."
command -v docker >/dev/null 2>&1 \
  || die "Docker is required. Install Docker Desktop: https://docs.docker.com/get-docker/"

printf '%s\n' "${BOLD}Wikipedia Edit-Triage Agent — installer${RESET}"

if [ -d "$DIR/.git" ]; then
  info "Existing checkout found in '$DIR'; updating"
  git -C "$DIR" fetch --quiet origin "$REF"
  git -C "$DIR" checkout --quiet "$REF"
  git -C "$DIR" pull --quiet --ff-only origin "$REF" || true
  ok "Updated '$DIR' to latest $REF"
else
  info "Cloning $REPO ($REF) into '$DIR'"
  git clone --quiet --branch "$REF" --depth 1 "$REPO" "$DIR"
  ok "Cloned into '$DIR'"
fi

cd "$DIR"
info "Launching ./start.sh"
exec ./start.sh
