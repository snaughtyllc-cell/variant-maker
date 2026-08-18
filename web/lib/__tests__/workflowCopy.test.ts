import { describe, it, expect } from "vitest";
import {
  workflowFoldersClash,
  workflowFoldersMustDiffer,
  workflowNeedTwoFolders,
  workflowOutputHint,
  workflowPageBlurb,
} from "@/lib/workflowCopy";

describe("workflow folder layout copy", () => {
  it("says inbox and output must differ, with one subfolder per source", () => {
    expect(workflowPageBlurb()).toMatch(/different Drive folders/i);
    expect(workflowPageBlurb()).toMatch(/subfolder/i);
    expect(workflowPageBlurb()).toMatch(/10 folders/i);
    expect(workflowFoldersMustDiffer()).toMatch(/different/i);
    expect(workflowNeedTwoFolders()).toMatch(/two Drive folders/i);
    expect(workflowOutputHint()).toMatch(/one subfolder per source/i);
  });

  it("treats the same destination or the same Drive folder as a clash", () => {
    expect(
      workflowFoldersClash(
        { id: "a", folder_id: "IN" },
        { id: "b", folder_id: "OUT" },
      ),
    ).toBe(false);
    expect(
      workflowFoldersClash(
        { id: "a", folder_id: "SAME" },
        { id: "a", folder_id: "SAME" },
      ),
    ).toBe(true);
    expect(
      workflowFoldersClash(
        { id: "a", folder_id: "FOLDER" },
        { id: "b", folder_id: "FOLDER" },
      ),
    ).toBe(true);
  });
});
