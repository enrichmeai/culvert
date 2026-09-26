#!/usr/bin/env bash
# PreToolUse(Bash): force a permission prompt for destructive, publishing or cloud-touching commands.
# Ported from enrichmeai/valuedocs (2026-09-26) and adapted to this repo's deploy and release rules
# (CLAUDE.md § "Deploy & cost rules").
#
# Why a hook as well as `ask` rules in settings.json: a Bash rule matches the command as written,
# so `Bash(git push *)` does not match `git -C . push --force` (docs: code.claude.com/docs/en/permissions,
# "what a Bash rule doesn't match"). This matches on the words anywhere in the command instead.
#
# It never denies and never allows: it only turns a would-be silent run into a prompt ("ask"). In a
# headless run (the GitHub Action) nobody can answer the prompt, so the command does not run.
set -uo pipefail

input=$(cat)
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null)
[ -z "$cmd" ] && exit 0

reason=""
check() { # $1 = extended regex, $2 = reason
  if [ -z "$reason" ] && printf '%s' "$cmd" | grep -Eiq -- "$1"; then reason="$2"; fi
}

# A program name, optionally invoked by path (/usr/bin/gcloud) or through env/command/exec.
P='(^|[;&|(`[:space:]])(env[[:space:]]+|command[[:space:]]+|exec[[:space:]]+)?([^[:space:];&|]*/)?'

check 'git[^|;&]*[[:space:]]push[^|;&]*([[:space:]]--force|[[:space:]]-[a-z]*f[a-z]*([[:space:]]|$)|[[:space:]]\+[^[:space:]]+)' 'force push'
check 'git[^|;&]*[[:space:]]push[^|;&]*[[:space:]](origin[[:space:]]+)?([^[:space:]]*:)?(refs/heads/)?main([[:space:]]|$)' 'push to main'
check 'git[^|;&]*[[:space:]]push[^|;&]*(--delete|[[:space:]]:[^[:space:]]+|--tags|--mirror|--all)' 'push that deletes refs or pushes tags'
check 'git[^|;&]*[[:space:]](reset[[:space:]]+--hard|clean[[:space:]]+-[a-z]*f|branch[[:space:]]+-D|tag[[:space:]]+(-[adfsmu]|--(delete|force|annotate|sign)|[^-[:space:]])|filter-branch|filter-repo|update-ref[[:space:]]+-d|checkout[[:space:]]+(--[[:space:]]+)?\.([[:space:]]|$)|restore[[:space:]]+(--[a-z]+[[:space:]]+)*\.([[:space:]]|$))' 'history, tag or working-tree change'
# CLAUDE.md § "Deploy & cost rules" 1: these markers in a commit message trigger deploy/publish workflows.
check 'git[^|;&]*[[:space:]]commit[^|;&]*\[(publish:)?deploy\]' 'commit message with [deploy] or [publish:deploy] triggers a deploy'
check "${P}rm[[:space:]]+([^;&|]*[[:space:]])?(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)([[:space:]]|$)" 'recursive delete'
check "${P}terraform([[:space:]]+-[^[:space:]]+)*[[:space:]]+(apply|destroy|import|taint|untaint|state[[:space:]]+(rm|mv|push)|force-unlock)" 'terraform state change'
check "${P}gcloud[[:space:]]" 'gcloud (GCP project access — run /finops-estimate first)'
check "${P}(gsutil|bq|kubectl)[[:space:]]" 'direct cloud data/infra CLI'
check "${P}helm[[:space:]]+(install|upgrade|uninstall|delete|rollback)" 'helm release change'
# Run (not read): the script is the command itself, or follows bash/sh.
R='(^|[;&|(][[:space:]]*)(env[[:space:]]+[^;&|]*)?((ba)?sh[[:space:]]+)?'
check "${R}[^[:space:];&|]*scripts/gcp/[^[:space:]]*\.sh" 'scripts/gcp/ touches a real GCP project'
check "${R}(\./)?(0[0-9]_[a-z_]+|cleanup_[a-z_]+|deploy_[a-z_]+|e2e_[a-z_]+)\.sh" 'a scripts/gcp/ script run from inside that directory'
check "${R}[^[:space:];&|]*(bootstrap_infrastructure|check_gcp_services)\.sh" 'script that calls gcloud against a real project'
# Publishing: Maven Central and PyPI releases are Joseph's trigger (CLAUDE.md, Engineer role).
check "${P}mvnw?[^|;&]*[[:space:]](deploy|release:[a-z]+)([[:space:]]|$)" 'Maven deploy/release (publishes artifacts)'
check "${P}mvnw?[^|;&]*[[:space:]]-P[[:space:]]*[^[:space:]]*release" 'Maven release profile'
check "${P}mvnw?[^|;&]*[[:space:]]-P[[:space:]]*[^[:space:]]*\bit\b" 'mvn -P it verify needs Docker and is architect/Joseph-run'
check "${P}(twine[[:space:]]+upload|hatch[[:space:]]+publish|flit[[:space:]]+publish|poetry[[:space:]]+publish|uv[[:space:]]+publish)" 'publish to PyPI'
check "${P}gh[[:space:]]+(release|pr[[:space:]]+merge|repo[[:space:]]+(delete|edit|archive|rename)|workflow[[:space:]]+(run|enable|disable)|secret|variable|api[^|;&]*(-X|--method)[[:space:]=]*(DELETE|PUT|PATCH|POST))" 'GitHub merge, admin, release or dispatch'
check "${P}pip3?[[:space:]]+install[^|;&]*(git\+|https?://|[[:space:]]-i[[:space:]]|--index-url|--extra-index-url)" 'pip install from a URL or another index'

# DCO: a Signed-off-by certifies the Developer Certificate of Origin, which only a person can do
# (CONTRIBUTING.md). Case-sensitive on purpose: -S is GPG signing, which is fine. 2026-09-26: Claude
# committed with -s on the batched-releases branch; this guard is the compound step for it.
if [ -z "$reason" ] && printf '%s' "$cmd" | grep -Eq -- 'git[^|;&]*[[:space:]](commit|rebase|am|cherry-pick)[^|;&]*[[:space:]](-[a-zA-RT-Z]*s[a-zA-Z]*|--signoff)([[:space:]]|$)'; then
  reason='DCO sign-off (-s/--signoff): only a person can certify the DCO — never Claude'
fi

# A push with no refspec pushes the current branch: when that is main, it is a push to main.
if [ -z "$reason" ] && printf '%s' "$cmd" | grep -Eq 'git[^|;&]*[[:space:]]push([[:space:]]|$)'; then
  dir=$(jq -r '.cwd // empty' <<<"$input"); [ -d "$dir" ] || dir=.
  if [ "$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ]; then reason='push while on main'; fi
fi

[ -z "$reason" ] && exit 0

jq -n --arg r "Guard hook: $reason — needs Joseph's approval (.claude/hooks/guard-destructive.sh)." '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $r
  }
}'
exit 0
