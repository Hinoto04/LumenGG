"use strict";
var CalculatorVisualModel = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // mobile/src/calculator-visual-model.ts
  var calculator_visual_model_exports = {};
  __export(calculator_visual_model_exports, {
    harmonyState: () => harmonyState,
    passiveActive: () => passiveActive,
    passiveArt: () => passiveArt,
    passiveCleanArt: () => passiveCleanArt,
    passiveSymbolArt: () => passiveSymbolArt,
    steppedCounter: () => steppedCounter,
    taoInputLocked: () => taoInputLocked,
    visualAction: () => visualAction,
    visualActive: () => visualActive,
    visualDefinition: () => visualDefinition,
    visualEnabled: () => visualEnabled,
    visualLabel: () => visualLabel,
    visualLayout: () => visualLayout,
    visualPresentation: () => visualPresentation,
    visualTokenPositions: () => visualTokenPositions,
    visualValue: () => visualValue
  });

  // mobile/src/calculator-passives.json
  var calculator_passives_default = {
    setsumei: {
      controls: []
    },
    nia: {
      controls: [
        {
          type: "toggle",
          key: "over_limit",
          label: "\uC624\uBC84 \uB9AC\uBC0B",
          labels: {
            ko: "\uC624\uBC84 \uB9AC\uBC0B",
            en: "Over Limit",
            ja: "\u30AA\u30FC\u30D0\u30FC\u30EA\u30DF\u30C3\u30C8"
          }
        }
      ]
    },
    root: {
      controls: [
        {
          type: "toggle",
          key: "root_charge",
          label: "\uCC28\uC9C0",
          labels: {
            ko: "\uCC28\uC9C0",
            en: "Charge",
            ja: "\u30C1\u30E3\u30FC\u30B8"
          }
        }
      ]
    },
    delphy: {
      controls: [
        {
          type: "toggle",
          key: "down_stance",
          label: "\uB2E4\uC6B4 \uC2A4\uD0E0\uC2A4",
          labels: {
            ko: "\uB2E4\uC6B4 \uC2A4\uD0E0\uC2A4",
            en: "Down Stance",
            ja: "\u30C0\u30A6\u30F3\u30B9\u30BF\u30F3\u30B9"
          }
        },
        {
          type: "counter",
          key: "garage_token",
          label: "\uAC1C\uB7EC\uC9C0 \uD1A0\uD070",
          max: 3,
          unit: "\uC7A5",
          labels: {
            ko: "\uAC1C\uB7EC\uC9C0 \uD1A0\uD070",
            en: "Garage Token",
            ja: "\u30AC\u30EC\u30FC\u30B8\u30C8\u30FC\u30AF\u30F3"
          }
        }
      ]
    },
    keith: {
      controls: [
        {
          type: "toggle",
          key: "notice",
          label: "\uC608\uACE0",
          labels: {
            ko: "\uC608\uACE0",
            en: "Advance Notice",
            ja: "\u4E88\u544A"
          }
        }
      ]
    },
    wolf: {
      controls: [
        {
          type: "counter",
          key: "howling_counter",
          label: "\uD558\uC6B8\uB9C1 \uCE74\uC6B4\uD130",
          max: 5,
          labels: {
            ko: "\uD558\uC6B8\uB9C1 \uCE74\uC6B4\uD130",
            en: "Howling",
            ja: "\u30CF\u30A6\u30EA\u30F3\u30B0"
          }
        },
        {
          type: "thresholdAction",
          key: "pressure",
          label: "\uC704\uC555",
          requires: {
            type: "counterAtLeast",
            key: "howling_counter",
            value: 5
          },
          resetKeys: [
            "howling_counter"
          ],
          resetLabel: "\uD558\uC6B8\uB9C1 \uCE74\uC6B4\uD130",
          labels: {
            ko: "\uC704\uC555",
            en: "Intimidation",
            ja: "\u5A01\u5727"
          }
        }
      ]
    },
    viola: {
      controls: [
        {
          type: "counter",
          key: "silver_counter",
          label: "\uC740\uC5F0 \uCE74\uC6B4\uD130",
          max: 3,
          labels: {
            ko: "\uC740\uC5F0 \uCE74\uC6B4\uD130",
            en: "Hidden Bond",
            ja: "\u96A0\u7E01"
          }
        }
      ]
    },
    tao: {
      controls: [
        {
          type: "counter",
          key: "yang_counter",
          label: "\uC591",
          max: 4,
          labels: {
            ko: "\uC591",
            en: "Yang",
            ja: "\u967D"
          }
        },
        {
          type: "counter",
          key: "yin_counter",
          label: "\uC74C",
          max: 4,
          labels: {
            ko: "\uC74C",
            en: "Yin",
            ja: "\u9670"
          }
        },
        {
          type: "latchedStatus",
          key: "harmony",
          label: "\uC870\uD654",
          activateWhen: {
            type: "allEquals",
            keys: [
              "yang_counter",
              "yin_counter"
            ],
            value: 4
          },
          keepWhile: {
            type: "allAtLeast",
            keys: [
              "yang_counter",
              "yin_counter"
            ],
            value: 3
          },
          labels: {
            ko: "\uC870\uD654",
            en: "Harmony",
            ja: "\u8ABF\u548C"
          }
        },
        {
          type: "choice",
          key: "harmony_effect",
          label: "\uC870\uD654 \uD6A8\uACFC",
          enableWhen: {
            type: "active",
            key: "harmony"
          },
          choices: [
            {
              value: "damage_100",
              label: "+100DMG"
            },
            {
              value: "fp_1",
              label: "+1FP"
            }
          ],
          labels: {
            ko: "\uC870\uD654 \uD6A8\uACFC",
            en: "Harmony effect",
            ja: "\u8ABF\u548C\u52B9\u679C"
          }
        }
      ],
      adapter: "tao"
    },
    rita: {
      controls: [
        {
          type: "toggle",
          key: "light_lumen",
          label: "\uBE5B\uC758 \uB8E8\uBA58",
          labels: {
            ko: "\uBE5B\uC758 \uB8E8\uBA58",
            en: "Light Lumen",
            ja: "\u5149\u306E\u30EB\u30FC\u30E1\u30F3"
          }
        },
        {
          type: "choice",
          key: "rita_role",
          label: "\uB808\uAE30\uC628",
          choices: [
            {
              value: "guardian",
              label: "\uAC00\uB514\uC5B8",
              labels: {
                ko: "\uAC00\uB514\uC5B8",
                en: "Guardian",
                ja: "\u30AC\u30FC\u30C7\u30A3\u30A2\u30F3"
              }
            },
            {
              value: "assassin",
              label: "\uC5B4\uC314\uC2E0",
              labels: {
                ko: "\uC5B4\uC314\uC2E0",
                en: "Assassin",
                ja: "\u30A2\u30B5\u30B7\u30F3"
              }
            },
            {
              value: "paladin",
              label: "\uD314\uB77C\uB518",
              labels: {
                ko: "\uD314\uB77C\uB518",
                en: "Paladin",
                ja: "\u30D1\u30E9\u30C7\u30A3\u30F3"
              }
            }
          ],
          labels: {
            ko: "\uB808\uAE30\uC628",
            en: "Legion",
            ja: "\u30EC\u30AE\u30AA\u30F3"
          }
        }
      ]
    },
    rev: {
      controls: [
        {
          type: "counter",
          key: "dagger_token",
          label: "\uB2E8\uAC80 \uD1A0\uD070",
          max: 6,
          labels: {
            ko: "\uB2E8\uAC80 \uD1A0\uD070",
            en: "Dagger Token",
            ja: "\u77ED\u5263\u30C8\u30FC\u30AF\u30F3"
          }
        },
        {
          type: "toggle",
          key: "dark_night",
          label: "\uC554\uC57C",
          labels: {
            ko: "\uC554\uC57C",
            en: "Dark Night",
            ja: "\u95C7\u591C"
          }
        }
      ]
    },
    rin: {
      controls: [
        {
          type: "counter",
          key: "ember_token",
          label: "\uBD88\uC528 \uD1A0\uD070",
          labels: {
            ko: "\uBD88\uC528 \uD1A0\uD070",
            en: "Ember",
            ja: "\u706B\u7A2E"
          }
        }
      ]
    },
    yohan: {
      controls: [
        {
          type: "counter",
          key: "foresight_counter",
          label: "\uC608\uC9C0 \uCE74\uC6B4\uD130",
          max: 10,
          labels: {
            ko: "\uC608\uC9C0 \uCE74\uC6B4\uD130",
            en: "Foresight",
            ja: "\u4E88\u77E5"
          }
        },
        {
          type: "toggle",
          key: "disaster_one",
          label: "\uB514\uC81C\uC2A4\uD130 \uC6D0",
          labels: {
            ko: "\uB514\uC81C\uC2A4\uD130 \uC6D0",
            en: "Disaster One",
            ja: "\u30C7\u30A3\u30B6\u30B9\u30BF\u30FC\u30FB\u30EF\u30F3"
          }
        }
      ]
    },
    jezebel: {
      controls: [
        {
          type: "counter",
          key: "spider_token",
          label: "\uAC70\uBBF8 \uD1A0\uD070",
          labels: {
            ko: "\uAC70\uBBF8 \uD1A0\uD070",
            en: "Spider Token",
            ja: "\u8718\u86DB\u30C8\u30FC\u30AF\u30F3"
          }
        }
      ]
    },
    iomong: {
      controls: []
    },
    chimera: {
      controls: [
        {
          type: "counter",
          key: "broken_card_count",
          label: "\uBE0C\uB808\uC774\uD06C\uB41C \uCE74\uB4DC \uC218",
          unit: "\uC7A5",
          labels: {
            ko: "\uBE0C\uB808\uC774\uD06C\uB41C \uCE74\uB4DC \uC218",
            en: "Broken card count",
            ja: "\u30D6\u30EC\u30A4\u30AF\u3055\u308C\u305F\u30AB\u30FC\u30C9\u6570"
          }
        }
      ]
    },
    muyeong: {
      controls: [
        {
          type: "status",
          key: "blue_flame",
          label: "\uCCAD\uC5FC",
          condition: {
            type: "hpAtMost",
            value: 2500
          },
          labels: {
            ko: "\uCCAD\uC5FC",
            en: "Blue Flame",
            ja: "\u9752\u708E"
          }
        }
      ]
    },
    finf: {
      controls: [
        {
          type: "toggle",
          key: "zero_suit",
          label: "\uC81C\uB85C \uC288\uD2B8",
          labels: {
            ko: "\uC81C\uB85C \uC288\uD2B8",
            en: "Zero Suit",
            ja: "\u30BC\u30ED\u30B9\u30FC\u30C4"
          }
        }
      ]
    },
    cmyk: {
      controls: [
        {
          type: "counter",
          key: "464",
          label: "\uC7BC \uB370\uC774",
          labels: {
            ko: "\uC7BC \uB370\uC774",
            en: "Jam Day",
            ja: "\u30B8\u30E3\u30E0\u30FB\u30C7\u30A4"
          }
        }
      ]
    },
    minyeong: {
      controls: [
        {
          type: "counter",
          key: "506",
          label: "\uD558\uC774\uD150\uC158",
          labels: {
            ko: "\uD558\uC774\uD150\uC158",
            en: "High Tension",
            ja: "\u30CF\u30A4\u30C6\u30F3\u30B7\u30E7\u30F3"
          }
        }
      ]
    }
  };

  // mobile/src/calculator-passive-art.json
  var calculator_passive_art_default = {
    condenser: {
      file: "viola-token.webp",
      width: 780,
      height: 1063,
      crop: [
        343,
        249,
        99,
        144
      ]
    },
    viola: {
      file: "viola-token.webp",
      width: 780,
      height: 1063,
      crop: [
        67,
        176,
        97,
        103
      ]
    },
    guardian: {
      file: "guardian.webp",
      width: 980,
      height: 1330,
      crop: [
        235,
        310,
        510,
        510
      ]
    },
    assassin: {
      file: "assassin.webp",
      width: 980,
      height: 1330,
      crop: [
        235,
        260,
        510,
        510
      ]
    },
    paladin: {
      file: "paladin.webp",
      width: 980,
      height: 1330,
      crop: [
        235,
        260,
        510,
        510
      ]
    }
  };

  // mobile/src/calculator-passive-visuals.json
  var calculator_passive_visuals_default = {
    setsumei: {
      layout: "seal",
      controls: {}
    },
    nia: {
      layout: "focus",
      controls: {
        over_limit: {
          symbol: "knowledge",
          effect: "orbit"
        }
      }
    },
    root: {
      layout: "core",
      controls: {
        root_charge: {
          symbol: "core",
          effect: "arc"
        }
      }
    },
    delphy: {
      layout: "workshop",
      controls: {
        down_stance: {
          symbol: "stance",
          effect: "arc"
        },
        garage_token: {
          symbol: "gear",
          effect: "spark"
        }
      }
    },
    keith: {
      layout: "calling-card",
      controls: {
        notice: {
          symbol: "notice",
          effect: "light"
        }
      }
    },
    wolf: {
      layout: "howling",
      controls: {
        howling_counter: {
          symbol: "claw",
          effect: "mist"
        },
        pressure: {
          symbol: "pressure",
          effect: "orbit"
        }
      }
    },
    viola: {
      layout: "tokens",
      controls: {
        silver_counter: {
          effect: "light"
        }
      }
    },
    tao: {
      layout: "balance",
      controls: {
        yang_counter: {
          effect: "light"
        },
        yin_counter: {
          effect: "mist"
        },
        harmony: {
          effect: "orbit"
        }
      }
    },
    rita: {
      layout: "legion",
      controls: {
        light_lumen: {
          effect: "light"
        },
        rita_role: {
          effect: "light"
        }
      }
    },
    rev: {
      layout: "dagger-fan",
      controls: {
        dagger_token: {
          symbol: "dagger",
          effect: "mist"
        },
        dark_night: {
          symbol: "veil",
          effect: "mist"
        }
      }
    },
    rin: {
      layout: "furnace",
      controls: {
        ember_token: {
          symbol: "furnace",
          effect: "fire"
        }
      }
    },
    yohan: {
      layout: "foresight",
      controls: {
        foresight_counter: {
          symbol: "foresight_coin",
          effect: "light"
        },
        disaster_one: {
          symbol: "foresight",
          effect: "arc",
          color: "#ff756c"
        }
      }
    },
    jezebel: {
      layout: "web",
      controls: {
        spider_token: {
          symbol: "spider",
          effect: "orbit"
        }
      }
    },
    iomong: {
      layout: "empty",
      controls: {}
    },
    chimera: {
      layout: "fracture",
      controls: {
        broken_card_count: {
          symbol: "fracture",
          effect: "arc"
        }
      }
    },
    muyeong: {
      layout: "blue-flame",
      controls: {
        blue_flame: {
          symbol: "blade",
          effect: "fire"
        }
      }
    },
    finf: {
      layout: "cockpit",
      controls: {
        zero_suit: {
          symbol: "cockpit",
          effect: "arc"
        }
      }
    },
    cmyk: {
      layout: "tracks",
      controls: {
        "464": {
          symbol: "wave",
          effect: "wave"
        }
      }
    },
    minyeong: {
      layout: "wishes",
      controls: {
        "506": {
          symbol: "wish",
          effect: "spark"
        }
      }
    }
  };

  // mobile/src/calculator-symbol-art.json
  var calculator_symbol_art_default = {
    seal: {
      file: "seal-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/seal.png"
    },
    core: {
      file: "core-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/core.png"
    },
    claw: {
      file: "claw-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/claw.png"
    },
    furnace: {
      file: "furnace-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/furnace.png"
    },
    fracture: {
      file: "fracture-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/fracture.png"
    },
    blade: {
      file: "blade-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/blade.png"
    },
    gear: {
      file: "gear-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/gear.png"
    },
    spider: {
      file: "spider-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/spider.png"
    },
    foresight: {
      file: "foresight-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/foresight.png"
    },
    dagger: {
      file: "dagger-painted-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/dagger.png"
    },
    knowledge: {
      file: "knowledge-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST1-PS1.webp",
      crop: [
        165,
        155,
        490,
        440
      ],
      card_code: "ST1-PS1",
      card_name: "\u300C\uC624\uBC84 \uB9AC\uBC0B\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST1-PS1.webp"
    },
    stance: {
      file: "stance-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST3-PS1.webp",
      crop: [
        150,
        170,
        510,
        450
      ],
      card_code: "ST3-PS1",
      card_name: "\u300C\uB2E4\uC6B4 \uC2A4\uD0E0\uC2A4\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST3-PS1.webp"
    },
    notice: {
      file: "notice-cutout-v3.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/notice-v3.png",
      canvas: [
        384,
        512
      ],
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/ST4-PS1.webp",
      card_code: "ST4-PS1",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST4-PS1.webp",
      edit: "Original calling card isolated; obscured corners reconstructed with image_gen."
    },
    pressure: {
      file: "pressure-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST5-PS1.webp",
      crop: [
        215,
        165,
        440,
        400
      ],
      card_code: "ST5-PS1",
      card_name: "\u300C\uC704\uC555\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST5-PS1.webp"
    },
    veil: {
      file: "veil-night-v3.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/veil-v3.png"
    },
    cockpit: {
      file: "cockpit-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/RFS-PS-002.webp",
      crop: [
        160,
        125,
        225,
        200
      ],
      card_code: "RFS-PS-002",
      card_name: "X-05 \uC194\uB2E4\uD2B8",
      source_url: "https://images.hinoto.kr/lumendb/webp/RFS-PS-002.webp"
    },
    wave: {
      file: "wave-group-v3.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/DFR-PS-001.webp",
      crop: [
        94,
        158,
        597,
        529
      ],
      card_code: "DFR-PS-001",
      card_name: "\uC7BC \uB370\uC774",
      source_url: "https://images.hinoto.kr/lumendb/webp/DFR-PS-001.webp",
      fit: "contain"
    },
    wish: {
      file: "wish-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/CB03-PS-001.webp",
      crop: [
        280,
        175,
        260,
        260
      ],
      card_code: "CB03-PS-001",
      card_name: "\uD558\uC774\uD150\uC158",
      source_url: "https://images.hinoto.kr/lumendb/webp/CB03-PS-001.webp"
    },
    foresight_coin: {
      file: "foresight-coin-v3.png",
      kind: "generated",
      source: "artifacts/calculator-character/raster-sources/generated/foresight-coin-v3.png"
    }
  };

  // mobile/src/calculator-clean-icons.json
  var calculator_clean_icons_default = {
    seal: {
      file: "seal-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/seal-v2.png",
      trim_alpha: true
    },
    core: {
      file: "core-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/core-v2.png",
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/UNC-PR-002.webp"
    },
    claw: {
      file: "claw-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/claw-v2.png",
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/UNC-PR-005.webp"
    },
    furnace: {
      file: "furnace-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/furnace-v2.png",
      trim_alpha: true
    },
    fracture: {
      file: "fracture-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/fracture-v2.png",
      trim_alpha: true
    },
    blade: {
      file: "blade-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/blade-v2.png",
      trim_alpha: true
    },
    gear: {
      file: "gear-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/gear-v2.png",
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/UNC-PR-003.webp"
    },
    spider: {
      file: "spider-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/spider-v2.png",
      trim_alpha: true
    },
    foresight: {
      file: "foresight-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/foresight-v2.png",
      trim_alpha: true
    },
    foresight_coin: {
      file: "foresight_coin-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/foresight_coin-v2.png",
      trim_alpha: true
    },
    dagger: {
      file: "dagger-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/dagger-v2.png",
      trim_alpha: true
    },
    knowledge: {
      file: "knowledge-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST1-PS1.webp",
      crop: [
        165,
        155,
        490,
        440
      ],
      card_code: "ST1-PS1",
      card_name: "\u300C\uC624\uBC84 \uB9AC\uBC0B\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST1-PS1.webp",
      fit: "contain"
    },
    stance: {
      file: "stance-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST3-PS1.webp",
      crop: [
        150,
        170,
        510,
        450
      ],
      card_code: "ST3-PS1",
      card_name: "\u300C\uB2E4\uC6B4 \uC2A4\uD0E0\uC2A4\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST3-PS1.webp",
      fit: "contain"
    },
    notice: {
      file: "notice-cutout-v2.png",
      kind: "restored-card",
      source: "artifacts/calculator-character/raster-sources/generated/notice-v3.png",
      canvas: [
        384,
        512
      ],
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/ST4-PS1.webp",
      card_code: "ST4-PS1",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST4-PS1.webp",
      edit: "Original calling card isolated; obscured corners reconstructed with image_gen."
    },
    pressure: {
      file: "pressure-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/ST5-PS1.webp",
      crop: [
        215,
        165,
        440,
        400
      ],
      card_code: "ST5-PS1",
      card_name: "\u300C\uC704\uC555\u300D",
      source_url: "https://images.hinoto.kr/lumendb/webp/ST5-PS1.webp",
      fit: "contain"
    },
    veil: {
      file: "veil-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/veil-v2.png",
      trim_alpha: true
    },
    cockpit: {
      file: "cockpit-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/RFS-PS-002.webp",
      crop: [
        160,
        125,
        225,
        200
      ],
      card_code: "RFS-PS-002",
      card_name: "X-05 \uC194\uB2E4\uD2B8",
      source_url: "https://images.hinoto.kr/lumendb/webp/RFS-PS-002.webp",
      fit: "contain"
    },
    wave: {
      file: "wave-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/DFR-PS-001.webp",
      crop: [
        94,
        158,
        597,
        529
      ],
      card_code: "DFR-PS-001",
      card_name: "\uC7BC \uB370\uC774",
      source_url: "https://images.hinoto.kr/lumendb/webp/DFR-PS-001.webp",
      fit: "contain"
    },
    wish: {
      file: "wish-card-v2.png",
      kind: "card",
      source: "artifacts/calculator-character/raster-sources/cards/CB03-PS-001.webp",
      crop: [
        190,
        198,
        270,
        270
      ],
      card_code: "CB03-PS-001",
      card_name: "\uD558\uC774\uD150\uC158",
      source_url: "https://images.hinoto.kr/lumendb/webp/CB03-PS-001.webp",
      fit: "contain"
    },
    condenser: {
      file: "condenser-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/condenser-v2.png",
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/UNC-PR-004.webp"
    },
    viola: {
      file: "viola-matte-v2.png",
      kind: "generated",
      source: "artifacts/calculator-character/clean-sources/generated/viola-v2.png",
      trim_alpha: true,
      reference_source: "artifacts/calculator-character/raster-sources/cards/UNC-PR-006.webp"
    },
    guardian: {
      file: "guardian-card-v2.png",
      kind: "card",
      source: "LumenGG/static/v2/calculator-character/passives/guardian.webp",
      crop: [
        165,
        380,
        650,
        450
      ],
      fit: "contain",
      card_code: "LMI-AT-056",
      source_url: "https://images.hinoto.kr/lumendb/webp/LMI-AT-056.webp"
    },
    assassin: {
      file: "assassin-card-v2.png",
      kind: "card",
      source: "LumenGG/static/v2/calculator-character/passives/assassin.webp",
      crop: [
        275,
        390,
        430,
        430
      ],
      fit: "contain",
      card_code: "LMI-AT-057",
      source_url: "https://images.hinoto.kr/lumendb/webp/LMI-AT-057.webp"
    },
    paladin: {
      file: "paladin-card-v2.png",
      kind: "card",
      source: "LumenGG/static/v2/calculator-character/passives/paladin.webp",
      crop: [
        245,
        395,
        490,
        460
      ],
      fit: "contain",
      card_code: "LMI-AT-058",
      source_url: "https://images.hinoto.kr/lumendb/webp/LMI-AT-058.webp"
    }
  };

  // mobile/src/calculator-display.ts
  function passiveActive(value) {
    return value === true || value === 1 || value === "true" || value === "on" || value === "ON";
  }
  function nextTaoEffect(current, chosen) {
    return current === chosen ? "" : chosen;
  }

  // mobile/src/core.ts
  function passiveGet(player, key = "", fallback = 0) {
    const entry = player.passive_state[key];
    return entry?.value ?? entry?.count ?? fallback;
  }
  function conditionMet(condition, player) {
    if (!condition) return false;
    if (condition.all) return condition.all.every((c) => conditionMet(c, player));
    if (condition.any) return condition.any.some((c) => conditionMet(c, player));
    const v = passiveGet(player, condition.key);
    switch (condition.type) {
      case "all":
        return (condition.conditions || []).every((c) => conditionMet(c, player));
      case "any":
        return (condition.conditions || []).some((c) => conditionMet(c, player));
      case "hpAtMost":
        return player.hp <= Number(condition.value);
      case "counterAtLeast":
        return Number(v) >= Number(condition.value);
      case "counterAtMost":
        return Number(v) <= Number(condition.value);
      case "active":
      case "truthy":
      case "keyActive":
        return v === true || v === "true" || v === "on" || v === "ON";
      case "equals":
      case "valueEquals":
      case "keyEquals":
        return v === condition.value;
      case "allEquals":
        return (condition.keys || []).every(
          (k) => Number(passiveGet(player, k)) === Number(condition.value)
        );
      case "allAtLeast":
        return (condition.keys || []).every(
          (k) => Number(passiveGet(player, k)) >= Number(condition.value)
        );
      case "not":
        return !conditionMet(condition.conditions?.[0], player);
      default:
        return false;
    }
  }
  function passiveActions(player, definition, target, key, value, label) {
    const action = (k, v, l = k) => ({
      action: "passive",
      target,
      key: k,
      value: v,
      label: l,
      passive_action: "set"
    });
    const actions = [action(key, value, label)];
    const next = {
      ...player,
      passive_state: { ...player.passive_state, [key]: { value } }
    };
    for (const status of definition.latchedStatuses || []) {
      const stored = passiveActive(passiveGet(player, status.key, false));
      const active = conditionMet(status.activateWhen, next);
      const keep = conditionMet(status.keepWhile || status.activateWhen, next);
      if (active && !stored) actions.push(action(status.key, true, status.label));
      else if (stored && !keep)
        actions.push(action(status.key, false, status.label));
    }
    if (definition.adapter === "tao" && ["yang_counter", "yin_counter"].includes(key)) {
      const yang = Number(passiveGet(next, "yang_counter")), yin = Number(passiveGet(next, "yin_counter"));
      const harmony = passiveActive(passiveGet(player, "harmony", false));
      if (yang === 4 && yin === 4 && !harmony)
        actions.push(action("harmony", true, "\uC870\uD654"));
      else if (harmony && (yang < 3 || yin < 3))
        actions.push(
          action("harmony_effect", "", "\uC870\uD654 \uD6A8\uACFC"),
          action("harmony", false, "\uC870\uD654")
        );
    }
    return actions.length === 1 ? actions[0] : { action: "batch", actions };
  }

  // mobile/src/calculator-visual-model.ts
  var passiveArt = calculator_passive_art_default;
  var passiveSymbolArt = calculator_symbol_art_default;
  var passiveCleanArt = calculator_clean_icons_default;
  function visualLayout(theme) {
    return calculator_passive_visuals_default[theme]?.layout || "focus";
  }
  function visualPresentation(theme, key) {
    return calculator_passive_visuals_default[theme]?.controls[key] || {};
  }
  function visualTokenPositions(theme) {
    const sets = {
      wolf: [
        [40, 76, -32],
        [64, 24, -15],
        [160, 24, 15],
        [184, 76, 32],
        [112, 148, 0]
      ],
      rev: [
        [24, 112, -50],
        [68, 68, -30],
        [96, 24, -10],
        [144, 24, 10],
        [172, 68, 30],
        [216, 112, 50]
      ],
      yohan: Array.from({ length: 10 }, (_, i) => [
        24 + 48 * (i % 5),
        i < 5 ? 24 : 152,
        0
      ])
    };
    return sets[theme]?.map(([x, y, rotation]) => ({
      x: x / (theme === "wolf" ? 224 : 240),
      y: y / 176,
      rotation
    })) || null;
  }
  function visualDefinition(theme) {
    return calculator_passives_default[theme] || { controls: [] };
  }
  function visualLabel(control, language) {
    return control.labels?.[language] || control.label;
  }
  function visualValue(player, control) {
    const initial = player.character?.initial_passive_state?.[control.key];
    return passiveGet(player, control.key, initial?.value ?? initial?.count ?? 0);
  }
  function harmonyState(player) {
    const yang = Number(passiveGet(player, "yang_counter"));
    const yin = Number(passiveGet(player, "yin_counter"));
    return yang === 4 && yin === 4 || passiveActive(passiveGet(player, "harmony", false)) && yang >= 3 && yin >= 3;
  }
  function taoInputLocked(player) {
    return harmonyState(player) && !["damage_100", "fp_1"].includes(
      String(passiveGet(player, "harmony_effect", ""))
    );
  }
  function visualActive(player, control) {
    return control.type === "status" ? conditionMet(control.condition, player) : passiveActive(visualValue(player, control));
  }
  function visualEnabled(player, control) {
    return (!control.enableWhen || conditionMet(control.enableWhen, player)) && (control.type !== "thresholdAction" || visualActive(player, control) || conditionMet(
      control.requires || control.activateWhen || control.condition,
      player
    ));
  }
  function steppedCounter(player, control, filled) {
    const current = Math.max(0, Number(visualValue(player, control)) || 0);
    return Math.max(
      0,
      Math.min(control.max ?? 32767, current + (filled ? -1 : 1))
    );
  }
  function visualAction(theme, player, target, key, value, language = "ko") {
    const definition = visualDefinition(theme);
    const control = definition.controls.find((c) => c.key === key);
    if (!control || control.type === "status" || !visualEnabled(player, control) && !(theme === "tao" && key === "harmony_effect" && harmonyState(player)))
      return null;
    if (theme === "tao" && ["yang_counter", "yin_counter"].includes(key) && taoInputLocked(player))
      return null;
    if (control.type === "counter") {
      if (!Number.isFinite(Number(value))) return null;
      value = Math.max(
        0,
        Math.min(control.max ?? 32767, Math.trunc(Number(value)))
      );
    }
    if (theme === "tao" && key === "harmony_effect") {
      if (!harmonyState(player) || !["damage_100", "fp_1"].includes(String(value)))
        return null;
      const chosen = nextTaoEffect(visualValue(player, control), String(value));
      const effect = {
        action: "passive",
        target,
        key,
        value: chosen,
        label: visualLabel(control, language),
        passive_action: "set"
      };
      return passiveActive(passiveGet(player, "harmony", false)) ? effect : {
        action: "batch",
        actions: [
          {
            action: "passive",
            target,
            key: "harmony",
            value: true,
            label: "\uC870\uD654",
            passive_action: "set"
          },
          effect
        ]
      };
    }
    if (control.type === "thresholdAction") {
      const actions = [
        {
          action: "passive",
          target,
          key,
          value,
          label: visualLabel(control, language),
          passive_action: "set"
        }
      ];
      if (value)
        for (const reset of control.resetKeys || [])
          actions.push({
            action: "passive",
            target,
            key: reset,
            value: 0,
            label: reset,
            passive_action: "set"
          });
      return { action: "batch", actions };
    }
    return passiveActions(
      player,
      definition,
      target,
      key,
      value,
      visualLabel(control, language)
    );
  }
  return __toCommonJS(calculator_visual_model_exports);
})();
