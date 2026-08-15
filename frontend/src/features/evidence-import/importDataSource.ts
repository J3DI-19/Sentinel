import type { ImportDataSource } from "./types";
import { HttpImportDataSource } from "./httpImportDataSource";
import { MockImportDataSource } from "./mockImportDataSource";

const useMock = import.meta.env.MODE === "test" || import.meta.env.VITE_TRACEVEIL_DATA_SOURCE === "mock";
export const importDataSource: ImportDataSource = useMock ? new MockImportDataSource() : new HttpImportDataSource();
