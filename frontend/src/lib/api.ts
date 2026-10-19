// The browser talks to the backend directly (not through the Vite/nginx origin): the BFF session cookie
// is scoped to the backend origin, and its CORS config explicitly allows the frontend one.
// Empty (the default) means same origin: the ingress routes /api to the backend. For a split-host setup
// (docker-compose), VITE_API_BASE_URL points to it, e.g. http://localhost:8000.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// FastAPI errors: {detail: "msg"} for HTTPException, {detail: [{msg, loc}, ...]} for validation errors.
async function toApiError(response: Response): Promise<ApiError> {
  let message = `Erreur ${response.status}`
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) message = body.detail[0].msg
  } catch {
    // Non-JSON error body: keep the generic message.
  }
  return new ApiError(response.status, message)
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  // For FormData the browser must set the multipart Content-Type (with its boundary) itself.
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE_URL}/api${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) throw await toApiError(response)
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

export const jsonBody = (data: unknown): string => JSON.stringify(data)
