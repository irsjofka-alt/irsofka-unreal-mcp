"""IRSofka Unreal Engine MCP — sisi stasiun dari jembatan Unreal Engine 5.8.

Arsitektur yang diikat operator 2026-10-15 15:02 dan 15:26: penerima utama adalah plugin
`IRSofkaStationCore` di dalam engine. Berkas ini adalah pihak yang memanggilnya lewat TCP
127.0.0.1:9877. Kalau plugin tidak terdeteksi, plugin tetap bekerja sebagai plugin normal dan
alat-alat di bawah menjawab `status: UNAVAILABLE` beserta sebabnya — bukan sukses palsu, bukan
pula kegagalan misterius.

Repo ini berdiri sendiri karena perintah langsung pemilik proyek (15 Okt 15:26): satu repo stasiun
menjadi beberapa — IRSofka Blender MCP, IRSofka ComfyUI MCP, IRSofka Unreal Engine MCP —
semuanya berlisensi BSL 1.1 di bawah PT IRSofka Data Teknologi.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import os

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    user_site = Path.home() / ".local/lib/python3.12/site-packages"
    if user_site.exists() and str(user_site) not in sys.path:
        sys.path.insert(0, str(user_site))
    from mcp.server.fastmcp import FastMCP

from bridge import execute_atomic_pipeline, send_to_engine, station_status

mcp = FastMCP("irsofka-unreal-mcp")


@mcp.tool()
def ue_station_status() -> str:
    """Keadaan jembatan SEKARANG — ditanyakan ke plugin, bukan disimpulkan dari socket.

    `mode` menjawab dengan tiga kata yang berbeda:
      * `station_bridge`      plugin hidup dan tahu terpasang ke ai-station (keadaan gabungan),
      * `standalone_listener` plugin hidup tapi binanya belum memuat `core.presence` —
                              jembatan bisa dipakai, tetapi keputusannya bukan dari plugin,
      * `no_receiver`         tidak ada yang menyahut: editor tertutup atau plugin tidak termuat.
    `detected` (bool) tetap ada untuk pemanggil lama; `station_root`, `evidence` dan `reported_by`
    hanya terisi pada keadaan pertama.
    """
    return json.dumps(station_status(), indent=2)


@mcp.tool()
def ue_world(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: World, Scene Hierarchy & Actors.
    Actions:
      - 'spawn': Spawns actor in level (params: actor_class, location, rotation, actor_label)
      - 'bulk_spawn': Spawns multiple actors in batch (params: requests: list)
      - 'duplicate': Clones existing actor with offset (params: source_label, new_label, offset)
      - 'set_transform': Updates location, rotation, or scale (params: actor_label, location, rotation, scale)
      - 'get_transform': Reads world coordinates (params: actor_label)
      - 'attach': Parents one actor to another (params: child_label, parent_label)
      - 'delete': Destroys actor in level (params: actor_label)
      - 'get_all_actors': Queries scene actors (params: class_filter)
      - 'select_actors': Highlights actors in editor viewport (params: actor_labels: list)
      - 'set_lighting': Adjust light intensity & color (params: actor_label, intensity, color)
      - 'set_physics': Toggles simulate physics (params: actor_label, simulate_physics)
      - 'set_visibility': Toggles actor visibility in editor/game (params: actor_label, visible)
      - 'set_folder': Organizes actor in World Outliner folder (params: actor_label, folder_path)
      - 'set_tags': Appends gameplay/editor tags (params: actor_label, tags: list)
      - 'set_material': Assigns material to mesh slot or ALandscape (params: actor_label, material_path, slot_index)
      - 'level_streaming': Manages streaming levels (params: streaming_action: 'get_levels')
      - 'open_level': Loads .umap level directly (params: level_path)
      - 'create_level': Creates new level and saves it (params: level_path, template_path, save_existing)
      - 'save_level': Saves current or specified level (params: level_path)
      - 'get_current_level': Returns active level package name & actor count
      - 'delete_pattern': Bulk deletes actors by wildcard pattern or folder (params: pattern, folder_path)
      - 'exec_cmd': Executes UE console command (params: command)
      - 'exec_python': Executes Python code or script (params: code, file_path, mode)
    """
    return json.dumps(send_to_engine("world", action, params or {}), indent=2)


@mcp.tool()
def ue_blueprint(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Blueprint Graph Authoring & Safe Compilation.
    Features intelligent Auto-Pin Resolver (fuzzy pin matching without case errors).
    Actions:
      - 'create': Creates new Blueprint asset (params: package_path, parent_class)
      - 'add_variable': Adds member variable (params: blueprint_path, variable_name, variable_type: 'bool'|'int'|'float'|'string')
      - 'add_function': Adds function graph (params: blueprint_path, function_name)
      - 'add_call_function': Drops K2Node_CallFunction node into graph (params: blueprint_path, target_class, function_name, pos_x, pos_y)
      - 'connect_pins': Connects node pins with fuzzy resolver (params: blueprint_path, source_pin, target_pin)
      - 'set_pin_default': Configures default pin literal value (params: blueprint_path, pin_name, default_value)
      - 'compile': Triggers safe GameThread compilation with error diagnostics (params: blueprint_path)
      - 'get_summary': Reflects variables and graphs on blueprint (params: blueprint_path)
    """
    return json.dumps(send_to_engine("blueprint", action, params or {}), indent=2)


@mcp.tool()
def ue_material(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Shaders, Materials & Instances.
    Actions:
      - 'create_material': Creates base UMaterial (params: package_path)
      - 'create_instance': Instantiates dynamic MaterialInstanceConstant (params: parent_material, instance_path)
      - 'set_parameter': Sets scalar or vector shader parameter (params: material_path, parameter_name, scalar_value, vector_value)
      - 'set_texture': Sets 2D texture parameter (params: material_path, parameter_name, texture_path)
      - 'set_static_switch': Toggles static boolean switch parameter (params: material_path, parameter_name, switch_value)
      - 'get_parameters': Reflects all scalar, vector, and texture parameter names (params: material_path)
    """
    return json.dumps(send_to_engine("material", action, params or {}), indent=2)


@mcp.tool()
def ue_media(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Audio, SoundWaves, Niagara Visual Effects & Sequencer.
    Actions:
      - 'import_sound': Imports WAV file into USoundWave asset (params: destination_path)
      - 'bind_sound': Binds SoundWave to Actor AudioComponent (params: actor_label, sound_path)
      - 'play_sound': Plays one-shot sound at world coordinates (params: sound_path, location)
      - 'spawn_niagara': Spawns Niagara particle system in level (params: niagara_path, location)
      - 'set_niagara_parameter': Sets float/vec3 user parameter on Niagara component (params: actor_label, parameter_name, float_value, vec3_value)
      - 'create_sequence': Creates Level Sequence cinematic asset (params: package_path)
    """
    return json.dumps(send_to_engine("media", action, params or {}), indent=2)


@mcp.tool()
def ue_importer(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Asset Ingestion & Batch File Importer.
    Solves Linux Wayland drag-and-drop & dialog constraints by directly invoking native factories.
    Actions:
      - 'import_mesh': Imports single FBX to UStaticMesh (params: source_file, destination_path, combine_meshes)
      - 'import_mesh_batch': Imports all FBX from folder (params: source_folder, destination_folder, combine_meshes)
      - 'import_texture': Imports single PNG/TGA to UTexture2D (params: source_file, destination_path, srgb)
      - 'import_texture_batch': Imports all textures from folder (params: source_folder, destination_folder)
    """
    return json.dumps(send_to_engine("importer", action, params or {}), indent=2)


@mcp.tool()
def ue_landscape(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Landscape & Terrain Ingestion.
    Directly spawns and configures native ALandscape in active UMap level from 16-bit heightmaps.
    Actions:
      - 'import_heightmap': Ingests 16-bit heightmap (params: heightmap_path, location, scale, actor_label)
    """
    return json.dumps(send_to_engine("landscape", action, params or {}), indent=2)


@mcp.tool()
def ue_vision(action: str, params: Dict[str, Any] = None) -> str:
    """
    Master Domain Tool: Viewport Multimodal Eyes for AI Visual Verification.
    Directly reads active viewport pixels and writes directly to disk for low-token, zero-drop visual verification.
    Actions:
      - 'capture': Captures active viewport frame to disk image file (params: output_path)
      - 'frame': Moves viewport camera to frame specified actor (params: actor_label)
      - 'set_camera': Moves editor viewport camera (params: location: [X,Y,Z], rotation: [Pitch,Yaw,Roll], fov: float)
      - 'get_camera': Returns current viewport camera location, rotation, and FOV
    """
    import base64
    import shutil

    result = send_to_engine("vision", action, params or {})

    # Auto-sync captured image to Antigravity artifact directory so MEDIA viewer renders it immediately
    if action in ("capture", "capture_viewport") and result.get("status") == "SUCCESS":
        # 1. Check if engine saved directly to file
        img_path = result.get("image_path")
        
        # 2. Backward compatibility: if engine returned base64_png
        if not img_path and "base64_png" in result:
            b64_data = result.pop("base64_png")
            station_home = Path(os.environ.get("AI_STATION_HOME", Path.home() / ".ai-station"))
            fallback_dir = station_home / "logs"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_file = fallback_dir / "ue_viewport.png"
            fallback_file.write_bytes(base64.b64decode(b64_data))
            img_path = str(fallback_file)
            result["image_path"] = img_path

        # 3. Mirror into active Antigravity Brain artifact directory
        if img_path and Path(img_path).exists():
            brain_dir = station_home / "engines" / "antigravity-cli" / "brain"
            if brain_dir.exists():
                active_dirs = [d for d in brain_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
                if active_dirs:
                    latest_brain = max(active_dirs, key=lambda d: d.stat().st_mtime)
                    artifact_dest = latest_brain / "ue_viewport.png"
                    try:
                        shutil.copyfile(img_path, artifact_dest)
                        result["artifact_url"] = f"file://{artifact_dest}"
                    except Exception as e:
                        result["artifact_error"] = str(e)

    return json.dumps(result, indent=2)


@mcp.tool()
def ue_pipeline(steps: List[Dict[str, Any]]) -> str:
    """
    Atomic Macro-Action Pipeline.
    Executes an array of domain steps sequentially with Partial Success reporting.
    Addresses macro fragility: preserves prior successful actions if an intermediate step fails.
    """
    return json.dumps(execute_atomic_pipeline(steps), indent=2)


@mcp.tool()
def ue_cmd(command: str) -> str:
    """
    Direct GameThread execution of Unreal Engine Console Commands (CMD).
    Eliminates fragile mouse-click automation to the editor command bar.
    Examples:
      - 'stat fps'
      - 'stat unit'
      - 'r.RayTracing 0'
      - 'viewmode unlit'
      - 'QUIT_EDITOR'
    """
    return json.dumps(send_to_engine("cmd", "exec_cmd", {"command": command}), indent=2)


@mcp.tool()
def ue_python(code: str = "", file_path: str = "", mode: str = "file") -> str:
    """
    Direct GameThread execution of Python scripts and interactive REPL inside Unreal Engine 5.8.
    Captures stdout/stderr, execution results, and errors without mouse clicks.
    
    Args:
      code: Python code string or one-liner.
      file_path: Absolute path to a .py script to execute.
      mode: 'file' (execute multi-line or file), 'statement'/'repl' (interactive single statement), 'eval' (evaluate expression).
    """
    params = {"mode": mode}
    if code:
        params["code"] = code
    if file_path:
        params["file_path"] = file_path
    return json.dumps(send_to_engine("python", "exec_python", params), indent=2)


@mcp.tool()
def ue_level(action: str, level_path: str = "", template_path: str = "", save_existing: bool = True) -> str:
    """
    Level Management: Create, Open, Save, and Inspect Unreal Engine Levels (.umap) directly.
    
    Actions:
      - 'open' / 'load': Loads an existing map (e.g., '/Game/Genesis/Maps/Zones/M_SangkanPurwa').
      - 'create' / 'new': Creates a new blank level or from template and saves it (params: level_path, template_path, save_existing).
      - 'save': Saves the current level or specified level path (params: level_path).
      - 'get_current' / 'status': Returns the package name and actor count of the currently active editor level.
    """
    params = {"action": action}
    if level_path:
        params["level_path"] = level_path
    if template_path:
        params["template_path"] = template_path
    params["save_existing"] = save_existing
    return json.dumps(send_to_engine("level", action, params), indent=2)


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        # Satu cara menanyakan "apakah server ini berperilaku" ke keempat repo MCP:
        # `server.py --selftest`. Bukti dijalankan lewat modul tes, tanpa engine dan tanpa jaringan
        # nyata, supaya gerbang bisa diukur jam tiga pagi ketika editor tutup.
        import runpy
        code = 0
        try:
            runpy.run_path(str(Path(__file__).resolve().parent / "tests" / "test_bridge.py"),
                           run_name="__main__")
        except SystemExit as exc:  # modul tes menutup dirinya dengan angka, dan angka itu yang dipakai
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        sys.exit(code)
    mcp.run()
