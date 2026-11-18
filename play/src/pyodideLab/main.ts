/**
 * 클라이언트 AI 시제품 화면. ?auto=off,on 이면 불러온 뒤 차례로 대전을 돌린다.
 * 결과는 화면 표, 콘솔(console.info), window.__clientAiLab에 남는다.
 */
type Reply = { id: number; type: "done" | "error" | "progress"; data?: any; error?: string };

const worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
const pending = new Map<number, { resolve: (value: any) => void; reject: (error: Error) => void }>();
let nextId = 1;
const pageStarted = performance.now();

const lab: { load?: any; games: any[]; progress?: any; error?: string; firstRunMs?: number } = { games: [] };
(window as unknown as { __clientAiLab: typeof lab }).__clientAiLab = lab;

const $ = <T extends HTMLElement>(selector: string) => document.querySelector(selector) as T;
const status = (text: string) => ($("#status").textContent = text);
const log = (text: string) => {
  const element = $("#log");
  element.textContent += `${text}\n`;
  console.info(`[client-ai] ${text}`);
};

worker.onmessage = (event: MessageEvent<Reply>) => {
  const reply = event.data;
  if (reply.type === "progress") {
    lab.progress = reply.data;
    status(`진행 중 · 명령 ${reply.data.commands} · ${reply.data.turn}턴 · ${(reply.data.elapsed_ms / 1000).toFixed(1)}초`);
    return;
  }
  const waiter = pending.get(reply.id);
  if (!waiter) return;
  pending.delete(reply.id);
  if (reply.type === "done") waiter.resolve(reply.data);
  else waiter.reject(new Error(reply.error));
};

function call(message: Record<string, unknown>) {
  const id = nextId++;
  return new Promise<any>((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, ...message });
  });
}

const ms = (value: number | undefined) => (value === undefined ? "-" : value >= 1000 ? `${(value / 1000).toFixed(2)}초` : `${Math.round(value)}ms`);
const kb = (value: number) => `${(value / 1024).toFixed(0)}KB`;

function row(table: string, cells: string[], header?: string) {
  const tr = document.createElement("tr");
  if (header) {
    const th = document.createElement("th");
    th.textContent = header;
    tr.append(th);
  }
  for (const cell of cells) {
    const td = document.createElement("td");
    td.textContent = cell;
    tr.append(td);
  }
  $(`${table} tbody`).append(tr);
}

async function load() {
  status("Pyodide 불러오는 중…");
  ($("#init") as HTMLButtonElement).disabled = true;
  const started = performance.now();
  const data = await call({ type: "init" });
  data.init_wall_ms = performance.now() - started;
  data.since_page_ms = performance.now() - pageStarted;
  data.viewport = `${innerWidth}x${innerHeight}@${devicePixelRatio}`;
  data.user_agent = navigator.userAgent;
  lab.load = data;
  const t = data.timings;
  row("#load", [`${data.pyodide} / Python ${String(data.python).split(" ")[0]}`], "Pyodide");
  row("#load", [ms(t.import_loader_ms + t.load_pyodide_ms)], "Pyodide 런타임 로드");
  row("#load", [`${ms(t.fetch_engine_ms)} 받기 · ${ms(t.import_engine_ms)} import`], "엔진 모듈");
  row("#load", [`${ms(t.fetch_sample_ms)} 받기 · ${ms(t.load_sample_ms)} 파싱`], "규칙 스냅샷");
  row("#load", [ms(data.init_wall_ms)], "불러오기 합계");
  const files = data.sizes.pyodide_files as { name: string; transfer: number; decoded: number }[];
  const pyTransfer = files.reduce((sum, file) => sum + file.transfer, 0);
  const pyDecoded = files.reduce((sum, file) => sum + file.decoded, 0);
  row("#load", [`전송 ${kb(pyTransfer)} · 원본 ${kb(pyDecoded)} (${files.map((file) => file.name).join(", ")})`], "Pyodide 크기");
  row("#load", [`원본 ${kb(data.sizes.engine_raw)} · gzip ${kb(data.sizes.engine_gzip)}`], "엔진 모듈 크기");
  row("#load", [`원본 ${kb(data.sizes.sample_raw)} · gzip ${kb(data.sizes.sample_gzip)} · 카드 ${data.sample.cards}장`], "시작 상태+규칙 크기");
  row("#load", [data.viewport], "창");
  log(`load ${JSON.stringify(data)}`);
  ($("#run-off") as HTMLButtonElement).disabled = false;
  ($("#run-on") as HTMLButtonElement).disabled = false;
  status("준비됨");
}

async function play(engineEval: boolean) {
  const maxCommands = Number(($("#max") as HTMLInputElement).value) || 2000;
  status(`대전 중 (엔진 평가 ${engineEval ? "켬" : "끔"})…`);
  const data = await call({ type: "run", engineEval, seed: "client-ai", maxCommands });
  data.viewport = `${innerWidth}x${innerHeight}`;
  lab.games.push(data);
  if (lab.firstRunMs === undefined) lab.firstRunMs = performance.now() - pageStarted;
  const ready = data.ready_decision;
  row("#games", [
    engineEval ? "켬" : "끔",
    `${data.completed ? "종료" : "미완"} · ${data.reason} · 승자 ${data.winner ?? "-"}`,
    `${data.commands} / ${data.turns}`,
    ms(data.game_ms),
    ready.count ? `${ms(ready.mean)} / ${ms(ready.p90)} / ${ms(ready.max)} (${ready.count}회)` : "-",
    ms(data.other_decision.mean),
    ms(data.submit.mean),
    String(data.simulations_per_ready),
  ]);
  log(`game ${JSON.stringify(data)}`);
  status("준비됨");
  return data;
}

function guard(task: () => Promise<unknown>) {
  return () => task().catch((error: Error) => {
    lab.error = error.message;
    status("오류");
    log(`error ${error.message}`);
  });
}

$("#init").addEventListener("click", guard(load));
$("#run-off").addEventListener("click", guard(() => play(false)));
$("#run-on").addEventListener("click", guard(() => play(true)));

const params = new URLSearchParams(location.search);
if (params.get("max")) ($("#max") as HTMLInputElement).value = params.get("max")!;
if (params.has("auto")) {
  const plan = (params.get("auto") || "off,on").split(",").filter(Boolean);
  guard(async () => {
    await load();
    for (const item of plan) await play(item === "on");
    status("자동 실행 완료");
  })();
}
