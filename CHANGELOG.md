# Changelog

## [0.2.0-rc](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.1.0...v0.2.0-rc) (2026-10-17)


### Features

* add asynchronous assistant runs executed by the worker ([309bfdd](https://github.com/mitchou10/spreadsheet-analyser/commit/309bfdd16474a1e1391ba8a6bfab1c0ae42043e4))
* add BFF auth with Keycloak (PKCE + Redis sessions) for backend and frontend ([7dabb63](https://github.com/mitchou10/spreadsheet-analyser/commit/7dabb63993d7e1ea73e174e7b0e641872bcb8f17))
* add ChatGPT-style UI with Tailwind, shadcn/ui and collections management ([ef26788](https://github.com/mitchou10/spreadsheet-analyser/commit/ef26788e0789ff9c49bd422c20f1e9a9137836ad))
* add data model, async repositories/services and S3 (RustFS) storage ([06a3f01](https://github.com/mitchou10/spreadsheet-analyser/commit/06a3f01155356a3c62708e2bceba834ca46a4da6))
* add LangGraph plan-then-answer agent and authenticated backend client in the worker ([4848326](https://github.com/mitchou10/spreadsheet-analyser/commit/4848326f2fccb2fff4d3548b5b8b89f944c2506f))
* administration page to see and manage who has access to what ([9cc7420](https://github.com/mitchou10/spreadsheet-analyser/commit/9cc74205d085004ec8f2b44511d73cad3015f648))
* connect frontend to backend (collections, upload, conversations) with routing ([ddaccc6](https://github.com/mitchou10/spreadsheet-analyser/commit/ddaccc695e6fe533b7acec2d8526622be05e49be))
* model selection per conversation with chat-capable model discovery ([e5e6364](https://github.com/mitchou10/spreadsheet-analyser/commit/e5e636429ffa0e278e6add01af5b27c3ae31b56e))
* spreadsheet analysis worker and analysis search tools for the agent ([1110654](https://github.com/mitchou10/spreadsheet-analyser/commit/11106542fcece2b9ca1d57e8f9d7c2486c4a5c95))
