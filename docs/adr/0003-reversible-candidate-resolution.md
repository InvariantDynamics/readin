# ADR 0003: Reversible Candidate Resolution Without Entity Merge

- Status: Accepted for local reference implementation
- Date: 2026-08-22

## Context

READIN needs to represent the possibility that two entity records refer to the same underlying
object. Treating a name, alias, external identifier, or model suggestion as an automatic merge would
erase disagreement, contaminate downstream history, and turn uncertain identity resolution into an
irreversible fact.

## Decision

Add two closed events: `entity.resolution_candidate_recorded` and
`entity.resolution_candidate_assessed`.

- A candidate relates two distinct known entities as `POSSIBLE_SAME_ENTITY`.
- At least one entity must already be tracked.
- Each candidate contains one or more supporting or challenging signals. Observation signals must
  reference an admitted observation concerning at least one candidate entity.
- Signal verification is explicit: asserted, reference-validated, or entity-record-validated.
  Entity-record validation is limited to exact shared aliases or external identifiers; it does not
  establish identity equivalence.
- Only one candidate may exist for an unordered entity pair.
- Assessments are manual and append-only. Every reassessment must supersede the latest assessment,
  retaining the complete review history.
- Candidate dispositions may remain possible, retain entities separately, reject the match, or
  record a confirmed match that is explicitly not merged.
- `automatic_merge` is always `false`; `merge_state` is always `NOT_MERGED`.
- Candidate and assessment events advance tracked-asset state and participate in hindsight-safe
  reconstruction.
- All events and views remain `NO_AUTHORITY`.

## Consequences

READIN can inspect and revise identity hypotheses without modifying canonical entities or erasing
earlier review decisions. This slice provides no matcher, similarity score, automatic candidate
generation, canonicalization, entity merge, external lookup, or identity authority.

Any future merge capability requires a separate versioned contract, explicit authorization gate,
rollback semantics, negative fixtures, and a new ADR. Candidate assessment alone is never merge
permission.
