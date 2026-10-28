# Constitution

**GOAL.** Every project under this constitution is built from modules that each stand alone. Each module can run by itself. This lets us build the project part by part, test each part by itself, then connect the parts.

This is the constitution of the repo. All work MUST FOLLOW AND COMPLY WITH these principles:
## FIRST PRINCIPLE: Module Boundaries

Split the code into parts so that changing one part does not force you to change the others.

**Rules**

- **B1.** Each module serves one purpose. Everything inside it belongs to that purpose.
- **B2.** A module uses another module only through its public call. It never reaches into the other one's internal variables, file formats or database tables.
- **B3.** Depend on things that change rarely. The business logic does not depend on outside tools that change often, such as an AI provider or a database. They depend on the logic's shape.
- **B4.** Each module hides one decision that might change. If it hides nothing, it may not need to exist.
- **B5.** Prefer deep modules: a small, simple interface that does a lot inside. Do not split into many tiny pieces that must be called in the right order.
- **B6.** Fix the boundary when you see a warning sign: circular imports, a growing `utils.py` or `helpers.py`, one change needing edits in many files, a module you are afraid to touch, a long import list, or the same 6 variables passed through 4 functions.

-Why it matters:
Without boundaries, one small change breaks five unrelated things. You become afraid to touch the code. Progress slows down.
With good boundaries, you can change, replace, or delete a part safely.
-The five core ideas
1. Cohesion: things that belong together stay together. A module has high cohesion when everything inside it serves one purpose.
Good: clause_splitter.py only splits text into clauses.
Bad: helpers.py holds PDF code, date formatting, and API calls.

2. Coupling: parts should know as little as possible about each other. Coupling is how much module A must know about module B.
Low coupling: A calls B.run(text) and does not care how B works.
High coupling: A reaches into B's internal variables, file formats, or database tables.

3. Dependency direction: arrows should point toward stable things
If A imports B, then A depends on B. When B changes, A may break.
Rule: depend on things that change rarely. Do not depend on things that change often.
Example: Your business logic changes slowly. Your choice of AI provider or database changes often. So the AI provider should depend on your logic's shape, not the other way around.

4. Information hiding

Each module should hide one decision that might change.

Example. The decision "we store data in SQLite" is hidden inside storage.py. The rest of the code calls save_report(report). If you move to Postgres, only storage.py changes.

Ask this about every module: what decision does this one hide? If the answer is "nothing", the module may not need to exist.

5. Deep modules beat shallow modules

This idea is from John Ousterhout's book.

A deep module has a small, simple interface and does a lot inside.
A shallow module has a big interface and does little. It just adds names to remember.

Example of shallow: ten tiny classes where you must call all ten in the right order.

Example of deep: one function review_contract(path) that handles the whole job.

Prefer deep. Splitting into many tiny pieces is not the same as good design.

**How to find the right boundaries**

Use these questions, in order.

What will change? AI provider, report format, input type, storage. Each of these wants its own boundary.
What changes together? If two things always change in the same commit, they probably belong together.
What is the core, and what is the edge? The core is your real logic. The edge is anything that talks to the outside world, like files, networks, and the terminal.
Who needs to know this? If only one module needs a detail, hide it there.

**Warning signs your boundaries are wrong**
Circular imports. A imports B and B imports A. The two should probably be one module, or they share a hidden third thing.
A utils.py or helpers.py that keeps growing. It is a dumping ground. Find the real home for each function.
Shotgun surgery. One small change needs edits in many files.
A module you are afraid to touch.
Long import lists at the top of a file. It knows too much.
Passing the same 6 variables through 4 functions. Those variables want to be one object.

## SECOND PRINCIPLE: Data Modeling

**Rules**

- **D1.** Keep raw data safe and unchanged. Save the original input and any outside response exactly as it arrived.
- **D2.** Make derived data rebuildable from the raw data. If you fix a bug, rerun the fixed step on the raw data.
- **D3.** Store each fact once. Other places point to it by an id. A copy is allowed only when speed matters and you can rebuild it. Then it counts as derived data and is labeled that way.
- **D4.** Treat data from outside as untrusted: files, APIs, AI output and user input. Validate it once where it enters, then trust it inside.
- **D5.** Add new fields instead of renaming when you can. New optional fields are safe. Renames break old data.
- **D6.** Change the data shape with migrations: small numbered scripts kept in the repo. Store a schema version number.
- **D7.** Never edit production data by hand without a backup first.
- **D8.** **Only if the project uses AI:** save the AI model's exact response as raw data.

1. The raw and derived rule

Keep raw data safe and unchanged. Make derived data rebuildable.

For contract-checker:

Raw: the original PDF, the AI model's exact response.
Derived: the split clauses, the risk score, the final report.

If you find a bug in your clause splitter, you can rerun it on the raw data. If you only kept the output, the bug is permanent.

2. Store each fact once

This idea is called normalization. In plain words: do not copy the same fact into many places.

Bad: the contract title is copied into every clause row. If the title changes, you must update 200 rows and you will miss one.

Good: the title lives in the Contract. Each Clause holds a contract_id that points to it.

When is copying fine? When speed matters and you can rebuild the copy. Then it is derived data, and you label it that way.

3. Check data at the edges

Data coming in from outside (files, APIs, AI output, user input) is untrusted. Validate it once, at the edge, then trust it inside. For example, Pydantic.

4. Changing data over time
Our data model will change. Plan for it.

-Add, do not rename, when you can. New optional fields are safe. Renames break old data.
-Use migrations. A migration is a small script that moves old data to the new shape. Keep them in your repo, numbered in order.
-Store a schema version. One number saying which shape the data has.
-Never edit production data by hand without a backup first.

## THIRD PRINCIPLE: Core Patterns

**Rules**

- **P1.** Use a pattern only when you can name the problem it solves in this project. Patterns are tools, not goals.
- **P2.** **Layered:** each layer talks only to the layer below it. Use it for a typical app with an interface, rules and storage. Do not use it for a one-way flow of steps. Do not add layers that only pass calls down.
- **P3.** **Pipeline:** data flows through a fixed series of steps, and each step takes input and gives output. Use it for documents, data and AI workflows. Do not use it when steps must talk back and forth a lot. Steps never share hidden state.
- **P4.** **Ports and adapters:** the core defines a port, a small interface for what it needs. An adapter fits a real tool to that port. Use it for things that change or are slow, costly or unreliable, such as AI providers, databases and file systems. Do not use it for a 50-line script. Do not make a port for something that will never change.
Patterns are tools, not goals. Beginners often add patterns because they sound professional. That makes the code worse.

Rule: use a pattern only when you can name the problem it solves in your project.
Pattern 1: Layered

Code is stacked in layers. Each layer only talks to the layer below it.

```
Interface layer   (CLI, web page)
      |
Logic layer       (your real rules)
      |
Data layer        (database, files)
```
Use when: typical apps with a user interface, rules, and storage.
Do not use when: the job is a one-way flow of steps. Use a pipeline.
Trap: layers that just pass calls down and add nothing.
Pattern 2: Pipeline

Data flows through a fixed series of steps. Each step takes input and gives output.

```
PDF -> text -> clauses -> risk flags -> report
```
Use when: processing documents, data, or AI workflows. Very common for AI projects.
Do not use when: steps need to talk back and forth a lot.
Strength: each step can be tested alone. You can inspect the data between steps.
Trap: steps that secretly share hidden state.

Pattern 3: Ports and adapters (also called hexagonal architecture)

This one deserves the most time. It was described by Alistair Cockburn.

Idea: your core logic defines what it needs, in plain terms. The outside world plugs in.

A port is a small interface the core defines. Example: "something that can assess a clause".
An adapter is code that fits a real tool to that port. Example: an adapter for one AI provider.
```
          +------------------------+
  CLI --> |         CORE           | --> LLM adapter
 Web  --> |  (rules, no I/O)       | --> Storage adapter
          +------------------------+
```
Use when: you depend on things that change or are slow, costly, or unreliable. AI providers, databases, file systems.
Do not use when: the project is a 50-line script.
Strength: swap the AI provider by writing one adapter. Test the core without the internet.
Trap: making a port for something that will never change.

## FOURTH PRINCIPLE: Interfaces

Define clearly how parts talk to each other, including what happens when things go wrong.

**Rules**

- **I1.** Name a function by what it does, not how. Use type hints so the inputs and the output are clear.
- **I2.** Avoid boolean flags that change what a function does. Write two functions instead.
- **I3.** Keep inputs few. More than four means the function does too much, or some inputs belong in one object.
- **I4.** Always return the same type. Return an empty list instead of `None` when nothing is found. Return a small named object, not a tuple of five things.
- **I5.** Split failures into two kinds. Expected failures, such as a missing file or a call to an outside service that timed out, get clear named errors. Bugs crash loudly.
- **I6.** Make your own error types, with one base error for everything the project raises on purpose.
- **I7.** Fail fast: check inputs at the start. Never swallow an error silently. Add context to every error. Handle errors at the edge, such as the command line or web layer, not in the core.
- **I8.** Design the error away when you can. Example: deleting something already gone counts as success.
- **I9.** Validate outside data once where it enters, then trust it inside.
- **I10.** Keep the promise stable. Adding an optional input or field is usually safe. Removing or renaming breaks callers. If you must, change all callers in the same commit, and add a version if other people use your code. Mark internal code with a leading underscore.
- **I11.** Write a short contract note on each main module's public function: input, output, errors raised and side effects. If the code and the note disagree, one is a bug.
- **I12.** **Command line:** use clear flag names, such as `--output report.md` instead of `-o`. Exit with code 0 on success and non-zero on failure. Print results to standard output and errors to standard error.
- **I13.** **Config:** load settings once at startup, validate them and pass them in. If a required setting is missing, fail at startup, not halfway through a job.
- **I14.** **Web APIs:** use clear nouns in paths, such as `/contracts/123/clauses`. Return proper status codes: 200 ok, 400 bad input, 404 not found, 500 server bug. Design operations to be idempotent, meaning doing it twice has the same effect as once, so retries are safe. Add a version such as `/v1/` if outside people will use it.
- **I15.** **Any outside service:** a call to an outside service is an interface to something unreliable. Set timeouts. Retry with limits and a pause between tries. Hide the service behind your own small interface (THIRD principle).
- **I16.** **Only if the project uses AI:** ask for structured output and validate it against a schema. Log the raw response (SECOND principle).

Rule 1: Make the signature say a lot

A function signature is its name, inputs, and output.

Bad:

```python
def process(data, flag=False, mode=None):
    ...
```

You cannot tell what this does. What is data? What does flag change?

Better:

```python
def split_clauses(contract_text: str) -> list[Clause]:
    ...
```

Name says the job. Types say the shape. No mystery.

Tips:

Use type hints in Python. Tools can then catch mistakes.
Name by what it does, not how. find_risky_clauses, not loop_and_check.
Avoid boolean flags that change what a function does. Two functions are clearer than one with a switch.
Keep inputs few. More than four is a sign the function does too much, or several inputs belong in one object.
Rule 2: Return data, not surprises
Return the same type every time. Not "a list, or None, or a string".
Prefer an empty list over None when you mean "nothing found".
Do not return a tuple of five things. Return a small named object.
Rule 3: Plan your errors

Errors are part of the interface. Decide on purpose.

Two kinds of failure
Expected failures. The caller can handle them. Example: file not found, AI call timed out.
Bugs. The code is wrong. Example: a function got None where it must never happen.

Handle expected failures with clear, named errors. Let bugs crash loudly.

Make your own error types
```python
class ContractError(Exception):
    """Base for all errors this project raises on purpose."""


class UnreadablePdfError(ContractError):
    pass


class AiResponseInvalidError(ContractError):
    pass
```

Now the CLI can do this:

```python
try:
    report = run_pipeline(path)
except UnreadablePdfError:
    print("Could not read that PDF. Is it scanned?")
except AiResponseInvalidError:
    print("The AI gave a broken answer. Try again.")
```
Error rules
Fail fast. Check inputs at the start. Do not let bad data travel deep.
Never swallow errors silently. A bare except: pass hides bugs for weeks.
Add context. "Failed on clause 14 of contract abc" beats "Failed".
Decide who handles it. Usually the edge (CLI, web layer), not the core.
Better still, design the error away

Ousterhout argues you should shape an interface so some errors cannot happen. Example: delete_report(id). If the report is already gone, treat that as success, because the caller wanted it gone. Now there is one less error for every caller to handle.

Rule 4: Validate at the boundary, trust inside

Check outside data once, where it enters. Inside the core, trust it. This ties to the SECOND principle.

Rule 5: Keep the promise stable

Other code depends on your interface. Changing it breaks them.

Adding an optional input or a new field is usually safe.
Removing or renaming is a breaking change.
If you must break it, change all callers in the same commit. If other people use your code, add a version.

Separate what is public (promised) from what is internal (free to change). In Python, a leading underscore, like _helper, marks internal.

Special interfaces to know
Command line
Use clear flag names. --output report.md beats -o.
Return exit code 0 for success and non-zero for failure.
Print results to standard output and errors to standard error.
Config
Load settings once at startup, validate, and pass them in.
Fail at startup if a required setting is missing, not halfway through a job.
Web APIs (short version)
Use clear nouns in paths. /contracts/123/clauses.
Return proper status codes. 200 ok, 400 bad input, 404 not found, 500 server bug.
Idempotent means doing it twice has the same effect as once. Design operations this way when you can. It makes retries safe.
Add a version, like /v1/, if outside people will use it.
AI model calls

This one matters for AI builders. A model call is an interface to something unreliable.

Ask for structured output and validate it against a schema.
Set timeouts. Never wait forever.
Retry with limits and a pause between tries.
Hide the provider behind your own small interface (THIRD principle).
Log the raw response so you can debug and rebuild (SECOND principle).
```python
def assess(self, clause: Clause) -> RiskFlag:
    raw = self.client.ask(f"Assess the risk of: {clause.text}", timeout=30)
    try:
        data = RiskFlagInput.model_validate_json(raw)
    except ValueError as e:
        raise AiResponseInvalidError(f"clause {clause.id}: {e}") from e
    return make_flag(clause.id, data.level, data.reason, self.client.model_name)
```
Write the contract down

For each main module, write a short note at the top.

```python
def split_clauses(contract_text: str) -> list[Clause]:
    """Split contract text into clauses.

    Input:   plain text, non-empty.
    Output:  clauses in document order. Empty list if none are found.
    Raises:  ValueError if the text is empty.
    Effects: none. Does not read or write files.
    """
```

That block is the interface. If the code and the note disagree, one is a bug.

## FIFTH PRINCIPLE: Testability

Design code that is easy to check, and use tests to find bad architecture early.

**Rules**

- **T1.** Keep the core pure: the same input gives the same output, and it touches no files, network, clock or screen.
- **T2.** Push side effects to thin edge modules. Do not let a function grab its own database, clock or outside client. Pass them in.
- **T3.** Prefer fakes (simple working stand-ins) over mocks (stand-ins that record how they were called).
- **T4.** Use a mix of tests: many unit tests on the core, a few integration tests with real storage, for example a SQLite file in a temporary folder, and one or two end-to-end tests with a tiny sample input and a fake of any outside tool.
- **T5.** Test behavior at the boundaries, not the inside. Ask: "If someone else rewrote this module, what would they have to keep true?"
- **T6.** Good targets: the main promise of each public function, edge cases, each expected error, and every bug you already fixed. Poor targets: private helpers, the exact number of calls, and glue code with no logic.
- **T7.** **Only if the project uses AI:** test everything around the model with a fake: parsing, validation, retries and error handling. Test your parser against saved real responses. Check shape, not exact words.
- **T8.** **Only if the project uses AI:** keep a small set of real examples with known good answers. Run it now and then to track quality, apart from the fast tests, because it costs money and varies.
- **T9.** Test the architecture too: check that the core never imports from adapters, treat a circular-import crash as a real signal, and run the tests in CI.
- **T10.** When testing hurts, fix the design. Do not just write a bigger test.

1. Keep the core pure

A pure function gives the same output for the same input and does nothing else. No files, no network, no clock, no printing.

Pure functions are the easiest thing in programming to test.

```python
def count_high_risks(flags: list[RiskFlag]) -> int:
    return sum(1 for f in flags if f.level == RiskLevel.HIGH)
```

Test:

```python
def test_count_high_risks():
    flags = [
        make_flag("c1", RiskLevel.HIGH),
        make_flag("c2", RiskLevel.LOW),
        make_flag("c3", RiskLevel.HIGH),
    ]
    assert count_high_risks(flags) == 2
```

No setup. No cleanup. Runs in a millisecond.

2. Push side effects to the edges

Side effects are file access, network calls, and the current time. Keep them in thin edge modules (THIRD principle). Keep the core pure.

This is the same idea as ports and adapters. Good architecture and good testability are the same thing seen from two sides.

3. Pass things in

Do not let a function grab its own database, clock, or AI client. Pass them in (dependency injection, THIRD principle).

Hard to test:

```python
def assess_all(clauses):
    client = OpenAiClient(api_key=os.environ["KEY"])   # grabs its own client
    return [client.ask(c.text) for c in clauses]
```

Easy to test:

```python
def assess_all(clauses, assessor):                      # receives it
    return [assessor.assess(c) for c in clauses]
```

Now a test passes a fake assessor. No key, no internet, no cost.

Fakes versus mocks
A fake is a simple working stand-in. Example: an assessor that always returns "low".
A mock is a stand-in that records how it was called, so you can check the calls.

Prefer fakes. Mocks tie your tests to how the code works inside. When you refactor, the tests break even though the behavior is fine.

The testing levels
| Level | Tests | Speed | Count |
|---|---|---|---|
| Unit | One function or module alone | Very fast | Many |
| Integration | Several parts together, with real storage | Fast to medium | Some |
| End to end | The whole program, as a user runs it | Slow | Very few |

For a solo project, a practical mix is:

Many unit tests on the core.
A few integration tests with a real SQLite file in a temporary folder.
One or two end-to-end tests with a tiny sample input and a fake AI.
What to test

Test behavior at the boundaries, not the inside.

Ask: "If someone else rewrote this module, what would they have to keep true?" Test exactly that.

Good targets:

The main promise of each public function.
Edge cases. Empty input, huge input, weird characters.
Each expected error (FOURTH principle).
Bugs you have already fixed. Add a test so they stay fixed.

Poor targets:

Private helper functions.
The exact number of times something was called.
Code that is just glue with no logic.
Testing AI output

AI output is not the same every time. You cannot test it like a normal function.

Test everything around the model with a fake. Parsing, validation, retries, error handling.
Save real responses as sample files (called fixtures). Test your parser against them.
Check shape, not exact words. Example: "level is one of low, medium, high", not "reason equals this sentence".
Keep a small set of real examples with known good answers and run them now and then to track quality. This is separate from your normal fast tests, because it costs money and varies.

Testing the architecture itself

You can also test the rules from the FIRST principle.

Import rules. A tool called import-linter can check that your core never imports from adapters/. Check its current docs for setup. Without a tool, a simple test can scan files for forbidden imports.
Circular imports. Python will often crash on these. Treat a crash as a real signal.
Run tests in CI (an automatic check on every push) so rules do not rot. GitHub Actions is free for small projects. Check current limits.
Tests as a design smell detector
| Pain while testing | What it usually means |
|---|---|
| Must set up 10 things first | The module knows or needs too much |
| Cannot test without internet | Side effect sits in the core |
| Must mock many things | Too many dependencies, boundary is wrong |
| Tests break after harmless refactor | Tests check the inside, not behavior |
| Hard to name the test | The function does more than one thing |

When testing hurts, fix the design. Do not just write a bigger test.

## SIXTH PRINCIPLE: Standalone Modules

**Rules**

- **S1.** Every module runs by itself. It has a terminal command that runs it alone on a sample input and gives an output you can open and read.
- **S2.** Every module has its own tests. They run without the other modules.
- **S3.** Every module writes down its input shape and its output shape. A shape is a description of what the data looks like when it goes in or comes out.
- **S4.** This constitution does not choose how modules pass data to each other, such as files, function calls or an API. Each project chooses its own way and records it.

**Why:** we build and test part by part, then connect. A module that cannot run alone cannot be tested alone.
