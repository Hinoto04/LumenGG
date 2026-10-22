import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { View, Text, Pressable } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { useFocusEffect } from "expo-router";
import { absoluteUrl } from "./api";
import type { PartyState, PartyTile } from "./party";

export function PartyBoard3D({
  state,
  selected,
  onSelect,
  routeTarget,
  itemTargets,
  itemTarget,
  onDirectionSelect,
  onMovementComplete,
  cameraRequest,
  canMove,
  interactionSeq,
  fallback,
}: {
  state: PartyState;
  selected?: number;
  onSelect: (tile: PartyTile) => void;
  routeTarget: number | null;
  itemTargets: number[];
  itemTarget?: number;
  onDirectionSelect: (id: number) => void;
  onMovementComplete: (version: number) => void;
  cameraRequest: { seat: number; id: number } | null;
  canMove: boolean;
  interactionSeq: number;
  fallback: React.ReactNode;
}) {
  const web = useRef<WebView>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [twoD, setTwoD] = useState(false);
  const isReady = useRef(false);
  const focused = useRef(true);
  const handledFocus = useRef(0);
  useEffect(() => {
    if (!cameraRequest || handledFocus.current === cameraRequest.id) return;
    if (failed) {
      handledFocus.current = cameraRequest.id;
      return;
    }
    if (twoD) {
      isReady.current = false;
      setReady(false);
      setTwoD(false);
      return;
    }
    if (ready) {
      web.current?.injectJavaScript(
        `window.partyBoardFocus?.(${cameraRequest.seat});true;`,
      );
      handledFocus.current = cameraRequest.id;
    }
  }, [cameraRequest, twoD, ready, failed]);
  useEffect(() => {
    if ((failed || twoD || !ready) && state.move_path)
      onMovementComplete(state.move_path.version);
  }, [failed, twoD, ready, state.move_path?.version, onMovementComplete]);
  const url = absoluteUrl("/battlelog/party/board/?v=20261019-supplies1");
  const source = useMemo(() => ({ uri: url }), [url]);
  const origin = useMemo(() => new URL(url).origin, [url]);
  const player = state.players.find((p) => p.seat === state.me?.seat);
  const legal =
    canMove &&
    player &&
    state.status === "running" &&
    state.turn === player.seat &&
    state.move &&
    !state.move_prompt &&
    !state.battle &&
    !state.expired
      ? (player.forward_exits ?? state.board.nodes[player.position]!.exits)
      : [];
  // Only public board state enters the WebView. Seat tokens and calculator controls stay native.
  const payload = JSON.stringify({
    board: state.board,
    players: state.players,
    status: state.status,
    turn: state.turn,
    round: state.round,
    turn_number: state.turn_number,
    turn_order: state.turn_order,
    last_action: state.last_action,
    interaction_seq: interactionSeq,
    move: state.move,
    move_path: state.move_path,
    movement_preview: state.movement_preview,
    preview_target: routeTarget,
    roadblocks: state.roadblocks,
    supplies: state.supplies,
    item_target_nodes: itemTargets,
    item_target_node: itemTarget,
    focus_seat: player?.seat ?? null,
  });
  const script = `window.updatePartyBoard?.(${payload.replace(/</g, "\\u003c")},${selected ?? "null"},${JSON.stringify(legal)});true;`;
  useEffect(() => {
    if (ready && !failed && !twoD) web.current?.injectJavaScript(script);
  }, [ready, failed, twoD, script]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!isReady.current) setFailed(true);
    }, 15000);
    return () => clearTimeout(timer);
  }, [twoD]);
  useFocusEffect(
    useCallback(() => {
      focused.current = true;
      web.current?.injectJavaScript("window.partyBoardActive?.(true);true;");
      return () => {
        focused.current = false;
        web.current?.injectJavaScript("window.partyBoardActive?.(false);true;");
      };
    }, [ready]),
  );
  function message(event: WebViewMessageEvent) {
    try {
      const value = JSON.parse(event.nativeEvent.data);
      if (value.type === "ready") {
        isReady.current = true;
        web.current?.injectJavaScript(
          `window.partyBoardActive?.(${focused.current});true;`,
        );
        setReady(true);
      }
      if (value.type === "fallback") setFailed(true);
      if (
        value.type === "settled" &&
        Number.isInteger(value.version) &&
        value.version >= 0 &&
        value.version <= state.version
      )
        onMovementComplete(value.version);
      if (
        value.type === "tile" &&
        Number.isInteger(value.id) &&
        value.id >= 0 &&
        value.id < state.board.nodes.length
      ) {
        const tile = state.board.nodes[value.id];
        if (tile) {
          onSelect(tile);
        }
      }
      if (
        value.type === "direction" &&
        Number.isInteger(value.id) &&
        value.id >= 0 &&
        value.id < state.board.nodes.length &&
        legal.length > 1 &&
        legal.includes(value.id)
      )
        onDirectionSelect(value.id);
    } catch {}
  }
  return (
    <View
      style={{
        position: "relative",
        borderRadius: 14,
        overflow: "hidden",
        backgroundColor: "#97b9d3",
        height: failed || twoD ? undefined : 360,
      }}
    >
      {failed || twoD ? (
        fallback
      ) : (
        <>
          <WebView
            ref={web}
            source={source}
            originWhitelist={[origin]}
            onMessage={message}
            javaScriptEnabled
            scrollEnabled={false}
            nestedScrollEnabled={false}
            androidLayerType="hardware"
            onError={() => setFailed(true)}
            onHttpError={() => setFailed(true)}
            onRenderProcessGone={() => setFailed(true)}
            onShouldStartLoadWithRequest={(request) =>
              request.url === url || request.url === "about:blank"
            }
            style={{ flex: 1, backgroundColor: "#97b9d3" }}
          />
          {!ready && (
            <Text
              style={{
                position: "absolute",
                top: 16,
                left: 140,
                color: "#36546f",
                fontSize: 11,
              }}
            >
              3D 보드를 준비하고 있어요…
            </Text>
          )}
        </>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={twoD ? "3D 지도로 돌아가기" : "전체 지도"}
        accessibilityState={{ selected: twoD }}
        disabled={failed}
        onPress={() => {
          isReady.current = false;
          setReady(false);
          setTwoD(!twoD);
        }}
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          width: 42,
          height: 42,
          borderRadius: 9,
          borderWidth: 1,
          borderColor: "#effaff99",
          backgroundColor: twoD ? "#ffe09b" : "#203e58dd",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 8,
        }}
      >
        <View
          style={{
            width: 21,
            height: 21,
            borderWidth: 1.8,
            borderRadius: 3,
            borderColor: twoD ? "#172e46" : "#fff4c8",
          }}
        >
          {[6, 12].map((left) => (
            <View
              key={left}
              style={{
                position: "absolute",
                left,
                top: 0,
                bottom: 0,
                width: 1,
                backgroundColor: twoD ? "#172e46" : "#fff4c8",
              }}
            />
          ))}
          <View
            style={{
              position: "absolute",
              left: 1,
              top: 7,
              width: 8,
              height: 1.5,
              backgroundColor: twoD ? "#172e46" : "#fff4c8",
              transform: [{ rotate: "30deg" }],
            }}
          />
          <View
            style={{
              position: "absolute",
              right: 1,
              bottom: 5,
              width: 8,
              height: 1.5,
              backgroundColor: twoD ? "#172e46" : "#fff4c8",
            }}
          />
        </View>
      </Pressable>
    </View>
  );
}
