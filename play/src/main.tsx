import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { DevicePreview, previewDevice } from "./dev/DevicePreview";
import { readMode } from "./mode";
import { installDecisionSound } from "./sound/events";
import { installSoundUnlock } from "./sound/sfx";
import "./styles.css";

installSoundUnlock();
installDecisionSound();

const device = import.meta.env.DEV ? previewDevice() : null;
const mode = readMode();

createRoot(document.getElementById("root")!).render(
  <StrictMode>{device ? <DevicePreview device={device} mode={mode} /> : <App mode={mode} />}</StrictMode>,
);
