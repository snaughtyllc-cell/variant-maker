/** Workflows: separate inbox vs output, one Drive subfolder per source clip. */

export function workflowPageBlurb(): string {
  return (
    "Inbox and output must be different Drive folders. Each source clip gets its own " +
    "subfolder in the output folder — 10 videos × 20 variants becomes 10 folders, not " +
    "200 files in one pile."
  );
}

export function workflowFoldersMustDiffer(): string {
  return "Inbox and output folders must be different.";
}

export function workflowNeedTwoFolders(): string {
  return "Save two Drive folders first — one inbox (raw clips) and one output (finished packs).";
}

export function workflowInboxHint(): string {
  return "Drop raw clips here. Not the same folder as output.";
}

export function workflowOutputHint(): string {
  return "Finished packs land here. One subfolder per source clip.";
}

export function workflowFoldersClash(
  inbox: { id: string; folder_id: string },
  output: { id: string; folder_id: string },
): boolean {
  return inbox.id === output.id || inbox.folder_id === output.folder_id;
}
