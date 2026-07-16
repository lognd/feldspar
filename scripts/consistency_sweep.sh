#!/usr/bin/env bash
# Detects stray git worktrees left over from agent dispatches whose branch
# is already merged into main -- prunable cruft that should have been
# removed (feldspar had no such sweep and accumulated stale worktrees
# under .worktrees/ and .claude/worktrees/; mirrors lithos's
# `make health-consistency` worktree check, but this leg is gating).
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

main_worktree="$(git rev-parse --path-format=absolute --git-common-dir)"
main_worktree="$(dirname "$main_worktree")"

status=0
found_stray=0
found_merged=0

current_path=""
current_branch=""

check_worktree() {
    local path="$1"
    local branch="$2"

    if [ "$path" = "$main_worktree" ]; then
        return
    fi

    found_stray=1
    echo "consistency-sweep: stray worktree at $path (branch: ${branch:-<detached>})"

    if [ -z "$branch" ]; then
        echo "consistency-sweep:   detached HEAD, cannot check merge status"
        return
    fi

    if git merge-base --is-ancestor "$branch" main 2>/dev/null; then
        echo "consistency-sweep:   MERGED into main -- prunable cruft (run: git worktree remove $path)"
        found_merged=1
    else
        echo "consistency-sweep:   not yet merged into main -- leave alone"
    fi
}

while IFS= read -r line; do
    case "$line" in
        worktree\ *)
            if [ -n "$current_path" ]; then
                check_worktree "$current_path" "$current_branch"
            fi
            current_path="${line#worktree }"
            current_branch=""
            ;;
        branch\ *)
            current_branch="${line#branch refs/heads/}"
            ;;
        "")
            ;;
    esac
done < <(git worktree list --porcelain)

if [ -n "$current_path" ]; then
    check_worktree "$current_path" "$current_branch"
fi

if [ "$found_merged" -eq 1 ]; then
    echo "consistency-sweep: FAIL -- merged stray worktree(s) found, prune them"
    status=1
elif [ "$found_stray" -eq 1 ]; then
    echo "consistency-sweep: stray worktree(s) found but none merged yet; ok"
    status=0
else
    echo "consistency-sweep: clean, no stray worktrees"
    status=0
fi

exit "$status"
