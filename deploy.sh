#!/bin/zsh
# One-command deploy: stages everything, commits, pushes to GitHub → Netlify auto-deploys.
# Usage:  ./deploy.sh              (default message with date)
#         ./deploy.sh "message"    (your own commit message)
set -e
cd "$(dirname "$0")"

# clear stale locks from crashed git processes (the Feb 2026 problem)
find .git -maxdepth 1 -name "*.lock" -mmin +60 -delete 2>/dev/null || true

git add -A
if git diff --cached --quiet; then
    if [ -z "$(git log origin/main..HEAD --oneline 2>/dev/null)" ]; then
        echo "Nothing to deploy — no changes."
        exit 0
    fi
    echo "No new changes, but unpushed commits found — pushing those."
else
    git commit -m "${1:-site update $(date '+%Y-%m-%d %H:%M')}"
fi
git push origin main
echo ""
echo "Pushed. Netlify will deploy in ~1-2 min. Check: https://app.netlify.com"
