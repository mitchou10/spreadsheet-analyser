# Changelog

## [0.6.2](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.6.1...v0.6.2) (2026-10-18)


### Bug Fixes

* **helm:** keep the default storage of the cnpg cluster, it cannot shrink ([028f085](https://github.com/mitchou10/spreadsheet-analyser/commit/028f085d6c86f352e3694591fa918bad5e93acd7))

## [0.6.1](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.6.0...v0.6.1) (2026-10-18)


### Bug Fixes

* **helm:** deploy redis with the bundled chart and point REDIS_URL at its service ([2620973](https://github.com/mitchou10/spreadsheet-analyser/commit/262097351b0a9728236ee43117822e555e0e57af))
* **helm:** set the resources and the storage of the cnpg cluster for the namespace quota ([6d51f5f](https://github.com/mitchou10/spreadsheet-analyser/commit/6d51f5fb1caae27aa52f89ce50502b8e5168da01))

## [0.6.0](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.5.1...v0.6.0) (2026-10-18)


### Features

* **helm:** expose the frontend and the backend through one ingress with an IP allowlist ([645cbfd](https://github.com/mitchou10/spreadsheet-analyser/commit/645cbfdd605da9afde1b2fa1ac9f76ec30d4e7a8))


### Bug Fixes

* **helm:** add the cnpg cluster dependency and commit the chart archives ([e4b8d44](https://github.com/mitchou10/spreadsheet-analyser/commit/e4b8d44c2ded146c961ef0801c8302632cc58b1f))
* **helm:** read the Vault secrets from global.vaultMount/vaultEnv and run PostgreSQL with cnpg ([4e2bbbe](https://github.com/mitchou10/spreadsheet-analyser/commit/4e2bbbe79dffeac4c20002b00d604a0e204875ad))

## [0.5.1](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.5.0...v0.5.1) (2026-10-18)


### Bug Fixes

* **secrets:** update mount paths to use environment variable for Vault KV mount ([c3e4c1c](https://github.com/mitchou10/spreadsheet-analyser/commit/c3e4c1ce0196fe9463d4954c275ff55515c12a3f))

## [0.5.0](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.4.0...v0.5.0) (2026-10-18)


### Features

* **agent-worker:** let the agent count and list the collections and files of the account ([b9f7db7](https://github.com/mitchou10/spreadsheet-analyser/commit/b9f7db7fead285c1875d586adabf72dcfaba45af))
* **agent-worker:** let the agent draw a chart of the result of a query ([ebdd3c8](https://github.com/mitchou10/spreadsheet-analyser/commit/ebdd3c8679df49f1d822aae49153c66ecc8eebd3))
* **agent-worker:** let the agent query the real rows of the files with SQL ([07b7f3a](https://github.com/mitchou10/spreadsheet-analyser/commit/07b7f3a496f7c75a94573c825f5051f7c0aef93a))
* **agent-worker:** send the plan, the files and the tool calls with each answer ([f6b5434](https://github.com/mitchou10/spreadsheet-analyser/commit/f6b5434b042c6a846d2605c29ae2f243796aa39a))
* **analysis-worker:** draw the charts from the result of a query ([354670a](https://github.com/mitchou10/spreadsheet-analyser/commit/354670aa9939d25c1bf1f08dc31a89abdda953ef))
* **analysis-worker:** run sandboxed SQL queries on the parquet copies ([2bec429](https://github.com/mitchou10/spreadsheet-analyser/commit/2bec4298c3d4d7c67027c084d0c0c3739bbc2a0a))
* **analysis-worker:** write a typed parquet copy of every sheet ([e8b204f](https://github.com/mitchou10/spreadsheet-analyser/commit/e8b204fb24068fd317fcaedc64c6b097916d89ef))
* **backend:** describe the requester's whole account to the agent worker ([8290029](https://github.com/mitchou10/spreadsheet-analyser/commit/82900298ebdce7ec49a36d9d62a7455b03b00925))
* **backend:** name the sources of a message, page the messages and store the agent's trace ([a10bc9d](https://github.com/mitchou10/spreadsheet-analyser/commit/a10bc9d60c159dd7dfceacc3dae8ce34ac8d8522))
* **backend:** queue, authorise and keep the SQL queries of the agent ([055c2d0](https://github.com/mitchou10/spreadsheet-analyser/commit/055c2d0995133b8561208103d096f76598c7d205))
* **backend:** store, serve and authorise the charts of an answer ([ae8b52a](https://github.com/mitchou10/spreadsheet-analyser/commit/ae8b52aeddea84ea4614b637ce2e04823416ac1b))
* **frontend:** choose the sources with a plus menu, page the chat and show the agent's tools ([a4232e9](https://github.com/mitchou10/spreadsheet-analyser/commit/a4232e912ef596190f0f0f2225244502d6265b00))
* **frontend:** import a file from the chat into a collection ([951c35e](https://github.com/mitchou10/spreadsheet-analyser/commit/951c35e24a3cfa2322bba8d2536032794b1a4711))
* **frontend:** render the assistant's answers as markdown ([7a86942](https://github.com/mitchou10/spreadsheet-analyser/commit/7a869429566dbbdcbd5cd10cc9c5d6d627904130))
* **frontend:** render the plan and the output of the tools as markdown ([87f3fe2](https://github.com/mitchou10/spreadsheet-analyser/commit/87f3fe2fbc245c0b9e496960b6acad20fd20d7e4))
* **frontend:** show the charts of an answer in its markdown ([686c201](https://github.com/mitchou10/spreadsheet-analyser/commit/686c2015323445f3c173e58b0c00162c711c8f11))
* **frontend:** show the SQL of a query and its result as a table ([5ac0c76](https://github.com/mitchou10/spreadsheet-analyser/commit/5ac0c766b67726ed2ea386ef5539f0e0643776b3))
* run the queries in their own worker and document them ([4784160](https://github.com/mitchou10/spreadsheet-analyser/commit/4784160bb83f1068642b8a87b19c6821a0bf8942))


### Bug Fixes

* **agent-worker:** do not end a failed query's message with two periods ([5bf37a2](https://github.com/mitchou10/spreadsheet-analyser/commit/5bf37a2989b159ffeaeea6fc158f29c2496e7f59))
* **backend:** start every S3 key with the project level and keep old objects reachable ([a6ef896](https://github.com/mitchou10/spreadsheet-analyser/commit/a6ef8964b496b0adc020207b177a1c6cc869ad7e))
* drop LLM_DEFAULT_MODEL and default to the first model the provider offers ([3c5fa68](https://github.com/mitchou10/spreadsheet-analyser/commit/3c5fa68853c93dd3535e69f3636f7c19eae43728))
* **workers:** start the search index keys with the project level ([d32e91f](https://github.com/mitchou10/spreadsheet-analyser/commit/d32e91ffb51c11070929de3828d07d31c43d4f44))


### Dependencies

* pass S3_KEY_PREFIX to the services that build or read S3 keys ([659f2e3](https://github.com/mitchou10/spreadsheet-analyser/commit/659f2e3f032b376228498560dbb73827ea3cf6d8))

## [0.5.0-rc.1](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.5.0-rc...v0.5.0-rc.1) (2026-10-18)


### Features

* **agent-worker:** let the agent count and list the collections and files of the account ([5d25a8e](https://github.com/mitchou10/spreadsheet-analyser/commit/5d25a8eeae806d3d0e6c074c8b5d2dc7d029e49a))
* **agent-worker:** let the agent draw a chart of the result of a query ([45036a0](https://github.com/mitchou10/spreadsheet-analyser/commit/45036a0bef8d2f0765a38e825b06d2578e255552))
* **agent-worker:** let the agent query the real rows of the files with SQL ([a021c95](https://github.com/mitchou10/spreadsheet-analyser/commit/a021c956d512a1442798423cffa2562adb8e7602))
* **analysis-worker:** draw the charts from the result of a query ([d5e4794](https://github.com/mitchou10/spreadsheet-analyser/commit/d5e47945d8980b813291daee54083d166e0f634e))
* **analysis-worker:** run sandboxed SQL queries on the parquet copies ([942b3e4](https://github.com/mitchou10/spreadsheet-analyser/commit/942b3e49377edec06f679fcea7b0ecbd2e2a9bb0))
* **analysis-worker:** write a typed parquet copy of every sheet ([711af31](https://github.com/mitchou10/spreadsheet-analyser/commit/711af3189e9fb4817649fbd42c429d60ad494f9b))
* **backend:** describe the requester's whole account to the agent worker ([bd19f61](https://github.com/mitchou10/spreadsheet-analyser/commit/bd19f611716a64c207edcc88df1b1e2f163f159a))
* **backend:** queue, authorise and keep the SQL queries of the agent ([20cc3ec](https://github.com/mitchou10/spreadsheet-analyser/commit/20cc3ec76803d0c9e2f15fe12340fe9b6cada051))
* **backend:** store, serve and authorise the charts of an answer ([a671bab](https://github.com/mitchou10/spreadsheet-analyser/commit/a671baba5130c210e29bb46ab7e3bb331b9e6cbb))
* **frontend:** import a file from the chat into a collection ([2643892](https://github.com/mitchou10/spreadsheet-analyser/commit/264389264736177eb8fa95d36ac184f0690d9d61))
* **frontend:** render the plan and the output of the tools as markdown ([d5d2e8c](https://github.com/mitchou10/spreadsheet-analyser/commit/d5d2e8cab690ee3ecf9f8adc81963a0f402423dc))
* **frontend:** show the charts of an answer in its markdown ([2208b63](https://github.com/mitchou10/spreadsheet-analyser/commit/2208b6301a867173ee8f444aa0e086f1b2d50968))
* **frontend:** show the SQL of a query and its result as a table ([1b5e806](https://github.com/mitchou10/spreadsheet-analyser/commit/1b5e80658e2735a46608d206b55cc4f606991fc8))
* run the queries in their own worker and document them ([6d65d98](https://github.com/mitchou10/spreadsheet-analyser/commit/6d65d98f3ec4ad8b2858424c76d4ec42c41a3ca8))


### Bug Fixes

* **agent-worker:** do not end a failed query's message with two periods ([70cb335](https://github.com/mitchou10/spreadsheet-analyser/commit/70cb335911c7e5e84bd5d42872901c5aa774a8a1))

## [0.5.0-rc](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.4.1-rc...v0.5.0-rc) (2026-10-17)


### Features

* **agent-worker:** send the plan, the files and the tool calls with each answer ([bceff09](https://github.com/mitchou10/spreadsheet-analyser/commit/bceff09b7c310891065360c398096d79e8262ee0))
* **backend:** name the sources of a message, page the messages and store the agent's trace ([c9bbc33](https://github.com/mitchou10/spreadsheet-analyser/commit/c9bbc33a429e7ab4ecd78aade9336a7e7ca61f97))
* **frontend:** choose the sources with a plus menu, page the chat and show the agent's tools ([e794bc0](https://github.com/mitchou10/spreadsheet-analyser/commit/e794bc0dc96957598fe9d6b16ef8db8ec67384f7))
* **frontend:** render the assistant's answers as markdown ([9581df6](https://github.com/mitchou10/spreadsheet-analyser/commit/9581df6bd005f57c6758f2ad4f4dc30b4fd24d5d))


### Bug Fixes

* drop LLM_DEFAULT_MODEL and default to the first model the provider offers ([8d3268c](https://github.com/mitchou10/spreadsheet-analyser/commit/8d3268c70abc997ac033cd63d82bbbea61ecf3dc))

## [0.4.1-rc](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.4.0...v0.4.1-rc) (2026-10-17)


### Bug Fixes

* **backend:** start every S3 key with the project level and keep old objects reachable ([92f42f0](https://github.com/mitchou10/spreadsheet-analyser/commit/92f42f0d7d5581fc498d2c5696bfc752888e7fe9))
* **workers:** start the search index keys with the project level ([1ab14df](https://github.com/mitchou10/spreadsheet-analyser/commit/1ab14df2a1c8d137edc17bc853f612c86aa698a9))


### Dependencies

* pass S3_KEY_PREFIX to the services that build or read S3 keys ([0dd46ee](https://github.com/mitchou10/spreadsheet-analyser/commit/0dd46ee16c34fcd7c977414b86befeb78b0be178))

## [0.4.0](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.3.0...v0.4.0) (2026-10-17)


### Features

* **agent-worker:** search the saved BM25 index of each collection, indexing the rest in memory ([c3e3bea](https://github.com/mitchou10/spreadsheet-analyser/commit/c3e3bea6e19350b1414ac3a98c18fbca2eee15b8))
* **agent-worker:** search the saved index of the user when a scope spans several collections ([d7fc3e7](https://github.com/mitchou10/spreadsheet-analyser/commit/d7fc3e7086899c985c69e38f478b3a2d711b814f))
* **analysis-worker:** keep the search index of each collection up to date in S3 ([f8e3aa1](https://github.com/mitchou10/spreadsheet-analyser/commit/f8e3aa16ce64c6910668543f4993291144a0a2d8))
* **backend:** drive the index worker and tell it who can read what ([f41c761](https://github.com/mitchou10/spreadsheet-analyser/commit/f41c7611019c89ddf19d54bb8b0108a24adf271d))
* **backend:** feed and trigger the search index (context, ready analyses, forget, rebuild) ([5eceab5](https://github.com/mitchou10/spreadsheet-analyser/commit/5eceab5efff72f524677c69d3e574012960f1247))
* **chart:** deploy the index worker ([624bde1](https://github.com/mitchou10/spreadsheet-analyser/commit/624bde12497157ccb2ac70ecd681515161604df9))
* **index-worker:** add a worker that keeps the collection and user search indexes up to date ([0089d98](https://github.com/mitchou10/spreadsheet-analyser/commit/0089d98b9357958647f3a732bb032bf7f7bf9dd2))


### Bug Fixes

* use a single dollar in the worker image healthchecks ([5d0a650](https://github.com/mitchou10/spreadsheet-analyser/commit/5d0a650c9a0f369e25ce496709129f8cda900d95))


### Code Refactoring

* **analysis-worker:** leave the search indexes to the index worker ([2d1fd52](https://github.com/mitchou10/spreadsheet-analyser/commit/2d1fd52ebec3184d9fad2cc4b4f527e6e5df817a))

## [0.4.0-rc](https://github.com/mitchou10/spreadsheet-analyser/compare/v0.3.0...v0.4.0-rc) (2026-10-17)


### Features

* **agent-worker:** search the saved BM25 index of each collection, indexing the rest in memory ([97216b3](https://github.com/mitchou10/spreadsheet-analyser/commit/97216b3356d39a51b9cfa4adfdfab5fad8d1bf5c))
* **agent-worker:** search the saved index of the user when a scope spans several collections ([05ef913](https://github.com/mitchou10/spreadsheet-analyser/commit/05ef913851c5b188ec53691a75d2e831469fea81))
* **analysis-worker:** keep the search index of each collection up to date in S3 ([8693c48](https://github.com/mitchou10/spreadsheet-analyser/commit/8693c48059dc35ede97b5be3396177890237076f))
* **backend:** drive the index worker and tell it who can read what ([80aff20](https://github.com/mitchou10/spreadsheet-analyser/commit/80aff202e489cdbc830b68b031fc74dc99dc0d87))
* **backend:** feed and trigger the search index (context, ready analyses, forget, rebuild) ([1faf5a9](https://github.com/mitchou10/spreadsheet-analyser/commit/1faf5a9f74a3f07b21b4494a22e5ce1b3d6db613))
* **chart:** deploy the index worker ([cf66f79](https://github.com/mitchou10/spreadsheet-analyser/commit/cf66f79ca5834b05188c4b1553ecd89007032cdd))
* **index-worker:** add a worker that keeps the collection and user search indexes up to date ([9b39e44](https://github.com/mitchou10/spreadsheet-analyser/commit/9b39e44f4e2cddf05496ee9b79a2c1c25e9f3dd7))


### Bug Fixes

* use a single dollar in the worker image healthchecks ([1f0ea78](https://github.com/mitchou10/spreadsheet-analyser/commit/1f0ea786ef9c9a5d9e22d8b834f1dba489896c29))


### Code Refactoring

* **analysis-worker:** leave the search indexes to the index worker ([17cccf7](https://github.com/mitchou10/spreadsheet-analyser/commit/17cccf75e00a4134f8b7de180f3ae18202552434))

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
