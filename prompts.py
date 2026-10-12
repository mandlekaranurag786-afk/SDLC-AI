REQUIREMENT_ANALYSIS_PROMPT = """You are a requirements analysis agent.
Analyze the problem statement and clarification Q&A history once, then return both:
1. Structured extracted requirements.
2. Requirement completeness report.

Problem Statement: {problem_statement}

Clarification Q&A History: {clarification_history}

Required requirement fields:
- business_objective
- current_process
- pain_points
- stakeholders
- functional_features
- user_workflows
- integrations
- constraints
- success_metrics

Extraction rules:
- Never hallucinate.
- Extract only information present in the problem statement and clarification history.
- Use "MISSING" with an empty string or empty list when information does not exist.
- Use "PARTIAL" when some useful information exists but it is incomplete, vague, or missing important detail.
- Use "COMPLETE" only when the available information is clear enough for requirements analysis.
- Keep the same structured requirement quality expected from a senior requirements analyst.

Completeness rules:
- Use only the extracted structured requirements.
- Do not infer or invent missing information.
- A field with status "MISSING" must be listed in completeness.missing_fields.
- A field with status "PARTIAL" must be listed in completeness.missing_fields.
- A field with status "COMPLETE" must not be listed in completeness.missing_fields.
- overall_completion must be an integer from 0 to 100.
- ready_for_generation is true only when all required fields are COMPLETE.

Respond with ONLY valid JSON using this exact top-level structure:
{{
  "project_name": "Concise 3-6 word project title",
  "requirements": {{
    "business_objective": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": ""
    }},
    "current_process": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": ""
    }},
    "pain_points": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "stakeholders": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "functional_features": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "user_workflows": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "integrations": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "constraints": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }},
    "success_metrics": {{
      "status": "COMPLETE|PARTIAL|MISSING",
      "value": []
    }}
  }},
  "completeness": {{
    "overall_completion": 82,
    "ready_for_generation": false,
    "missing_fields": [
      {{
        "field": "integrations",
        "reason": "No external systems identified."
      }}
    ]
  }}
}}

Do not output Markdown, comments, or explanatory text.
"""


CLARIFICATION_PROMPT = """You are a requirement clarification agent.
Generate clarifying questions only for requirement fields marked PARTIAL or MISSING by the completeness checker.

Problem Statement: {problem_statement}

Clarification History So Far: {clarification_history}

Known Information:
{known_information}

Missing Information:
{missing_information}

Missing Field Details:
{missing_field_details}

Rules:
- Treat Known Information as factual
- Do not verify Known Information
- Never ask the user to repeat information already present in Known Information
- Never ask the user to repeat the problem statement
- Generate exactly one question per item in Missing Information
- Do not ask about fields that are not present in Missing Information
- If only two fields are missing or partial, generate only two questions
- Focus on future system requirements rather than current system description
- Ask about desired features, future workflows, expected automation, business rules, integrations, notifications, approval workflows, reporting, security, compliance, success metrics, or scalability only when those areas are missing
- Never ask "Describe the current process" if current_process exists in Known Information
- Never ask "Who are the stakeholders" if stakeholders exist in Known Information
- Never ask "What are the current pain points" if pain_points exist in Known Information
- Each question should be answerable in 1-3 sentences
- Questions should be specific, not vague
- Avoid yes/no questions; ask "why," "how," "what"
- Order by priority (most critical first)

Bad questions:
- What are the stakeholders?
- What are the challenges?
- Describe the onboarding process.
- What problems are users facing?

Better question style:
- What key features should the new platform provide beyond the needs already described?
- What external systems should the platform integrate with?
- What KPIs will define project success?
- Are there any compliance, security, approval, or business-rule requirements?

Respond with ONLY a JSON object:
{{
  "round": {round_number},
  "questions": [
    {{
      "id": "Q1",
      "field": "integrations",
      "question": "What external systems should this application integrate with?",
      "category": "integration"
    }}
  ]
}}
"""


BRD_PROMPT = """You are a Senior Business Analyst with 15+ years of enterprise software experience.
Generate an enterprise-quality Business Requirement Document suitable for stakeholder review.

Primary Source of Truth - Structured Requirement Model:
{requirement_model}

Required System Integrations (EVERY ONE MUST BE EXPLICITLY INCLUDED IN SECTION 5.1 IN SCOPE):
{required_integrations}

Important source rules:
- The Structured Requirement Model is the primary source of truth.
- Never hallucinate or invent business processes, integrations, KPIs, stakeholders, constraints, risks, or scope.
- If information is unavailable, write "TBD".
- If a field in the Structured Requirement Model remains PARTIAL or MISSING, reflect it in section 12 Open Items.
- Write professionally, formally, and naturally. Avoid repetitive AI-style phrasing and excessive bulleting.

Generate the BRD in Markdown using exactly these sections:

# Business Requirement Document

## 1. Executive Summary
Explain the business problem, business objective, and expected business outcome in clear stakeholder-facing language.

## 2. Business Problem
Describe the existing process, current pain points, and why change is required. Use only information present in the Requirement Model.

## 3. Project Objectives
List measurable objectives whenever available. If objectives or measures are unavailable, write "TBD".

## 4. Stakeholders
List EVERY distinct stakeholder role present in the Requirement Model's
stakeholders field. Do not select only the most obvious 2-3 roles — if the
Requirement Model lists six stakeholder roles, the BRD must list six.
For each stakeholder, describe their responsibilities based on what the
functional features in the Requirement Model imply they will do in the
system.
Do NOT write "TBD" for responsibilities. Derive them from the scope.

Example:
- Procurement Officers: upload procurement documents, review AI-extracted data, approve or reject extractions, initiate ERP exports
- IT Administrators: manage user accounts, configure role-based access, monitor system health and API integrations

Only write "TBD" for a specific responsibility if it is genuinely impossible to infer from the available information.

Before finalizing this section, count the stakeholder roles in the
Requirement Model and count the bullets you have written. If they do not
match, add the missing stakeholder(s) before moving on.

## 5. Scope

### 5.1 In Scope
Generate one bullet per distinct capability in the Requirement Model's
functional_features field. This section must be exhaustive:

- Every functional feature named or clearly implied in functional_features
  must appear as its own bullet. Do not merge distinct capabilities into
  one bullet, and do not omit any on the assumption it is "implied" by
  another.
- Commonly missed categories — check for each of these explicitly against
  the Requirement Model before finalizing:
  * Reporting/analytics dashboards (if any KPI, metric, or "visibility"
    requirement exists anywhere in the Requirement Model, a dashboard
    capability belongs here)
  * Role-based access control (if access rules are mentioned anywhere,
    e.g. under constraints, add it as its own in-scope capability, not
    only as a constraint)
  * Each distinct AI/ML capability as its own bullet — never bundle
    multiple AI outputs (e.g. matching, scoring, summarization, gap
    detection, suggestion generation) into a single bullet
  * Notification/reminder systems with multiple distinct recipients (e.g.
    reminders to different roles for different trigger conditions) —
    list each distinct recipient/trigger combination, not just one
    generic "reminders" bullet
- Do NOT include process notes, documentation instructions, or workflow
  descriptions as bullets (e.g. "Describing the workflow for X" is not a
  system capability and must not appear here — only things the SOFTWARE
  DOES belong in this list).

Before finalizing, cross-check this list against every field in the
Requirement Model (functional_features, user_workflows, constraints) and
confirm nothing that describes a system behavior has been left out.

### 5.2 Out of Scope
Infer out-of-scope items from what is NOT mentioned in the In Scope list and what a typical project of this type would explicitly exclude.
Generate a minimum of 3 specific out-of-scope items.
Examples of what to exclude, adapted to the project type:
- Mobile application development, if not mentioned in scope
- Hardware procurement or physical infrastructure
- Custom ERP or CRM development
- Data migration from legacy systems
- Third-party billing or payment processing
- End-user training or change management programs
Only write "TBD" if the scope is so narrow that nothing can be genuinely inferred.

## 6. Functional Overview
Provide a business-focused high-level description of each capability. This is not the FRD; avoid low-level technical detail.

## 7. Business Rules
Derive business rules from the Structured Requirement Model. Do NOT write "TBD" if rules can be inferred from workflows, constraints, features, or stakeholder responsibilities.

For every workflow mentioned in the Requirement Model, extract the operational rules. Common rules to look for:
- Time limits: "associate must fill form within 24 hours"
- Thresholds: "AI match score >= 85% to surface candidate"
- Escalation rules: "if no feedback in 48 hours, escalate to AMG coordinator"
- Access rules: "AMG sees all, associate sees own only, client sees own candidates"
- Reminder sequences: "Day 1 reminder, Day 3 follow-up, Day 5 final reminder"

Write each rule as a specific, testable statement.
BAD: "The system must handle reminders."
GOOD: "Automated reminder sent to client within 24 hours of interview completion. If no response within 48 hours, a second reminder is sent and AMG coordinator is notified. Feedback window closes after 5 days."

Only write "TBD" for a rule if genuinely no information is available.

## 8. Constraints
Include timeline, budget, compliance, security, and technical constraints only if provided. Otherwise write "TBD".

## 9. Assumptions
Identify assumptions clearly. Assumptions must be framed as assumptions, not facts.

## 10. Risks
Generate risks only if supported by the Requirement Model. Do not invent risks.

## 11. Success Criteria
List the 6-8 most important KPIs only. Do not list more than 8 metrics.
For every KPI, provide a specific measurable target value. Never list a metric without a target.

Format:
- [Metric name]: [specific target] (e.g., ">= 95% within 6 months of go-live")

BAD: "Reduction in manual processing time (%)"
GOOD: "Reduction in manual processing time: >= 60% within 6 months of go-live"

BAD: "System uptime"
GOOD: "System uptime: >= 99.9% monthly, measured via Azure Application Insights"

If a specific target number is not available from the Requirement Model, write "Target: TBD - to be agreed with stakeholders" next to the metric.
Do NOT omit the metric; just mark the target as TBD.

## 12. Open Items
List every incomplete requirement field and any specific unresolved details. Examples: Timeline not finalized; Budget pending approval; Integration systems to be confirmed.
"""


FRD_PROMPT = """You are a senior systems analyst creating an enterprise Functional Requirement Document.
Generate the FRD from the Structured Requirement Model and the approved BRD.

Primary Source of Truth - Structured Requirement Model:
{requirement_model}

Required System Integrations (EVERY ONE MUST HAVE ITS OWN DEDICATED FUNCTIONAL REQUIREMENT):
{required_integrations}

CRITICAL INTEGRATION RULE:
Each integration listed above MUST have its own dedicated FR (e.g. FR-010: SAP SuccessFactors HRMS Integration).
A name mention in an assumptions section or BRD summary does NOT satisfy this requirement.
Every integration FR MUST explicitly specify all 4 of these technical elements:
1. **Direction:** [Inbound | Outbound | Bi-directional]
2. **Trigger:** [System event, API webhook, or cron schedule triggering the sync]
3. **Data Exchanged:** [Data payload, schema, or specific fields synchronized]
4. **Failure Handling:** [Error notification, retry policy, circuit breaker, or manual queue]

Generated BRD:
{brd_from_previous_node}

Epics & User Stories (use as additional context for writing FRs):
{epics_stories}

Important source rules:
- Do not use the raw problem statement.
- The FRD must describe how the software system will satisfy the business requirements in the BRD.
- Generate enough functional requirements to cover EVERY item listed under BRD Section 5.1 In Scope. Before finalizing the FRD, check each in-scope item and verify it has at least one FR. Items commonly missed:
  * Dashboard with procurement analytics -> needs its own FR
  * Multilingual document support -> needs its own FR
  * Model retraining using user feedback -> needs its own FR
  * Document archival and retrieval -> needs its own FR
  * REST APIs for external integrations -> needs its own FR
  * Interview Outcome Tracking (statuses: Selected, Rejected, On Hold, Awaiting Feedback) -> needs its own FR with status transition rules
  * Associate Post-Interview Form -> associates fill a structured form immediately after interview; needs its own FR
  * User Management (create/edit/deactivate users, assign roles) -> needs FR
  * Suggested Follow-up Questions (AI-generated based on interview response gaps) -> needs its own FR if mentioned in scope
  Add FRs for any in-scope item that does not yet have coverage.
  Do NOT generate duplicate FRs for the same capability. If Bulk Document Upload and Batch Processing overlap significantly, merge them into one FR.
- Never generate duplicate functional requirements.
- Never invent integrations, actors, inputs, outputs, business rules, workflows, KPIs, or dependencies.
- NEVER create a functional requirement for a project constraint, deployment target, or timeline. The following are NOT functional requirements and must NOT appear as FRs:
  * Deployment platform, such as "Azure Cloud Deployment", belongs in the Estimation doc and architecture notes, not the FRD.
  * Project timeline, such as "12-Week Timeline to MVP", belongs in the Estimation doc and project plan, not the FRD.
  * Compliance obligations, such as "GDPR Compliance", should be reflected as specific business rules inside relevant FRs, for example "data must be encrypted at rest per GDPR Article 32", not as a standalone FR.
  A functional requirement must describe something the SOFTWARE SYSTEM DOES: a user action, system response, or automated behaviour. If a requirement cannot be tested by a developer in isolation, it is not an FR.
- AI features must each have their own dedicated FR. Never bundle multiple AI capabilities into a single FR. For example:
  BAD: FR-007: AI Capabilities (covering fit scoring + summarization + skill gap)
  GOOD:
    FR-007: Associate-JD Fit Scoring
      Description: System scores each associate-JD pair using an AI model
      Business Rules: Score >= 70% surfaces the associate; score displayed as percentage
    FR-008: Interview Feedback Summarization
      Description: System summarizes unstructured feedback text using NLP
      Business Rules: Summary <= 150 words; low-confidence summaries flagged for review
    FR-009: Skill Gap Detection
      Description: System identifies missing skills in associate profile vs JD requirements
      Business Rules: Missing skills listed in priority order; AMG coordinator notified
  Apply this splitting rule to any FR that describes multiple distinct AI-driven outputs or algorithms.
- If required implementation detail is unavailable, write "TBD".
- Every FR must trace back to a SPECIFIC BRD section and capability name.
  WRONG: "Maps to BRD Section: 5.1 In Scope"
  CORRECT: "Maps to BRD Section: 5.1 - Bulk Document Upload"
  CORRECT: "Maps to BRD Section: 8. Constraints - Security and Compliance"
  CORRECT: "Maps to BRD Section: 5.1 - Dashboard with Procurement Analytics"
  Always name the specific capability after the section number.
  If a User Story ID is available in the Epics & User Stories context, also add it: "implements US-007, Maps to BRD Section: 5.1 - Export Formats"
- Where a User Story exists for a capability, use the User Story's role and benefit to write a more specific FR description and business rules. Reference the User Story ID in the FR Traceability section ONLY if the story genuinely implements that FR's capability. Each FR must reference a DIFFERENT User Story ID that matches its content.
  WRONG: FR-008 (Role-Based Access Control) "Implements US-007: Match Accuracy Analytics"
  CORRECT: FR-008 (Role-Based Access Control) "Implements US-006: Associate Profile Management"
  If no matching User Story exists for a FR, write "No direct User Story - maps to Epic [E-XXX]" instead of copying an unrelated US reference.
- Before finalizing, internally validate that every BRD capability has at least one FR, every FR maps to the BRD, there are no orphan FRs, no contradictions, and no duplicated functionality. Fix issues before returning the final FRD.

Generate the FRD in Markdown.

# Functional Requirement Document

For each functional requirement use this exact structure:

---
## FR-XXX: [Title]

**Requirement ID:** FR-XXX

**Title:** [Business capability or system function]

**Description:** [How the software system satisfies the related business requirement]

**Priority:** High|Medium|Low|TBD

**Actors:**
- [Actor or TBD]

**Preconditions:**
- [Precondition or TBD]

**Trigger:**
- [Trigger or TBD]

**Inputs:**
- [Input or TBD]

**Outputs:**
- [Output or TBD]

**Business Rules:**
- Write 2-4 specific, testable business rules. Each rule must describe a concrete system constraint, threshold, or enforcement condition.
  WRONG: "The system must provide bulk document upload capabilities."
  CORRECT: "Users may upload a maximum of 50 documents per batch."
  CORRECT: "Accepted file formats: PDF, DOCX, XLSX, PNG, JPEG only."
  CORRECT: "Files exceeding 25MB must be rejected with a specific error message."
  CORRECT: "Fields with confidence score < 80% must be automatically flagged for manual review and cannot be auto-approved."
  Never write a business rule that simply restates the FR title or description.

**Main Workflow:**
1. [Step or TBD]

**Alternative Workflow:**
1. [Alternative step or TBD]

**Exception Handling:**
- [Exception condition and handling or TBD]

**Dependencies:**
- [Dependency or TBD]

**Acceptance Criteria:**
- [Given/When/Then criterion or clear acceptance condition]

**Traceability:**
- Maps to BRD Section: [section number and name]
---

Ordering rules:
- Order FRs by business/user journey.
- Use FR-001, FR-002, FR-003, etc.
- Keep each FR implementable and testable.
- Use professional, formal, concise language suitable for engineering and stakeholder review.
"""


VALIDATION_PROMPT = """You are a senior QA analyst reviewing enterprise BRD and FRD documents.
You are a REVIEWER only. Do not rewrite or modify the documents.
Return a structured validation report with specific refinement recommendations.

Python deterministic validation already checked:
- Duplicate FR IDs
- Missing FR IDs
- Duplicate Requirement IDs
- Traceability format
- BRD section existence
- Whether every FR has Traceability
- Duplicate functional requirements based on IDs
- Missing BRD mappings
- Numbering consistency
- Missing mandatory sections

Do NOT repeat those structural checks. Review ONLY:
1. Requirement ambiguity
2. Business consistency
3. Contradictions
4. Missing logical workflows
5. Requirement quality
6. Functional completeness
7. Overall document quality

BRD: {brd}

FRD: {frd}

Scoring rules:
- Return score values from 0 to 100.
- overall_quality is the aggregate document quality score.
- requirement_mapping measures logical business capability coverage, not mechanical traceability syntax.
- constraint_coverage measures whether business constraints are meaningfully reflected in functional behaviour.
- traceability should reflect semantic traceability quality only; syntax is checked by Python.
- consistency measures contradictions, duplicated intent, workflow gaps, and internal alignment.

Respond with JSON:
{{
  "is_valid": true/false,
  "scores": {{
    "overall_quality": 91,
    "requirement_mapping": 95,
    "constraint_coverage": 80,
    "traceability": 100,
    "consistency": 90
  }},
  "issues": [
    {{
      "type": "ambiguity|business_inconsistency|contradiction|missing_logical_workflow|requirement_quality|functional_completeness|semantic_traceability_gap",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "section": "BRD Section 5.1 or FR-001",
      "affected_requirement": "Requirement or capability name",
      "recommendation": "Specific refinement recommendation."
    }}
  ],
  "summary": "Overall assessment"
}}

Validation pass criteria:
- is_valid must be true only when there are no HIGH or MEDIUM severity issues.
- If is_valid is false, recommendations must be specific enough for a refinement agent to apply.
"""


BRD_FRD_CORRECTION_PROMPT = """You previously generated a BRD and FRD. A validation review found issues that must be fixed before document export.

Validation Issues:
{issues_formatted}

Original BRD:
{brd_draft}

Original FRD:
{frd_draft}

CRITICAL REFINEMENT RULES:
1. Fix issues directly in the text with concrete, testable functional statements.
2. NEVER insert meta-phrases, reviewer annotations, or placeholder instructions into requirement bodies.
   Banned phrases: "shall be clarified", "must be defined", "must be specified", "ensure that all items", "to be determined by stakeholders", "This concludes".
3. If a detail cannot be resolved from available context, place it inside BRD Section 12 (Open Items) as a bullet point. Do NOT leave meta-notes inside Section 5/7 of the BRD or inside FR fields in the FRD.
4. Do NOT append conversational sign-offs or closing chatter (e.g., "This concludes the BRD/FRD", "End of document") at the end of the text.
5. Do not change sections that were not flagged.
6. Keep the same overall structure and numbering. Add new FRs only where validation explicitly requests a missing functional requirement.
7. Never remove valid requirements. Never hallucinate new business capabilities.

Respond with ONLY valid JSON:
{{
  "brd": "updated BRD markdown",
  "frd": "updated FRD markdown",
  "change_summary": [
    "Brief description of applied correction"
  ]
}}
"""


PROJECT_ESTIMATION_PROMPT = """You are a senior project manager and solution architect.
Based on the BRD and FRD provided, generate a project estimation document covering
timeline, team structure, and cost.

BRD:
{brd}

FRD:
{frd}

Rules:
- This is a POC-level estimation. Do not assume real integrations or external systems.
- Derive the team structure directly from the functional requirements in the FRD.
- Do not invent roles that are not supported by the FRD.
- For timeline: count the FRs, group them into logical sprints (1 sprint = 2 weeks),
  add buffer for testing and review.
- For cost: use standard market rates below. Never ask for user input.
- Always include the cost disclaimer.
- Write formally and concisely. No bullet-point-only sections; use prose where appropriate.
- If a specific detail cannot be determined from the BRD/FRD, write "TBD".

Standard Market Day Rates (use these for estimation):
- Junior Developer: $400-600/day (offshore), $800-1,200/day (onshore)
- Mid-Level Developer: $600-900/day (offshore), $1,200-1,800/day (onshore)
- Senior Developer: $900-1,200/day (offshore), $1,800-2,500/day (onshore)
- QA Engineer: $400-700/day (offshore), $800-1,200/day (onshore)
- DevOps Engineer: $600-900/day (offshore), $1,200-1,800/day (onshore)
- Project Manager: $500-800/day (offshore), $1,000-1,500/day (onshore)
- Business Analyst: $500-750/day (offshore), $1,000-1,500/day (onshore)

Generate the estimation in Markdown using exactly these sections:

# Project Estimation Report

## 1. Overview
Briefly describe the project, scope summary, and estimation basis
(e.g., number of FRs, complexity, technology inferred).

## 2. Timeline

### 2.1 Sprint Breakdown
List each sprint with its focus area and FRs covered:
| Sprint | Duration | Focus Area | FRs Covered |
|--------|----------|------------|-------------|
| Sprint 1 | 2 weeks | [area] | FR-001, FR-002 |

### 2.2 Phase Summary
List phases: Discovery/Setup, Development, QA & Testing, UAT & Deployment.
Include estimated weeks per phase.

### 2.3 Total Timeline
State the overall estimated project duration in weeks.
If BRD Section 8 (Constraints) specifies a timeline constraint, for example "12-week timeline to MVP", compare it against the estimated duration:
- If the estimation fits within the constraint: confirm it is achievable.
- If the estimation EXCEEDS the constraint: explicitly flag this as a risk. Example: "Estimated duration is 15 weeks. The BRD constraint of 12 weeks to MVP is at risk. Recommended mitigation: reduce Phase 1 scope to core scheduling and feedback features only, deferring AI capabilities to Phase 2."
Never silently produce an estimate that conflicts with the BRD constraint.

## 3. Team Structure

### 3.1 Recommended Team
For each role provide: Role, Headcount, Responsibility.
Only include roles directly supported by the FRD requirements.

Before finalizing the team table, scan every FR title, description, and
business rules for terms indicating AI/ML behavior: match, score, rank,
recommend, predict, classify, summarize, analyze, extract, detect, NLP,
ML, AI, algorithm. If ANY FR contains such terms, you MUST include an
AI/ML Engineer role in the team table — do not omit it, even if the AI
behavior is only one part of a broader FR:
| AI/ML Engineer | 1 | Design and implement AI matching model, NLP summarization pipeline, skill gap detection |

Separately, if the FRD contains any FR describing a user-facing screen,
form, portal, or dashboard (true for nearly every FRD unless it is
explicitly backend/API-only), include a Frontend Developer or UI Engineer
role:
| Frontend Developer | 1 | Build user-facing portals, forms, and dashboards described in the FRD |

| Role | Count | Key Responsibilities |
|------|-------|---------------------|
| Senior Backend Developer | 1 | [responsibilities from FRD] |

### 3.2 Team Size
State total team headcount and note any roles that may be shared or part-time.

## 4. Cost Estimate

### 4.1 Effort Breakdown
For each role, estimate working days:
| Role | Count | Working Days | Day Rate (Offshore) | Day Rate (Onshore) |
|------|-------|-------------|--------------------|--------------------|
| Senior Backend Developer | 1 | 45 | $900-$1,200 | $1,800-$2,500 |

### 4.2 Total Cost Range
| Scenario | Estimated Cost |
|----------|---------------|
| Offshore Team | $XX,XXX - $XX,XXX |
| Onshore Team | $XX,XXX - $XX,XXX |
| Blended (50/50) | $XX,XXX - $XX,XXX |

### 4.3 Additional Costs
Use BRD Section 8 (Constraints) to estimate infrastructure and tooling costs.
If the BRD mentions specific cloud services, list their estimated monthly cost.

Common Azure service estimates (use these if referenced in BRD constraints):
- Azure Kubernetes Service (AKS): $200-$800/month depending on node count
- Azure Blob Storage: $20-$100/month for document storage
- Azure AI Document Intelligence: $1.50 per 1,000 pages (estimate volume)
- Azure App Service: $50-$200/month
- Azure SQL / PostgreSQL: $100-$300/month
- Azure API Management: $100-$500/month
- Monitoring (Application Insights): $50-$150/month

Estimate a monthly infrastructure cost range based on which services appear in BRD Section 8 (Constraints).
Format as: | Service | Estimated Monthly Cost |
Add a note: "Infrastructure costs assumed for a moderate-scale deployment. Actual costs depend on usage volume and Azure pricing tier."
Only write "TBD" for costs where the BRD provides no basis for inference.

## 5. Key Assumptions
List all assumptions made during estimation (team experience level, sprint velocity, etc.).

## 6. Risks & Buffers
List estimation risks (scope changes, integration complexity, resource availability).
State recommended buffer: typically 15-20% added to base estimate.

## 7. Disclaimer
Include verbatim:

> **Disclaimer:** This is a rough order-of-magnitude (ROM) estimate generated by
> SDLC AI based on the functional requirements provided. Actual timelines and costs
> may vary significantly depending on team experience, technology choices,
> organisational processes, integration complexity, and scope changes. This estimate
> should not be used as a contractual basis without further detailed planning and
> stakeholder review.
"""


PROTOTYPE_PROMPT = """You are a senior UI/UX developer creating a static HTML wireframe prototype.
Generate a single, self-contained HTML file that represents the main screens of the application
described in the UI context below.

UI Context:
{prototype_context}

Rules:
- Generate ONE complete, self-contained HTML file. No external CSS or JS libraries.
- All CSS must be inline in a <style> tag inside <head>.
- All JavaScript must be inline in a <script> tag before </body>.
- Identify the main user-facing screens from the UI context (actors, screens, navigation, forms,
  tables, dashboard widgets, and user workflows).
  Typically: Login/Home screen, plus one screen per major actor or major workflow.
  Maximum 8 screens. Minimum 3 screens.
- Each screen should represent a realistic layout for that workflow
  (e.g., a dashboard shows a table of records with action buttons;
   a form screen shows labeled inputs and a submit button;
   a list screen shows a filterable table with pagination controls).
- Navigation: use a top navigation bar with tabs/links. Clicking a tab shows
  that screen and hides all others. Default to the first screen on load.
- Wireframe quality: placeholder content is fine (use realistic labels like
  "Employee Name" not "Lorem ipsum").
  Show real form field labels, realistic button labels, column headers in tables.
- Color palette: use a clean, professional palette. Suggested:
  - Primary: #1F3864 (dark navy)
  - Accent: #2563EB (blue)
  - Background: #F9FAFB
  - Card/Panel: #FFFFFF
  - Border: #E5E7EB
  - Text: #111827
  - Secondary text: #6B7280
- Typography: system font stack (Arial, sans-serif). No Google Fonts.
- Do NOT include real data or personally identifiable information.
- Do NOT include any backend logic, API calls, or real functionality.
- This is a WIREFRAME: it demonstrates layout and navigation only.
- Add a clearly visible banner at the top:
  "SDLC AI - Auto-Generated Prototype Wireframe | For demonstration purposes only"

Return ONLY the complete HTML. No markdown, no explanation, no backticks.
The response must start with <!DOCTYPE html> and end with </html>.
"""


EPICS_STORIES_PROMPT = """You are a senior product owner and agile coach.
Using the approved BRD below, generate a structured Epics and User Stories document.

BRD:
{brd}

Rules:
- Group all BRD in-scope capabilities into 4-6 logical Epics.
- Each Epic must have a clear theme, such as Document Processing or User Management.
- Each Epic must contain 3-8 User Stories.
- Every User Story must follow this format exactly:
  "As a [role], I want [feature], so that [benefit]."
- Every User Story must have 2-4 Acceptance Criteria in Given/When/Then format.
- Every User Story must have a Priority (High/Medium/Low) and an estimated Story Points value (1, 2, 3, 5, 8, or 13).
- Story Points follow Fibonacci scale: 1=trivial, 2=simple, 3=small, 5=medium, 8=large, 13=very large.
- Every User Story must trace back to a SPECIFIC BRD section and capability name.
  WRONG: "BRD Section 5.1 - In Scope"
  CORRECT: "BRD Section 5.1 - Automated Interview Scheduling"
  CORRECT: "BRD Section 5.1 - Client Feedback Collection via Self-Service Portal"
  CORRECT: "BRD Section 8. Constraints - Role-Based Access Control"
  Always name the specific capability after the section number.
- Do NOT invent features not present in the BRD.
- Do NOT duplicate stories across Epics.
- Write in professional, concise language suitable for a product backlog.
- If a detail is unclear from the BRD, write "TBD" rather than guessing.

Generate the document in Markdown using exactly this structure:

# Epics & User Stories

## Summary Table
| Epic ID | Epic Name | Stories Count | Total Story Points |
|---------|-----------|---------------|-------------------|
| E-001 | [Epic Name] | [count] | [total SP] |

---

## E-001: [Epic Name]

**Description:** [One sentence describing what this epic covers and why it matters]

**BRD Reference:** [BRD Section(s) this epic maps to]

### US-001: [Short Story Title]

**User Story:**
As a [role], I want [feature], so that [benefit].

**Priority:** High | Medium | Low

**Story Points:** [1 | 2 | 3 | 5 | 8 | 13]

**Acceptance Criteria:**
- Given [context], when [action], then [outcome].
- Given [context], when [action], then [outcome].

**BRD Traceability:** BRD Section [X.X - Section Name]

---

[Repeat for each story within the epic]

[Repeat for each epic]

## Backlog Summary
| Story ID | Story Title | Epic | Priority | Story Points |
|----------|------------|------|----------|-------------|
| US-001 | [Title] | E-001 | High | 5 |

**Total Story Points:** [output only the final computed integer, e.g. "68" — do not show the addition expression]
**Estimated Sprints:** [output only the final computed integer, e.g. "4" — do not show the division expression]
"""

