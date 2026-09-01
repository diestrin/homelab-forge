# TASK-012 plan

## Request

a monitoring and alerting system for the forge, capable of sending alerts via ntfy and slack when deployments are failing or the host resources are going to dangerous levels

## Approach

(Refine in Slack thread — this stub was written without Cursor SDK.)

## Out of scope

- Silent prod deploy / kubectl apply to Argo apps
- Merge from Slack

## Deploy

After human merge to `main`, Argo CD syncs (ADR-008).
