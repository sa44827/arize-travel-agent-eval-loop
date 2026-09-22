# Arize FDE Interview Screen — Candidate Project Brief

> Text extracted from `Arize FDE Interview Screen.pdf`, provided by the user in
> chat. This is the requirements source for the "what we are evaluated on"
> and "final deliverables" sections referenced throughout `docs/BUILD_LOG.md`
> and the solution deck.
>
> **Note on the original PDF file:** I received this document's content
> through the chat's document viewer, which gave me extracted text per page —
> not the original PDF's bytes or a filesystem path. I cannot copy a file I
> was never given access to on disk. If you want the actual PDF in the repo
> (e.g. `docs/Arize FDE Interview Screen.pdf`), drop the file itself into
> `docs/` and it'll be there for both of us to reference; this markdown file
> covers the same content in the meantime.

---

## Interview Loop
1. **Hiring Screen** — 15 minutes — Nick Luzio or An Nguyen
2. **Interview 1: Customer Discovery & Requirements Gathering** — 1 hr — Nick Luzio, An Nguyen, Lucas Moehlenbrock
3. **Interview 2: End-to-End Solution Presentation** — 1 hr — Nick Luzio, An Nguyen, Lucas Moehlenbrock
4. **Interview 3: Bar Raiser** — 30 minutes — Trevor LaViale

## Forward Deployed AI Engineer — Candidate Project

### Overview
As part of the Forward Deployed Engineer interview process, you will complete a
simulated customer engagement focused on building a production-ready feedback
loop for an AI agent.

The agent itself can be simple and may solve any problem you choose. We are
more interested in how you instrument, evaluate, monitor, and continuously
improve the agent than in the complexity of the agent's core functionality.

This exercise evaluates your ability to:
- Work through ambiguity and define a solution approach
- Build or adapt an AI agent using the stack of your choice
- Implement tracing, evaluations, and production observability
- Design an automated feedback loop for agent quality
- Use Arize or Phoenix tooling to improve agent development workflows
- Communicate technical tradeoffs to engineering and business stakeholders
- Translate customer needs into clear deliverables

### Project Scenario
A customer is deploying an AI agent into production and wants confidence that
the agent will continue to perform well over time.

For the purposes of this example, they are less concerned with what the agent
does and more concerned with whether the system around the agent can:
- Capture useful telemetry data
- Detect failures or regressions
- Run repeatable evaluations
- Feed results back into development workflows
- Support production monitoring
- Provide visibility to technical and business stakeholders

Your task is to build an AI agent and an automated feedback loop around it.
The agent can be anything you choose, such as:
- A support assistant
- A RAG-based question-answering assistant
- Any other agentic application

The agent does not need to be complex. A simple agent with a strong feedback
loop is preferred over a complex agent with weak observability.

### Core Requirement: Automated Agent Feedback Loop
Your primary deliverable is an automated feedback loop that monitors and
improves agent quality over time.

Your feedback loop should include:
1. **Capture traces for agent activity.** You may use Arize AX (free account)
   or Phoenix (OSS) for this.
2. **Evaluation.** Define and run evaluations that are appropriate for your
   agent. Explain why you selected these evaluations and how they connect to
   the customer's business goals.
3. **Automation.** Build an automated process that runs evaluations or
   feedback workflows on a repeatable basis. You may use any orchestration
   tool or workflow system, such as the Arize AX Airflow Provider or
   Kubernetes jobs.
4. **Skills Usage.** Use either Arize skills or Phoenix skills (and/or CLI) as
   part of your development workflow. Be prepared to explain which skills you
   used, how they helped your workflow, and what you would improve or
   automate further in a real customer deployment.

### Production Readiness
Your solution should be designed as if it could be deployed for a real
enterprise customer (think along the lines of millions of requests per day).

You should address:
- Deployment architecture
- Environment configuration
- Secrets management and security
- Error handling
- Logging and tracing
- Resource usage
- Scalability
- Cost considerations
- Reliability and rollback strategy

The agent should be capable of handling realistic production traffic for its
use case. You do not need to over-engineer the deployment, but you should
clearly explain how it would scale.

### Final Deliverables
Please prepare:
1. A working agent demo with an automated feedback loop
2. A customer-facing presentation outlining:
   a. Architecture of the agent and the feedback loop
   b. A production readiness plan
   c. How the solution solves the business and technical requirements laid
      out by the customer
   d. Any relevant metrics or results
3. A link to your codebase

## Interview Structure

### Interview 1: Customer Discovery & Requirements Gathering
You will meet with a simulated customer team to understand their business
objectives, technical requirements, and operational constraints.

The goal of this session is to ask questions in order to gather enough
information to define a successful project plan and implementation approach.

You should be prepared to:
- Ask clarifying questions
- Identify business goals and success criteria
- Understand technical requirements and constraints
- Discover operational and production-readiness expectations
- Identify risks, assumptions, and unknowns
- Understand what types of failures matter most to the customer
- Determine how agent quality should be measured and monitored

The customer may intentionally leave some requirements unspecified. We
encourage you to actively drive the conversation and uncover the information
needed to scope a successful project.

Following this session, you will begin implementing your solution.

### Interview 2: End-to-End Solution Presentation
In this session, you will present the completed solution to the customer.
Your presentation should demonstrate both the technical implementation and
how the solution satisfies the customer's original requirements. Your review
should include:

**Agent Demonstration**
- Overview of the agent
- Example workflows
- Key capabilities

**Automated Feedback Loop**
- Instrumentation and tracing
- Evaluation framework
- Automated workflows
- Feedback collection and analysis
- Continuous improvement process

**Production Readiness**
- Deployment architecture
- Monitoring and alerting
- Scalability considerations
- Reliability and operational visibility
- Cost and performance considerations

**Results & Learnings**
- Evaluation outcomes
- Tradeoffs and design decisions
- Future recommendations

You should be prepared to answer both technical and business-focused
questions about your implementation and decision-making process.

## What We Are Evaluating
We are not looking for a perfect agent. We are looking for evidence that you
can help a customer deploy, observe, evaluate, and improve agentic systems in
production.

We will evaluate:
- Quality of the automated feedback loop
- Observability and tracing design
- Evaluation methodology
- Production readiness
- Systems thinking
- Customer communication
- Ability to handle ambiguity
- Technical judgment
- Tradeoff discussions
- Clarity of presentation

There is no single correct solution. Make reasonable assumptions, communicate
them clearly, and focus on building a system that helps a customer understand
and improve agent performance over time.
