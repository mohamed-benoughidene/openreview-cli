# Tweet Thread — Spec 017: Playbook Versioning

**Status:** Draft for review
**Topic:** `openreview` playbook versioning (contract review CLI)
**Format:** 4-post thread, X (Twitter)

---

**1/4**

Rubrics drift and nobody notices. Old reviews get scored against rules you wrote six months later.

**2/4**

We added versioning to playbooks. They're just YAML files — Preferred, Acceptable, Walkaway. Run `openreview precheck contract.pdf` and it locks the version in. Change the file? New version. Old reviews stay put.

**3/4**

Content hash + a counter. v1, v2, whatever. stdlib hashlib + sqlite3, no new deps. Re-run a review from last year — same result.

**4/4**

Three bundled: PreCheck, DealCheck, HireCheck. `--playbook-version v1` to pin one. github.com/mohamed-benoughidene/openreview. 737 tests.

When would this matter for you?
