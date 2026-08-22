# ADR-0001: Phase 0 Reference Runtime

**Status:** Accepted for the initial repository slice
**Date:** 2026-08-21

## Context

The architecture targets Go for the future control/API plane, Python for analytical fitters,
TypeScript and React for the interface, NATS for event transport, PostgreSQL/PostGIS for
transactional and geospatial state, and object storage for evidence.

Phase 0 has a narrower exit condition: a tracked entity can receive immutable observations with
complete provenance. Deploying the full runtime would obscure that contract and create premature
operational surface.

## Decision

Implement Phase 0 as a Python 3.11 schema-first reference runtime with an append-only local JSONL
ledger and CLI. Keep logical boundaries explicit so the event contracts can later be consumed by a
Go control plane and transported over NATS without moving analytical semantics into the API.

The reference runtime has no network acquisition, service listener, database, distributed event
transport, model runtime, or action authority.

## Consequences

- The first slice is directly inspectable and testable with minimal infrastructure.
- Event and object semantics stabilize before persistence and transport choices become costly.
- JSONL is not the production store and POSIX file locking is not a distributed concurrency model.
- A future runtime change must preserve or explicitly version the v0.1 event contracts.
