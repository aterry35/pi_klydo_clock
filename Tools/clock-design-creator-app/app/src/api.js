export async function apiRequest(path, {
  method = 'GET', body = null, csrfToken = null, headers = {},
} = {}) {
  const requestHeaders = { Accept: 'application/json', ...headers };
  let requestBody = body;
  if (body && !(body instanceof FormData)) {
    requestHeaders['Content-Type'] = 'application/json';
    requestBody = JSON.stringify(body);
  }
  if (csrfToken) requestHeaders['X-CSRF-Token'] = csrfToken;
  const response = await fetch(path, {
    method,
    body: requestBody,
    headers: requestHeaders,
    credentials: 'same-origin',
  });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : null;
  if (!response.ok) throw new Error(payload?.error || `Request failed (${response.status}).`);
  return payload;
}
