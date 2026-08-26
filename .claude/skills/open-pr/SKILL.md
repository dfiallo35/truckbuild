---
name: open-pr
description: Opens a pull request for finished work in this repo using the GitHub MCP tools, since the gh CLI is not installed on this machine and shelling out to it fails. Use this whenever a task is complete and its changes are worth landing — after a stage checkpoint passes, after a feature or fix is verified, whenever asked to make, open, raise, or submit a PR — and also when reading PR status, checks, diffs, comments, or reviews. Finishing a task means the work is in a PR, not merely committed locally, so treat opening one as the last step of the task rather than a separate errand.
---

# Opening a pull request

## Use the MCP tools, not `gh`

**The `gh` CLI is not installed here.** `gh pr create` fails with `command not found`. The GitHub MCP
tools do the same jobs, and they take structured arguments rather than shell-quoted strings, which
matters for PR bodies containing backticks, `$`, and newlines.

These tools are **deferred** — their names are visible but their schemas are not loaded, so calling one
directly fails with `InputValidationError`. Load them first:

```
ToolSearch("select:mcp__github__create_pull_request,mcp__github__list_pull_requests,mcp__github__pull_request_read")
```

| Job | Tool |
|---|---|
| Create a PR | `mcp__github__create_pull_request` |
| Find existing PRs | `mcp__github__list_pull_requests` (add `fields` to keep the response small) |
| Read one PR, its checks, diff, or comments | `mcp__github__pull_request_read` (methods: `get`, `get_status`, `get_check_runs`, `get_diff`, `get_files`, `get_comments`, `get_reviews`) |
| Edit title, body, or base | `mcp__github__update_pull_request` |
| Merge | `mcp__github__merge_pull_request` |
| Issues | `mcp__github__issue_read`, `mcp__github__issue_write`, `mcp__github__add_issue_comment` |

Repo coordinates: **owner `dfiallo35`, repo `truckbuild`**, default base **`main`**.

Git itself still works normally through Bash — branching, committing, and pushing are ordinary git.
Only the GitHub-side operations need MCP.

## Workflow

### 1. Confirm the work is actually finished

Run the CI-equivalent sweep before opening anything — a PR that arrives red wastes the reviewer's pass.
The commands are in the `stage-checkpoint` skill, which also covers stage-specific gates. If the change
touches nothing under `api/` or `web/`, say so and skip the sweep, but prove it:

```bash
git diff --stat origin/main
```

That output is the evidence for any claim about what CI will do. Don't assert CI is unaffected without it.

### 2. Get the branch right

**Fetch before branching.** Local `main` goes stale the moment a PR is merged through the web UI, and
branching off a stale `main` silently re-proposes commits that already landed.

```bash
git fetch origin
git checkout -b <descriptive-branch> origin/main
```

Never commit directly to `main`. If work is already committed on the wrong branch, move it rather than
pushing it.

**If an open PR already covers this concern, add a commit to its branch instead of opening a second
one.** Two open PRs touching the same files conflict for no benefit; update the existing PR's body to
describe the enlarged scope.

### 3. Commit

Write a message that explains why the change exists, not just what changed — the diff already shows
what. End with the trailer:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

Use a heredoc (`git commit -F -`) rather than `-m` for anything multi-paragraph.

### 4. Push, and verify it landed on its own terms

```bash
git push -u origin <branch>
```

Then confirm by comparing SHAs rather than trusting the command's printed output:

```bash
git rev-parse HEAD origin/<branch>
```

Never pipe a push, install, build, or test through `tail` or `head`. The pipe replaces the command's
exit status with the pager's, so a failure reports success. This repo has already been bitten by it
once, which is why it is written down.

### 5. Check for an existing PR, then create

`list_pull_requests` with `state: "all"` — a closed-but-merged PR looks identical to a closed-unmerged
one in a listing, so read the `merged` field on the PR itself before concluding anything about what is
already on `main`.

Then `create_pull_request` with `owner`, `repo`, `title`, `head`, `base`, `body`.

### 6. Report the URL

Give the user the PR link and a short summary of what a reviewer should look at. The result of
`create_pull_request` contains the `url`.

## What goes in the body

The PR is where a reviewer decides whether to trust the change, so write for the person who was not in
the session. The convention established in this repo's PRs:

- **A one-line statement of what the change is for**, then scope — especially "docs only, CI unaffected"
  or which services are touched.
- **A table** when the change has several parts, one row each. For skills or components, a column for
  the failure mode each one targets is more useful than a description of what it does.
- **Decisions you made that the reviewer might reverse.** Anything where the spec was silent and you
  chose — a file path, a data format, a default. Say what you chose and why, so disagreeing is cheap.
- **Forward-looking references**, if the change names paths or commands that do not exist yet.
- **What you deliberately left out**, and the reasoning. This prevents the review comment asking for
  something that was already considered and rejected.
- **Verification** — what you actually ran and what it printed. A table works well.
- Close with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Report honestly. If tests fail or a step was skipped, the PR body says so. A PR body that overstates
what was verified is worse than one that admits a gap, because the reviewer stops checking.

## After opening

Checks take time to appear. To look at them later:

```
pull_request_read(method: "get_check_runs", ...)   # individual CI jobs
pull_request_read(method: "get_status", ...)       # combined commit status
```

If CI comes back red, fix it on the same branch and push — the PR updates itself.
