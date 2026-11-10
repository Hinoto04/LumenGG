import { useCallback, useEffect, useRef, useState } from "react";
import type { AppMode } from "../mode";
import { FixtureBar } from "./FixtureBar";

const DEVICES = {
  phone: { width: 390, height: 844, label: "휴대폰 세로" },
  "phone-land": { width: 844, height: 390, label: "휴대폰 가로" },
  tablet: { width: 820, height: 1180, label: "태블릿" },
  laptop: { width: 1366, height: 768, label: "노트북" },
} as const;

export type DeviceName = keyof typeof DEVICES;

function withDevice(name: DeviceName | null): string {
  const query = new URLSearchParams(location.search);
  if (name) query.set("device", name);
  else query.delete("device");
  const search = query.toString().replace(/=(?=&|$)/g, "");
  return `${location.pathname}${search ? `?${search}` : ""}${location.hash}`;
}

export function isEmbedded(): boolean {
  return window.self !== window.top;
}

export function previewDevice(): DeviceName | null {
  if (isEmbedded()) return null;
  const device = new URLSearchParams(location.search).get("device");
  return device && device in DEVICES ? (device as DeviceName) : null;
}

/**
 * 개발용: ?device=phone 으로 열면 같은 앱을 기기 크기 iframe에 띄운다.
 * 픽스처 조작은 바깥에서 하고, iframe에는 해시만 넘긴다.
 * 화면보다 큰 기기는 축소해서 보여 준다.
 */
export function DevicePreview({ device, mode }: { device: DeviceName; mode: AppMode }) {
  const spec = DEVICES[device];
  const frame = useRef<HTMLIFrameElement>(null);
  const [src] = useState(() => {
    const query = new URLSearchParams(location.search);
    query.delete("device");
    const search = query.toString();
    return `${location.pathname}${search ? `?${search.replace(/=(?=&|$)/g, "")}` : ""}${location.hash}`;
  });
  const [scale, setScale] = useState(1);

  useEffect(() => {
    document.title = `미리보기 · ${spec.label}`;
    const fit = () => {
      const available = { w: window.innerWidth - 48, h: window.innerHeight - 110 };
      setScale(Math.min(1, available.w / (spec.width + 20), available.h / (spec.height + 20)));
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [spec]);

  const remote = useCallback((hash: string) => {
    const target = frame.current?.contentWindow;
    if (target && target.location.hash !== hash) target.location.hash = hash;
  }, []);

  return (
    <div className="device-stage">
      <div className="device-toolbar">
        {mode.kind === "fixtures" && <FixtureBar remote={remote} />}
        <div className="device-switch">
          {(Object.keys(DEVICES) as DeviceName[]).map((name) => (
            <a key={name} href={withDevice(name)} className={name === device ? "is-active" : ""}>
              {DEVICES[name].label} {DEVICES[name].width}×{DEVICES[name].height}
            </a>
          ))}
          <a href={withDevice(null)}>전체 화면</a>
        </div>
      </div>
      <div className="device-holder" style={{ width: (spec.width + 20) * scale, height: (spec.height + 20) * scale }}>
        <iframe
          ref={frame}
          title={spec.label}
          src={src}
          className="device-frame"
          style={{ width: spec.width + 20, height: spec.height + 20, transform: `scale(${scale})` }}
        />
      </div>
    </div>
  );
}
