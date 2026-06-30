# Draft Edits: 005-cli-wizard-redesign

## plan.md changes
Minimal impact. The wizard refactoring (replacing `Prompt.ask()` with questionary) doesn't own the slot list — that's S-4's domain.

No changes needed to the wizard plan itself. The wizard step loop should query S-4's active/required slots rather than hardcoding "5 steps of 5".

## tasks.md changes
No task changes needed. S-5 tasks operate on the SetupWizard's public API, which remains unchanged (the slot loop detail is internal to S-4).
