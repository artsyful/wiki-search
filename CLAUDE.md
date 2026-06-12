# CLAUDE.md — Instructions for Claude Code

## Maintaining this file
This file is process instructions for Claude Code — not a deliverable. Design decisions go in DESIGN.md, requirement changes in PRD.md, eval design in EVALS.md, setup/run instructions in README.md. Only record a gotcha
here if it changes how you should work in future sessions, and keep it to one line.

## README instructions
The README.md is the reviewer's entry point — how to run and test the project. 
When to update it: A new setup/run/test command is established → record it. It must contain, in this order:
1. **One-line description** — what the system does and what it's built on
2. **Setup** — exact commands to install deps and configure the API key
3. **Run the CLI** — the 2-3 most useful invocations with real example questions
4. **Run the evals** — command to run the full suite and what the output looks like
5. **Results** — latest eval numbers (update these after every eval run)
6. **Design** — one sentence + pointer to DESIGN.md / EVALS.md. 

## Prompt iteration log
After any change to a system prompt, judge rubric, grader logic, or eval case expectations, append an entry to `PROMPT_ITERATION.md` at the time of the change — including changes that didn't help or that you reverted. Improving or expanding the eval suite itself counts as a change worth logging. Fill in **Result** after the next eval run; never leave it TBD at session end.

### <n>. <one-line summary of the fix> — `<file>`
- **Failure:** <what the eval or author caught, with case ids where relevant>
- **Change:** <the edit — quote the key line for prompt rules; describe it for grader/judge/case changes>
- **Result:** <metric before → after, naming the grader/dimension; or "no effect — reverted>

## GIT
- Always commit directly to the `main` branch. Never create a branch unless I specifically say so.
- Don't create pull requests, unless I specifically say so.

## Code Style
- Return `@dataclass` types from functions with structured results, not plain dicts. Dicts are acceptable at I/O boundaries (JSON in/out, API payloads) but not between internal functions where the shape is known at write time.
- Define string identifiers that cross file boundaries as module-level constants (`EVENT_TYPE = "user.signup"`). Import the constant; never repeat the string.
- Annotate every function parameter, including callbacks and `None` defaults. Use `Callable[[ArgType], ReturnType] | None` for optional callbacks rather than leaving them untyped

