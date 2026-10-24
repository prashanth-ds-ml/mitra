# PRD: FastAPI + Ollama RAG App

## Problem

Create a local retrieval-augmented demo that proves the agent can wire a small backend, indexing flow, and chat surface together.

## Goals

- Build a local RAG app with FastAPI and Ollama
- Keep all runtime behavior local-first
- Make the retrieval path easy to explain in a demo

## Non-goals

- Multi-tenant auth
- Cloud dependencies
- Production-grade ingestion scale

## Users

- Demo viewers
- Engineers validating local AI app scaffolding

## Requirements

- FastAPI API
- Document ingestion or indexing step
- Retrieval-backed answer endpoint
- Simple UI or API docs path

## Success Criteria

- App runs locally
- Retrieval behavior is visible in the demo
- Build and startup instructions are clear

## Risks

- Overcomplicating retrieval or storage
- Hiding the local-only behavior
- Mixing demo polish with infrastructure work

