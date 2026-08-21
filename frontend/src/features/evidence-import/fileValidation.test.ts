import { describe, expect, it } from "vitest";
import { MAX_EVIDENCE_FILE_BYTES, inspectEvidenceFile } from "./fileValidation";

function sizedFile(name: string, size: number, type = ""): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("evidence file inspection", () => {
  it("accepts CSV and JSON extensions case-insensitively", () => {
    expect(inspectEvidenceFile(sizedFile("events.CSV", 1)).validation.status).toBe("valid");
    expect(inspectEvidenceFile(sizedFile("events.JsOn", 1)).validation.status).toBe("valid");
  });

  it("accepts a file exactly at the 50 MiB boundary", () => {
    expect(inspectEvidenceFile(sizedFile("events.csv", MAX_EVIDENCE_FILE_BYTES)).validation.status).toBe("valid");
  });

  it.each([
    ["empty.csv", 0, "empty_file"],
    ["events.jsonl", 1, "unsupported_type"],
    ["events.csv", MAX_EVIDENCE_FILE_BYTES + 1, "file_too_large"],
  ])("rejects %s with a stable code", (name, size, code) => {
    const result = inspectEvidenceFile(sizedFile(name, size));
    expect(result.validation).toMatchObject({ status: "invalid", code });
  });
});
