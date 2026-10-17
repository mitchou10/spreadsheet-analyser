# Changelog

## [0.3.0](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.2.0...v0.3.0) (2026-10-17)


### Features

* **chart:** rebuild the helm chart on the Muffin base with one deployment per worker ([c15b3bc](https://github.com/mitchou10/spreadsheet-analyser/commit/c15b3bc2b9dd9f74ddd0c1798104c0f0d790a94c))


### Code Refactoring

* split the worker into agent-worker and analysis-worker ([f7e150a](https://github.com/mitchou10/spreadsheet-analyser/commit/f7e150a5b8eefb5804e0ba744fe4e1c3724f899c))

## [0.3.0-rc](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.2.0...v0.3.0-rc) (2026-10-17)


### Features

* **chart:** rebuild the helm chart on the Muffin base with one deployment per worker ([9ccd2f9](https://github.com/mitchou10/spreadsheet-analyser/commit/9ccd2f96a319dddf71c9c62c36c7ea1c08c3d20e))


### Code Refactoring

* split the worker into agent-worker and analysis-worker ([8e09e7e](https://github.com/mitchou10/spreadsheet-analyser/commit/8e09e7e28353aebb0229036e5510c037fa22f50d))

## [0.2.0](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.1.0...v0.2.0) (2026-10-17)


### Features

* add asynchronous assistant runs executed by the worker ([6db4363](https://github.com/mitchou10/spreadsheet-analyser/commit/6db436374df97c6f70fcd9323f860433f5ed0173))
* add BFF auth with Keycloak (PKCE + Redis sessions) for backend and frontend ([cb01591](https://github.com/mitchou10/spreadsheet-analyser/commit/cb01591bb93414dba58aafa7a0fe30227c0e7d0a))
* add ChatGPT-style UI with Tailwind, shadcn/ui and collections management ([a28c9b9](https://github.com/mitchou10/spreadsheet-analyser/commit/a28c9b9d40fb7fe376b2a53a83eebd347af161b5))
* add data model, async repositories/services and S3 (RustFS) storage ([e746056](https://github.com/mitchou10/spreadsheet-analyser/commit/e7460565e0c0d3ac46ec3e137f844d195b7e0928))
* add LangGraph plan-then-answer agent and authenticated backend client in the worker ([7173772](https://github.com/mitchou10/spreadsheet-analyser/commit/71737727e9a6cc596490067d37219ae82f0be497))
* administration page to see and manage who has access to what ([b68bece](https://github.com/mitchou10/spreadsheet-analyser/commit/b68becebe3ea3eab6e9a74d3e1622641d358c11f))
* connect frontend to backend (collections, upload, conversations) with routing ([6dce078](https://github.com/mitchou10/spreadsheet-analyser/commit/6dce078aa9f6805ad565ba098d4a171c894e2060))
* model selection per conversation with chat-capable model discovery ([ca10658](https://github.com/mitchou10/spreadsheet-analyser/commit/ca106588819adb9bccda7edd12d4d3b66c623e50))
* spreadsheet analysis worker and analysis search tools for the agent ([595da50](https://github.com/mitchou10/spreadsheet-analyser/commit/595da500d6794d074a0fac92676a5830cff20544))

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
