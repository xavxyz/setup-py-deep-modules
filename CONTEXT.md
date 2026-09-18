# setup-py-deep-modules

A skill that sets up a Python repository so its packages are deep modules: a public surface in `__init__.py`, implementation behind it, and a checker that fails when anything reaches past it.

## Language

**Target repository**:
The Python repository the skill is run on, as opposed to this one. Everything the skill leaves there is something its owner has to review, keep, or delete.
_Avoid_: external repo, user repo, project

**Proof**:
Watching the check go red on a violation the agent introduced, then green again once it is reverted. Whatever the proof writes into the target repository, it removes.
_Avoid_: validation, smoke test

**Worked example**:
The example package the user chose to take, kept in the target repository as a shape to copy.
_Avoid_: scaffold, sample, billing package

**Proof scaffold**:
The example package written only because the target repository has no private name for the proof to use, and removed when the proof is done.
_Avoid_: worked example, greenfield scaffold
