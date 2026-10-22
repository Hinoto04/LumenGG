(() => {
  const home = document.querySelector("[data-party-home]");
  const root = document.querySelector("[data-party-room]");
  if (!home && !root) return;
  const colors = ["#e4b76a", "#87c9e4", "#c2a0ea", "#91d4ab"];
  const csrf =
    document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  const storageKey = (code) => `lumendb.party.${code}`;
  const stored = (key) => {
    try {
      return localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  };
  const remember = (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {}
  };
  const error = (message) => {
    document.querySelector("[data-party-error]").textContent = message || "";
  };
  function node(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  let busy = false;
  let advanceTimer = null;
  let endTurnTimer = null,
    automaticActionTimer = null;
  let arrivalChoiceKey = "",
    arrivalSelection = null;
  let online = false;
  let pollFlight = false;
  let state = root
    ? JSON.parse(document.getElementById("party-initial-state").textContent)
    : null;
  let token = root ? stored(storageKey(root.dataset.code)) : "";
  let selectedTile = null;
  let routeTarget = null,
    routeRollKey = "";
  let releasedEncounter = "",
    duelTarget = null;
  let itemSelection = null;
  let inventoryDrag = null,
    raisedInventory = null,
    inventoryKey = "";
  let cardPreview = null;
  const rosterCards = new Map();
  let world = null;
  let mapMode = "3d";
  let worldFailed = false;
  let flatMapKey = "";
  let movementHold = null;
  function finishMovement(version) {
    if (!movementHold || movementHold.version !== version) return;
    movementHold = null;
    queueMicrotask(render);
  }
  let rollTimer = null;
  let eventTimer = null;
  let serverOffset = (state?.server_time || Date.now()) - Date.now();
  function accept(next) {
    const receipt = next.move_path;
    if (
      state.code !== next.code ||
      state.me?.seat !== next.me?.seat ||
      next.battle
    )
      movementHold = null;
    else if (
      world &&
      mapMode === "3d" &&
      !worldFailed &&
      receipt?.version !== state.move_path?.version &&
      receipt?.nodes.length > 1 &&
      !receipt.teleport
    ) {
      movementHold = {
        version: receipt.version,
        previous: movementHold?.previous || state,
      };
    }
    state = next;
    serverOffset = (next.server_time || Date.now()) - Date.now();
  }
  function rollTimes(roll) {
    const at = (ms) =>
      roll.started_at + ((roll.end_at - roll.started_at) * ms) / 3200;
    return {
      rolling: roll.settle_at ?? at(900),
      settled: roll.number_at ?? at(1250),
      number: roll.add_at,
      bonus: roll.count_at ?? at(2050),
      counting: roll.total_at ?? at(2500),
      total: roll.end_at,
    };
  }
  function rollStage() {
    const roll = state.dice_roll;
    const now = Date.now() + serverOffset;
    if (
      !roll ||
      state.status !== "running" ||
      state.expired ||
      roll.turn_number !== state.turn_number ||
      roll.seat !== state.turn ||
      now >= roll.end_at
    )
      return null;
    return (
      Object.entries(rollTimes(roll)).find(([, end]) => now < end)?.[0] || null
    );
  }
  const diePips = {
    1: [4],
    2: [0, 8],
    3: [0, 4, 8],
    4: [0, 2, 6, 8],
    5: [0, 2, 4, 6, 8],
    6: [0, 2, 3, 5, 6, 8],
  };
  function die(value, index, roll, now) {
    const cycling = now < rollTimes(roll).rolling;
    const faces = [1, 5, 2, 6, 3, 4];
    const faceValue = cycling
      ? faces[
          (Math.floor(Math.max(0, now - roll.started_at) / 75) + index * 2) % 6
        ]
      : value;
    const shell = node("div", undefined, "party-die-shell");
    shell.dataset.face = faceValue;
    const face = node("span", undefined, "party-die-face");
    for (let pip = 0; pip < 9; pip++)
      face.append(
        node("i", undefined, diePips[faceValue].includes(pip) ? "is-pip" : ""),
      );
    shell.append(face);
    shell.setAttribute("aria-label", `주사위 ${faceValue}`);
    return shell;
  }
  function renderRoll() {
    clearTimeout(rollTimer);
    const holder = q("[data-party-roll]");
    const stage = rollStage(),
      roll = state.dice_roll;
    holder.hidden = !stage;
    root.classList.toggle("showing-roll", !!stage);
    if (!stage) {
      holder.dataset.key = "";
      holder.replaceChildren();
      return;
    }
    const now = Date.now() + serverOffset,
      times = rollTimes(roll);
    const diceVisible = stage === "rolling" || stage === "settled";
    const key = `${roll.version}:${diceVisible ? (stage === "rolling" ? Math.floor(Math.max(0, now - roll.started_at) / 75) : "settled") : "number"}`;
    holder.dataset.stage = stage;
    if (holder.dataset.key !== key) {
      holder.dataset.key = key;
      holder.replaceChildren();
      holder.append(
        node(
          "p",
          `${state.players.find((p) => p.seat === roll.seat)?.name || "플레이어"}의 주사위`,
          "party-roll-name",
        ),
      );
      if (diceVisible) {
        const dice = node("div", undefined, "party-roll-dice");
        roll.dice_values.forEach((value, index) =>
          dice.append(die(value, index, roll, now)),
        );
        holder.append(dice);
      } else {
        const total = node("div", undefined, "party-roll-number-wrap");
        total.append(node("strong", undefined, "party-roll-value"));
        holder.append(total, node("p", "칸 이동", "party-roll-caption"));
      }
    }
    if (!diceVisible) {
      const modifier = holder.querySelector(".party-roll-modifier");
      if ((stage === "bonus" || stage === "counting") && !modifier)
        holder
          .querySelector(".party-roll-number-wrap")
          .append(node("span", `+${roll.bonus}`, "party-roll-modifier"));
      else if (stage !== "bonus" && stage !== "counting") modifier?.remove();
      const base = roll.dice_values.reduce((a, b) => a + b, 0);
      const progress = Math.max(
        0,
        Math.min(
          1,
          (now - times.bonus) / Math.max(1, times.counting - times.bonus),
        ),
      );
      holder.querySelector(".party-roll-value").textContent =
        base + Math.round(roll.bonus * progress);
    }
    const next =
      stage === "rolling"
        ? Math.min(times.rolling, now + 75)
        : stage === "counting"
          ? Math.min(times.counting, now + 40)
          : times[stage];
    rollTimer = setTimeout(
      render,
      Math.max(20, next - Date.now() - serverOffset + 20),
    );
  }
  function renderEvent() {
    clearTimeout(eventTimer);
    const holder = q("[data-party-event]"),
      event = state.event;
    const now = Date.now() + serverOffset;
    const stage =
      !movementHold && event && !state.expired && state.status === "running"
        ? event.pending && now >= event.show_at && now < event.reveal_until
          ? "card"
          : !event.pending && now < event.effect_until
            ? "effect"
            : null
        : null;
    holder.hidden = !stage;
    root.classList.toggle("showing-event", stage === "card");
    if (!stage) {
      holder.replaceChildren();
      holder.dataset.key = "";
    } else if (holder.dataset.key !== `${event.version}:${stage}`) {
      holder.dataset.key = `${event.version}:${stage}`;
      holder.dataset.stage = stage;
      holder.replaceChildren();
      if (stage === "card") {
        const card = cardVisual(event);
        card.classList.add("party-event-card");
        holder.append(card);
      } else {
        const effect = node("div", undefined, "party-event-effect");
        effect.append(node("h2", event.label), node("p", event.description));
        holder.append(effect);
      }
    }
    if (!event) return;
    const next = [event.show_at, event.reveal_until, event.effect_until]
      .filter((t) => t > now)
      .sort((a, b) => a - b)[0];
    if (next) eventTimer = setTimeout(render, next - now + 20);
    if (
      event.pending &&
      now >= event.reveal_until &&
      !movementHold &&
      myTurn() &&
      online &&
      !busy &&
      !document.hidden
    )
      eventTimer = setTimeout(
        () => void act("resolve_event", { event_version: event.version }),
        80,
      );
  }
  function cardVisual(entry, compact = false) {
    const card = node("div", undefined, "party-card-visual");
    card.setAttribute("role", "img");
    card.setAttribute("aria-label", `${entry.label} · ${entry.description}`);
    if (compact) card.classList.add("is-compact");
    const art = node("img");
    art.src = entry.image;
    art.alt = "";
    art.draggable = false;
    const box = entry.effect_box || {
      left: 0.1,
      top: 60 / 88,
      width: 0.8,
      height: 20.2 / 88,
      fontPt: 8.8,
      lineHeight: 1.25,
    };
    const region = node("div", undefined, "party-card-effect-box");
    region.setAttribute("aria-hidden", "true");
    for (const key of ["left", "top", "width", "height"])
      region.style[key] = `${box[key] * 100}%`;
    card.style.setProperty("--card-font-pt", box.fontPt || 8.8);
    card.style.setProperty("--card-line-height", box.lineHeight || 1.25);
    region.append(node("div", entry.description, "party-card-effect-text"));
    card.append(art, region);
    return card;
  }
  function renderCardPreview() {
    const holder = q("[data-party-card-preview]");
    const entry = state.board.shop[cardPreview];
    holder.hidden = !entry;
    if (!entry) {
      holder.replaceChildren();
      holder.dataset.key = "";
      return;
    }
    const key = JSON.stringify(entry);
    if (holder.dataset.key === key) return;
    holder.dataset.key = key;
    const content = node("div", undefined, "party-card-preview-content");
    const close = button("닫기", () => {
      cardPreview = null;
      renderCardPreview();
    });
    close.disabled = false;
    close.setAttribute("aria-label", "카드 미리보기 닫기");
    content.append(cardVisual(entry), close);
    holder.replaceChildren(content);
    close.focus({ preventScroll: true });
    holder.onkeydown = (event) => {
      if (event.key === "Escape") {
        cardPreview = null;
        renderCardPreview();
      }
      if (event.key === "Tab") {
        event.preventDefault();
        close.focus();
      }
    };
  }
  async function api(url, data, playerToken = token) {
    const response = await fetch(url, {
      method: data === undefined ? "GET" : "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
        "X-Party-Player": playerToken,
      },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok)
      throw new Error(result.error || "요청을 처리하지 못했습니다.");
    return result;
  }
  function saveSeat(result) {
    token = result.token;
    remember(storageKey(result.state.code), token);
    remember("lumendb.party.recent", result.state.code);
  }
  if (home) {
    home
      .querySelector("[data-party-create]")
      .addEventListener("submit", async (event) => {
        event.preventDefault();
        if (busy) return;
        busy = true;
        const button = event.target.querySelector("button");
        button.disabled = true;
        try {
          error("");
          const data = Object.fromEntries(new FormData(event.target));
          data.character_id = Number(data.character_id);
          const result = await api("/battlelog/party/create/", data, "");
          saveSeat(result);
          location.assign(result.state.url);
        } catch (err) {
          error(err.message);
        } finally {
          busy = false;
          button.disabled = false;
        }
      });
    home
      .querySelector("[data-party-enter]")
      .addEventListener("submit", (event) => {
        event.preventDefault();
        location.assign(
          `/battlelog/party/${new FormData(event.target).get("code").trim().toUpperCase()}/`,
        );
      });
    const recent = stored("lumendb.party.recent");
    if (/^[A-Z2-9]{6}$/.test(recent)) {
      const link = node("a", `최근 파티 ${recent}로 복귀`, "party-recent");
      link.href = `/battlelog/party/${recent}/`;
      home.querySelector("[data-party-recent]").append(link);
    }
    return;
  }
  const q = (selector) => root.querySelector(selector);
  const base = `/battlelog/party/${root.dataset.code}/`;
  const me = () =>
    state.players.find((player) => player.seat === state.me?.seat);
  const forwardExits = (player) =>
    player?.forward_exits ?? state.board.nodes[player?.position]?.exits ?? [];
  const myTurn = () =>
    state.status === "running" &&
    state.me?.seat === state.turn &&
    !state.battle &&
    !state.expired;
  const canMove = () =>
    myTurn() &&
    me()?.hp > 0 &&
    !state.counter_prompt &&
    !state.hand_task &&
    !state.move?.reveal_pending &&
    !state.event?.pending &&
    !movementHold &&
    !itemSelection;
  function button(label, run, disabled = false, primary = false) {
    const item = node(
      "button",
      label,
      `v2-button${primary ? " v2-button-primary" : ""}`,
    );
    item.type = "button";
    if (label === "이동") item.classList.add("party-move-button");
    item.disabled = disabled || busy || !online || state.expired;
    item.addEventListener("click", run);
    return item;
  }
  async function act(action, data = {}) {
    if (busy || !online || movementHold) return;
    busy = true;
    if (action === "challenge" || action === "counterattack")
      releasedEncounter = "";
    render();
    try {
      error("");
      const result = await api(`${base}action/`, {
        action,
        expected_version: state.version,
        ...data,
      });
      accept(result.state);
    } catch (err) {
      error(err.message);
      await refresh();
    } finally {
      busy = false;
      render();
      maybeOpenBattle();
    }
  }
  async function refresh() {
    if (pollFlight) return;
    pollFlight = true;
    const readToken = token;
    try {
      const next = await api(`${base}state/`, undefined, readToken);
      if (readToken !== token) return;
      if (
        next.version >= state.version &&
        !(
          next.version === state.version &&
          next.battle &&
          state.battle &&
          next.battle.version < state.battle.version
        )
      )
        accept(next);
      online = true;
    } catch {
      if (readToken !== token) return;
      online = false;
    } finally {
      pollFlight = false;
      render();
      maybeOpenBattle();
    }
  }
  function maybeOpenBattle() {
    const battle = state.battle;
    if (!battle?.control_token || battle.completed || busy) return;
    const key = `lumendb.party.opened.${state.code}`;
    if (stored(key) !== String(battle.id)) {
      remember(key, String(battle.id));
      location.assign(
        battle.calculator_url +
          (battle.calculator_url.includes("?") ? "&" : "?") +
          "choose_ui=1",
      );
    }
  }
  async function switchTestPlayer(value) {
    if (busy || !online || !state.test_controls) return;
    busy = true;
    render();
    try {
      const result = await api(`${base}test-seat/`, {
        seat: value === "spectator" ? value : Number(value),
      });
      saveSeat(result);
      accept(result.state);
      selectedTile = null;
      routeTarget = null;
      releasedEncounter = "";
      itemSelection = null;
      q("[data-party-selection]").hidden = true;
      q("[data-party-tile-info]").textContent =
        "칸을 누르면 효과를 확인할 수 있습니다.";
      if (state.battle)
        remember(`lumendb.party.opened.${state.code}`, String(state.battle.id));
      online = true;
      error("");
      render();
      world?.reset();
    } catch (err) {
      error(err.message);
    } finally {
      busy = false;
      render();
    }
  }
  function renderTestTools() {
    const tools = q("[data-party-test-tools]");
    if (!tools) return;
    tools.hidden = !state.test_controls;
    root.classList.toggle("has-test-controls", !!state.test_controls);
    if (!state.test_controls) return;
    const select = q("[data-party-test-seat]");
    const key = JSON.stringify(state.players.map((p) => [p.seat, p.name]));
    if (select.dataset.players !== key) {
      select.replaceChildren();
      const observer = node("option", "관전");
      observer.value = "spectator";
      select.append(observer);
      state.players.forEach((player) => {
        const option = node("option", `${player.seat + 1}P · ${player.name}`);
        option.value = String(player.seat);
        select.append(option);
      });
      select.dataset.players = key;
    }
    select.value = String(state.me?.seat ?? "spectator");
    select.disabled = busy || !online;
  }
  function drawMap() {
    const map = q("[data-party-map]");
    const exits =
      canMove() && state.move && !state.move_prompt && online && !busy
        ? forwardExits(me())
        : [];
    if (mapMode === "3d" && window.LumenParty3D && !worldFailed) {
      try {
        flatMapKey = "";
        if (!world)
          world = window.LumenParty3D.create(map, {
            onTileSelect: selectTile,
            onMovementComplete: finishMovement,
            onDirectionSelect: chooseDirection,
            interactionRoot: root,
            getInsets: () => {
              if (innerWidth <= 700)
                return { left: 104, right: 12, top: 50, bottom: 142 };
              const roster = q("[data-party-players]").getBoundingClientRect();
              return {
                left: roster.width + 35,
                right: 40,
                top: innerHeight <= 600 ? 96 : 56,
                bottom: innerHeight <= 600 ? 14 : 165,
              };
            },
            onFailure: () => {
              worldFailed = true;
              if (movementHold) finishMovement(movementHold.version);
              world?.dispose();
              world = null;
              drawMap();
            },
          });
        world.update(
          {
            ...state,
            preview_target: routeTarget,
            item_target_nodes:
              itemSelection &&
              state.board.shop[itemSelection.item]?.target === "tile"
                ? state.item_targets?.[itemSelection.item] || []
                : [],
            item_target_node: itemSelection?.node,
          },
          selectedTile,
          exits,
        );
        root.dataset.renderMode = "3d";
        q("[data-party-map-toggle]").setAttribute("aria-label", "전체 지도");
        q("[data-party-map-toggle]").title = "전체 지도";
        q("[data-party-map-toggle]").setAttribute("aria-pressed", "false");
        q("[data-party-map-toggle]").disabled = false;
        root
          .querySelectorAll("[data-party-camera]")
          .forEach((control) => (control.disabled = false));
        return;
      } catch (err) {
        world?.dispose();
        world = null;
        worldFailed = true;
        console.warn("Party 3D fallback:", err.message);
      }
    }
    root.dataset.renderMode = "2d";
    if (movementHold) finishMovement(movementHold.version);
    root
      .querySelectorAll("[data-party-camera]")
      .forEach((control) => (control.disabled = true));
    q("[data-party-map-toggle]").disabled = worldFailed || !window.LumenParty3D;
    q("[data-party-map-toggle]").setAttribute(
      "aria-label",
      worldFailed ? "전체 지도" : "3D 지도로 돌아가기",
    );
    q("[data-party-map-toggle]").title = worldFailed
      ? "전체 지도"
      : "3D 지도로 돌아가기";
    q("[data-party-map-toggle]").setAttribute("aria-pressed", "true");
    const key = JSON.stringify([
      state.version,
      state.me?.seat,
      selectedTile,
      routeTarget,
      itemSelection,
      online,
      busy,
      state.expired,
    ]);
    if (flatMapKey === key) return;
    flatMapKey = key;
    map.replaceChildren();
    const bounds = state.board.bounds || { min: 0, max: 100 };
    const normalize = (value) =>
      ((value - bounds.min) * 100) / (bounds.max - bounds.min);
    const mapNodes = state.board.nodes.map((tile) => ({
      ...tile,
      x: normalize(tile.x),
      y: normalize(tile.y),
    }));
    map.style.setProperty(
      "--party-node-size",
      state.board.version >= 2 ? "4.6%" : "7.5%",
    );
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    const drawn = new Set();
    const preview = state.movement_preview;
    const focused = preview?.routes?.[routeTarget];
    const routeNodes = new Set(preview?.nodes || []);
    const routeEdges = new Set(preview?.edges || []);
    const focusedNodes = new Set(focused?.nodes || []);
    const focusedEdges = new Set(focused?.edges || []);
    mapNodes.forEach((tile) =>
      tile.exits.forEach((id) => {
        const edge = [tile.id, id].sort((a, b) => a - b).join("-");
        if (drawn.has(edge)) return;
        drawn.add(edge);
        const other = mapNodes[id];
        const line = document.createElementNS(svg.namespaceURI, "line");
        for (const [key, value] of Object.entries({
          x1: tile.x,
          y1: tile.y,
          x2: other.x,
          y2: other.y,
        }))
          line.setAttribute(key, value);
        if (tile.ring !== other.ring) line.classList.add("party-bridge");
        line.dataset.edge = edge;
        line.classList.toggle("party-route", routeEdges.has(edge));
        line.classList.toggle(
          "is-route-dimmed",
          !!focused && !focusedEdges.has(edge),
        );
        svg.append(line);
      }),
    );
    const choices = [];
    mapNodes.forEach((tile) =>
      tile.exits.forEach((id) => {
        const other = mapNodes[id];
        const dx = other.x - tile.x,
          dy = other.y - tile.y,
          length = Math.hypot(dx, dy);
        const ux = dx / length,
          uy = dy / length;
        const lane = other.exits.includes(tile.id) ? 0.6 : 0;
        const x = tile.x + dx * 0.55 - uy * lane,
          y = tile.y + dy * 0.55 + ux * lane;
        if (
          exits.length > 1 &&
          me()?.position === tile.id &&
          exits.includes(id)
        ) {
          const choice = node("button", undefined, "party-direction-choice");
          choice.type = "button";
          choice.dataset.from = tile.id;
          choice.dataset.to = id;
          choice.style.left = `${x}%`;
          choice.style.top = `${y}%`;
          const label =
            other.ring === tile.ring
              ? id === (tile.clockwise ?? tile.exits[0])
                ? "시계 방향"
                : "반시계 방향"
              : other.ring === "inner"
                ? "중앙 길"
                : "외곽 길";
          choice.setAttribute("aria-label", `방향 선택 · ${label}`);
          choice.title = label;
          const glyph = node("span", "➜");
          glyph.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
          choice.append(glyph);
          choice.addEventListener("click", () => chooseDirection(id));
          choices.push(choice);
        }
      }),
    );
    map.append(svg);
    mapNodes.forEach((tile) => {
      const item = node("button", undefined, `party-node kind-${tile.kind}`);
      item.type = "button";
      item.style.left = `${tile.x}%`;
      item.style.top = `${tile.y}%`;
      item.classList.toggle("is-next", exits.includes(tile.id));
      item.classList.toggle("is-reachable", routeNodes.has(tile.id));
      item.classList.toggle(
        "is-route-dimmed",
        routeNodes.has(tile.id) && !!focused && !focusedNodes.has(tile.id),
      );
      item.classList.toggle("is-selected", selectedTile === tile.id);
      item.classList.toggle(
        "is-item-target",
        !!itemSelection &&
          state.board.shop[itemSelection.item]?.target === "tile" &&
          (state.item_targets?.[itemSelection.item] || []).includes(tile.id),
      );
      if (state.roadblocks?.some((b) => b.node === tile.id)) {
        const barrier = node("span", "▰", "party-roadblock-marker");
        barrier.title = "통행 금지 · 도착하면 정지";
        item.append(barrier);
      }
      const crate = state.supplies?.find((s) => s.node === tile.id);
      if (crate) {
        const marker = node("span", "▣", "party-supply-marker");
        marker.setAttribute("aria-label", `보급함 · HP ${crate.hp}`);
        item.append(marker);
      }
      const occupants = state.players.filter((p) => p.position === tile.id);
      item.setAttribute(
        "aria-label",
        `${tile.label}${crate ? ` · 보급함 HP ${crate.hp}` : ""}: ${occupants.map((p) => p.name).join(", ") || "빈 칸"}`,
      );
      item.append(node("strong", tile.icon));
      if (tile.background_img) {
        const background = node("img", undefined, "party-tile-background");
        background.src = tile.background_img;
        background.alt = "";
        background.draggable = false;
        background.addEventListener(
          "load",
          () => item.classList.add("has-background"),
          { once: true },
        );
        background.addEventListener("error", () => background.remove(), {
          once: true,
        });
        item.append(background);
      }
      const owner = state.players.find((p) => p.home === tile.id);
      if (tile.kind === "camp" && owner) {
        const img = node("img", undefined, "party-camp-owner");
        img.src = owner.character.icon_img || owner.character.img;
        img.alt = `${owner.name}의 거점`;
        item.append(img);
      }
      const pawns = node("span", undefined, "party-pawns");
      occupants.forEach((player) => {
        const pawn = node("span", undefined, "party-pawn");
        pawn.addEventListener("click", (event) => {
          event.stopPropagation();
          focusPlayer(player.seat);
        });
        pawn.title = `${player.name} · ${player.character.name}`;
        pawn.style.setProperty("--pawn-color", colors[player.seat]);
        const source =
          player.character.body_img ||
          player.character.sd_img ||
          player.character.icon_img ||
          player.character.img;
        if (source) {
          const image = node("img");
          image.src = source;
          image.alt = player.character.name;
          image.draggable = false;
          image.addEventListener("error", () => image.remove(), { once: true });
          pawn.append(image);
        }
        pawn.append(node("b", player.seat + 1));
        pawns.append(pawn);
      });
      item.append(pawns);
      item.addEventListener("click", () => {
        selectTile(tile.id);
      });
      map.append(item);
    });
    map.append(...choices);
  }
  function selectTile(id) {
    const tile = state.board.nodes[id];
    if (!tile) return;
    if (
      itemSelection &&
      state.board.shop[itemSelection.item]?.target === "tile" &&
      state.item_targets?.[itemSelection.item]?.includes(id)
    ) {
      itemSelection.node = id;
      renderItemPicker();
    }
    selectedTile = tile.id;
    const preview = state.movement_preview;
    routeTarget =
      preview?.nodes.includes(id) && preview.routes?.[id] ? id : null;
    showTileInfo(id);
    drawMap();
  }
  function focusPlayer(seat) {
    const player = state.players.find((p) => p.seat === seat);
    if (!player) return;
    if (worldFailed) {
      selectTile(player.position);
      return;
    }
    mapMode = "3d";
    drawMap();
    world?.focusPlayer(seat);
  }
  function showTileInfo(id) {
    const tile = state.board.nodes[id];
    if (!tile) return;
    q("[data-party-selection]").hidden = false;
    const image = q("[data-party-tile-image]");
    image.hidden = !tile.background_img;
    if (tile.background_img) image.src = tile.background_img;
    const owner =
      tile.kind === "camp" && state.players.find((p) => p.home === tile.id);
    q("[data-party-tile-title]").textContent = owner
      ? `${owner.name}의 거점`
      : tile.label;
    q("[data-party-tile-info]").textContent =
      `${tile.description}${routeTarget === id ? " 이 칸으로 이어지는 경로를 강조합니다." : ""}`;
    const crate = state.supplies?.find((s) => s.node === id);
    if (crate)
      q("[data-party-tile-info]").textContent +=
        ` 보급함 HP ${crate.hp}/${crate.max_hp}. 만나면 기술 카드를 속도 오름차순으로 사용해 공격할 수 있습니다. 파괴 보상: 2코인.`;
  }
  function chooseDirection(id) {
    const exits = forwardExits(me());
    if (
      canMove() &&
      state.move &&
      !state.move_prompt &&
      online &&
      !busy &&
      exits.length > 1 &&
      exits.includes(id)
    )
      void act("move", { node: id });
  }
  function renderItemPicker() {
    const holder = q("[data-party-item-picker]");
    holder.hidden = !itemSelection;
    root.classList.toggle("using-item", !!itemSelection);
    root.classList.toggle(
      "placing-item",
      !!itemSelection &&
        state.board.shop[itemSelection.item]?.target === "tile",
    );
    holder.replaceChildren();
    if (!itemSelection) return;
    const selected = itemSelection,
      item = state.board.shop[selected.item];
    holder.append(cardVisual(item));
    if (item.target === "tile")
      holder.append(
        node("h2", item.label),
        node("p", item.description),
        button("카드 보기", () => {
          cardPreview = selected.item;
          renderCardPreview();
        }),
      );
    const choices = node("div", undefined, "party-item-choices");
    const valid = state.item_targets?.[selected.item] || [];
    if (item.target === "player") {
      state.players
        .filter((p) => valid.includes(p.seat))
        .forEach((player) => {
          const choose = button(
            `${player.name} · ♥${player.hp}${player.shielded ? " · 보호막" : ""}`,
            () => {
              selected.target = player.seat;
              renderItemPicker();
            },
          );
          choose.setAttribute(
            "aria-pressed",
            String(selected.target === player.seat),
          );
          choices.append(choose);
        });
      if (!valid.length)
        choices.append(
          node("p", "사거리 내에 선택할 수 있는 캐릭터가 없어요."),
        );
    } else if (item.target === "number") {
      for (let value = 1; value <= 6; value++) {
        const choose = button(String(value), () => {
          selected.value = value;
          renderItemPicker();
        });
        choose.setAttribute("aria-pressed", String(selected.value === value));
        choices.append(choose);
      }
    } else if (item.target === "tile") {
      choices.append(
        node(
          "p",
          selected.node == null
            ? "강조된 칸 중 설치할 곳을 지도에서 선택하세요."
            : `설치 지점: ${state.board.nodes[selected.node].label}`,
        ),
      );
    }
    const disabled =
      item.target === "player"
        ? !valid.includes(selected.target)
        : item.target === "tile"
          ? !valid.includes(selected.node)
          : item.target === "number"
            ? !selected.value
            : false;
    const actions = node("div", undefined, "party-item-picker-actions");
    actions.append(
      button("사용", () => act("use_item", { ...selected }), disabled, true),
      button("취소", () => {
        itemSelection = null;
        render();
      }),
    );
    holder.append(choices, actions);
  }
  function finishInventoryDrag() {
    if (!inventoryDrag) return;
    inventoryDrag.ghost?.remove();
    inventoryDrag.card.style.opacity = "";
    try {
      inventoryDrag.card.releasePointerCapture(inventoryDrag.pointerId);
    } catch {}
    inventoryDrag = null;
    q("[data-party-item-drop]").hidden = true;
    root.classList.remove("dragging-item");
  }
  function useDraggedItem(item) {
    if (
      !state.can_use_items ||
      !online ||
      busy ||
      movementHold ||
      !state.me?.items.includes(item)
    )
      return;
    raisedInventory = null;
    if (state.board.shop[item].target === "self")
      void act("use_item", { item });
    else openItem(item);
  }
  function renderInventory() {
    const items = q("[data-party-items]"),
      visibleMe = movementHold ? movementHold.previous.me : state.me;
    const key = JSON.stringify([
      state.code,
      visibleMe?.seat,
      visibleMe?.items,
      visibleMe?.items.map((item) => state.board.shop[item]),
    ]);
    if (inventoryKey === key) return;
    inventoryKey = key;
    finishInventoryDrag();
    raisedInventory = null;
    items.replaceChildren();
    items.className = "party-items";
    (visibleMe?.items || []).forEach((item, index) => {
      const card = node("button", undefined, "party-item-card");
      card.type = "button";
      card.dataset.item = item;
      card.dataset.slot = index;
      card.setAttribute(
        "aria-label",
        `${state.board.shop[item].label} · 중앙으로 끌어 사용 · 눌러서 카드 보기`,
      );
      card.append(cardVisual(state.board.shop[item], true));
      let suppressClick = false;
      card.addEventListener("click", (event) => {
        if (suppressClick) {
          suppressClick = false;
          return;
        }
        if (
          event.detail === 0 ||
          matchMedia("(hover:hover) and (pointer:fine)").matches ||
          raisedInventory === index
        ) {
          openItem(item);
          return;
        }
        raisedInventory = index;
        items
          .querySelectorAll("button")
          .forEach((el) => el.classList.toggle("is-raised", el === card));
      });
      card.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || inventoryDrag) return;
        event.stopPropagation();
        inventoryDrag = {
          card,
          item,
          index,
          pointerId: event.pointerId,
          x: event.clientX,
          y: event.clientY,
          active: false,
          ghost: null,
        };
        card.setPointerCapture(event.pointerId);
      });
      card.addEventListener("pointermove", (event) => {
        const drag = inventoryDrag;
        if (!drag || drag.card !== card || drag.pointerId !== event.pointerId)
          return;
        if (
          !drag.active &&
          Math.hypot(event.clientX - drag.x, event.clientY - drag.y) > 8
        ) {
          drag.active = true;
          drag.ghost = cardVisual(state.board.shop[item], true);
          drag.ghost.classList.add("party-drag-card");
          document.body.append(drag.ghost);
          card.style.opacity = ".3";
          const drop = q("[data-party-item-drop]");
          drop.hidden = false;
          drop.textContent = state.can_use_items
            ? "여기에 놓아 사용"
            : "아이템은 내 턴의 이동 전에 사용해요";
          root.classList.add("dragging-item");
        }
        if (!drag.active) return;
        event.preventDefault();
        event.stopPropagation();
        drag.ghost.style.left = `${event.clientX}px`;
        drag.ghost.style.top = `${event.clientY}px`;
        const r = q("[data-party-item-drop]").getBoundingClientRect();
        q("[data-party-item-drop]").classList.toggle(
          "is-over",
          event.clientX >= r.left &&
            event.clientX <= r.right &&
            event.clientY >= r.top &&
            event.clientY <= r.bottom &&
            state.can_use_items,
        );
      });
      card.addEventListener("pointerup", (event) => {
        const drag = inventoryDrag;
        if (!drag || drag.card !== card) return;
        const r = q("[data-party-item-drop]").getBoundingClientRect();
        const use =
          drag.active &&
          event.clientX >= r.left &&
          event.clientX <= r.right &&
          event.clientY >= r.top &&
          event.clientY <= r.bottom;
        suppressClick = drag.active;
        finishInventoryDrag();
        if (use) useDraggedItem(item);
        else if (drag.active) render();
      });
      card.addEventListener("pointercancel", () => {
        finishInventoryDrag();
        render();
      });
      card.addEventListener("lostpointercapture", () => {
        if (inventoryDrag?.card === card) finishInventoryDrag();
      });
      items.append(card);
    });
    for (let index = visibleMe?.items.length || 0; index < 3; index++) {
      const empty = node("div", undefined, "party-item-card is-empty");
      empty.setAttribute("aria-label", "빈 아이템 칸");
      items.append(empty);
    }
  }
  function openItem(item) {
    if (!state.me?.items.includes(item)) return;
    if (!state.can_use_items || busy || !online || movementHold) {
      cardPreview = item;
      renderCardPreview();
      return;
    }
    itemSelection = { item };
    selectedTile = null;
    q("[data-party-selection]").hidden = true;
    if (state.board.shop[item].target === "tile") {
      mapMode = "2d";
    }
    render();
  }
  function renderSupplyChoice() {
    const holder = q("[data-party-supply-choice]");
    const crate = state.supply_encounter;
    holder.hidden =
      !crate ||
      !myTurn() ||
      !!movementHold ||
      duelVisible() ||
      !!state.battle ||
      !!state.item_reward ||
      !!state.camp_gift ||
      !!state.hand_task ||
      !!state.event?.pending;
    root.classList.toggle("choosing-supply", !holder.hidden);
    if (holder.hidden) {
      holder.dataset.key = "";
      return;
    }
    const key = `${state.code}:${state.me.seat}:${state.turn_number}:${crate.id}:${crate.hp}`;
    if (holder.dataset.key !== key) {
      holder.dataset.key = key;
      holder.replaceChildren();
      const panel = node(
        "form",
        undefined,
        "party-arrival-panel party-supply-panel",
      );
      panel.append(
        node("small", "SUPPLY CRATE"),
        node("h2", "보급함을 만났어요"),
        node("div", "▣", "party-supply-art"),
        node("strong", `♥ ${crate.hp} / ${crate.max_hp}`),
        node(
          "p",
          "실물 카드를 속도 오름차순으로 사용하세요. 장수 제한은 없으며 사용한 카드는 리스트로 보냅니다.",
        ),
      );
      const speedsLabel = node("label", "사용한 카드의 속도 순서"),
        speeds = node("input");
      speeds.type = "text";
      speeds.placeholder = "예: 3, 5, 8";
      speeds.className = "v2-input";
      speeds.setAttribute("aria-label", "사용한 카드의 속도 순서");
      speedsLabel.append(speeds);
      const damageLabel = node("label", "콤보 보정·효과 적용 후 최종 피해"),
        damage = node("input");
      damage.type = "number";
      damage.min = "1";
      damage.step = "1";
      damage.inputMode = "numeric";
      damage.placeholder = "예: 800";
      damage.className = "v2-input";
      damage.setAttribute("aria-label", "보급함 최종 피해");
      damageLabel.append(damage);
      const feedback = node("p", "", "party-supply-feedback");
      feedback.setAttribute("role", "alert");
      panel.append(
        speedsLabel,
        damageLabel,
        node(
          "p",
          "파괴하면 2코인 획득. 피해 보상과 플레이어 기절 보상은 적용되지 않습니다.",
        ),
      );
      const actions = node("div", undefined, "party-arrival-actions");
      actions.append(
        button("지나가기", () => act("skip_supply", { crate_id: crate.id })),
        button("공격 결과 반영", () => panel.requestSubmit(), false, true),
      );
      panel.append(actions);
      panel.append(feedback);
      panel.addEventListener("submit", (event) => {
        event.preventDefault();
        const tokens = speeds.value
            .trim()
            .split(/[\s,，→>]+/)
            .filter(Boolean),
          values = tokens.map(Number),
          amount = Number(damage.value);
        if (
          !tokens.length ||
          tokens.some((t) => !/^-?\d+$/.test(t)) ||
          values.some(
            (v, i) => !Number.isSafeInteger(v) || (i > 0 && v <= values[i - 1]),
          )
        ) {
          feedback.textContent =
            "사용한 카드의 속도를 작은 수부터, 같은 수 없이 입력해주세요.";
          return;
        }
        if (!Number.isSafeInteger(amount) || amount <= 0) {
          feedback.textContent = "최종 피해를 입력해주세요.";
          return;
        }
        feedback.textContent = "";
        void act("attack_supply", {
          crate_id: crate.id,
          speeds: values,
          damage: amount,
        }).then(() => {
          feedback.textContent = q("[data-party-error]").textContent || "";
        });
      });
      holder.append(panel);
    }
    holder.querySelectorAll("button").forEach((button) => {
      button.disabled = busy || !online || state.expired;
    });
  }
  function arrivalKind() {
    if (state.camp_gift) return "camp_gift";
    if (state.supply_encounter) return null;
    if (state.move_prompt?.own_camp || state.move_prompt?.shared_camp)
      return "camp_pass";
    if (state.can_transfer) return "transfer";
    if (state.can_charge) return "charge";
    return state.can_buy_item ? "shop" : null;
  }
  function renderArrivalChoice() {
    const holder = q("[data-party-arrival-choice]");
    const hadFocus = holder.contains(document.activeElement),
      wasHidden = holder.hidden;
    const kind = arrivalKind(),
      direct = kind === "camp_pass" || kind === "transfer";
    holder.hidden =
      !kind ||
      !myTurn() ||
      !!movementHold ||
      duelVisible() ||
      !!state.item_reward ||
      !!state.hand_task ||
      !!state.event?.pending ||
      !!state.battle;
    root.classList.toggle("choosing-arrival", !holder.hidden);
    if (holder.hidden) {
      holder.dataset.key = "";
      return;
    }
    const cards = kind === "shop" || kind === "camp_gift";
    const options =
      kind === "shop"
        ? state.shop_offers
        : kind === "camp_gift"
          ? state.camp_gift.items
          : direct
            ? []
            : state.players
                .filter(
                  (p) => p.seat !== state.me.seat && p.hp > 0 && !p.cloaked,
                )
                .map((p) => p.seat);
    const key = JSON.stringify([
      state.code,
      state.turn_number,
      state.me.seat,
      me().position,
      kind,
      options,
    ]);
    if (key !== arrivalChoiceKey) {
      arrivalChoiceKey = key;
      arrivalSelection = null;
    }
    const renderKey = JSON.stringify([
      key,
      arrivalSelection,
      busy,
      online,
      me().coins,
      state.me.items.length,
    ]);
    if (holder.dataset.key === renderKey) return;
    holder.dataset.key = renderKey;
    holder.replaceChildren();
    const titles = {
      shop: "어떤 아이템을 살까요?",
      charge: "누구에게 돌격할까요?",
      camp_gift: "승점 획득! 보상을 골라주세요",
      camp_pass: "거점에 머무를까요?",
      transfer: "교체 지점에 도착했어요",
    };
    holder.setAttribute("aria-label", titles[kind]);
    const panel = node("div", undefined, "party-arrival-panel");
    panel.classList.toggle("is-direct-choice", direct);
    panel.append(
      node(
        "small",
        {
          shop: "ITEM SHOP",
          charge: "CHARGE",
          camp_gift: "CRYSTAL REWARD",
          camp_pass: "CAMP",
          transfer: "TRANSFER",
        }[kind],
      ),
      node("h2", titles[kind]),
    );
    const actions = node("div", undefined, "party-arrival-actions");
    const cancelAction = {
      shop: "skip_shop",
      charge: "skip_charge",
      camp_gift: "skip_camp_gift",
      camp_pass: "continue_move",
      transfer: "skip_transfer",
    }[kind];
    if (direct) {
      const image = node("img", undefined, "party-arrival-tile");
      image.src = state.board.nodes[me().position].background_img;
      image.alt = state.board.nodes[me().position].label;
      panel.append(image);
      if (kind === "camp_pass") {
        const detail =
          me().crystals >= 3
            ? "승점을 모두 구매했어요"
            : state.camp_purchase_done
              ? "이번 턴 승점 구매 완료"
              : `승점 구매까지 앞으로 ${state.camp_stop_shortfall}골드`;
        actions.append(
          button("이대로 이동", () => act("continue_move")),
          button(
            `거점에 멈추기\n(${detail})`,
            () => act("stop_home"),
            false,
            true,
          ),
        );
      } else
        actions.append(
          button("여기에 멈추기", () => act("skip_transfer")),
          button("반대편 교체로 이동", () => act("transfer"), false, true),
        );
    } else {
      panel.append(
        node(
          "p",
          kind === "shop"
            ? `무작위 아이템 3개 · 보유 ${me().coins}코인 · 가방 ${state.me.items.length}/3`
            : kind === "camp_gift"
              ? "세 아이템 중 하나를 무료로 획득합니다."
              : "상대를 선택한 뒤 확인을 눌러주세요.",
        ),
      );
      const choices = node("div", undefined, "party-arrival-options");
      options.forEach((value) => {
        const entry = cards
          ? state.board.shop[value]
          : state.players.find((p) => p.seat === value);
        const card = button("", () => {
          arrivalSelection = value;
          renderArrivalChoice();
        });
        card.className = "party-arrival-option";
        card.setAttribute("aria-pressed", String(arrivalSelection === value));
        card.setAttribute(
          "aria-label",
          cards ? entry.label : `${entry.name}에게 돌격`,
        );
        if (cards)
          card.append(
            cardVisual(entry),
            node("strong", entry.label),
            node(
              "span",
              kind === "camp_gift" ? "무료 획득" : `${entry.price}코인`,
            ),
          );
        else {
          const image = node("img", undefined, "party-charge-standing");
          image.src = standingSource(entry);
          image.alt = entry.character.name;
          image.draggable = false;
          card.append(
            image,
            node("strong", entry.name),
            node("span", `♥${entry.hp} · FP ${entry.fp}`),
          );
        }
        choices.append(card);
      });
      if (!options.length)
        choices.append(node("p", "돌격할 수 있는 상대가 없어요."));
      const selected = cards
        ? state.board.shop[arrivalSelection]
        : state.players.find((p) => p.seat === arrivalSelection);
      const affordable =
        kind !== "shop" ||
        (selected && me().coins >= selected.price && state.me.items.length < 3);
      const hint = node(
        "p",
        arrivalSelection === null
          ? "아이템 또는 상대를 선택해주세요."
          : cards
            ? !affordable
              ? "코인과 가방 공간을 확인해주세요."
              : kind === "camp_gift" && state.me.items.length >= 3
                ? "획득 후 교체할 아이템을 선택합니다."
                : selected.label
            : `${selected.name}의 위치로 이동합니다.`,
        "party-arrival-hint",
      );
      actions.append(
        button(kind === "camp_gift" ? "받지 않기" : "취소", () =>
          act(cancelAction),
        ),
        button(
          "확인",
          () =>
            act(
              kind === "shop"
                ? "buy_item"
                : kind === "camp_gift"
                  ? "choose_camp_gift"
                  : "charge",
              cards ? { item: arrivalSelection } : { target: arrivalSelection },
            ),
          arrivalSelection === null || !affordable,
          true,
        ),
      );
      panel.append(choices, hint);
    }
    panel.append(actions);
    holder.append(panel);
    panel.tabIndex = -1;
    holder.onkeydown = (event) => {
      if (event.key === "Escape" && !busy && online) {
        event.preventDefault();
        void act(cancelAction);
      } else if (event.key === "Tab") {
        const enabled = [...holder.querySelectorAll("button:not(:disabled)")],
          first = enabled[0],
          last = enabled.at(-1);
        if (
          event.shiftKey &&
          (document.activeElement === first || document.activeElement === panel)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    if (hadFocus || wasHidden)
      (holder.querySelector('[aria-pressed="true"]') || panel).focus({
        preventScroll: true,
      });
  }
  function renderControls() {
    const holder = q("[data-party-controls]");
    root.classList.toggle(
      "choosing-transfer",
      !!state.can_transfer && !movementHold,
    );
    root.classList.toggle(
      "shopping",
      !movementHold && myTurn() && !!state.can_buy_item,
    );
    holder.replaceChildren();
    if (movementHold || state.event?.pending) return;
    if (state.expired) {
      holder.append(node("p", "방이 만료되었습니다. 새 파티를 만들어주세요."));
      return;
    }
    if (state.status === "finished") {
      holder.append(
        node(
          "p",
          `우승: ${state.winners.map((seat) => state.players.find((p) => p.seat === seat)?.name).join(", ")}`,
        ),
      );
      const link = node("a", "새 파티 만들기", "v2-button");
      link.href = "/battlelog/party/";
      holder.append(link);
      return;
    }
    if (!state.me) {
      return;
    }
    if (state.status === "lobby") {
      holder.append(
        button(
          me().ready ? "준비 취소" : "준비 완료",
          () => act("ready"),
          false,
          true,
        ),
      );
      if (state.me.is_host)
        holder.append(
          button(
            "파티 시작",
            () => act("start"),
            state.players.length < 2 || state.players.some((p) => !p.ready),
          ),
        );
      holder.append(node("p", "모두 준비를 완료하면 방장이 시작합니다."));
      return;
    }
    if (state.battle) {
      return;
    }
    if (state.move?.reveal_pending) return;
    if (!myTurn()) {
      return;
    }
    const player = me();
    const tile = state.board.nodes[player.position];
    if (state.counter_prompt) {
      holder.append(node("p", "상대의 반격 선택을 기다리는 중…"));
      return;
    }
    if (player.hp <= 0) {
      holder.append(
        node(
          "p",
          player.ko_status === "resting"
            ? "이번 턴은 쉬어요. 다음 자기 턴에 이 자리에서 부활합니다."
            : "기절했어요. 다음 자기 턴을 쉬어야 합니다.",
        ),
        button("쉬는 턴 마치기", () => act("end_turn"), false, true),
      );
      return;
    }
    if (state.hand_task) {
      holder.append(
        node(
          "p",
          `손패를 모두 버리고 ${state.hand_task.count ?? "캐릭터의 최대 손패"}${state.hand_task.count != null ? "장" : ""}까지 획득하세요. (${state.hand_task.reason})`,
        ),
        button(
          "손패 교체 완료",
          () => act("ack_hand", { task_version: state.hand_task.version }),
          false,
          true,
        ),
      );
      return;
    }
    if (duelVisible()) return;
    if (state.item_reward) {
      holder.append(
        node(
          "p",
          `${state.board.shop[state.item_reward].label} 획득! 가방이 가득 차 교체할 아이템을 선택해주세요.`,
        ),
      );
      state.me.items.forEach((item, index) =>
        holder.append(
          button(`${state.board.shop[item].label} 교체`, () =>
            act("claim_item", { index }),
          ),
        ),
      );
      holder.append(
        button("새 아이템 받지 않기", () =>
          act("claim_item", { discard: true }),
        ),
      );
    }
    if (state.move) {
      holder.append(
        node("div", `남은 이동 ${state.move.remaining}칸`, "party-dice"),
      );
      if (state.move_prompt) {
        if (state.move_prompt.targets.length)
          holder.append(
            node(
              "p",
              "상대를 지나치는 중입니다. 교전하거나 계속 이동할 수 있어요.",
            ),
          );
        holder.append(
          button(
            state.move_prompt.shop_open ? "상점 닫고 계속 이동" : "계속 이동",
            () => act("continue_move"),
          ),
        );
      } else
        holder.append(
          node(
            "p",
            forwardExits(player).length > 1
              ? "지도 화살표를 눌러 방향을 선택하세요."
              : "진행 방향으로 이동 중…",
          ),
        );
    } else if (!state.landed && state.arrival !== "dash")
      holder.append(button("이동", () => act("roll"), false, true));
    if (state.challenge_targets.length)
      holder.append(
        button("전투", () => {
          releasedEncounter = "";
          render();
        }),
      );
    if (
      state.landed &&
      !state.can_auto_end_turn &&
      !state.can_buy_item &&
      !state.can_charge &&
      !state.camp_gift &&
      !state.item_reward
    ) {
      holder.append(button("턴 종료", () => act("end_turn"), false, true));
    }
  }
  function renderBattle() {
    const holder = q("[data-party-battle]");
    holder.replaceChildren();
    holder.hidden = !state.battle;
    if (!state.battle) return;
    const battle = state.battle;
    const participants = [battle.p1, battle.p2].map((seat) =>
      state.players.find((p) => p.seat === seat),
    );
    holder.append(
      node("h2", `${participants[0].name} ↔ ${participants[1].name}`),
      node(
        "p",
        `${battle.completed && battle.exchanges === 1 ? "첫 공방 기절 · 전투 종료" : `완료한 공방 ${battle.exchanges}/2`} · ♥${participants[0].hp} / ♥${participants[1].hp}`,
      ),
    );
    const link = node(
      "a",
      battle.control_token
        ? !battle.completed
          ? "교전 계산기로 이동"
          : "최종 계산기 확인"
        : "계산기 관전",
      "v2-button v2-button-primary",
    );
    link.href =
      battle.calculator_url +
      (battle.calculator_url.includes("?") ? "&" : "?") +
      "choose_ui=1";
    holder.append(link);
    if (battle.can_confirm) {
      holder.append(
        node("p", "참가자 한 명이 제출하면 HP와 기절 결과가 바로 반영됩니다."),
      );
      holder.append(
        button("전투 결과 반영", () =>
          act("confirm_battle", {
            battle_version: battle.version,
          }),
        ),
      );
    }
    if (state.me?.is_host)
      holder.append(
        button("교전 취소 · 시작 전 상태 유지", () => act("cancel_battle")),
      );
  }
  const standingSource = (player) =>
    player.character.body_img ||
    player.character.sd_img ||
    player.character.icon_img ||
    player.character.img;
  const ordinal = (index) =>
    ["1st", "2nd", "3rd", "4th"][index] || `${index + 1}th`;
  function encounterKey() {
    return `${state.code}:${state.turn_number}:${me()?.position}:${state.move?.roll_version || "landed"}:${state.challenge_targets.join(",")}`;
  }
  function duelVisible() {
    if (movementHold) return false;
    return (
      (state.counter_prompt?.seat === state.me?.seat &&
        !!state.me &&
        !state.battle &&
        !state.expired) ||
      (myTurn() &&
        !state.counter_prompt &&
        !state.item_reward &&
        !state.camp_gift &&
        !state.challenge_declined &&
        !state.hand_task &&
        state.challenge_targets.length > 0 &&
        releasedEncounter !== encounterKey())
    );
  }
  function renderVersus() {
    const holder = q("[data-party-versus]");
    const active = state.battle;
    const counter =
      !active && state.counter_prompt?.seat === state.me?.seat && !!state.me;
    holder.hidden = !active && !duelVisible();
    root.classList.toggle("has-duel", !holder.hidden);
    if (holder.hidden) {
      holder.dataset.key = "";
      return;
    }
    const attacker = active
      ? state.players.find((p) => p.seat === active.p1)
      : me();
    const targets = counter
      ? state.players.filter((p) => p.seat === state.counter_prompt.target)
      : active
        ? [state.players.find((p) => p.seat === active.p2)]
        : state.players.filter((p) => state.challenge_targets.includes(p.seat));
    const target = targets.find((p) => p.seat === duelTarget) || targets[0];
    if (!attacker || !target) return;
    duelTarget = target.seat;
    const key = JSON.stringify([
      state.code,
      counter,
      active?.id,
      active?.exchanges,
      active?.completed,
      attacker.seat,
      attacker.hp,
      target.seat,
      target.hp,
      targets.map((p) => p.seat),
      busy,
      online,
      state.expired,
    ]);
    if (holder.dataset.key === key) return;
    holder.dataset.key = key;
    holder.replaceChildren();
    holder.classList.toggle("is-active-battle", !!active);
    const title = node(
      "p",
      active
        ? active.completed
          ? active.exchanges === 1
            ? "첫 공방 기절 · 전투 종료"
            : "전투 종료 · 결과 제출"
          : `교전 중 · 공방 ${active.exchanges}/2`
        : counter
          ? "반격할까요?"
          : "승부를 걸까요?",
      "party-duel-title",
    );
    holder.append(title);
    if (targets.length > 1) {
      const choices = node("div", undefined, "party-duel-targets");
      targets.forEach((p) => {
        const choice = button(p.name, () => {
          duelTarget = p.seat;
          renderVersus();
        });
        choice.setAttribute("aria-pressed", String(p.seat === target.seat));
        choices.append(choice);
      });
      holder.append(choices);
    }
    const cast = node("div", undefined, "party-duel-cast");
    [attacker, target].forEach((player, index) => {
      if (index === 1) cast.append(node("strong", "VS", "party-vs-mark"));
      const figure = node(
        "figure",
        undefined,
        `party-duel-fighter fighter-${index}`,
      );
      const image = node("img");
      image.src = standingSource(player);
      image.alt = `${player.name} · ${player.character.name}`;
      image.draggable = false;
      figure.append(
        image,
        node("figcaption", player.name),
        node("span", `♥${player.hp} · FP ${player.fp}`, "party-duel-hp"),
      );
      cast.append(figure);
    });
    holder.append(cast);
    if (!active) {
      const actions = node("div", undefined, "party-duel-actions");
      const release = button("놓아주기", () => {
        if (counter) {
          void act("skip_counter");
          return;
        }
        releasedEncounter = encounterKey();
        if (
          state.move_prompt &&
          !(
            state.move_prompt.own_camp ||
            state.move_prompt.shared_camp ||
            state.move_prompt.shop ||
            state.move_prompt.supply
          )
        )
          void act("continue_move");
        else void act("skip_challenge");
      });
      const fight = button(
        "전투",
        () =>
          act(counter ? "counterattack" : "challenge", { target: target.seat }),
        false,
        true,
      );
      release.classList.add("party-release-button");
      fight.classList.add("party-fight-button");
      actions.append(release, fight);
      holder.append(actions);
    }
  }
  function renderPlayers() {
    const holder = q("[data-party-players]");
    const order = state.turn_order || state.players.map((p) => p.seat);
    const key = `${state.code}:${order.join(",")}`;
    const changed = holder.dataset.order && holder.dataset.order !== key;
    const oldRects = new Map(
      [...rosterCards].map(([seat, card]) => [
        seat,
        card.getBoundingClientRect(),
      ]),
    );
    const cards = [];
    order.forEach((seat, index) => {
      const player = (movementHold?.previous.players || state.players).find(
        (p) => p.seat === seat,
      );
      if (!player) return;
      let card = rosterCards.get(seat);
      if (!card) {
        card = node("article", undefined, "party-hud-player");
        card.dataset.seat = seat;
        const portrait = node("img", undefined, "party-hud-standing");
        portrait.draggable = false;
        const focus = node("button", undefined, "party-focus-player");
        focus.type = "button";
        focus.setAttribute("aria-label", `${player.name} 위치 보기`);
        focus.addEventListener("click", () => focusPlayer(seat));
        focus.append(portrait);
        const details = node("div", undefined, "party-hud-details");
        const name = node("h3", undefined, "party-hud-name");
        const crystals = node("div", undefined, "party-hud-crystals");
        const stats = node("div", undefined, "party-hud-stats");
        stats.append(
          node("span", "♥", "party-heart"),
          node("span", "", "party-hud-hp"),
          node("span", "●", "party-coin"),
          node("span", "", "party-hud-coins"),
        );
        details.append(
          name,
          crystals,
          stats,
          node("small", "", "party-hud-fp"),
        );
        card.append(focus, details, node("small", "", "party-hud-order"));
        rosterCards.set(seat, card);
      }
      card.style.setProperty("--party-color", colors[seat]);
      card.classList.toggle(
        "is-turn",
        state.status === "running" && seat === state.turn,
      );
      card.classList.toggle("is-me", seat === state.me?.seat);
      const portrait = card.querySelector("img");
      const source = standingSource(player);
      if (portrait.getAttribute("src") !== source) portrait.src = source;
      portrait.alt = `${player.character.name} 스탠딩`;
      portrait.onerror = () => {
        if (portrait.getAttribute("src") !== player.character.img)
          portrait.src = player.character.img;
      };
      card.querySelector("h3").textContent =
        `${seat === state.turn && state.status === "running" ? "▸ " : ""}${player.name}${seat === state.me?.seat ? " · 나" : ""}`;
      card.querySelector(".party-hud-crystals").textContent =
        "◆".repeat(Math.max(0, Math.min(3, player.crystals))) +
        "◇".repeat(Math.max(0, 3 - player.crystals)) +
        (player.crystals > 3 ? ` +${player.crystals - 3}` : "");
      card.querySelector(".party-hud-hp").textContent = player.hp;
      card.querySelector(".party-hud-coins").textContent = player.coins;
      card.querySelector(".party-hud-fp").textContent =
        `${player.ko_status ? (player.ko_status === "resting" ? "휴식 · 다음 턴 부활" : "기절 · 다음 턴 휴식") : `FP ${player.fp}`}${player.cloaked ? " · 투명" : ""}${player.shielded ? " · 보호막" : ""}${player.revenge_ready ? " · 반격" : ""}${state.status === "lobby" ? (player.ready ? " · 준비 완료" : " · 준비 중") : ""}${player.poison_turns ? ` · 독 ${player.poison_turns}턴` : ""}`;
      card.querySelector(".party-hud-order").textContent = ordinal(index);
      card.setAttribute(
        "aria-label",
        `${index + 1}번째 ${player.name}, 체력 ${player.hp}, 코인 ${player.coins}, 승점 ${player.crystals}, FP ${player.fp}`,
      );
      cards.push(card);
    });
    for (const [seat, card] of rosterCards)
      if (!order.includes(seat)) {
        card.remove();
        rosterCards.delete(seat);
      }
    if (holder.dataset.order !== key)
      cards.forEach((card) => holder.append(card));
    holder.dataset.order = key;
    if (changed && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      cards.forEach((card) => {
        const before = oldRects.get(Number(card.dataset.seat));
        const after = card.getBoundingClientRect();
        if (before && (before.x !== after.x || before.y !== after.y)) {
          card.animate(
            [
              {
                transform: `translate(${before.x - after.x}px,${before.y - after.y}px)`,
              },
              { transform: "translate(0,0)" },
            ],
            { duration: 720, easing: "cubic-bezier(.22,.8,.24,1)" },
          );
        }
      });
      holder.dataset.reorderRound = state.round;
    }
  }
  function render() {
    renderRoll();
    if (
      itemSelection &&
      (!state.can_use_items || !state.me?.items.includes(itemSelection.item))
    )
      itemSelection = null;
    const roll = state.move
      ? `${state.code}:${state.move.roll_version ?? `${state.round}:${state.turn}:${state.move.dice}`}`
      : "";
    if (roll !== routeRollKey) {
      routeRollKey = roll;
      routeTarget = null;
    }
    renderTestTools();
    q("[data-party-status]").textContent =
      state.status === "lobby"
        ? `대기실 · ${state.players.length}/4명`
        : `라운드 ${state.round}${state.status === "finished" ? " · 종료" : ""}`;
    q("[data-party-connection]").textContent = online
      ? state.me
        ? "연결됨 · 내 자리로 참여 중"
        : "연결됨 · 관전 중"
      : "재연결 중 · 조작 잠금";
    q("[data-party-join]").hidden =
      !!state.me ||
      state.status !== "lobby" ||
      state.players.length >= 4 ||
      state.expired;
    q("[data-party-bonuses]").textContent =
      `이동력 +${state.movement_power} · 공격자 FP +${state.attacker_bonus}`;
    renderEvent();
    renderCardPreview();
    const track = q("[data-party-round-track]");
    track.replaceChildren();
    for (let round = 0; round < 3; round++)
      track.append(
        node("span", "", round < (state.round - 1) % 3 ? "is-complete" : ""),
      );
    renderInventory();
    drawMap();
    renderControls();
    renderBattle();
    renderPlayers();
    renderVersus();
    renderArrivalChoice();
    renderSupplyChoice();
    renderItemPicker();
    q("[data-party-controls]").parentElement.hidden =
      !q("[data-party-controls]").children.length ||
      !!itemSelection ||
      (!!state.supply_encounter && myTurn());
    clearTimeout(advanceTimer);
    clearTimeout(endTurnTimer);
    clearTimeout(automaticActionTimer);
    const automaticAction =
      state.arrival === "dash" && !state.move && !state.landed
        ? "roll"
        : state.can_buy_crystal &&
            me()?.crystals < 3 &&
            me().coins >= state.board.crystal_costs[me().crystals]
          ? "buy_crystal"
          : null;
    if (
      automaticAction &&
      canMove() &&
      !duelVisible() &&
      !state.item_reward &&
      !state.camp_gift &&
      !state.supply_encounter &&
      !cardPreview &&
      !inventoryDrag &&
      online &&
      !busy &&
      !document.hidden
    ) {
      const version = state.version,
        seatToken = token;
      automaticActionTimer = setTimeout(() => {
        if (
          state.version === version &&
          token === seatToken &&
          !document.hidden
        )
          void act(automaticAction);
      }, 150);
    }
    if (
      state.can_auto_end_turn &&
      myTurn() &&
      online &&
      !busy &&
      !movementHold &&
      !document.hidden &&
      !itemSelection &&
      !cardPreview &&
      !inventoryDrag &&
      !state.event?.pending &&
      !(state.event?.effect_until > Date.now() + serverOffset)
    ) {
      const version = state.version,
        seatToken = token;
      endTurnTimer = setTimeout(() => {
        if (
          state.version === version &&
          token === seatToken &&
          !document.hidden
        )
          void act("auto_end_turn");
      }, 650);
    }
    if (
      !document.hidden &&
      !movementHold &&
      myTurn() &&
      state.move &&
      !state.move_prompt &&
      online &&
      !busy &&
      ((state.move.reveal_pending && !rollStage()) ||
        (canMove() && forwardExits(me()).length === 1))
    ) {
      const version = state.version,
        seatToken = token;
      advanceTimer = setTimeout(() => {
        if (
          state.version === version &&
          token === seatToken &&
          !document.hidden
        )
          void act("advance");
      }, 100);
    }
    const log = q("[data-party-log]");
    const visibleLog = movementHold ? movementHold.previous.log : state.log;
    if (
      log.dataset.count !== String(visibleLog.length) ||
      log.dataset.last !== visibleLog.at(-1)?.at
    ) {
      log.replaceChildren(
        ...visibleLog
          .slice()
          .reverse()
          .map((entry) => node("li", entry.text)),
      );
      log.dataset.count = String(visibleLog.length);
      log.dataset.last = visibleLog.at(-1)?.at || "";
    }
  }
  q("[data-party-join]").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    try {
      const data = Object.fromEntries(new FormData(event.target));
      data.character_id = Number(data.character_id);
      const result = await api(`${base}join/`, data, "");
      saveSeat(result);
      accept(result.state);
      error("");
    } catch (err) {
      error(err.message);
    } finally {
      busy = false;
      render();
    }
  });
  q("[data-party-share]").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(location.origin + state.url);
      q("[data-party-share]").textContent = "복사 완료";
    } catch {
      error(`초대 주소: ${location.origin}${state.url}`);
    }
  });
  q("[data-party-selection-close]").addEventListener("click", () => {
    selectedTile = null;
    routeTarget = null;
    q("[data-party-selection]").hidden = true;
    drawMap();
  });
  q("[data-party-map]").addEventListener("pointerleave", () => {
    if (selectedTile === null) q("[data-party-selection]").hidden = true;
  });
  render();
  q("[data-party-test-seat]")?.addEventListener(
    "change",
    (event) => void switchTestPlayer(event.target.value),
  );
  window.addEventListener("lumen-party-3d-ready", () => drawMap());
  q("[data-party-map-toggle]").addEventListener("click", () => {
    if (worldFailed) return;
    mapMode = mapMode === "3d" ? "2d" : "3d";
    world?.dispose();
    world = null;
    drawMap();
  });
  root.querySelectorAll("[data-party-camera]").forEach((control) =>
    control.addEventListener("click", () => {
      if (!world) return;
      const action = control.dataset.partyCamera;
      if (action === "in" || action === "out")
        world.zoom(action === "in" ? 1.15 : 1 / 1.15);
      if (action === "reset") world.reset();
    }),
  );
  window.addEventListener("pagehide", (event) => {
    clearTimeout(eventTimer);
    clearTimeout(advanceTimer);
    clearTimeout(rollTimer);
    if (!event.persisted) world?.dispose();
  });
  void refresh();
  window.setInterval(() => {
    if (!document.hidden && !busy) void refresh();
  }, 1000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) void refresh();
  });
})();
