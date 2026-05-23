# Welcome to Sayone Tech — Review Master

## How We Use Claude

Based on Renjith's usage over the last 30 days across 60 sessions:

Work Type Breakdown:
  Build Feature    ███████████████░░░░░  73%
  Debug Fix        ██░░░░░░░░░░░░░░░░░░  12%
  Improve Quality  ██░░░░░░░░░░░░░░░░░░  12%
  Plan Design      █░░░░░░░░░░░░░░░░░░░   3%

Top Skills & Commands:
  /gsd-plan-phase      ████████████████████  30x/month
  /gsd-progress        ███████████████░░░░░  23x/month
  /gsd-discuss-phase   ███████████░░░░░░░░░  17x/month
  /gsd-execute-phase   ███████████░░░░░░░░░  17x/month
  /gsd-ui-phase        ████████░░░░░░░░░░░░  12x/month
  /gsd-code-review     ████░░░░░░░░░░░░░░░░   6x/month
  /gsd-new-milestone   ███░░░░░░░░░░░░░░░░░   5x/month

Top MCP Servers:
  Playwright (browser automation)  ████████████████████  110 calls
  code-review-graph (code graph)   ██░░░░░░░░░░░░░░░░░░   12 calls
  AWS Pricing (cost estimates)     ██░░░░░░░░░░░░░░░░░░   12 calls
  Chrome DevTools (debugging)      ██░░░░░░░░░░░░░░░░░░   11 calls

## Your Setup Checklist

### Codebases
- [ ] review-master — github.com/sayone-tech/review-master-v2

### MCP Servers to Activate
- [ ] **Playwright** — browser automation for visual verification of UI changes. Add the MCP server to your Claude Code settings (`~/.claude/settings.json` → `mcpServers`). Requires Node.js.
- [ ] **code-review-graph** — persistent knowledge graph that gives Claude structural context about the codebase (callers, dependents, test coverage). Already wired into CLAUDE.md — run `/plugin` to verify it's active.
- [ ] **Chrome DevTools MCP** — debug runtime issues, inspect network, and profile performance from inside Claude. Requires Chrome running with `--remote-debugging-port=9222`.
- [ ] **deploy-on-aws (AWS Pricing)** — cost estimation for infrastructure decisions. Part of the deploy-on-aws plugin bundle — activate via `/plugin deploy-on-aws`.

### Skills to Know About
- `/gsd-discuss-phase` — lock requirements and decisions for a phase before any code is written. Always start here for new features.
- `/gsd-ui-phase` — generate a UI design contract (UI-SPEC.md) that the planner and executor follow. Required before any frontend phase.
- `/gsd-plan-phase` — turn a discussed phase into a wave-ordered PLAN.md with tasks, tests, and dependency checks. Run after discuss (and ui-phase for frontend work).
- `/gsd-execute-phase` — execute a PLAN.md step by step with atomic commits and checkpoint gates. The main workhorse.
- `/gsd-progress` — check project state and get routed to the next action. Good first command when resuming after a break.
- `/gsd-code-review` — multi-agent code review of the current branch or a specific PR number.
- `/gsd-new-milestone` — spin up a fresh milestone with a roadmap. Used at the start of each v0.x cycle.

## Team Tips

_TODO_

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
