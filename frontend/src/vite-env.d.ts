/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TRACEVEIL_DATA_SOURCE?: "api" | "mock";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
