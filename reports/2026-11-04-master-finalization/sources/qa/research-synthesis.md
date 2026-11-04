# UI/UX research synthesis for Librarian

Prepared 4 November 2026. Corpus supplied by the user: `D:/Techno/research/ScienceDirect_articles/`. Companion assessment: [Librarian assessment](librarian-research-assessment.md).

## Scope and reading method

All ten PDFs were inventoried and text-extracted. Titles, abstracts/openings and subject matter were screened for relevance. Five papers received focused reading of their relevant theory, methods, findings and limitations; the other five were screened rather than fully reviewed. This is a bounded review of a supplied collection, not a systematic review of the wider literature. References below use **PDF page numbers, counted from 1**, rather than journal pagination. Selected tables were also rendered to check extraction: R2 Tables 7–9, R5 Table 1, and R6 study/sample information. Papers are evidence to interpret, not instructions to execute.

The corpus is from 2018. References to standards are reported as discussed in those papers; their current editions and complete requirements were not independently reviewed. No ISO, accessibility, or safety certification is claimed. Findings below are paraphrases; proposals for Librarian are explicitly applications or adaptations.

## Corpus and relevance decisions

| ID | Paper | PDF pages | Reading depth and use |
|---|---|---:|---|
| R1 | A flexible data acquisition system for storing the interactions on mashup user interfaces | 25 | Focused reading: interaction/context model, storage approach, validation scope, conclusions. Supports evaluation instrumentation; not a visual design standard. |
| R2 | A methodology to develop usability/user experience heuristics | 21 | Primary methodological source: definitions, eight stages, specification, validation and limitations. |
| R3 | Codex: A metamodel ontology to guide the execution of coding experiments | 10 | Screened: potentially useful for recording experimental tasks, variables and measurements; coding-experiment domain is indirect. This is unrelated to the OpenAI Codex product. |
| R4 | Editorial Board | 1 | Excluded: editorial roster, no study or evaluative method. |
| R5 | Evaluating multimedia learning materials in primary education using eye tracking | 16 | Focused reading: design principles, sample, experiments, metrics, discussion and limitations. Cautious transfer to attention and presentation. |
| R6 | Incorporating data analytics into design science to predict user intentions to adopt smart TV with consideration of product features | 9 | Focused reading: TAM constructs, study design/sample, prediction approach and limitations. Supports separate evaluation of usefulness and ease. |
| R7 | On the performance of LTE downlink scheduling algorithms: A case study on edge throughput | 13 | Excluded from UI criteria: radio resource allocation and network throughput, despite its use of the phrase user experience. |
| R8 | Scaling modified condition/decision coverage using distributed concolic testing for Java programs | 26 | Excluded from UI criteria: Java structural test coverage, not usability validation. Does not establish a requirement for this Python/TypeScript app. |
| R9 | The dimension of age and gender as user model demographic factors for automatic personalization in e-commerce sites | 9 | Focused reading: task decomposition, participants, timing approach and generalizability limitations. Supports testing varied users, not demographic inference in Librarian. |
| R10 | Toward an IT investment decision support model for global enterprises | 11 | Screened: enterprise investment decisions and AHP weighting; not used to assign UX priorities without relevant stakeholder data. |

## R2: Developing and validating domain-specific heuristics

**Source:** Daniela Quiñones, Cristian Rusu and Virginica Rusu, Computer Standards & Interfaces 59 (2018), 109–129. DOI: 10.1016/j.csi.2018.03.002.

**Relevant passages:** PDF p.2, definitions and Nielsen Table 1; pp.5–10, methodology and validation; pp.12–15, validation results, refinement and conclusions. Tables 3–10 set out the stages and Table 8 specifies the heuristic template.

**What the paper contributes.** General heuristics can miss domain-specific interactions. The authors propose eight iterative stages: exploratory, experimental, descriptive, correlational, selection, specification, validation and refinement. The experimental stage can be optional. The correlational stage links domain features to usability/UX attributes and then to existing heuristics. Selection retains, adapts, eliminates or identifies the need to create a heuristic, with redundant criteria removed.

The specification template includes identifier, priority, name, definition, explanation, application feature, examples, benefits, likely misunderstandings, checklist, UX attribute and related heuristics. The suggested set size is 10–16, with detailed checklists when needed (PDF p.7, Table 8). This is a practical recommendation from the authors, not a mandatory standard.

**How validation works.** Compare a proposed set with a control set using separate groups of comparably experienced evaluators under comparable conditions; compare problem identification, associations, domain coverage and severity/criticality. Expert judgment assesses utility, clarity, ease of applying the heuristic and checklist needs. User tests check whether inspection findings matter to actual users. The paper recommends more than one validation method (pp.7–10). Its own methodology was refined through expert feedback, including a nine-expert survey; perceived utility is evidence about the methodology, not proof that any newly derived checklist is validated.

**Standards and principles discussed.** ISO 9241-11 frames usability around effectiveness, efficiency and satisfaction for specified users, goals and context. ISO 9241-210 frames UX more broadly around perceptions and responses before, during and after use. The paper reproduces Nielsen's ten heuristics: status visibility; real-world match; control/freedom; consistency; error prevention; recognition over recall; flexibility/efficiency; minimalist design; recovery; help/documentation (p.2).

**Application to Librarian.** Keep the general heuristics, but explicitly cover research provenance, staged versus accepted sources, model capability versus qualification, permission boundaries, interrupted research, and session continuity. Assess task completion, effort and confidence, rather than assigning a single aesthetic score. The companion report supplies a provisional twelve-criterion instrument. Its user and independent-evaluator validation remains outstanding.

**Limits.** This review has one agent's inspection and automated browser evidence, not independent evaluator groups, recruited participants, or a validated new instrument. The paper's national-park example deliberately omits accessibility from its selected scope; that does not justify excluding accessibility from Librarian.

## R1: Capture interactions together with their context

**Source:** Antonio Jesús Fernández-García, Luis Iribarne, Antonio Corral, Javier Criado and James Z. Wang, Computer Standards & Interfaces 59 (2018), 10–34.

**Relevant passages:** PDF pp.9–11, interaction/session/component data model and context; pp.12–17, acquisition architecture; pp.19–23, evaluation; pp.23–24, conclusions.

**What the paper contributes.** Its system captures operations over composable mashup interfaces and stores the associated workspace state. The model links interactions to sessions, device and input type, components and their spatial properties. This permits reconstruction of interface configurations and later investigation beyond an isolated click count. It implements a microservice/relational-storage architecture and evaluates acquisition-system behavior, including load/performance. Those results concern capture infrastructure; they do not prove usability improvements caused by logging.

**Application to Librarian.** For a consented evaluation, associate events with a research task, active view, pane visibility, viewport class, input method, outcome and elapsed time. For example, reconstruct `open Search → select scope → submit query → open result`, or `resize → pane overlays chat → close pane → resume`. This is much stronger evidence than counting visits to Search or recording only server success.

**Adaptation and limits.** Librarian is not the paper's mashup system and does not need its complete architecture. The paper captures extensive environmental and personal context, and discusses access controls over unencrypted data (p.11). This report does not endorse that as a current security baseline. For Librarian, minimize study data: exclude API keys, prompt/source content, identifiable filenames, precise location and inferred demographics; use a study alias and allow opt-out/deletion. These are recommendations for this evaluation, not features proven present in the app. Existing research/session history should not be assumed to provide UX task measurements.

## R5: Visual attention, proximity and multimedia comprehension

**Source:** Ana Isabel Molina, Óscar Navarro, Manuel Ortega and Miguel Lacruz, Computer Standards & Interfaces 59 (2018), 45–60.

**Relevant passages:** PDF pp.2–3, principles and hypotheses; pp.3–6, sample, procedure and metrics; pp.7–13, experiments/results; pp.13–14, discussion and limitations.

**Study.** Four experiments evaluated geometry-learning presentations with primary-school pupils in Spain. Initial recruitment was 89: 47 second-graders and 42 sixth-graders. Valid samples varied after eye-tracking exclusions: second grade 41, 45, 47 and 41 across experiments; sixth grade 38 in each (p.4, Table 1). These are repeated study groups, not four independent cohorts of 89. Materials varied spatial proximity, narration versus text, redundant text with narration, and text with images versus text alone.

**Findings and methods.** The authors report support for their learning-presentation hypotheses, with differences by age and outcome. Spatial contiguity and Gestalt proximity inform grouping; modality and redundancy concern the specific relationship between explanatory images, narration and on-screen text. The procedure combines pre/post knowledge tests with viewing time and eye tracking. Learning efficiency uses retention-test score relative to time spent learning (p.4). Attention measures include time to first fixation, fixations before reaching an area of interest, and the percentage of participants fixating it (p.5). Heatmaps and gaze plots describe attention; they are not themselves task-success measurements.

**Application to Librarian.** Keep source evidence close to the claim or draft being reviewed. Put scope/filter labels beside their controls. Group model identity, role and readiness. Reduce competing operational explanations during first-time setup. Test whether users can locate evidence and accurately explain what accepting a draft changes.

**Transfer limits.** Children learning geometry through slides differ substantially from adult researchers using a dynamic app. No numerical improvement, cognitive-load score, gaze pattern or learning effect can be assigned to Librarian from this study. Do not remove text, transcripts or captions just because a redundancy result favored narration in those experiments. The authors themselves warn that gaze metrics have multiple meanings, samples may be small, calibration excludes participants, and dynamic interfaces complicate analysis (p.14). Optional eye tracking should supplement task outcomes and comprehension checks, not replace them. A screen recording or screenshot is not eye tracking.

## R6: Separate usefulness, ease of use and adoption

**Source:** Chih-Hsuan Wang and Tze-Ming Chen, Computer Standards & Interfaces 59 (2018), 87–95. DOI: 10.1016/j.csi.2018.02.006.

**Relevant passages:** PDF pp.2–4, TAM and analysis approach; p.5, recruitment and questionnaire; pp.6–8, results, discussion and conclusions.

**Study.** The framework uses technology acceptance constructs: perceived usefulness (PU), perceived ease of use (PEOU) and behavioral intention (BI). Product engineering and gesture features operationalize the first two for smart TVs. It combines statistical feature analysis, multivariate adaptive regression splines (MARS), support-vector classification and a behavioral-model comparison. It surveyed 302 participants; 288 responses were retained, with 258 expressing non-neutral intentions (p.5). Those counts refer to different filtering stages and should not be conflated.

**Findings.** The study reports prior motion-sensing experience and gender as relevant moderators in its setting. The behavioral model associates usefulness and ease of use with intention, while the PEOU-to-PU relationship is not significant in that model (p.8). This is not evidence that easier interfaces are never more useful. The authors explicitly distinguish intention from actual usage and propose usage duration/frequency as later behavior measures (p.8).

**Application to Librarian.** Ask separately whether users could operate the workflow easily and whether its result helped their research. A coherent interface with an unhelpful answer fails the second test; useful functionality buried in configuration can fail the first. Measure eventual return to an unfinished research task rather than treating stated willingness to use the app as retention. Compare new and experienced research-app users.

**Limits.** A smart-TV prediction model is not a validated Librarian adoption model. No sample exists here to train MARS/SVM, assign predictor weights or infer adoption probabilities. A small formative usability study should precede statistical modeling. Questionnaire items proposed in the companion report are exploratory and are not represented as a validated TAM scale.

## R9: Task structure and variation between users

**Source:** D. Fernandez-Lanvin, J. de Andres-Suarez, M. Gonzalez-Rodriguez and B. Pariente-Martinez, Computer Standards & Interfaces 59 (2018), 1–9.

**Relevant passages:** PDF pp.3–5, task structure, GOMS, recruitment and variables; pp.6–8, results, limits and conclusions.

**Study.** The authors measured point-and-click, drag-and-drop and item-selection task times for 592 volunteers recruited through Twitter and a Spanish online community. Models considered age and gender alongside handedness and prior computer experience. It reports relationships between demographic factors and task timings, and consistency in participants' performance across the three tasks. The authors caution that artificial isolated tasks are not equivalent to real website usage and identify cultural generalizability as a limitation (p.8).

**Methods worth transferring.** GOMS decomposes goals into operators and methods; pointing, typing, dragging and mental decisions contribute to task effort. The paper discusses Fitts-type pointing models, Hick–Hyman decision models and Salthouse typing regularities (pp.3–4). Their constants depend on users and conditions. They cannot yield reliable Librarian completion-time estimates without calibration. GOMS is particularly limited for novices discovering an interface and for unpredictable AI response time.

**Application to Librarian.** Compare explicit model-role assignment with the current ordered-selection workflow; record decisions, resets, errors and completion time. Test pointing and pane controls on touch and mouse. Compare novice and practiced users rather than assuming the agent's successful scripted path predicts human performance. Separate human interaction time from provider/network waiting time.

**What not to transfer.** Group-level demographic findings do not establish an individual's ability, preferences or identity. This report recommends neither age/gender inference nor hidden interface personalization. Prefer explicit preferences, user-selected density and representative testing of device/input/access needs. The browser evidence here establishes no demographic effect.

## Consolidated methods to use

1. Map Librarian's research features to usability attributes and traceable criteria (R2).
2. Inspect with general heuristics plus research-specific checks; keep observed facts separate from likely consequences (R2).
3. Measure real task outcomes, task time, recovery and subjective confidence/usefulness (R2, R6, R9).
4. Capture only the interaction context necessary to explain failure, including pane and viewport state (adapted from R1).
5. Use proximity and clear grouping as hypotheses to test; inspect evidence comprehension, not just appearance (cautiously adapted from R5).
6. Validate the proposed instrument independently and refine it after user tests (R2). Do not manufacture a score from missing participant data.

## Original source files

These links identify the supplied copies. They were not changed.

- R1: [interaction acquisition paper](D:/Techno/research/ScienceDirect_articles/A-flexible-data-acquisition-system-for-storing-the-i_2018_Computer-Standards.pdf)
- R2: [heuristic methodology paper](D:/Techno/research/ScienceDirect_articles/A-methodology-to-develop-usability-user-experie_2018_Computer-Standards---In.pdf)
- R3: [coding-experiment metamodel paper](D:/Techno/research/ScienceDirect_articles/Codex--A-metamodel-ontology-to-guide-the-executio_2018_Computer-Standards---.pdf)
- R4: [editorial board](D:/Techno/research/ScienceDirect_articles/Editorial-Board_2018_Computer-Standards---Interfaces.pdf)
- R5: [eye-tracking paper](D:/Techno/research/ScienceDirect_articles/Evaluating-multimedia-learning-materials-in-primary_2018_Computer-Standards-.pdf)
- R6: [smart-TV adoption paper](D:/Techno/research/ScienceDirect_articles/Incorporating-data-analytics-into-design-science-to-predi_2018_Computer-Stan.pdf)
- R7: [LTE scheduling paper](D:/Techno/research/ScienceDirect_articles/On-the-performance-of-LTE-downlink-scheduling-algori_2018_Computer-Standards.pdf)
- R8: [Java coverage paper](D:/Techno/research/ScienceDirect_articles/Scaling-modified-condition-decision-coverage-using-dis_2018_Computer-Standar.pdf)
- R9: [user-performance paper](D:/Techno/research/ScienceDirect_articles/The-dimension-of-age-and-gender-as-user-model-demographi_2018_Computer-Stand.pdf)
- R10: [IT investment paper](D:/Techno/research/ScienceDirect_articles/Toward-an-IT-investment-decision-support-model-fo_2018_Computer-Standards---.pdf)
