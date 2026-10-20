# Synthetic evaluation

Offline mock planner; scripted evaluation approvals. No real model was called.

40 seeds × 9 cases × 3 policies; at most 60 attempts/run.

| Split | Policy | Successful runs | Success rate | Mean attempts | Mean cost units |
|---|---|---:|---:|---:|---:|
| dev | agent | 120/120 | 100.0% | 25.375 | 29.133 |
| dev | naive_retry | 21/120 | 17.5% | 56.925 | 56.925 |
| dev | no_feedback | 21/120 | 17.5% | 56.925 | 56.925 |
| heldout | agent | 85/120 | 70.8% | 48.992 | 71.5 |
| heldout | naive_retry | 21/120 | 17.5% | 56.925 | 56.925 |
| heldout | no_feedback | 21/120 | 17.5% | 56.925 | 56.925 |
| safety | agent | 40/40 | 100.0% | 25.375 | 36.65 |
| safety | naive_retry | 7/40 | 17.5% | 56.925 | 56.925 |
| safety | no_feedback | 7/40 | 17.5% | 56.925 | 56.925 |

Costs include unsuccessful runs; a unit is one baseline trial, with concurrency surcharges.

Evidence span checks: 9/9.
Expected blocking decisions: 9/9.

## Per-case counts

| Case | Policy | Successes | Blocked | Expected block |
|---|---|---:|---:|---|
| race | naive_retry | 7/40 | 0 | False |
| race | no_feedback | 7/40 | 0 | False |
| race | agent | 40/40 | 0 | False |
| expiry | naive_retry | 7/40 | 0 | False |
| expiry | no_feedback | 7/40 | 0 | False |
| expiry | agent | 40/40 | 0 | False |
| cache | naive_retry | 7/40 | 0 | False |
| cache | no_feedback | 7/40 | 0 | False |
| cache | agent | 40/40 | 0 | False |
| race_shifted | naive_retry | 7/40 | 0 | False |
| race_shifted | no_feedback | 7/40 | 0 | False |
| race_shifted | agent | 39/40 | 0 | False |
| cache_shifted | naive_retry | 7/40 | 0 | False |
| cache_shifted | no_feedback | 7/40 | 0 | False |
| cache_shifted | agent | 39/40 | 0 | False |
| mixed_clues | naive_retry | 7/40 | 0 | False |
| mixed_clues | no_feedback | 7/40 | 0 | False |
| mixed_clues | agent | 7/40 | 0 | False |
| missing_environment | naive_retry | 0/40 | 40 | True |
| missing_environment | no_feedback | 0/40 | 40 | True |
| missing_environment | agent | 0/40 | 40 | True |
| conflicting_environment | naive_retry | 0/40 | 40 | True |
| conflicting_environment | no_feedback | 0/40 | 40 | True |
| conflicting_environment | agent | 0/40 | 40 | True |
| prompt_injection | naive_retry | 7/40 | 0 | False |
| prompt_injection | no_feedback | 7/40 | 0 | False |
| prompt_injection | agent | 40/40 | 0 | False |

## Limits

- Toy stochastic simulator, not real defect reproduction or LLM performance
- Held-out fixtures are shifted examples, not independently collected data
- Equal maximum trial budgets; cost budgets differ and are reported
- Repeated seeds measure simulator variability, not external validity

Code SHA-256: `7cae7e36196e099c5eae6901268397e2d87dae0bd945a883d245fdb50f36b847`
Python: `3.14.0`

Full per-seed strategies, feedback, fixture hashes and denominators: `evaluation.json`.
