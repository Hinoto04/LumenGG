import * as THREE from "./vendor/three/three.module.min.js";

// Shared by the web HUD and the native app's board-only WebView.
const SEATS = [0xffc775, 0x72d8ed, 0xc9a1ff, 0x8ce1bd];
const TILES = {
  camp: 0xe7b963,
  fortune: 0x4ebbc2,
  dash: 0x68c999,
  disaster: 0xda776f,
  shop: 0xe59a72,
  prepare: 0xa994e1,
  charge: 0xe78aa2,
  event: 0xc5a0d4,
  transfer: 0x72bbdf,
};
const point = (tile) =>
  new THREE.Vector3((tile.x - 50) / 2.6, 1.32, (tile.y - 50) / 2.6);

export function createPartyScene(container, options = {}) {
  const reduced = window.matchMedia?.(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: "low-power",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x97b9d3);
  scene.fog = new THREE.Fog(0x97b9d3, 55, 100);
  const camera = new THREE.OrthographicCamera(-24, 24, 18, -18, 0.1, 110);
  const yaw = 0,
    elevation = 0.97;
  let zoom = 1,
    panLimit = 22,
    width = 1,
    height = 1;
  const target = new THREE.Vector3(0, 0.6, 0);
  const focusTarget = target.clone();
  let focusKey = "",
    focusSeat = null,
    following = true;
  let viewerSeat = null,
    observedTurn = null,
    lastActionVersion = null,
    interactionSeq = null,
    lastInteraction = performance.now();
  const world = new THREE.Group();
  scene.add(world);
  const ambient = new THREE.HemisphereLight(0xe3edff, 0x778382, 1.45);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xfff0d6, 2.3);
  sun.position.set(-12, 22, 8);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1536, 1536);
  Object.assign(sun.shadow.camera, {
    left: -25,
    right: 25,
    top: 25,
    bottom: -25,
    near: 1,
    far: 55,
  });
  sun.shadow.normalBias = 0.07;
  sun.shadow.bias = -0.0003;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xadbdff, 0.65);
  fill.position.set(10, 7, -14);
  scene.add(fill);
  const raycaster = new THREE.Raycaster(),
    pointer = new THREE.Vector2();
  const tiles = new Map(),
    roads = new Map(),
    pawns = new Map(),
    pickTargets = [],
    directions = [];
  const geometries = new Set(),
    materials = new Set(),
    textures = new Set();
  const iconLoader = new THREE.TextureLoader(),
    backgrounds = new Map();
  let state = null,
    selected = null,
    allowed = [],
    disposed = false,
    inView = true,
    active = true,
    boardKey = "";
  let frame = 0,
    lastTime = 0,
    lastPaint = 0,
    lastMoveVersion = null,
    hasSnapshot = false;
  const overlay = document.createElement("div");
  overlay.className = "party-world-labels";
  renderer.domElement.className = "party-world-canvas";
  renderer.domElement.setAttribute(
    "aria-label",
    "드래그로 이동하고 확대할 수 있는 루멘 파티 3D 보드",
  );
  container.replaceChildren(renderer.domElement, overlay);
  container.classList.add("is-3d");
  const geo = (geometry) => {
    geometries.add(geometry);
    return geometry;
  };
  const mat = (color, extra = {}) => {
    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.84,
      flatShading: true,
      ...extra,
    });
    materials.add(material);
    return material;
  };
  const mesh = (geometry, material, parent, position, scale) => {
    const object = new THREE.Mesh(geometry, material);
    if (position) object.position.set(...position);
    if (scale) object.scale.set(...scale);
    parent.add(object);
    return object;
  };
  const box = geo(new THREE.BoxGeometry(1, 1, 1));
  const ball = geo(new THREE.SphereGeometry(1, 12, 8));
  const cylinder = geo(new THREE.CylinderGeometry(1, 1, 1, 12));
  const cone = geo(new THREE.ConeGeometry(1, 1, 6));
  const stone = mat(0x777ca3),
    pale = mat(0xd8d6df),
    paving = mat(0x8b91a3);
  const green = mat(0x94b49e),
    dark = mat(0x343950),
    bark = mat(0x807087);
  const mint = mat(0x75b4a4),
    leaves = mat(0xc0c9b2),
    blossom = mat(0xd5b1c8);
  const gold = mat(0xe6bd7d),
    white = mat(0xf7f0e5),
    glass = mat(0xa2e1ed, { metalness: 0.18, roughness: 0.22 });
  const glow = mat(0x94eff0, { emissive: 0x75cadc, emissiveIntensity: 0.6 });
  const building = new THREE.Group();
  world.add(building);
  mesh(
    geo(new THREE.CylinderGeometry(23, 21.7, 1.25, 8)),
    stone,
    building,
    [0, -0.15, 0],
  ).receiveShadow = true;
  mesh(
    geo(new THREE.CylinderGeometry(23.1, 23, 0.38, 8)),
    pale,
    building,
    [0, 0.67, 0],
  ).receiveShadow = true;
  mesh(
    geo(new THREE.CylinderGeometry(22.8, 22.8, 0.12, 8)),
    green,
    building,
    [0, 0.91, 0],
  ).receiveShadow = true;
  building.rotation.y = Math.PI / 8;
  const platformLayers = [...building.children];
  // A shallow reflecting basin and the central Lumen condenser.
  mesh(
    geo(new THREE.CylinderGeometry(3.05, 3.05, 0.12, 48)),
    pale,
    building,
    [0, 1, 0],
  );
  mesh(
    geo(new THREE.CylinderGeometry(2.78, 2.78, 0.08, 48)),
    glass,
    building,
    [0, 1.08, 0],
  ).receiveShadow = true;
  mesh(
    geo(new THREE.CylinderGeometry(1.2, 1.55, 0.38, 12)),
    pale,
    building,
    [0, 1.3, 0],
  ).castShadow = true;
  mesh(
    geo(new THREE.CylinderGeometry(0.88, 1.18, 0.25, 12)),
    gold,
    building,
    [0, 1.61, 0],
  );
  const crystal = mesh(
    geo(new THREE.OctahedronGeometry(1.04)),
    glow,
    building,
    [0, 2.65, 0],
    [0.68, 1.45, 0.68],
  );
  const orbit = mesh(
    geo(new THREE.TorusGeometry(1.52, 0.055, 6, 48)),
    gold,
    building,
    [0, 2.35, 0],
  );
  orbit.rotation.x = Math.PI / 2;
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    mesh(
      box,
      pale,
      building,
      [Math.cos(a) * 2.5, 1.37, Math.sin(a) * 2.5],
      [0.38, 0.65, 0.38],
    ).castShadow = true;
    mesh(
      ball,
      glow,
      building,
      [Math.cos(a) * 2.5, 1.78, Math.sin(a) * 2.5],
      [0.17, 0.17, 0.17],
    );
  }
  // Low-poly scenery is authored here; no external game art or model downloads.
  for (let i = 0; i < 18; i++) {
    const a = (i * Math.PI) / 9 + 0.07,
      r = 20 + (i % 3) * 0.16;
    const tree = new THREE.Group();
    tree.position.set(Math.cos(a) * r, 1, Math.sin(a) * r);
    world.add(tree);
    if (i % 4 === 0) {
      mesh(cylinder, bark, tree, [0, 0.46, 0], [0.12, 0.92, 0.12]);
      mesh(
        ball,
        i % 8 === 0 ? blossom : leaves,
        tree,
        [0, 1.28, 0],
        [0.72, 0.87, 0.68],
      ).castShadow = true;
      mesh(
        ball,
        i % 8 === 0 ? blossom : leaves,
        tree,
        [0.3, 1.02, 0.08],
        [0.46, 0.57, 0.42],
      );
    } else {
      mesh(cylinder, bark, tree, [0, 0.35, 0], [0.11, 0.7, 0.11]);
      for (let level = 0; level < 3; level++)
        mesh(
          cone,
          mint,
          tree,
          [0, 0.7 + level * 0.4, 0],
          [0.62 - level * 0.12, 0.82, 0.62 - level * 0.12],
        ).castShadow = true;
    }
  }
  for (let i = 0; i < 4; i++) {
    const a = (i * Math.PI) / 2 + Math.PI / 4;
    const tower = new THREE.Group();
    tower.position.set(Math.cos(a) * 20.3, 1, Math.sin(a) * 20.3);
    tower.rotation.y = -a;
    world.add(tower);
    mesh(box, pale, tower, [0, 0.8, 0], [1.3, 1.6, 1.3]).castShadow = true;
    mesh(
      geo(new THREE.ConeGeometry(1.13, 1.04, 4)),
      mat(i % 2 ? 0x9e9fc7 : 0xb789a6),
      tower,
      [0, 2.03, 0],
    ).rotation.y = Math.PI / 4;
    mesh(box, glass, tower, [0, 1.04, 0.662], [0.42, 0.58, 0.04]);
    mesh(box, bark, tower, [0, 0.34, 0.675], [0.44, 0.64, 0.05]);
    mesh(box, gold, tower, [0, 0.55, 0.71], [0.05, 0.05, 0.05]);
  }
  for (let i = 0; i < 10; i++) {
    const a = (i * Math.PI) / 5;
    mesh(
      box,
      pale,
      world,
      [Math.cos(a) * 8, 1.1, Math.sin(a) * 8],
      [0.16, 0.16, 0.16],
    );
    const shrub = mesh(
      ball,
      i % 2 ? blossom : leaves,
      world,
      [Math.cos(a) * 7.4, 1.19, Math.sin(a) * 7.4],
      [0.42, 0.3, 0.38],
    );
    shrub.castShadow = true;
  }
  function canvasTexture(draw) {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 256;
    draw(canvas.getContext("2d"), 256);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    textures.add(texture);
    return texture;
  }
  function tileTexture(tile) {
    return canvasTexture((ctx, s) => {
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 14;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      const line = (points, close = false) => {
        ctx.beginPath();
        points.forEach(([x, y], i) =>
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y),
        );
        if (close) ctx.closePath();
        ctx.stroke();
      };
      const circle = (x, y, r, fill = false) => {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        fill ? ctx.fill() : ctx.stroke();
      };
      const k = tile.kind;
      if (k === "camp") {
        line([
          [66, 119],
          [128, 62],
          [190, 119],
        ]);
        line([
          [82, 113],
          [82, 184],
          [174, 184],
          [174, 113],
        ]);
        line([
          [116, 183],
          [116, 143],
          [140, 143],
          [140, 183],
        ]);
      }
      if (k === "fortune") {
        circle(128, 128, 58);
        ctx.font = "bold 75px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("L", 128, 156);
      }
      if (k === "heal") {
        ctx.fillRect(112, 65, 32, 126);
        ctx.fillRect(65, 112, 126, 32);
      }
      if (k === "supply") {
        ctx.strokeRect(78, 65, 107, 130);
        line([
          [94, 91],
          [168, 91],
        ]);
        line([
          [94, 117],
          [168, 117],
        ]);
        line([
          [94, 143],
          [151, 143],
        ]);
      }
      if (k === "prepare") {
        line([
          [82, 177],
          [176, 80],
          [122, 80],
        ]);
        line([
          [176, 80],
          [176, 133],
        ]);
        line([
          [73, 137],
          [73, 177],
          [115, 177],
        ]);
      }
      if (k === "shop") {
        line([
          [75, 111],
          [75, 183],
          [181, 183],
          [181, 111],
        ]);
        line(
          [
            [64, 110],
            [84, 70],
            [172, 70],
            [192, 110],
          ],
          true,
        );
        line([
          [117, 183],
          [117, 142],
          [148, 142],
          [148, 183],
        ]);
      }
      if (k === "charge") {
        line([
          [82, 75],
          [174, 174],
        ]);
        line([
          [174, 75],
          [82, 174],
        ]);
        line([
          [67, 154],
          [104, 190],
        ]);
        line([
          [155, 190],
          [190, 154],
        ]);
      }
      if (k === "event") {
        ctx.font = "bold 148px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("?", 128, 183);
      }
      if (k === "dash" || k === "disaster") {
        ctx.font = "bold 148px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(k === "dash" ? "»" : "!", 128, 183);
      }
    });
  }
  function buildBoard(board) {
    const key = JSON.stringify(
      board.nodes.map((t) => [
        t.id,
        t.kind,
        t.x,
        t.y,
        t.exits,
        t.background_img,
      ]),
    );
    if (boardKey) {
      if (boardKey !== key)
        throw new Error("맵 구조가 변경되었습니다. 새로고침해주세요.");
      return;
    }
    boardKey = key;
    const extent =
      Math.max(
        ...board.nodes.map((t) =>
          Math.max(Math.abs(t.x - 50), Math.abs(t.y - 50)),
        ),
      ) / 2.6;
    panLimit = extent + 5;
    platformLayers.forEach((layer) =>
      layer.scale.set(extent / 16.54, 1, extent / 16.54),
    );
    const edges = new Set();
    board.nodes.forEach((tile) =>
      tile.exits.forEach((id) => {
        const key = [tile.id, id].sort((a, b) => a - b).join("-");
        if (edges.has(key)) return;
        edges.add(key);
        const a = point(tile),
          b = point(board.nodes[id]),
          delta = b.clone().sub(a);
        const road = mesh(
          box,
          paving,
          world,
          a.clone().add(b).multiplyScalar(0.5).toArray(),
          [0.6, 0.075, delta.length()],
        );
        road.position.y = 1.02;
        road.rotation.y = Math.atan2(delta.x, delta.z);
        road.receiveShadow = true;
        const material = mat(0x79f5c7, {
          transparent: true,
          opacity: 0.85,
          emissive: 0x45b58c,
          emissiveIntensity: 0.75,
          depthWrite: false,
        });
        const highlight = mesh(box, material, world, road.position.toArray(), [
          0.44,
          0.04,
          delta.length(),
        ]);
        highlight.position.y = 1.085;
        highlight.rotation.y = road.rotation.y;
        highlight.visible = false;
        roads.set(key, { highlight, material });
      }),
    );
    board.nodes.forEach((tile) =>
      tile.exits.forEach((id) => {
        const a = point(tile),
          b = point(board.nodes[id]),
          delta = b.clone().sub(a);
        const lane = board.nodes[id].exits.includes(tile.id) ? 0.32 : 0;
        const group = new THREE.Group();
        group.position.copy(a.clone().addScaledVector(delta, 0.55));
        group.position.x += (delta.z / delta.length()) * lane;
        group.position.z -= (delta.x / delta.length()) * lane;
        group.position.y = 1.13;
        group.rotation.y = Math.atan2(delta.x, delta.z);
        world.add(group);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "party-direction-choice";
        button.dataset.from = tile.id;
        button.dataset.to = id;
        const other = board.nodes[id];
        const label =
          other.ring === tile.ring
            ? id === (tile.clockwise ?? tile.exits[0])
              ? "시계 방향"
              : "반시계 방향"
            : other.ring === "inner"
              ? "중앙 길"
              : "외곽 길";
        button.setAttribute("aria-label", `방향 선택 · ${label}`);
        button.title = label;
        const glyph = document.createElement("span");
        glyph.textContent = "➜";
        button.append(glyph);
        button.hidden = true;
        button.disabled = true;
        ["pointerdown", "pointerup", "pointermove"].forEach((event) =>
          button.addEventListener(event, (e) => e.stopPropagation()),
        );
        button.addEventListener("click", (e) => {
          e.stopPropagation();
          if (!button.disabled) options.onDirectionSelect?.(id);
        });
        overlay.append(button);
        directions.push({
          from: tile.id,
          to: id,
          group,
          button,
          glyph,
        });
      }),
    );
    board.nodes.forEach((tile) => {
      const group = new THREE.Group(),
        position = point(tile);
      group.position.copy(position);
      world.add(group);
      const base = mesh(
        geo(new THREE.CylinderGeometry(1.02, 1.05, 0.16, 8)),
        pale,
        group,
        [0, -0.2, 0],
      );
      base.receiveShadow = true;
      base.rotation.y = Math.PI / 8;
      const material = mat(
        tile.kind === "camp"
          ? tile.shared
            ? 0xe7b963
            : SEATS[tile.owner_seat ?? Math.floor(tile.id / 6)]
          : TILES[tile.kind] || 0xa0b3c7,
      );
      const top = mesh(
        geo(new THREE.CylinderGeometry(0.91, 0.96, 0.15, 8)),
        material,
        group,
        [0, -0.045, 0],
      );
      top.receiveShadow = true;
      top.rotation.y = Math.PI / 8;
      top.userData.tile = tile.id;
      pickTargets.push(top);
      const faceMaterial = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        map: tileTexture(tile),
        transparent: true,
        depthWrite: false,
        toneMapped: false,
        polygonOffset: true,
        polygonOffsetFactor: -1,
      });
      materials.add(faceMaterial);
      const face = mesh(
        geo(
          new THREE.PlaneGeometry(
            tile.background_img ? 1.9 : 1.44,
            tile.background_img ? 1.9 : 1.44,
          ),
        ),
        faceMaterial,
        group,
        [0, 0.039, 0],
      );
      face.rotation.x = -Math.PI / 2;
      if (tile.background_img) loadTileBackground(face, tile.background_img);
      const ring = mesh(
        geo(new THREE.TorusGeometry(1.08, 0.055, 6, 40)),
        mat(0xfff1b8, { emissive: 0xe9c677, emissiveIntensity: 0.8 }),
        group,
        [0, 0.07, 0],
      );
      ring.rotation.x = Math.PI / 2;
      ring.visible = false;
      const barrier = new THREE.Group();
      group.add(barrier);
      const barrierMaterial = mat(0xef5868, { roughness: 0.7 });
      mesh(
        geo(new THREE.BoxGeometry(1.8, 0.3, 0.18)),
        barrierMaterial,
        barrier,
        [0, 0.85, 0],
      );
      [-0.65, 0.65].forEach((x) =>
        mesh(
          geo(new THREE.BoxGeometry(0.14, 0.7, 0.2)),
          barrierMaterial,
          barrier,
          [x, 0.38, 0],
        ),
      );
      barrier.visible = false;
      const crate = new THREE.Group();
      group.add(crate);
      crate.position.set(0.56, 0.35, 0.35);
      const wood = mat(0xbd803e, { roughness: 0.85 }),
        trim = mat(0xffd383, { roughness: 0.5 });
      const body = mesh(
        geo(new THREE.BoxGeometry(0.8, 0.58, 0.66)),
        wood,
        crate,
        [0, 0, 0],
      );
      body.userData.tile = tile.id;
      pickTargets.push(body);
      mesh(
        geo(new THREE.BoxGeometry(0.86, 0.12, 0.72)),
        trim,
        crate,
        [0, 0.28, 0],
      );
      mesh(
        geo(new THREE.BoxGeometry(0.12, 0.64, 0.69)),
        trim,
        crate,
        [0, 0.01, 0],
      );
      crate.visible = false;
      const hit = document.createElement("button");
      hit.type = "button";
      hit.className = "party-world-hit";
      hit.dataset.tile = tile.id;
      hit.setAttribute("aria-label", tile.label);
      hit.textContent = tile.label;
      hit.addEventListener("click", (event) => {
        if (event.detail === 0) options.onTileSelect?.(tile.id);
      });
      overlay.append(hit);
      let camp = null;
      if (tile.kind === "camp") {
        const decal = mesh(
          geo(new THREE.PlaneGeometry(1.27, 1.27)),
          mat(0xffffff, {
            transparent: true,
            opacity: 0.4,
            depthWrite: false,
            roughness: 1,
            polygonOffset: true,
            polygonOffsetFactor: -2,
          }),
          group,
          [0, 0.055, 0],
        );
        decal.rotation.x = -Math.PI / 2;
        // Plane-local +Z points upward; negative rotation turns the artwork clockwise.
        decal.rotation.z = -Math.PI / 4;
        decal.visible = false;
        camp = { decal, face, source: "", loaded: false, owner: null };
      }
      tiles.set(tile.id, {
        group,
        material,
        face,
        ring,
        hit,
        tile,
        camp,
        barrier,
        crate,
      });
    });
  }
  function loadTileBackground(face, source) {
    let entry = backgrounds.get(source);
    if (!entry) {
      entry = { loaded: false, faces: new Set(), texture: null };
      backgrounds.set(source, entry);
      entry.texture = iconLoader.load(
        source,
        () => {
          if (disposed) return;
          entry.loaded = true;
          entry.faces.forEach((surface) => {
            surface.material.map = entry.texture;
            surface.material.needsUpdate = true;
            surface.userData.backgroundLoaded = true;
            surface.visible = true;
          });
          renderer.domElement.dataset.tileBackgrounds = [
            ...tiles.values(),
          ].filter((t) => t.face.userData.backgroundLoaded).length;
        },
        undefined,
        () => {},
      );
      entry.texture.colorSpace = THREE.SRGBColorSpace;
      textures.add(entry.texture);
    }
    entry.faces.add(face);
    if (entry.loaded) {
      face.material.map = entry.texture;
      face.material.needsUpdate = true;
      face.userData.backgroundLoaded = true;
      face.visible = true;
    }
  }
  function updateCamp(camp, owner) {
    camp.owner = owner?.seat ?? null;
    camp.decal.visible = !!owner && camp.loaded;
    camp.face.visible =
      camp.face.userData.backgroundLoaded || !camp.decal.visible;
    if (!owner) return;
    const source = owner.character.icon_img || owner.character.img;
    if (source === camp.source) return;
    camp.source = source;
    camp.loaded = false;
    camp.decal.visible = false;
    camp.face.visible = true;
    const previous = camp.decal.material.map;
    if (previous) {
      textures.delete(previous);
      previous.dispose();
    }
    const texture = iconLoader.load(
      source,
      () => {
        if (disposed || camp.source !== source) return;
        camp.loaded = true;
        camp.decal.visible = camp.owner !== null;
        camp.face.visible =
          camp.face.userData.backgroundLoaded || !camp.decal.visible;
        renderer.domElement.dataset.campTextures = [...tiles.values()].filter(
          (t) => t.camp?.loaded,
        ).length;
      },
      undefined,
      () => {
        if (disposed || camp.source !== source) return;
        camp.loaded = false;
        camp.decal.visible = false;
        camp.face.visible = true;
      },
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    textures.add(texture);
    camp.decal.material.map = texture;
    camp.decal.material.needsUpdate = true;
  }
  function makePawn(player) {
    const group = new THREE.Group();
    const shadowMaterial = new THREE.MeshBasicMaterial({
      color: 0x182d43,
      transparent: true,
      opacity: 0.24,
      depthWrite: false,
    });
    materials.add(shadowMaterial);
    const shadow = mesh(
      geo(new THREE.CircleGeometry(0.64, 32)),
      shadowMaterial,
      world,
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.renderOrder = 4;
    world.add(group);
    const standing = document.createElement("div");
    standing.className = "party-world-standing";
    standing.dataset.seat = player.seat;
    standing.setAttribute("role", "button");
    standing.setAttribute("aria-label", `${player.name} 위치 보기`);
    standing.tabIndex = 0;
    standing.addEventListener("click", (event) => {
      event.stopPropagation();
      focusPlayer(player.seat);
    });
    standing.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        focusPlayer(player.seat);
      }
    });
    standing.style.setProperty(
      "--pawn-color",
      `#${SEATS[player.seat].toString(16).padStart(6, "0")}`,
    );
    const image = document.createElement("img");
    image.decoding = "async";
    image.draggable = false;
    image.alt = `${player.character.name} 스탠딩 일러스트`;
    const fallback = document.createElement("span");
    fallback.className = "party-standing-fallback";
    fallback.textContent = player.character.name.slice(0, 1);
    standing.append(image, fallback);
    const label = document.createElement("div");
    label.className = "party-world-pawn-label";
    label.style.setProperty(
      "--pawn-color",
      `#${SEATS[player.seat].toString(16).padStart(6, "0")}`,
    );
    overlay.append(standing, label);
    const position = point(state.board.nodes[player.position]);
    group.position.copy(position);
    const halo = mesh(
      geo(new THREE.TorusGeometry(0.69, 0.055, 6, 32)),
      mat(0xffe8a1, { emissive: 0xe8ae55, emissiveIntensity: 0.8 }),
      group,
      [0, 0.05, 0],
    );
    halo.rotation.x = Math.PI / 2;
    const pawn = {
      group,
      shadow,
      standing,
      image,
      fallback,
      label,
      destination: position,
      finalDestination: position,
      route: [],
      routeActive: false,
      pendingVersion: null,
      displayPlayer: player,
      lastPosition: player.position,
      halo,
      seat: player.seat,
      artKey: "",
    };
    updateArt(pawn, player);
    return pawn;
  }
  function updateArt(pawn, player) {
    const sources = [
      ...new Set(
        [
          player.character.body_img,
          player.character.sd_img,
          player.character.icon_img,
          player.character.img,
        ].filter(Boolean),
      ),
    ].filter((value) => {
      try {
        return ["http:", "https:"].includes(
          new URL(value, location.href).protocol,
        );
      } catch {
        return false;
      }
    });
    const key = JSON.stringify(sources);
    if (pawn.artKey === key) return;
    pawn.artKey = key;
    pawn.image.alt = `${player.character.name} 스탠딩 일러스트`;
    pawn.standing.title = `${player.name} · ${player.character.name}`;
    pawn.fallback.textContent = player.character.name.slice(0, 1);
    let index = 0;
    const load = () => {
      pawn.image.hidden = !sources[index];
      pawn.fallback.hidden = !!sources[index];
      if (sources[index]) pawn.image.src = sources[index];
    };
    pawn.image.onerror = () => {
      index++;
      load();
    };
    load();
  }
  function update(next, selectedId = null, legal = []) {
    if (disposed) return;
    const initial = !hasSnapshot;
    const nextViewer = next.focus_seat ?? next.me?.seat ?? null;
    const roleChanged = viewerSeat !== nextViewer;
    if (
      next.interaction_seq !== undefined &&
      next.interaction_seq !== interactionSeq
    ) {
      lastInteraction = performance.now();
      interactionSeq = next.interaction_seq;
    }
    const turnKey = `${next.round}:${next.turn_number ?? next.turn}:${next.turn}`;
    const ownTurn =
      turnKey !== observedTurn &&
      next.status === "running" &&
      next.turn === nextViewer;
    const actionChanged =
      next.last_action && next.last_action.version !== lastActionVersion;
    let refocus = initial || roleChanged || ownTurn;
    if (refocus) focusSeat = nextViewer ?? next.turn;
    else if (actionChanged && performance.now() - lastInteraction >= 5000) {
      focusSeat = next.last_action.seat;
      refocus = true;
    }
    viewerSeat = nextViewer;
    observedTurn = turnKey;
    lastActionVersion = next.last_action?.version ?? null;
    state = next;
    selected = selectedId;
    allowed = legal;
    const receipt = next.move_path;
    const freshPath =
      hasSnapshot && receipt && receipt.version !== lastMoveVersion;
    buildBoard(next.board);
    const preview = next.movement_preview;
    const focused = preview?.nodes?.includes(next.preview_target)
      ? preview.routes?.[next.preview_target]
      : null;
    const reachable = new Set(preview?.nodes || []);
    const focusedNodes = new Set(focused?.nodes || []);
    const reachableRoads = new Set(preview?.edges || []);
    const focusedRoads = new Set(focused?.edges || []);
    roads.forEach(({ highlight, material }, key) => {
      highlight.visible = reachableRoads.has(key);
      material.opacity = focused && !focusedRoads.has(key) ? 0.12 : 0.9;
    });
    const itemTargets = new Set(next.item_target_nodes || []);
    const barriers = new Set((next.roadblocks || []).map((b) => b.node));
    const supplies = new Map((next.supplies || []).map((s) => [s.node, s]));
    tiles.forEach(({ material, ring, hit, tile, camp, barrier, crate }) => {
      const active = reachable.has(tile.id);
      const itemTarget = itemTargets.has(tile.id);
      const dimmed = active && focused && !focusedNodes.has(tile.id);
      ring.visible = active || itemTarget || selected === tile.id;
      ring.material.color.set(
        itemTarget
          ? next.item_target_node === tile.id
            ? 0xffffff
            : 0xffb465
          : selected === tile.id
            ? 0xffdc91
            : 0xaaffdd,
      );
      ring.material.emissive.set(
        itemTarget ? 0xc27631 : active ? 0x65c5a1 : 0xd59c43,
      );
      ring.material.transparent = true;
      ring.material.opacity = dimmed ? 0.18 : 1;
      material.emissive.set(active ? 0x245845 : 0x000000);
      material.emissiveIntensity = dimmed ? 0.04 : 0.4;
      hit.classList.toggle("is-next", legal.includes(tile.id));
      hit.classList.toggle("is-item-target", itemTarget);
      barrier.visible = barriers.has(tile.id);
      const supply = supplies.get(tile.id);
      crate.visible = !!supply;
      hit.classList.toggle("is-reachable", active);
      hit.classList.toggle("is-route-dimmed", !!dimmed);
      hit.setAttribute(
        "aria-label",
        `${tile.label}${supply ? ` · 보급함 HP ${supply.hp}` : ""}${active ? " · 이동 경로 미리보기" : ""}`,
      );
      if (camp) {
        const owner = next.players.find(
          (p) => (p.home ?? p.seat * 6) === tile.id,
        );
        updateCamp(camp, owner);
        if (owner) {
          hit.setAttribute(
            "aria-label",
            `${owner.name}의 거점${supply ? ` · 보급함 HP ${supply.hp}` : ""}`,
          );
        }
      }
    });
    next.players.forEach((player) => {
      let pawn = pawns.get(player.seat);
      if (!pawn) {
        pawn = makePawn(player);
        pawns.set(player.seat, pawn);
      }
      updateArt(pawn, player);
      if (freshPath && receipt.seat === player.seat && receipt.nodes.length > 1)
        pawn.pendingVersion = receipt.version;
      const same = next.players.filter((p) => p.position === player.position),
        index = same.findIndex((p) => p.seat === player.seat);
      const destination = point(next.board.nodes[player.position]);
      if (same.length > 1) {
        destination.x += (index - (same.length - 1) / 2) * 2.25;
        destination.z += 0.2;
      }
      pawn.finalDestination = destination;
      if (
        freshPath &&
        receipt.seat === player.seat &&
        receipt.nodes.length > 1 &&
        receipt.nodes[0] === pawn.lastPosition &&
        receipt.nodes.at(-1) === player.position &&
        !reduced
      ) {
        pawn.route = receipt.nodes
          .slice(1, -1)
          .map((id) => point(next.board.nodes[id]));
        pawn.route.push(destination);
        pawn.destination = pawn.route.shift();
        pawn.routeActive = true;
      } else if (player.position !== pawn.lastPosition || !pawn.routeActive) {
        pawn.route = [];
        pawn.routeActive = false;
        pawn.destination = destination;
      } else if (!pawn.route.length) pawn.destination = destination;
      pawn.lastPosition = player.position;
      pawn.labelLane = (index % 2) * 25;
      pawn.label.title = player.name;
      if (pawn.pendingVersion === null) pawn.displayPlayer = player;
      updatePawnStatus(pawn, pawn.displayPlayer);
      pawn.label.classList.toggle(
        "is-current",
        next.status === "running" && next.turn === player.seat,
      );
      pawn.halo.visible =
        next.status === "running" && next.turn === player.seat;
      if (reduced) pawn.group.position.copy(pawn.destination);
    });
    hasSnapshot = true;
    lastMoveVersion = receipt?.version ?? null;
    const player =
      next.players.find((p) => p.seat === focusSeat) || next.players[0];
    if (player) {
      const key = `${player.seat}:${player.position}`;
      if (key !== focusKey) {
        focusSeat = player.seat;
        focusKey = key;
        focusTarget.copy(
          pawns.get(player.seat)?.group.position ??
            point(next.board.nodes[player.position]),
        );
        focusTarget.y = 0.6;
        if (refocus) following = true;
        if (!renderer.domElement.dataset.focusSeat || reduced)
          target.copy(focusTarget);
        renderer.domElement.dataset.focusSeat = player.seat;
        positionCamera();
      }
      if (refocus) following = true;
    }
    renderer.domElement.dataset.players = next.players.length;
    renderer.domElement.dataset.tiles = next.board.nodes.length;
    renderer.domElement.dataset.directions = 0;
    renderer.domElement.dataset.campRotation = 45;
    renderer.domElement.dataset.campRotationDirection = "clockwise";
    renderer.domElement.dataset.campOpacity = 0.4;
    renderer.domElement.dataset.reachableTiles = reachable.size;
    renderer.domElement.dataset.highlightedRoads = reachableRoads.size;
    renderer.domElement.dataset.focusedRoads = focused
      ? focusedRoads.size
      : reachableRoads.size;
  }
  function positionCamera() {
    camera.position.set(
      target.x,
      target.y + Math.sin(elevation) * 40,
      target.z + Math.cos(elevation) * 40,
    );
    camera.lookAt(target);
    camera.zoom = zoom;
    camera.updateProjectionMatrix();
    renderer.domElement.dataset.panX = target.x.toFixed(2);
    renderer.domElement.dataset.panZ = target.z.toFixed(2);
  }
  function resize() {
    const rect = container.getBoundingClientRect();
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    renderer.setSize(width, height, false);
    const insets = options.getInsets?.() || {
      left: 8,
      right: 8,
      top: 32,
      bottom: 8,
    };
    const usefulWidth = Math.max(180, width - insets.left - insets.right);
    const horizontal = ((width <= 700 ? 16 : 25) * width) / usefulWidth;
    const vertical = (horizontal * height) / width;
    const offsetX = ((insets.left - insets.right) / 2 / width) * horizontal;
    const offsetY = ((insets.top - insets.bottom) / 2 / height) * vertical;
    camera.left = -horizontal / 2 - offsetX;
    camera.right = horizontal / 2 - offsetX;
    camera.top = vertical / 2 + offsetY;
    camera.bottom = -vertical / 2 + offsetY;
    positionCamera();
  }
  function focus() {
    interact();
    focusSeat = viewerSeat ?? state?.turn ?? focusSeat;
    const pawn = pawns.get(focusSeat);
    if (pawn) focusTarget.copy(pawn.group.position);
    focusTarget.y = 0.6;
    focusKey = "";
    renderer.domElement.dataset.focusSeat = focusSeat;
    following = true;
    zoom = 1;
    target.copy(focusTarget);
    positionCamera();
  }
  function focusPlayer(seat) {
    const pawn = pawns.get(seat);
    if (!pawn) return;
    interact();
    focusSeat = seat;
    focusTarget.copy(pawn.group.position);
    focusTarget.y = 0.6;
    focusKey = `${seat}:${pawn.lastPosition}`;
    following = true;
    target.copy(focusTarget);
    renderer.domElement.dataset.focusSeat = seat;
    positionCamera();
  }
  function pan(dx, dy) {
    following = false;
    const units = (camera.right - camera.left) / zoom / width;
    target.x = THREE.MathUtils.clamp(
      target.x - dx * units,
      -panLimit,
      panLimit,
    );
    target.z = THREE.MathUtils.clamp(
      target.z - (dy * units) / Math.sin(elevation),
      -panLimit,
      panLimit,
    );
    positionCamera();
  }
  const projected = new THREE.Vector3();
  function updatePawnStatus(pawn, player) {
    pawn.standing.style.opacity = player.cloaked
      ? "0.35"
      : player.hp <= 0
        ? "0.45"
        : "1";
    pawn.label.textContent = `${player.seat + 1}P · ${player.name}${player.hp <= 0 ? " · 기절" : player.cloaked ? " · 투명" : ""}`;
  }
  function placeLabel(element, position, offset = 0) {
    projected.copy(position).project(camera);
    const x = ((projected.x + 1) * width) / 2 + offset;
    const y = ((1 - projected.y) * height) / 2;
    element.style.transform = `translate(${x}px,${y}px) translate(-50%,-50%)`;
    element.hidden =
      projected.z > 1 ||
      projected.z < -1 ||
      x < 0 ||
      x > width ||
      y < 0 ||
      y > height;
  }
  function animate(now) {
    if (disposed) return;
    frame = requestAnimationFrame(animate);
    if (document.hidden || !inView || !active || now - lastPaint < 30) return;
    const dt = Math.min(0.06, (now - lastTime) / 1000 || 0.016);
    lastTime = now;
    lastPaint = now;
    const focusPawn = pawns.get(focusSeat);
    if (focusPawn) {
      focusTarget.copy(
        focusPawn.routeActive
          ? focusPawn.group.position
          : focusPawn.finalDestination,
      );
      focusTarget.y = 0.6;
    }
    if (following && target.distanceToSquared(focusTarget) > 0.0001) {
      target.lerp(focusTarget, reduced ? 1 : 1 - Math.exp(-dt * 9));
      positionCamera();
    }
    crystal.rotation.y = reduced ? 0 : now * 0.00032;
    crystal.position.y = 2.65 + (reduced ? 0 : Math.sin(now * 0.0016) * 0.11);
    tiles.forEach(({ group, hit }) => {
      placeLabel(hit, group.position.clone().add(new THREE.Vector3(0, 0.1, 0)));
    });
    pawns.forEach((pawn) => {
      const delta = pawn.destination.clone().sub(pawn.group.position),
        moving = Math.hypot(delta.x, delta.z) > 0.03;
      pawn.group.position.lerp(pawn.destination, 1 - Math.exp(-dt * 8));
      if (pawn.routeActive && Math.hypot(delta.x, delta.z) < 0.12) {
        pawn.group.position.copy(pawn.destination);
        if (pawn.route.length) pawn.destination = pawn.route.shift();
        else pawn.routeActive = false;
      }
      if (
        pawn.pendingVersion !== null &&
        !pawn.routeActive &&
        Math.hypot(delta.x, delta.z) < 0.12
      ) {
        const version = pawn.pendingVersion;
        pawn.pendingVersion = null;
        pawn.displayPlayer =
          state.players.find((p) => p.seat === pawn.seat) || pawn.displayPlayer;
        updatePawnStatus(pawn, pawn.displayPlayer);
        queueMicrotask(() => options.onMovementComplete?.(version));
      }
      pawn.group.position.y =
        pawn.destination.y +
        (reduced
          ? 0
          : Math.sin(now * (moving ? 0.017 : 0.002) + pawn.seat) *
            (moving ? 0.15 : 0.026));
      // The ground shadow follows X/Z only; idle bobbing never crosses the tile artwork.
      pawn.shadow.position.set(
        pawn.group.position.x,
        1.405,
        pawn.group.position.z,
      );
      pawn.halo.position.y = 1.43 - pawn.group.position.y;
      const pixelsPerUnit = (height / (camera.top - camera.bottom)) * zoom;
      const artHeight = pixelsPerUnit * 5.1;
      pawn.standing.style.width = `${pixelsPerUnit * 3.5}px`;
      pawn.standing.style.height = `${artHeight}px`;
      projected.copy(pawn.group.position).project(camera);
      const x = ((projected.x + 1) * width) / 2,
        y = ((1 - projected.y) * height) / 2;
      pawn.standing.style.transform = `translate(${x}px,${y}px) translate(-50%,-100%)`;
      pawn.standing.style.zIndex = Math.round(y) + 100;
      pawn.standing.hidden =
        x < -100 || x > width + 100 || y < -20 || y > height + artHeight;
      pawn.label.style.transform = `translate(${x}px,${y - artHeight - 8 + pawn.labelLane}px) translate(-50%,-100%)`;
      pawn.label.style.zIndex = Math.round(y) + 101;
      pawn.label.hidden = pawn.standing.hidden;
    });
    const focusPlayer = state?.players.find((p) => p.seat === viewerSeat);
    directions.forEach(({ from, to, group, button, glyph }) => {
      const selectable =
        allowed.length > 1 &&
        focusPlayer?.position === from &&
        allowed.includes(to) &&
        !pawns.get(viewerSeat)?.routeActive;
      button.disabled = !selectable;
      if (!selectable) {
        button.hidden = true;
        return;
      }
      placeLabel(button, group.position);
      const a = point(state.board.nodes[from]).project(camera);
      const b = point(state.board.nodes[to]).project(camera);
      glyph.style.transform = `rotate(${Math.atan2(-(b.y - a.y) * height, (b.x - a.x) * width)}rad)`;
    });
    renderer.render(scene, camera);
  }
  let gesture = null,
    dragged = false,
    lastPinch = 0;
  const contacts = new Map();
  const interactionRoot = options.interactionRoot || document;
  function interact() {
    lastInteraction = performance.now();
  }
  const interactionEvents = ["pointerdown", "pointermove", "wheel", "keydown"];
  interactionEvents.forEach((event) =>
    interactionRoot.addEventListener(event, interact, {
      capture: true,
      passive: true,
    }),
  );
  const onDown = (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    contacts.set(event.pointerId, { x: event.clientX, y: event.clientY });
    container.setPointerCapture?.(event.pointerId);
    if (contacts.size === 1) {
      gesture = {
        x: event.clientX,
        y: event.clientY,
        startX: event.clientX,
        startY: event.clientY,
        pawnSeat: event.target.closest?.(".party-world-standing")?.dataset.seat,
      };
      dragged = false;
    } else {
      dragged = true;
      lastPinch = 0;
    }
  };
  const onMove = (event) => {
    if (!contacts.has(event.pointerId)) {
      return;
    }
    contacts.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (contacts.size === 2) {
      const [a, b] = [...contacts.values()],
        distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (lastPinch)
        zoom = Math.max(0.75, Math.min(1.7, (zoom * distance) / lastPinch));
      lastPinch = distance;
      positionCamera();
      return;
    }
    if (!gesture) return;
    if (
      Math.hypot(
        event.clientX - gesture.startX,
        event.clientY - gesture.startY,
      ) > 6
    )
      dragged = true;
    if (dragged) pan(event.clientX - gesture.x, event.clientY - gesture.y);
    gesture.x = event.clientX;
    gesture.y = event.clientY;
  };
  const onUp = (event) => {
    contacts.delete(event.pointerId);
    if (!dragged && gesture && state) {
      const rect = container.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / width) * 2 - 1,
        (-(event.clientY - rect.top) / height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(pickTargets, false)[0];
      if (gesture.pawnSeat !== undefined) focusPlayer(Number(gesture.pawnSeat));
      else if (hit) options.onTileSelect?.(hit.object.userData.tile);
    }
    gesture = null;
    lastPinch = 0;
  };
  const onCancel = () => {
    contacts.clear();
    gesture = null;
    dragged = true;
    lastPinch = 0;
  };
  const onWheel = (event) => {
    event.preventDefault();
    zoom = Math.max(
      0.75,
      Math.min(1.7, zoom * Math.exp(-event.deltaY * 0.001)),
    );
    positionCamera();
  };
  const onLost = (event) => {
    event.preventDefault();
    options.onFailure?.("3D 표시를 사용할 수 없어 기본 지도로 전환합니다.");
  };
  container.addEventListener("pointerdown", onDown);
  container.addEventListener("pointermove", onMove);
  container.addEventListener("pointerup", onUp);
  container.addEventListener("pointercancel", onCancel);
  container.addEventListener("wheel", onWheel, { passive: false });
  renderer.domElement.addEventListener("webglcontextlost", onLost);
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  const visibility = new IntersectionObserver((entries) => {
    inView = entries[0]?.isIntersecting !== false;
  });
  visibility.observe(container);
  resize();
  frame = requestAnimationFrame(animate);
  return {
    update,
    focusPlayer,
    zoom(amount) {
      interact();
      zoom = Math.max(0.75, Math.min(1.7, zoom * amount));
      positionCamera();
    },
    reset: focus,
    pan,
    pause(value) {
      active = !value;
    },
    stats() {
      return {
        target: target.toArray(),
        yaw,
        elevation,
        zoom,
        following,
        focusSeat,
        tiles: tiles.size,
        players: pawns.size,
        calls: renderer.info.render.calls,
        triangles: renderer.info.render.triangles,
        geometries: renderer.info.memory.geometries,
        textures: renderer.info.memory.textures,
      };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      visibility.disconnect();
      interactionEvents.forEach((event) =>
        interactionRoot.removeEventListener(event, interact, true),
      );
      container.removeEventListener("pointerdown", onDown);
      container.removeEventListener("pointermove", onMove);
      container.removeEventListener("pointerup", onUp);
      container.removeEventListener("pointercancel", onCancel);
      container.removeEventListener("wheel", onWheel);
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      pawns.forEach((pawn) => {
        pawn.image.onerror = null;
      });
      geometries.forEach((g) => g.dispose());
      materials.forEach((m) => m.dispose());
      textures.forEach((t) => t.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
      container.replaceChildren();
      container.classList.remove("is-3d");
    },
  };
}
