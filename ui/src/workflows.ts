/** What each workflow does and what it leaves behind, in one place: the Queue-an-action menu shows
 *  `does` as a hint and `result` as a visible line, and Settings → Commands & shortcuts explains
 *  every shortcut with the same words. `result` is empty for a command that only moves you
 *  somewhere. */
export interface WorkflowInfo { does: string; result: string }

export const WORKFLOWS: Record<string, WorkflowInfo> = {
  settings: { does: "Opens Settings: models, providers, permissions, review options and health.", result: "" },
  search: { does: "Moves to Search and puts the cursor in the search box.", result: "" },
  staging: { does: "Opens Staging: sources, folders, lenses, concepts, topics and offerings waiting for your review.", result: "" },
  sessions: { does: "Opens the Sessions menu, to resume, start or branch a thread.", result: "" },
  checkpoints: { does: "Opens Checkpoints: decisions an agent is waiting for you to make.", result: "" },
  intake: {
    does: "Opens the paperclip, to attach a file or link a note to this library.",
    result: "After you ask the librarian to capture it, the source waits in Staging for your review.",
  },
  "clear-enrichment-backlog": {
    does: "Fetches each queued reference, drafts a short description of it and stages it for review. Runs in the background; you can cancel it.",
    result: "Every queued source moves to Staging → Sources, Captured, to review. Nothing joins the library until you accept it.",
  },
  "deep-read-staged": {
    does: "Reads the whole text of each captured source, part by part: claims and limits with the pages they come from, and any reasoning stance worth keeping as a lens. Runs in the background; you can cancel it.",
    result: "Each source gets its claims, limits and proposed lenses, ready for review in Staging (Sources and Lenses). Nothing is accepted for you.",
  },
  "review-conversation": {
    does: "Takes a bounded snapshot of the recent conversation and suggests sources that would help.",
    result: "A list of suggested sources to consider. It writes nothing to the library.",
  },
  "review-due": {
    does: "Finds concepts whose review is due and opens a parked learning session for each (up to five; reviews already open are skipped).",
    result: "Parked sessions appear under Sessions, ready to resume. Nothing is written until you work through them.",
  },
  "weekly-review": {
    does: "Reads one pursuit's tasks, what was read and written, and its desk, then drafts a reflection.",
    result: "A drafted weekly reflection for you to read. It is written only if you accept it.",
  },
  approved: {
    does: "Runs the batch for sources you approved for ingestion: reads each in full, describes it and stages the result.",
    result: "Approved sources move to Staging → Sources, Ingested, ready to accept.",
  },
  retry: {
    does: "Runs only the reading steps that waited because no model was available, now that models are chosen.",
    result: "Those sources are updated in Staging and leave the list of sources waiting for a model.",
  },
  resume: {
    does: "Carries on a batch that failed, was cancelled or was interrupted, from the stage where it stopped. Finished work is not repeated.",
    result: "The batch completes and its sources are updated in Staging.",
  },
  stop: {
    does: "Lets the running batch finish its current stage, then stops it.",
    result: "The batch halts cleanly and can be resumed later.",
  },
};

/** The full hint for a workflow: what it does, then what it leaves behind. */
export function workflowHint(id: string): string {
  const info = WORKFLOWS[id];
  return info ? (info.result ? `${info.does}\nResult: ${info.result}` : info.does) : "";
}
