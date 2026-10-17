/** Only what the backend serves is an image we load (its charts). Anything else a model writes, such as an external
 * URL, is not: loading it would send a request to a site of its choosing, with whatever it put in the address. */
export const isBackendImage = (src: string | null | undefined): src is string => !!src && /^\/api\/[^/]/.test(src)
