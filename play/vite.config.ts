import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const fixtureDir = path.resolve(__dirname, "fixtures");

/**
 * 개발 서버 전용: play/fixtures/*.json을 /__fixtures/ 아래로 제공한다.
 * 픽스처는 scripts/export-play-fixtures.ps1로 만든다.
 */
function fixtures(): Plugin {
  return {
    name: "lumen-play-fixtures",
    apply: "serve",
    configureServer(server) {
      server.watcher.add(fixtureDir);
      server.middlewares.use("/__fixtures/", (req, res) => {
        const name = decodeURIComponent((req.url || "/").slice(1).split("?")[0]);
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.setHeader("Cache-Control", "no-store");
        if (!name || name === "index.json") {
          const files = fs.existsSync(fixtureDir)
            ? fs.readdirSync(fixtureDir).filter((file) => /^step-.*\.json$/.test(file)).sort()
            : [];
          res.end(JSON.stringify(files));
          return;
        }
        const file = path.join(fixtureDir, path.basename(name));
        if (!fs.existsSync(file)) {
          res.statusCode = 404;
          res.end("{}");
          return;
        }
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

/** 격리된 개발 게임 서버(scripts/serve-play-dev.ps1). 같은 출처로 프록시해 CORS·쿠키 문제를 피한다. */
const backend = process.env.LUMEN_PLAY_SERVER ?? "http://127.0.0.1:8874";

/**
 * vite build --mode django: Django가 /battlelog/play/에서 제공할 번들을 LumenGG/static/play/에 만든다.
 * 템플릿(templates/battlelog/play.html)이 이름으로 참조하므로 파일 이름에 해시를 붙이지 않는다.
 * 캐시 무효화는 Django의 정적 파일 저장소(collectstatic)가 맡는다.
 */
const djangoBuild = {
  base: "/static/play/",
  build: {
    outDir: path.resolve(__dirname, "../LumenGG/static/play"),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve(__dirname, "src/main.tsx"),
      output: {
        entryFileNames: "play.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: (asset: { names?: string[] }) =>
          (asset.names ?? []).some((name) => name.endsWith(".css")) ? "play.css" : "assets/[name][extname]",
      },
    },
  },
};

export default defineConfig(({ mode }) => ({
  plugins: [react(), fixtures()],
  ...(mode === "django" ? djangoBuild : {}),
  server: {
    port: 5175,
    strictPort: true,
    proxy: {
      "/battlelog": backend,
      "/play-dev": backend,
      "/static": backend,
      "/ws": { target: backend, ws: true },
    },
  },
}));
