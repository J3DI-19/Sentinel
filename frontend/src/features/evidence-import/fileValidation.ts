import type { SelectedEvidenceFile } from "./types";

export const MAX_EVIDENCE_FILE_BYTES = 50 * 1024 * 1024;
export const ACCEPTED_EVIDENCE_EXTENSIONS = ".csv,.json";

export function inspectEvidenceFile(file: File): SelectedEvidenceFile {
  const extension = file.name.split(".").pop()?.toLowerCase();
  const mediaType = extension === "csv" ? "text/csv" : "application/json";
  let validation: SelectedEvidenceFile["validation"] = { status: "valid" };

  if (file.size === 0) validation = { status: "invalid", code: "empty_file", message: "The selected file is empty." };
  else if (extension !== "csv" && extension !== "json") validation = { status: "invalid", code: "unsupported_type", message: "Choose a CSV or JSON file." };
  else if (file.size > MAX_EVIDENCE_FILE_BYTES) validation = { status: "invalid", code: "file_too_large", message: "The selected file exceeds the 50 MiB limit." };

  return { file, name: file.name, mediaType, sizeBytes: file.size, validation };
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const mib = bytes / (1024 * 1024);
  if (mib >= 1) return `${mib.toFixed(mib >= 10 ? 1 : 2)} MiB`;
  return `${(bytes / 1024).toFixed(1)} KiB`;
}
