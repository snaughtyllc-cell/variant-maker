// Usage: node web/scripts/sse-smoke.mjs <path-to-fixture.mp4>
// Posts a 1-variant job through the proxy, streams events, prints arrival deltas.
// Uses Node.js http module for SSE to avoid undici fetch buffering in Node v25.
import { readFileSync } from "node:fs";
import http from "node:http";

const BASE_URL = new URL("http://localhost:3000");
const file = process.argv[2];

// Step 1: POST the job via fetch (not streaming, so undici buffering is fine here)
const fd = new FormData();
fd.append("count", "1");
fd.append("files", new Blob([readFileSync(file)], { type: "video/mp4" }), "smoke.mp4");
const created = await (await fetch(`${BASE_URL.origin}/api/jobs`, { method: "POST", body: fd })).json();
console.log("job", created.job_id);

// Step 2: Stream SSE via http module to get true per-chunk timing
let t0 = Date.now(), seen = 0;
await new Promise((resolve, reject) => {
  const req = http.get({
    hostname: BASE_URL.hostname,
    port: BASE_URL.port || 80,
    path: `/api/jobs/${created.job_id}/events`,
    headers: { Accept: "text/event-stream" },
  }, (res) => {
    let buf = "";
    res.on("data", (chunk) => {
      buf += chunk.toString();
      const lines = buf.split("\n");
      buf = lines.pop(); // keep incomplete last line
      for (const line of lines) {
        if (line.startsWith("data:")) {
          seen++;
          console.log(`+${Date.now() - t0}ms`, line.slice(5).trim().slice(0, 80));
          if (line.includes("job-done")) {
            console.log(`OK: ${seen} events, streamed incrementally`);
            resolve();
          }
        }
      }
    });
    res.on("end", () => resolve());
    res.on("error", reject);
  });
  req.on("error", reject);
});
