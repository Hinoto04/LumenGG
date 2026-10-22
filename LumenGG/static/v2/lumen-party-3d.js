import { createPartyScene } from "./lumen-party-scene.js?v=20261019-supplies1";
window.LumenParty3D = { create: createPartyScene };
window.dispatchEvent(new Event("lumen-party-3d-ready"));
