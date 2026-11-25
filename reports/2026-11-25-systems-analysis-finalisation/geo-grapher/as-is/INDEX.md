#  — as-is pack



[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC1d | [graph-building](views/graph-building.views.md) | `IMPLEMENTED_VERIFIED` | 36 | 18 | 11 | — | 0 | 0 | 0 | 2 |

## Weakness register

Every weakness found in the as-is, and the to-be element that handles it.

| Id | Kind | In | Weakness | Handled by |
|---|---|---|---|---|

0 weaknesses; 0 not yet handled by the to-be.

## Checks

Errors (0):

Warnings (2):
- graph-building: written use case lacks: Use case name, Brief description, Primary actor, Supporting actors, Preconditions, Trigger, Success guarantee, Minimal guarantee, Open questions
- graph-building: decision d2 ('strata, store ownership, and disk valid?') tests a quantity but declares no boundary values
