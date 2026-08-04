# GCIHS Memo Management System — Comprehensive Training Manual

**System reviewed:** `memo_management_system` on `portal.gcihs.edu.gh`  
**Manual revision:** 3 August 2026  
**Audience:** memo originators, approvers, recipients, action-point assignees, executives, memo managers, administrators, trainers, and auditors

> This manual describes the system as it is actually configured and coded. A final section identifies configuration and governance issues that management should decide before organisation-wide training.

## Learning Outcomes

At the end of training, participants should be able to:

- explain the difference between drafting, approving, circulating, acknowledging, and completing an action point
- create a valid memo with recipients, references, attachments, and action points
- route an approval-required memo to the correct approver
- approve or reject a memo without editing its business content
- acknowledge an approved memo and update assigned actions
- locate pending, urgent, rejected, and approved memos from the workspace and report
- print the official memo and interpret its routing audit trail
- recognise which actions are permitted for their role and when to escalate an access problem

## Quick Process Map

```text
Originator creates Draft
          |
          +-- Approval required --> Pending Approval
          |                              |
          |                       Approve | Reject
          |                              |
          |                         Approved / Rejected
          |                                      |
          |                            Correct and resubmit
          |
          +-- No approval required --> Approved and Circulated

Approved memo --> recipient acknowledgement (if required)
              --> action-point follow-up
              --> governance monitoring and official print
```

This manual explains how to use the Memo Management System as it is currently implemented in this app. It is intended for end users, approvers, and administrators working inside the `Memo Management` workspace.

## Purpose

The system is used to:

- create formal internal memos
- route memos for approval
- circulate approved memos to named recipients
- collect recipient acknowledgements when required
- assign follow-up action points
- link memos to related ERPNext records such as `Material Request` and `Purchase Order`
- monitor memo activity through routing history, print output, and the governance report

## System Overview

The app installs a workspace named `Memo Management` with these main entry points:

- `Memo`: create, review, approve, circulate, acknowledge, and track memos
- `Memo Settings`: configure defaults, access behavior, approval behavior, and notification behavior
- `Memo Governance Report`: review memo volume, approvals, acknowledgements, and open or overdue action points

The app also installs the `Official Memo` print format as the default print layout for memos.

## Roles and Responsibilities

The app creates these working roles during install or migrate:

- `Memo User`
- `Memo Approver`
- `Memo Manager`
- `Memo Administrator`

`System Manager` also has full access.

### Memo User

Typical responsibilities:

- create new memos
- edit their own memos while the memo is still `Draft` or `Rejected`
- submit a memo for approval
- read memos where they are the owner, approver, or a recipient
- acknowledge memos assigned to them when acknowledgement is required
- update action points assigned to them

### Memo Approver

Typical responsibilities:

- open memos in `Pending Approval`
- approve and circulate a memo
- reject a memo with remarks
- re-circulate an already approved memo when needed

### Memo Manager and Memo Administrator

Typical responsibilities:

- review all memos across the system
- manage settings and access strategy
- review governance reporting
- assist with recirculation and operational control

## Before Training Starts

Administrators should confirm the following:

- each participating staff member has a `User`
- each participating staff member has an `Employee` linked to that user
- each employee who needs automatic approval routing has a valid `Reports To` value in HR
- the correct desk roles have been assigned
- `Memo Settings` has been reviewed and confirmed

If `Automatically Grant Memo Access to Employee Users` is enabled, the system will add the memo user role to active employees with linked users.

## Memo Lifecycle

The active standard Frappe workflow is `Memo Approval Workflow`. It uses the Memo `Status` field as its workflow-state field. The normal workflow is:

1. `Draft`
2. `Pending Approval` if approval is required
3. `Approved` after approval or after direct circulation when approval is disabled
4. `Rejected` if the approver rejects the memo

`Cancelled` exists as a status value but is not part of the normal user training path in the current implementation.

The standard Workflow controls which state transition is available. A synchronous transition task then invokes the Memo controller to perform routing-history, circulation, acknowledgement, audit, and notification work in the same transaction. `Re-circulate Memo`, `Acknowledge Receipt`, and `Update Action Point` remain custom Memo actions because they do not change workflow state.

## Creating a Memo

Open `Memo Management > Memo` and click `Add Memo`.

### Step 1: Complete the Identity Section

Key fields:

- `Series`: defaults to the memo naming series, normally `MEMO-.YYYY.-`
- `Status`: system-managed
- `Memo Category`: for example `Administrative`, `Finance`, or `Operations`
- `Priority`: `Normal`, `Low`, `High`, or `Urgent`
- `Confidentiality`: `Internal`, `Confidential`, or `Restricted`
- `Requires Approval`: controls whether the memo goes through approver review

### Step 2: Review the Origin Section

The system pulls origin details from the current user’s linked employee record where available:

- `Origin Employee`
- `From`
- `Originator Designation`
- `Department`
- `Company`

The user normally enters:

- `Memo Date`
- `Effective Date` if needed

Rule:

- `Effective Date` cannot be earlier than `Memo Date`

### Step 3: Enter the Memo Content

Required fields:

- `Subject`
- `Content`

Optional field:

- `Summary`

Use `Summary` for a short executive overview. Use `Content` for the full body of the memo.

### Step 4: Add Recipients

Every memo must have at least one recipient row, and at least one row must be of type `To`.

Recipient row fields include:

- `Recipient Type`: `To` or `Cc`
- `Employee`
- `Employee Name`
- `User ID`
- `Designation`
- `Department`
- `Official Mail`
- `Requires Acknowledgement`
- `Acknowledgement Due Date`
- `Acknowledgement Status`

Important rules:

- every recipient row must point to a valid employee
- the same employee cannot appear twice on one memo
- at least one recipient must be `To`

### Step 5: Decide on Acknowledgement

If `Require Recipient Acknowledgement` is enabled:

- the memo gets an `Acknowledgement Due Date`
- recipient rows inherit the acknowledgement requirement by default
- acknowledgement status starts as `Pending Circulation`
- after approval and circulation, acknowledgement status changes to `Pending`

Rule:

- acknowledgement due dates cannot be earlier than the memo date

### Step 6: Add Action Points if Follow-up Is Needed

Action points are optional, but each row must be complete if added.

Action point fields:

- `Action Title`
- `Assigned Employee`
- `Assigned User`
- `Assigned Designation`
- `Due Date`
- `Priority`
- `Status`
- `Action Details`
- `Completion Notes`

Rules:

- each action point must have a title, assignee, and due date
- due date cannot be earlier than the memo date
- status must be `Open`, `In Progress`, `Completed`, or `Cancelled`
- the same action title cannot be duplicated for the same assigned employee

### Step 7: Link Related Documents and Attachments

Use this area to connect the memo to supporting records.

Available fields:

- `Material Request`
- `Purchase Order`
- `Primary Attachment`
- `Additional Related Documents`

Each related document row must include:

- `Relation Type`
- `Reference DocType`
- `Reference Document`
- optional `Remarks`

Rule:

- referenced documents must exist
- the same related document cannot be added twice

### Step 8: Save the Draft

When the memo is saved, the system also captures digital sign-off information such as:

- `Prepared By`
- `Prepared On`

Standard users can only edit their own memos while the memo is in `Draft` or `Rejected`.

## Submitting a Memo

When a saved memo is still editable, the form's `Actions` menu shows one of these standard workflow actions:

- `Submit for Approval`
- `Approve and Circulate`

### If Approval Is Required

When the user selects `Submit for Approval` from `Actions`:

- the memo moves to `Pending Approval`
- the approver is notified
- routing history records `Submitted for Approval`

If the `Approver` field is blank, the system attempts to default it from the current employee’s `Reports To` manager. If no approver can be determined, the memo cannot be submitted until an approver is set.

### If Approval Is Not Required

When the user selects `Approve and Circulate` from `Actions`:

- the memo moves directly to `Approved`
- approval details are stamped automatically
- circulation details are stamped automatically
- recipients are notified immediately
- routing history records `Approved and Circulated`

## Approving or Rejecting a Memo

When an authorized approver opens a memo in `Pending Approval`, the form's `Actions` menu shows:

- `Approve Memo`
- `Reject Memo`

### Approve Memo

The form asks for optional approval remarks before applying the standard workflow action.

Result:

- status changes to `Approved`
- `Approved By` and `Approved On` are recorded
- circulation begins immediately
- recipient acknowledgement rows move to `Pending` where applicable
- recipients are notified
- the memo owner is notified
- routing history records `Approved and Circulated`

### Reject Memo

The form requires rejection remarks before applying the standard workflow action.

Result:

- status changes to `Rejected`
- rejection remarks are required
- the memo owner is notified
- routing history records `Rejected`

After rejection, the memo owner can edit the memo and submit it again.

## Re-circulating an Approved Memo

An approved memo can be sent out again using `Re-circulate Memo`.

Who can do this:

- the memo owner
- the named approver
- users with privileged approval or global roles

Result:

- circulation details are refreshed
- recipients are notified again
- unacknowledged acknowledgement rows return to `Pending`
- already acknowledged rows remain acknowledged
- routing history records `Re-circulated`

## Acknowledging a Memo

Recipients see `Acknowledge Receipt` when all of the following are true:

- the memo is `Approved`
- they are listed as a recipient through their employee record
- their recipient row requires acknowledgement
- they have not already acknowledged the memo

Result:

- acknowledgement status becomes `Acknowledged`
- `Acknowledged By` and `Acknowledged On` are recorded
- optional acknowledgement remarks are stored
- the memo owner is notified
- the approver is also notified if one is recorded
- routing history records `Acknowledged`

## Updating Action Points

The system shows `Update Action Point` when the user has at least one open action point they are allowed to update.

Who can update action points:

- the assigned employee’s linked user
- the memo owner
- users with approval or global access roles

Available status updates:

- `Open`
- `In Progress`
- `Completed`
- `Cancelled`

Result:

- the selected action point status is updated
- `Completed By` and `Completed On` are stamped when status becomes `Completed`
- the memo owner is notified
- the assigned user is notified
- the approver is notified if one exists
- routing history records `Action Point Updated`

## Notifications and Routing History

The system creates notification log entries for memo events such as:

- submission for approval
- approval
- rejection
- circulation
- acknowledgement
- action point updates

If email notifications are enabled in `Memo Settings`, the system also sends email to recipient addresses captured from the employee record.

Routing history is read-only and acts as the memo audit trail.

## Printing an Official Memo

Use the standard print action on a memo to generate the `Official Memo` format.

The print layout includes:

- memo number and status
- date, sender, department, priority, and confidentiality
- recipients
- summary and content
- action points
- related documents
- primary attachment reference
- digital sign-off
- routing history

## Using the Memo Governance Report

Open `Memo Management > Memo Governance Report`.

Available filters:

- `From Date`
- `To Date`
- `Department`
- `Status`
- `Priority`
- `Approver`

The report shows:

- memo number
- memo date
- subject
- department
- status
- priority
- originator
- approver
- total recipients
- acknowledged recipients
- open action points
- overdue action points
- circulated on

Use this report for operational monitoring, acknowledgement follow-up, and overdue action tracking.

## Memo Settings

Open `Memo Settings` to control system defaults.

### Access Defaults

- `Automatically Grant Memo Access to Employee Users`
- `Default Memo User Role`
- `Limit Standard Users to Their Own Memos`
- `Require Approval by Default`
- `Require Recipient Acknowledgement by Default`
- `Enable Email Notifications`

### Document Defaults

- `Default Naming Series`
- `Default Confidentiality`
- `Default Priority`
- `Default Acknowledgement Window (Days)`

### Privileged Roles

- `Roles With Access to All Memos`
- `Roles That Can Approve Any Memo`

## Access Rules to Train Users On

If employee scope is enabled, a standard user can normally access only memos where they are:

- the memo owner
- the approver
- a listed recipient

Important practical consequences:

- a user without a linked employee record may not be able to see recipient memos
- acknowledgement depends on recipient rows matching the user through the employee record
- automatic approver selection depends on the origin employee’s `Reports To` value

## Workflow Administration

`Memo Approval Workflow` is installed and synchronized by the app during installation and migration. It uses `Status` as the workflow-state field and derives privileged transitions from the role tables in `Memo Settings`.

All state-changing transitions must retain the synchronous `Memo Workflow Side Effects` transition task. Administrators should not remove it or create an unhandled shortcut to `Approved`, because the task is what connects the standard state transition to circulation, acknowledgement activation, routing history, audit entries, and notifications. Permanent workflow changes should be implemented in the app setup code and applied through migration.

## Common Validation Errors

Users should understand these common save or submit failures:

- `Subject is required.`
- `Memo content is required.`
- `Add at least one recipient before saving the memo.`
- `Add at least one primary recipient of type To.`
- `Duplicate recipient detected`
- `Acknowledgement due date cannot be earlier than the memo date.`
- `Effective date cannot be earlier than the memo date.`
- `Set an approver before submitting this memo for approval.`
- `Each action point must include an action title.`
- `Each action point must include an assigned employee.`
- `Each action point must include a due date.`
- `Related document ... does not exist.`

## Recommended Training Flow

Run training in this order:

1. Administrator reviews `Memo Settings`, roles, employee links, and approver hierarchy.
2. Memo user creates a draft memo with recipients and one action point.
3. Memo user submits the memo for approval.
4. Approver approves the memo and checks circulation.
5. Recipient acknowledges the memo.
6. Assigned staff member updates the action point to `In Progress` and then `Completed`.
7. Manager reviews the same memo in the `Memo Governance Report`.
8. Trainer prints the memo using the `Official Memo` format and reviews the routing trail.

## Suggested Practice Exercise

Use this simple lab during onboarding:

- create a memo with category `Operations`
- set one `To` recipient and one `Cc` recipient
- require acknowledgement
- add one action point due three days after the memo date
- attach one related document such as a `Material Request`
- submit for approval
- approve it as the approver
- acknowledge it as the primary recipient
- close the action point as the assignee
- verify the memo in the governance report

This exercise covers the full working path of the current app.
