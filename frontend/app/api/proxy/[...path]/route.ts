const BACKEND_BASE_URL =
  process.env.JIRA_SUMMARY_BACKEND_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

function buildBackendUrl(pathSegments: string[], requestUrl: string): string {
  const incoming = new URL(requestUrl);
  const path = pathSegments.join("/");
  const target = new URL(`${BACKEND_BASE_URL}/${path}`);
  target.search = incoming.search;
  return target.toString();
}

async function proxyRequest(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const targetUrl = buildBackendUrl(path, request.url);
  const headers = new Headers(request.headers);
  headers.delete("host");
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }
  const response = await fetch(targetUrl, init);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export async function GET(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function POST(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function PUT(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function DELETE(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}
