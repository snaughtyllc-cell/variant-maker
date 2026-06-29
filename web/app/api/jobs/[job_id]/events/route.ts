import { NextRequest } from "next/server";

const UPSTREAM = process.env.API_PROXY_TARGET || "http://localhost:8000";

export const dynamic = "force-dynamic";
export const runtime = "edge";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ job_id: string }> }
) {
  const { job_id } = await params;
  let upstream: Response;
  try {
    upstream = await fetch(`${UPSTREAM}/api/jobs/${job_id}/events`, {
      headers: { Accept: "text/event-stream" },
    });
  } catch {
    return new Response("upstream unavailable", { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    return new Response("upstream error", { status: upstream.status || 502 });
  }

  const upstreamReader = upstream.body.getReader();

  const stream = new ReadableStream({
    async pull(controller) {
      const { value, done } = await upstreamReader.read();
      if (done) {
        controller.close();
        return;
      }
      controller.enqueue(value);
    },
    cancel() {
      upstreamReader.cancel();
    },
  });

  return new Response(stream, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
