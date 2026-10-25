# IRSofka Unreal Engine MCP

Station-side MCP bridge for the **IRSofkaStationCore** Unreal Engine 5.8 plugin.

Licenced under the **Business Source License 1.1** by **PT IRSofka Data Teknologi**
(NIB (OSS) 1258 0003 4132 6 · D&B DUNS 5645 3618 4 · admin@irsofka.co.id · irsofka.co.id).
"Unreal Engine" is a trademark of Epic Games and is used here descriptively: no Epic code is
contained in this repository — the transport is ours, written against our own plugin.

## Why this repository exists

The project owner's instruction of 2026-10-15 15:26:
one ai-station repository becomes three — **IRSofka Blender MCP**, **IRSofka ComfyUI MCP**,
**IRSofka Unreal Engine MCP** — because the Unreal bridge "will be changed completely and adapted",
and a repository that is going to be rewritten must be able to carry its own version, licence and
tests.

## Architecture: the plugin is the receiver, the station is the caller

Stated by the project owner on 2026-10-15 15:02, implemented as two measurable states:

| condition | behaviour |
|---|---|
| plugin listener present on `127.0.0.1:9877` | the bridge is live: domain calls are executed on Unreal's GameThread by `IRSofkaStationCore` and results come back as one JSON line |
| plugin **not** detected | the plugin does what a normal plugin does — nothing is broken, nothing is simulated. Every MCP tool answers `status: UNAVAILABLE` with the reason, and `ue_station_status()` says `detected: false` |

`ue_station_status()` measures rather than remembers: it opens the socket now, so "engine not
started", "plugin not loaded" and "bridge alive" remain three different facts in the log instead of
collapsing into one word for failure.

```
AI engine (Qoder / Antigravity)
        │  MCP over stdio — 12 tools total:
        │  • Diagnostic: ue_station_status
        │  • 6 Master Domains: ue_world, ue_blueprint, ue_material, ue_media, ue_vision, ue_pipeline
        │  • Extended Native Automation: ue_importer, ue_landscape, ue_cmd, ue_python, ue_level
        ▼
server.py ──► bridge.py ── TCP 127.0.0.1:9877, one JSON line per call ──► IRSofkaStationCore (C++)
                                                                              └─ GameThread task runner,
                                                                                 transaction rollback
```

## Tools & Verification Status

| Tool | Category | Status | Notes |
|---|---|---|---|
| `ue_station_status` | Diagnostics | **Verified** | Socket probe verifies offline/online listener states (10/10 test_bridge) |
| `ue_world` | Master Domain | **Verified** | Spawning, transforms, folder hierarchy, actor deletion, level streaming |
| `ue_cmd` | Automation | **Verified** | Direct console command execution on GameThread |
| `ue_python` | Automation | **Verified** | Python execution & REPL on GameThread |
| `ue_level` | Management | **Verified** | Level create, open, save, and inspector |
| `ue_vision` | Master Domain | **Verified** | Viewport capture to disk / artifact folder and camera framing |
| `ue_pipeline` | Master Domain | **Verified** | Multi-step transaction pipeline with Partial Success isolation |
| `ue_blueprint` | Master Domain | **Compiled / Bridge Tested** | Node graph & fuzzy pin connection; pending live editor deep test |
| `ue_material` | Master Domain | **Compiled / Bridge Tested** | Parameter assignment & inspection; pending live editor deep test |
| `ue_media` | Master Domain | **Compiled / Bridge Tested** | Sound & Niagara trigger; pending live editor deep test |
| `ue_importer` | Automation | **Compiled / Bridge Tested** | Batch FBX & PNG/TGA ingestion avoiding Wayland dialogs |
| `ue_landscape` | Automation | **Compiled / Bridge Tested** | Native ALandscape 16-bit heightmap ingestion |

## Roadmap: Addressing Tooling Gaps (Glama Analysis)

The following capabilities are tracked for upcoming releases:
1. **Blueprint Authoring**: Dynamic component additions and custom event graph node generation.
2. **Material Graph**: Material graph expression node creation/deletion beyond parameter assignment.
3. **Sequencer**: Track and keyframe automation for cinematic Level Sequences.

## Files

| file | owns |
|---|---|
| `server.py` | the published MCP surface (tools + docstrings the engines display) |
| `bridge.py` | the transport: framing, `station_status`, atomic pipeline with Partial Success |
| `tests/test_bridge.py` | the two-state proof, against a simulated listener on a free port — 10/10, no engine required |

## Install

```jsonc
{
  "mcpServers": {
    "irsofka-unreal-mcp": {
      "command": "python3",
      "args": ["$HOME/Apps/mcp/irsofka-unreal-mcp/server.py"]
    }
  }
}
```

Requires Python ≥ 3.10 and the `mcp` package. The plugin itself is installed separately as
`Engine/Plugins/Marketplace/IRSofkaStationCore`; its source repository is the private
`IRSofka-UE-AIStation-Core` repository, and the plugin directory is a
**build artefact**, not the source.

## What is not finished here — stated, not implied

1. **The plugin holds the two states; a given editor may not have that build yet.**
   `FIRSofkaStationPresence` lives in the plugin's source (`Source/IRSofkaCore/`) and is compiled by
   `RunUAT BuildPlugin` from that repository. Loading it into a running editor means a module rebuild
   or Live Coding in somebody's live session, which is that person's call, not a run's. Until an
   editor has the new binary, `ue_station_status()` reports `standalone_listener` — the receiver is
   alive but does not yet decide its own state. That is a measured fact about the installed build, not
   a failure of this server.
2. **The engine-side transform defects have code, not a live measurement.** A bare class name is no
   longer silently replaced by `AActor`, and `set_transform` now answers the transform that actually
   landed, inside a transaction. Both changes compile; proving them needs an editor listening on
   9877 and a mutating round trip, so until that run exists this claim is "compiled", not "measured".
3. **No remote is configured.** Publication shape and timing belong to the project owner; creating a
   repository is outward-facing and does not happen as a side effect of a task.

