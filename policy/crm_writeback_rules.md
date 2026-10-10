# CRM Write-Back Rules (mock document)

## Purpose
Agents can update the CRM, which is powerful and risky. These rules keep customer data safe while still letting agents keep prospect records fresh.

## Customer records are protected
Records with the status customer must never be overwritten by an agent. Agents may add new notes and new activity entries on customer records, but they must not change existing field values such as lifecycle stage, owner, industry, employee count or contract data. If an agent believes a customer field is wrong, it must create a task for the account owner instead.

## Prospect records
On prospect records, agents may update enrichment fields such as industry, employee count, funding stage and technology stack. Each write must store the previous value in the field history so that a human can undo it. Agents must not change the owner field on any record.

## Duplicates
Before creating a new account, agents must search for existing accounts with a similar name. Company names must be compared after removing punctuation and legal endings such as Inc, LLC, Ltd and Corp. If a similar account exists, the agent must update the existing record or ask for human review. Creating a second record for the same company is not allowed, because duplicates cause double outreach and wrong reporting.

## Dry runs
Every new or changed agent must complete a dry run before touching real accounts. The dry run report lists which records would change and which would be blocked. A human reviewer reads the report before launch.

## Rollback
If a live run writes wrong data, RevOps pauses the agent, restores values from field history, and records the incident.
