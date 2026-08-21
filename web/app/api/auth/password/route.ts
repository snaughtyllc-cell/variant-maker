import { NextRequest } from "next/server";

const UPSTREAM = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Proxy email/password login without dropping the session Set-Cookie. */
export async function POST(req: NextRequest) {
  const incoming = new URL(req.url);
  const body = await req.text();
  let res: Response;
  try {
    res = await fetch(`${UPSTREAM}/api/auth/password`, {
      method: "POST",
      redirect: "manual",
      headers: {
        cookie: req.headers.get("cookie") ?? "",
        host: incoming.host,
        "content-type": req.headers.get("content-type") ?? "application/json",
        "x-forwarded-proto": incoming.protocol.replace(":", ""),
        "x-forwarded-host": incoming.host,
      },
      body,
    });
  } catch {
    return new Response("upstream unavailable", { status: 502 });
  }

  const headers = new Headers();
  const contentType = res.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const setCookie = res.headers.get("set-cookie");
  if (setCookie) headers.set("Set-Cookie", setCookie);
  return new Response(await res.text(), { status: res.status, headers });
}
