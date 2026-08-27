# ADR 0015: Prospective Forecast-Fitter Specification Without Training or Execution

- Status: Accepted for local reference implementation
- Date: 2026-08-26

## Context

ADR 0014 records that a Phase 8E descriptive reference residual cannot support a validity update.
One blocker is the absence of a registered forecast fitter. Registering an executable or trained
model would also require training-data selection, temporal splits, leakage controls, negative
controls, implementation binding, validation data, uncertainty estimation, and a separate selection
contract. Those gates are not open.

The next bounded slice needs to distinguish a declared future forecast method from the Phase 4
diagnostic fitters and the Phase 8C constant benchmark without retroactively changing any completed
assessment.

## Decision

Add the closed event `forecast.fitter_specification_registered`.

- A specification belongs to one tracked asset and declares one numeric target plus one or more
  numeric, pre-origin feature contracts.
- The only current model family is `LINEAR_REGRESSION`, retained as a specification rather than an
  implementation or model artifact.
- Training uses a declared squared-error objective, but training data, temporal split, negative
  controls, and a per-design cutoff remain required and unbound.
- Point prediction and uncertainty outputs are required but not implemented.
- Registration is prospective only. Retroactive application is prohibited, prior validity
  assessments are unchanged, and no forecast-evaluation design selects the specification.
- Implementation, training, selection, execution, prediction, validation-corpus scoring,
  calibration, empirical validity, and future admissibility remain unopened.
- Network access is false and authority remains `NO_AUTHORITY`.

## Consequences

READIN can now catalog a typed candidate forecast method and its required input, target, temporal,
control, and output boundaries without presenting it as a trained or executable model. A later
contract can bind a specification to a future evaluation design only after the missing training,
split, implementation, validation, and uncertainty prerequisites are explicitly opened.

This Phase 8G slice does not select observations, access data, train a model, provide executable
code, run inference, produce a forecast, estimate uncertainty, create a validation corpus, score a
model, revise the Phase 8F historical assessment, update validity or weights, change admissibility,
begin learning, deploy a service, or grant operational or action authority. It does not complete the
Phase 8 residual-loop exit condition.
