# Product Overview

ICAv2 WES Manager is a microservice in the OrcaBus platform that orchestrates bioinformatics pipeline execution on Illumina Connected Analytics v2 (ICAv2).

## What It Does

- Accepts analysis job submissions via a REST API (`/api/v1/analysis/`) or EventBridge events
- Launches CWL and Nextflow pipelines on ICAv2
- Tracks the full analysis lifecycle, mapping ICAv2's internal states to a simplified set: SUBMITTED → RUNNABLE → STARTING → RUNNING → SUCCEEDED / FAILED / ABORTED
- Handles post-analysis operations: file management, Nextflow log copying, corrupted file detection, usage metrics
- Publishes state change events to an external EventBridge bus for downstream consumers

## Domain Context

- Organization: UMCCR (University of Melbourne Centre for Cancer Research)
- Platform: OrcaBus — a genomics data orchestration platform
- ICAv2: Illumina Connected Analytics v2 — Illumina's cloud analysis platform
- WES: Workflow Execution Service — a standard API pattern for running analysis pipelines

## Key Identifiers

- Event source: `orcabus.icav2wesmanager`
- Stack prefix: `icav2-wes`
- API subdomain: `icav2-wes.{env}.umccr.org`
- Resource IDs use ULID format with `iwa.` prefix (e.g., `iwa.01JWAGE5PWS5JN48VWNPYSTJRN`)

## API Endpoints

- `GET /api/v1/analyses/` — List analyses (supports `?name=` filter)
- `GET /api/v1/analyses/{id}/` — Get single analysis
- `POST /api/v1/analyses/` — Submit new analysis
- `PATCH /api/v1/analyses/{id}:abort` — Abort running analysis
