/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Version of the frontend (package.json), set at build time by vite.config.ts.
declare const __APP_VERSION__: string
