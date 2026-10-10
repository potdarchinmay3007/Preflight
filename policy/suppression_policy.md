# Suppression and Do-Not-Contact Policy (mock document)

## Purpose
This policy defines which accounts and people must never receive automated outreach. It applies to every agent that sends email, LinkedIn messages or any other outbound message on behalf of the GTM team.

## What counts as suppressed
An account is suppressed when any of the following is true: a person at the account has unsubscribed from marketing email, a person at the account has replied asking not to be contacted, the account is on a legal hold or compliance review, or the account is a competitor flagged by the sales leadership team. Suppression applies to the whole account, not only to the individual who asked.

## How suppression is stored
The suppressed flag lives on the account record in the CRM. Agents must read this flag at run time and must never cache it for longer than one hour. A suppressed account may still receive internal enrichment, such as industry or employee count updates, because enrichment does not contact the customer.

## Removing a suppression
Only a RevOps manager can clear a suppression, and only after written confirmation from the account contact. Agents must never clear a suppression flag themselves, even if a new signal suggests strong buying intent.

## Launch rule
A run that targets one or more suppressed accounts with outreach must not be approved. Remove the suppressed accounts from the target list and simulate the run again. Approval reasons must state that the list was re-checked after removal.

## Audit
Every blocked attempt to contact a suppressed account is logged with the agent name, the account, the time, and the person who reviewed the run. These logs are reviewed by the RevOps lead every Monday.
