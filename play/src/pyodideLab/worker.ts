/**
 * Pyodide에서 서버 엔진·AI 모듈을 그대로 실행하는 Web Worker.
 * 메인 스레드는 화면만 그리고, 판정·AI 계산은 모두 여기서 한다.
 */
import driverSource from "./driver.py?raw";

export const PYODIDE_VERSION = "0.29.5";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

type Request =
  | { id: number; type: "init" }
  | { id: number; type: "run"; engineEval: boolean; seed: string; maxCommands: number };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let pyodide: any = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let driver: any = null;

const post = (message: unknown) => (self as unknown as { postMessage: (value: unknown) => void }).postMessage(message);
const now = () => performance.now();

async function fetchText(url: string) {
  const started = now();
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url}: ${response.status} ${await response.text()}`);
  const text = await response.text();
  return {
    text,
    ms: now() - started,
    raw: Number(response.headers.get("X-Raw-Length") || text.length),
    gzip: Number(response.headers.get("X-Gzip-Length") || 0),
  };
}

async function init() {
  const timings: Record<string, number> = {};
  let started = now();
  const module = await import(/* @vite-ignore */ `${INDEX_URL}pyodide.mjs`);
  timings.import_loader_ms = now() - started;
  started = now();
  pyodide = await module.loadPyodide({ indexURL: INDEX_URL });
  timings.load_pyodide_ms = now() - started;

  const engine = await fetchText("/__client-ai/engine.json");
  timings.fetch_engine_ms = engine.ms;
  started = now();
  const files = JSON.parse(engine.text) as Record<string, string>;
  pyodide.FS.mkdirTree("/lab/lumen_game");
  pyodide.FS.writeFile("/lab/lumen_game/__init__.py", "");
  for (const [name, source] of Object.entries(files)) pyodide.FS.writeFile(`/lab/lumen_game/${name}`, source);
  pyodide.FS.writeFile("/lab/driver.py", driverSource);
  pyodide.runPython("import sys; sys.path.insert(0, '/lab')");
  timings.write_fs_ms = now() - started;
  started = now();
  driver = pyodide.pyimport("driver");
  timings.import_engine_ms = now() - started;

  const sample = await fetchText("/__client-ai/sample.json");
  timings.fetch_sample_ms = sample.ms;
  started = now();
  const summary = JSON.parse(driver.load_sample(sample.text));
  timings.load_sample_ms = now() - started;

  const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
  const pyodideFiles = resources
    .filter((entry) => entry.name.startsWith(INDEX_URL))
    .map((entry) => ({
      name: entry.name.slice(INDEX_URL.length),
      transfer: entry.transferSize,
      encoded: entry.encodedBodySize,
      decoded: entry.decodedBodySize,
      ms: Math.round(entry.duration),
    }));
  return {
    pyodide: PYODIDE_VERSION,
    python: pyodide.runPython("import sys; sys.version").toString(),
    timings,
    sizes: {
      engine_raw: engine.raw,
      engine_gzip: engine.gzip,
      sample_raw: sample.raw,
      sample_gzip: sample.gzip,
      pyodide_files: pyodideFiles,
    },
    sample: summary,
  };
}

function run(request: Extract<Request, { type: "run" }>) {
  const progress = (text: string) => post({ id: request.id, type: "progress", data: JSON.parse(text) });
  const started = now();
  const result = driver.run_game(request.engineEval, request.seed, request.maxCommands, progress);
  const data = JSON.parse(result.toString());
  data.wall_ms = now() - started;
  return data;
}

self.onmessage = async (event: MessageEvent<Request>) => {
  const request = event.data;
  try {
    const data = request.type === "init" ? await init() : run(request);
    post({ id: request.id, type: "done", data });
  } catch (error) {
    post({ id: request.id, type: "error", error: String((error as Error)?.stack || error) });
  }
};
