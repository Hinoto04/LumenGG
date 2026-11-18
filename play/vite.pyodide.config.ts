import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { defineConfig, type Plugin } from "vite";

/**
 * Pyodide 클라이언트 AI 시제품 전용 개발 서버(기존 vite.config.ts와 별개).
 *
 *   node play/node_modules/vite/bin/vite.js --config play/vite.pyodide.config.ts
 *   → http://127.0.0.1:5176/pyodide-lab.html  (?auto=off,on 이면 자동 실행)
 *
 * /__client-ai/engine.json  엔진·AI 모듈 원본을 {파일 이름: 소스}로 묶어 제공(서버 코드 수정 없음)
 * /__client-ai/sample.json  scripts/export_client_ai_sample.py가 만든 시작 상태와 규칙 스냅샷
 * 둘 다 Accept-Encoding이 허용하면 gzip으로 보내 실제 전송 크기를 브라우저에서 잴 수 있게 한다.
 */
const repo = path.resolve(__dirname, "..");
const gameDir = path.join(repo, "LumenGG/battlelog/game");
const sampleFile = path.join(repo, ".temp/client-ai/sample.json");

/** Django를 쓰지 않고 대전·AI에 필요한 모듈만. catalog·training·sandbox·review·drafts는 뺀다. */
export const ENGINE_FILES = [
  "engine.py",
  "effects.py",
  "spec.py",
  "handlers.py",
  "card_identity.py",
  "ai.py",
  "ai_profile.py",
  "ai_preview.py",
  "ai_decisions.py",
  "ai_matrix.py",
  "ai_engine_eval.py",
  "ai_effect_defaults.toml",
  "ai_profile_template.toml",
];

function send(req: { headers: Record<string, string | string[] | undefined> }, res: any, body: Buffer) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Raw-Length", String(body.length));
  const accept = String(req.headers["accept-encoding"] || "");
  if (accept.includes("gzip")) {
    const gz = zlib.gzipSync(body, { level: 9 });
    res.setHeader("Content-Encoding", "gzip");
    res.setHeader("X-Gzip-Length", String(gz.length));
    res.end(gz);
  } else {
    res.end(body);
  }
}

function clientAi(): Plugin {
  return {
    name: "lumen-client-ai",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__client-ai/", (req, res) => {
        const name = (req.url || "/").slice(1).split("?")[0];
        if (name === "engine.json") {
          const files: Record<string, string> = {};
          for (const file of ENGINE_FILES) files[file] = fs.readFileSync(path.join(gameDir, file), "utf8");
          send(req, res, Buffer.from(JSON.stringify(files), "utf8"));
          return;
        }
        if (name === "sample.json") {
          if (!fs.existsSync(sampleFile)) {
            res.statusCode = 404;
            res.end('{"error":"scripts/export_client_ai_sample.py를 먼저 실행하세요."}');
            return;
          }
          send(req, res, fs.readFileSync(sampleFile));
          return;
        }
        res.statusCode = 404;
        res.end("{}");
      });
    },
  };
}

export default defineConfig({
  root: __dirname,
  plugins: [clientAi()],
  server: { port: 5176, strictPort: true, host: "127.0.0.1" },
  worker: { format: "es" },
});
