You are assessing a software-factory job before implementation.

Your task is to decide whether the job is clear enough to implement now, or whether the factory should ask the user for clarification first.

Choose exactly one decision:

IMPLEMENT_NOW
- Choose this when the title and description are specific enough for an agent to make a useful, bounded code change.
- Minor implementation choices are acceptable if the intent is clear.

NEEDS_CLARIFICATION
- Choose this when the request is too vague, missing the desired behavior, missing acceptance criteria, or could reasonably lead to multiple incompatible implementations.
- Ask only the smallest useful set of questions needed to make the job actionable.
- If you choose NEEDS_CLARIFICATION, questions must contain at least one question and no more than four questions.

Return only JSON in this exact shape:

{
  "decision": "IMPLEMENT_NOW",
  "reason": "Short reason for the decision.",
  "questions": []
}

or:

{
  "decision": "NEEDS_CLARIFICATION",
  "reason": "Short reason for the decision.",
  "questions": [
    "First clarification question?",
    "Second clarification question?"
  ]
}

Example IMPLEMENT_NOW response:

{
  "decision": "IMPLEMENT_NOW",
  "reason": "The request identifies a specific endpoint, desired response fields, and expected behavior.",
  "questions": []
}

Example NEEDS_CLARIFICATION response:

{
  "decision": "NEEDS_CLARIFICATION",
  "reason": "The request asks to improve health checks but does not say what should be checked or what response format is expected.",
  "questions": [
    "Should the health check verify only the application process, or also external dependencies?",
    "What response fields and HTTP status behavior should the endpoint return?"
  ]
}

Job:

Workflow: {workflow_id}
Target repo: {target_repo}
Base branch: {base_branch}
Title: {title}
Description: {description}

Available repos:
{available_repos}

Conversation history:
The following JSON array contains the conversation messages currently stored for this job. Each item may include role, type, content, and questions. Use this history together with the title and description when making your decision.

{messages}
