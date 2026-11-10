import assert from "node:assert/strict";
import { test } from "node:test";
import { classifyNavigation } from "../src/battle-nav";

const origin = "https://lumen.hinoto.kr";

test("the game stays in the WebView", () => {
  assert.equal(classifyNavigation(`${origin}/battlelog/play/?game=v&seat=p1&token=t`, origin), "allow");
  assert.equal(classifyNavigation(`${origin}/battlelog/play/?game=v`, origin), "allow");
  assert.equal(classifyNavigation(`${origin}/battlelog/simulator/v/p1/t/`, origin), "allow");
  assert.equal(classifyNavigation("about:blank", origin), "allow");
});

test("leaving the game returns to the app", () => {
  assert.equal(classifyNavigation(`${origin}/battlelog/play/`, origin), "close");
});

test("other pages open in the browser", () => {
  assert.equal(classifyNavigation(`${origin}/login/?next=/battlelog/play/`, origin), "external");
  assert.equal(classifyNavigation("https://evil.example/battlelog/play/?game=v", origin), "external");
  assert.equal(classifyNavigation(`${origin}.evil.example/battlelog/play/?game=v`, origin), "external");
});
