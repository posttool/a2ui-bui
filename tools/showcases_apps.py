# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Non-Blender showcases: creative tools, apps, dashboards, ops."""

import math

from showcase_lib import P, SEP, Surface, T, ev, M


def render_farm():
  b = Surface()
  job_row = b("Row", id="job_row", children=[
      b.label(P("name"), icon=P("icon"), weight=2.2),
      b("ProgressBar", value=P("progress"), text=P("status"), weight=3),
      b.label(P("node"), color="muted", size="small", weight=1),
      b("IconButton", icon="PAUSE", action=ev("job_pause", job=P("id")), description="Pause job"),
      b("IconButton", icon="X", action=ev("job_cancel", job=P("id")), description="Cancel job"),
  ], spacing="small")
  queue = b.panel("Queue", b("Column", children=T(job_row, "/jobs"), spacing="small"), icon="SEQUENCE")
  node_box = b("Box", id="node_box", children=[
      b.row(b.label(P("name"), icon="SERVER", bold=True), b("Spacer"), b.label(P("state"), color=P("color"), size="small")),
      b("ProgressBar", value=P("cpu"), text=P("cpu_text")),
      b.label(P("gpu"), size="small", color="muted"),
  ])
  workers = b.panel("Workers", b("Grid", columns=3, children=T(node_box, "/nodes")), icon="NETWORK_DRIVE")
  hist = b("ListView", items=P("/history"), rows=6, selected=P("/history_sel"), filter=True,
           action=ev("job_inspect", index=P("/history_sel")))
  preview = b("Video", src="assets/render_preview.mp4", poster="assets/render_poster.png", controls=True, loop=True,
              autoplay=True, height=10, fit="cover", action=ev("preview_ended"))
  submit = b("Popover", text="Submit Job", icon="ADD", children=[
      b.prop("Blend file", b("PathField", value="//shots/sh040_lighting.blend", action=ev("browse_blend"))),
      b.prop("Frames", b.row(b("NumberField", label="Start", value=1001, integer=True),
                             b("NumberField", label="End", value=1120, integer=True), align=True)),
      b.prop("Priority", b("NumberSlider", value=50, min=0, max=100, precision=0)),
      b.prop("Pool", b("Dropdown", value="gpu-a100", items=["gpu-a100", "gpu-l4", "cpu-highmem"])),
      b("Button", text="Submit", icon="EXPORT", depress=True, action=ev("job_submit")),
  ])
  header = b.row(b.label("Render farm", size="title", icon="RENDER_ANIMATION"), b("Spacer"),
                 b.label(P("/summary"), color="muted"),
                 b("Toggle", label="Pause queue", value=P("/paused"), icon="PAUSE",
                   action=ev("queue_pause", paused=P("/paused"))),
                 submit)
  top = b.row(b.col(b.label("Latest frame — sh040_lighting", color="muted", size="small"), preview, weight=3),
              b.col(b.label("Finished jobs", color="muted", size="small"), hist, weight=2), spacing="large")
  b.col(header, top, queue, workers, id="root", spacing="normal")

  def jobs(p):
    return [
        {"id": "j812", "name": "sh040_lighting", "icon": "RENDER_ANIMATION", "progress": min(1, 0.42 + p), "node": "a100-03",
         "status": f"Frame {1001 + int(119 * min(1, 0.42 + p))}/1120"},
        {"id": "j813", "name": "sh050_fx_smoke", "icon": "MOD_FLUIDSIM", "progress": min(1, 0.1 + p * 1.5), "node": "a100-01",
         "status": "Simulating cache" if p < 0.4 else "Rendering"},
        {"id": "j814", "name": "asset_turntables", "icon": "OUTLINER_OB_CAMERA", "progress": p * 0.8, "node": "l4-07",
         "status": "Queued" if p == 0 else f"{int(p * 80)}%"},
        {"id": "j815", "name": "comp_final_v12", "icon": "NODE_EDITOR", "progress": 0, "node": "—", "status": "Waiting on sh040"},
    ]
  nodes = [{"name": f"a100-0{i}", "state": "Rendering" if i != 2 else "Idle", "color": "green" if i != 2 else "muted",
            "cpu": c, "cpu_text": f"CPU {int(c * 100)}%", "gpu": g} for i, c, g in
           ((1, 0.92, "2× A100 · 71 °C"), (2, 0.04, "2× A100 · 38 °C"), (3, 0.88, "2× A100 · 69 °C"))]
  b.data({"paused": False, "summary": "4 jobs · 3 workers", "jobs": jobs(0), "nodes": nodes, "history_sel": 0,
          "history": [{"label": "sh030_layout", "icon": "CHECKMARK", "description": "Done 08:14 · 1h 12m"},
                      {"label": "sh020_lighting", "icon": "CHECKMARK", "description": "Done 06:52 · 3h 40m"},
                      {"label": "sh010_fx", "icon": "ERROR", "description": "Failed: out of VRAM on frame 1043"},
                      {"label": "char_lookdev_v4", "icon": "CHECKMARK", "description": "Done yesterday"},
                      {"label": "env_forest_bake", "icon": "CHECKMARK", "description": "Done yesterday"}]})
  for p in (0.1, 0.25, 0.45):
    b.data(jobs(p), path="/jobs")
  return {"name": "Render farm monitor", "window": "Render Farm — studio queue", "width": 1100,
          "description": "Farm dashboard: a looping Video preview of the latest frame, a filterable ListView of finished "
                         "jobs, queue rows templated from /jobs with per-job ProgressBars that later updateDataModel "
                         "messages advance, a Grid of worker Boxes and a Submit Job popover.",
          "messages": b.messages()}


def synth_patch():
  b = Surface()
  def knob(label, path, lo, hi, suffix="", prec=2):
    return b("NumberSlider", label=label, value=P(path), min=lo, max=hi, suffix=suffix, precision=prec)
  osc1 = b("Node", key="osc1", title="Oscillator A", kind="input", location=[20, 30], width=7,
           inputs=[{"name": "Pitch", "type": "float", "value": 0}, {"name": "Detune", "type": "float", "value": -7}],
           outputs=[{"name": "Audio", "type": "shader"}])
  osc2 = b("Node", key="osc2", title="Oscillator B", kind="input", location=[20, 210], width=7,
           inputs=[{"name": "Pitch", "type": "float", "value": 12}, {"name": "Detune", "type": "float", "value": 7}],
           outputs=[{"name": "Audio", "type": "shader"}])
  lfo = b("Node", key="lfo", title="LFO", kind="input", location=[220, 330], width=6,
          inputs=[{"name": "Rate", "type": "float", "value": 0.8}, {"name": "Depth", "type": "float", "value": 0.4}],
          outputs=[{"name": "Value", "type": "float"}])
  mix = b("Node", key="mix", title="Mixer", kind="converter", location=[240, 90], width=6,
          inputs=[{"name": "A", "type": "shader"}, {"name": "B", "type": "shader"}, {"name": "Balance", "type": "float", "value": 0.5}],
          outputs=[{"name": "Audio", "type": "shader"}])
  flt = b("Node", key="filter", title="Ladder Filter", kind="filter", location=[440, 70], width=7,
          inputs=[{"name": "Audio", "type": "shader"}, {"name": "Cutoff", "type": "float", "value": 1800},
                  {"name": "Resonance", "type": "float", "value": 0.35}, {"name": "Mod", "type": "float"}],
          outputs=[{"name": "Audio", "type": "shader"}])
  env = b("Node", key="env", title="ADSR Envelope", kind="converter", location=[440, 290], width=7,
          inputs=[{"name": "Gate", "type": "float"}, {"name": "Attack", "type": "float", "value": 0.01},
                  {"name": "Release", "type": "float", "value": 0.6}],
          outputs=[{"name": "Env", "type": "float"}])
  vca = b("Node", key="vca", title="VCA", kind="converter", location=[650, 110], width=5,
          inputs=[{"name": "Audio", "type": "shader"}, {"name": "Gain", "type": "float"}],
          outputs=[{"name": "Audio", "type": "shader"}])
  rev = b("Node", key="reverb", title="Plate Reverb", kind="filter", location=[820, 60], width=6,
          inputs=[{"name": "Audio", "type": "shader"}, {"name": "Mix", "type": "float", "value": 0.25},
                  {"name": "Decay", "type": "float", "value": 2.4}],
          outputs=[{"name": "Audio", "type": "shader"}])
  out = b("Node", key="out", title="Audio Out", kind="output", location=[1000, 120], width=5,
          inputs=[{"name": "Left", "type": "shader"}, {"name": "Right", "type": "shader"}], outputs=[])
  editor = b("NodeEditor", children=[osc1, osc2, lfo, mix, flt, env, vca, rev, out], links=P("/links"), height=21,
             action=ev("patch_changed", links=P("/links")))
  wave = b("EnumRow", value=P("/osc/wave"), items=["Sine", "Triangle", "Saw", "Square", "Noise"],
           action=ev("osc_wave", wave=P("/osc/wave")))
  osc_p = b.panel("Oscillator A", wave, b.col(knob("Detune", "/osc/detune", -50, 50, " ct", 0),
                                              knob("Pulse Width", "/osc/pw", 0.05, 0.95), knob("Level", "/osc/level", 0, 1),
                                              align=True), icon="WAVE")
  flt_p = b.panel("Filter", b("Dropdown", value=P("/filter/type"), items=["Low Pass 24 dB", "Low Pass 12 dB", "Band Pass", "High Pass"]),
                  b.col(knob("Cutoff", "/filter/cutoff", 20, 20000, " Hz", 0), knob("Resonance", "/filter/res", 0, 1),
                        knob("Env Amount", "/filter/env", -1, 1), align=True), icon="MOD_SMOOTH")
  env_p = b.panel("Envelope", b("Grid", columns=2, align=True, children=[
                      knob("Attack", "/env/a", 0, 2, " s"), knob("Decay", "/env/d", 0, 2, " s"),
                      knob("Sustain", "/env/s", 0, 1), knob("Release", "/env/r", 0, 4, " s")]),
                  b("CurveMapping", curves=P("/env/curve"), height=4), icon="IPO_EASE_IN_OUT")
  spec = b.panel("Spectrum", b("Histogram", bins=P("/spectrum"), mode="bars", height=5,
                               labels=["20", "", "", "", "", "", "", "1k", "", "", "", "", "", "", "20k"]),
                 b.row(b("NumberField", label="BPM", value=P("/bpm"), integer=True, min=40, max=240),
                       b("Toggle", label="Hold", value=False, icon="PINNED")),
                 b("Button", text="Play note", icon="PLAY_SOUND", action=ev("note_on", note="C3", bpm=P("/bpm"))),
                 icon="SEQ_HISTOGRAM")
  presets = b("IDSelector", items=["Warm Pad", "Acid Bass", "Glass Bells", "Init"], value="Acid Bass", icon="FILE_SOUND",
              users=1, fakeUser=True, action=ev("preset", op="select"))
  b.col(b.row(presets, b("Spacer"), b("Dropdown", value="MIDI In: Keystep", items=["MIDI In: Keystep", "MIDI In: All", "None"])),
        editor, b("Grid", columns=4, children=[osc_p, flt_p, env_p, spec]), id="root", spacing="normal")
  b.data({
      "links": [{"from": "osc1", "out": 0, "to": "mix", "in": 0}, {"from": "osc2", "out": 0, "to": "mix", "in": 1},
                {"from": "mix", "out": 0, "to": "filter", "in": 0}, {"from": "lfo", "out": 0, "to": "filter", "in": 3},
                {"from": "filter", "out": 0, "to": "vca", "in": 0}, {"from": "env", "out": 0, "to": "vca", "in": 1},
                {"from": "vca", "out": 0, "to": "reverb", "in": 0}, {"from": "reverb", "out": 0, "to": "out", "in": 0},
                {"from": "reverb", "out": 0, "to": "out", "in": 1}],
      "osc": {"wave": "Saw", "detune": -7, "pw": 0.5, "level": 0.8},
      "filter": {"type": "Low Pass 24 dB", "cutoff": 1800, "res": 0.35, "env": 0.6},
      "env": {"a": 0.01, "d": 0.3, "s": 0.55, "r": 0.6,
              "curve": [{"name": "Env", "color": "#e8a33b", "points": [[0, 0], [0.05, 1], [0.3, 0.55], [0.75, 0.55], [1, 0]]}]},
      "spectrum": [0.2, 0.45, 0.8, 0.95, 0.85, 0.7, 0.62, 0.5, 0.42, 0.35, 0.28, 0.2, 0.14, 0.08, 0.04],
      "bpm": 124,
  })
  return {"name": "Synth patch", "window": "Modular Synth — Acid Bass", "width": 1200,
          "description": "Not Blender: a modular synth patch as a NodeEditor (oscillators, filter, envelope, VCA, reverb) "
                         "with links bound to /links, NumberSlider knobs, a waveform EnumRow, an envelope CurveMapping "
                         "and a spectrum Histogram.",
          "messages": b.messages()}


def weather_dashboard():
  b = Surface()
  stat = b("Box", id="stat_box", children=[
      b.label(P("title"), icon=P("icon"), color="muted", size="small"),
      b.label(P("value"), size="title", bold=True),
      b.label(P("note"), color=P("tone"), size="small"),
  ])
  temps = [11.2, 10.8, 10.5, 10.3, 10.6, 11.4, 12.9, 14.2, 15.6, 16.8, 17.4, 18.1, 18.6, 18.4, 17.9, 17.2, 16.1, 15.0,
           13.9, 13.1, 12.6, 12.1, 11.8, 11.5]
  rain = [0, 0, 0, 0.1, 0.4, 0.8, 1.2, 0.6, 0.2, 0, 0, 0, 0, 0, 0, 0.1, 0.3, 0.9, 1.6, 2.1, 1.4, 0.7, 0.2, 0]
  hours = [f"{h:02d}" if h % 3 == 0 else "" for h in range(24)]
  today = b.col(
      b.panel("Temperature (°C)", b("Histogram", bins=P("/hourly/temp"), mode="bars", height=6, labels=hours), icon="THERMOMETER"),
      b.panel("Precipitation (mm)", b("Histogram", bins=P("/hourly/rain"), mode="bars", height=3, labels=hours), icon="RAIN"),
      spacing="small")
  week = b("ListView", items=P("/week"), rows=7, selected=0, action=ev("day_select"))
  radar = b.col(b("Image", src="assets/radar.svg", height=13, fit="contain", alt="Precipitation radar"),
                b.row(b("NumberSlider", label="Opacity", value=0.8, min=0, max=1, weight=1),
                      b("Toggle", label="Animate", value=False, icon="PLAY")))
  tabs = b("Tabs", current=P("/ui/tab"), tabs=[{"title": "Today", "icon": "CLOCK", "child": today},
                                                {"title": "7 days", "icon": "CALENDAR", "child": week},
                                                {"title": "Radar", "icon": "MAP", "child": radar}])
  header = b.row(b.col(b.label(P("/station/name"), size="title", bold=True),
                       b.label(P("/station/updated"), color="muted", size="small"), spacing="none"),
                 b("Spacer"),
                 b("EnumRow", value=P("/units"), items=["°C", "°F"], action=ev("units", units=P("/units"))),
                 b("Dropdown", value=P("/station/id"), items=["KSFO — San Francisco", "KOAK — Oakland", "KSJC — San José"],
                   icons=["PIN", "PIN", "PIN"], action=ev("station", id=P("/station/id"))),
                 b("IconButton", icon="FILE_REFRESH", emboss=True, action=ev("refresh"), description="Refresh now"))
  alerts = b.panel("Alerts", b.label(P("/alert"), icon="WARNING", color="yellow"), icon="INFO", collapsed=False)
  b.col(header, b("Grid", columns=4, children=T(stat, "/stats")), alerts, tabs, id="root", spacing="normal")
  b.data({
      "units": "°C", "ui": {"tab": 0},
      "station": {"id": "KSFO — San Francisco", "name": "San Francisco Intl.", "updated": "Updated 10:42 · METAR"},
      "stats": [
          {"title": "Temperature", "icon": "THERMOMETER", "value": "17.4 °C", "note": "+1.2 since 06:00", "tone": "green"},
          {"title": "Wind", "icon": "WIND", "value": "18 km/h", "note": "WNW, gusts 31", "tone": "muted"},
          {"title": "Humidity", "icon": "HUMIDITY", "value": "72 %", "note": "Dew point 12.2 °C", "tone": "muted"},
          {"title": "Rain (24 h)", "icon": "RAIN", "value": "10.6 mm", "note": "Heavy band from 18:00", "tone": "orange"},
      ],
      "alert": "Small craft advisory until 21:00 — west winds 20–30 kt.",
      "hourly": {"temp": temps, "rain": rain},
      "week": [{"label": f"{d} — {hi}° / {lo}°", "icon": ic, "description": desc} for d, hi, lo, ic, desc in (
          ("Mon", 18, 11, "SUN", "Sunny"), ("Tue", 17, 12, "CLOUD", "Overcast"), ("Wed", 15, 11, "RAIN", "Showers, 8 mm"),
          ("Thu", 14, 10, "RAIN", "Rain, 14 mm"), ("Fri", 16, 10, "CLOUD", "Clearing"), ("Sat", 19, 11, "SUN", "Sunny"),
          ("Sun", 21, 12, "SUN", "Warm"))],
  })
  b.data({"title": "Temperature", "icon": "THERMOMETER", "value": "17.9 °C", "note": "+1.7 since 06:00", "tone": "green"},
         path="/stats/0")
  return {"name": "Weather station", "window": "Weather — KSFO", "width": 980,
          "description": "Not Blender: a weather dashboard with a templated Grid of stat Boxes (Label sizes and colors), "
                         "hourly temperature and rain Histograms in bars mode with axis labels, a week ListView and a "
                         "radar Image, switched with Tabs.",
          "messages": b.messages()}


def smart_home():
  b = Surface()
  room = b("Box", id="room_box", children=[
      b.row(b.label(P("name"), icon=P("icon"), bold=True), b("Spacer"),
            b("Toggle", value=P("on"), icon="PLUG", action=ev("light_power", room=P("id"), on=P("on")),
              description="Lights on/off")),
      b("NumberSlider", label="Brightness", value=P("level"), min=0, max=100, suffix="%", precision=0,
        enabled=P("on"), action=ev("light_level", room=P("id"), level=P("level"))),
      b.prop("Color", b("ColorSwatch", value=P("color"), picker="circle", action=ev("light_color", room=P("id"), color=P("color"))),
             factor=0.35),
  ])
  rooms = b.panel("Lights", b("Grid", columns=3, children=T(room, "/rooms")), icon="LIGHT")
  climate = b.panel(
      "Climate",
      b("EnumRow", value=P("/climate/mode"), items=["Heat", "Cool", "Auto", "Off"],
        icons=["FIRE", "SNOW", "TIME_CLOCK", "CANCEL"], action=ev("climate_mode", mode=P("/climate/mode"))),
      b.prop("Target", b("NumberField", value=P("/climate/target"), min=10, max=30, step=0.5, precision=1, suffix=" °C",
                         action=ev("climate_target", target=P("/climate/target")))),
      b.prop("Fan", b("NumberSlider", value=P("/climate/fan"), min=0, max=5, precision=0)),
      b.prop("", b("Checkbox", label="Eco schedule", value=P("/climate/eco"))),
      b.prop("Now", b.label(P("/climate/now"), icon="THERMOMETER")),
      icon="THERMOMETER")
  cam_row = b("Row", id="cam_row", children=[
      b("Toggle", value=P("live"), icon="HIDE_ON", iconOn="HIDE_OFF", emboss=False, description="Camera privacy",
        action=ev("camera_privacy", camera=P("name"), live=P("live"))),
      b.label(P("name"), icon="CAMERA", weight=1),
      b.label(P("status"), color="muted", size="small"),
  ])
  security = b.panel("Security",
                     b.prop("Alarm", b("Dropdown", value=P("/security/alarm"), items=["Disarmed", "Home", "Away"],
                                       icons=["UNLOCKED", "HOUSE", "LOCKED"])),
                     b("Column", children=T(cam_row, "/cameras"), spacing="small"),
                     icon="SHIELD")
  scenes = b.panel("Scenes", b.row(*[b("Button", text=t, icon=i, action=ev("scene_activate", scene=t)) for t, i in
                                    (("Morning", "SUN"), ("Movie", "TV"), ("Dinner", "KITCHEN"), ("Night", "MOON"))]),
                   b("Button", text="All off", icon="CANCEL", alert=True, action=ev("all_off")), icon="WORKSPACE")
  energy = b.panel("Energy today", b("ProgressBar", value=P("/energy/frac"), text=P("/energy/text")),
                   b.label("Solar covered 64% of usage.", color="green", size="small"), icon="BOLT")
  b.col(rooms, b.row(b.col(climate, energy, weight=1, spacing="small"), b.col(security, scenes, weight=1, spacing="small")),
        id="root", spacing="small")
  b.data({
      "rooms": [{"id": "living", "name": "Living room", "icon": "SOFA", "on": True, "level": 70, "color": [1, 0.8, 0.55, 1]},
                {"id": "kitchen", "name": "Kitchen", "icon": "KITCHEN", "on": True, "level": 100, "color": [1, 1, 0.95, 1]},
                {"id": "bed", "name": "Bedroom", "icon": "BED", "on": False, "level": 30, "color": [1, 0.55, 0.3, 1]},
                {"id": "office", "name": "Office", "icon": "DESKTOP", "on": True, "level": 85, "color": [0.8, 0.9, 1, 1]},
                {"id": "hall", "name": "Hallway", "icon": "DOOR", "on": False, "level": 50, "color": [1, 0.9, 0.7, 1]},
                {"id": "garden", "name": "Garden", "icon": "LEAF", "on": True, "level": 40, "color": [0.45, 0.6, 1, 1]}],
      "climate": {"mode": "Auto", "target": 21.5, "fan": 2, "eco": True, "now": "Indoor 20.8 °C · 46 % RH"},
      "security": {"alarm": "Home"},
      "cameras": [{"name": "Front door", "live": True, "status": "Motion 2 min ago"},
                  {"name": "Garage", "live": True, "status": "Idle"},
                  {"name": "Nursery", "live": False, "status": "Privacy on"}],
      "energy": {"frac": 0.46, "text": "9.2 of 20 kWh"},
  })
  return {"name": "Smart home", "window": "Home — Overview", "width": 1000,
          "description": "Not Blender: a Grid of room Boxes templated from /rooms (power Toggle, brightness NumberSlider "
                         "disabled while off, color wheel), climate controls, camera rows with eye Toggles "
                         "(emboss off, HIDE_ON / HIDE_OFF) and scene Buttons.",
          "messages": b.messages()}


def cicd_pipeline():
  b = Surface()
  stage = b("Node", id="stage_tpl", key=P("key"), title=P("title"), kind=P("kind"), location=P("loc"), width=6.5,
            inputs=P("inputs"), outputs=P("outputs"), collapsed=P("collapsed"))
  dag = b("NodeEditor", children=T(stage, "/stages"), links=P("/links"), height=15)
  commits = b("ListView", items=P("/commits"), rows=6, selected=P("/commit_sel"), filter=True,
              action=ev("commit_select", index=P("/commit_sel")))
  step_row = b("Row", id="step_row", children=[
      b.label(P("name"), icon=P("icon"), weight=2),
      b("ProgressBar", value=P("progress"), text=P("text"), weight=3),
  ], spacing="small")
  log = b("TextArea", value=P("/log"), rows=9, monospace=True, label="Job log")
  b.col(
      b.row(b.label("ci / monorepo", size="title", icon="BRANCH"),
            b("Dropdown", value=P("/branch"), items=["main", "release/4.3", "feat/node-links"], icons=["BRANCH", "BRANCH", "BRANCH"]),
            b("Spacer"),
            b.label(P("/run"), color="muted"),
            b("Button", text="Re-run", icon="FILE_REFRESH", action=ev("pipeline_rerun", branch=P("/branch"))),
            b("Button", text="Cancel", icon="CANCEL", alert=True, action=ev("pipeline_cancel"))),
      b("ProgressBar", value=P("/overall"), text=P("/overall_text")),
      dag,
      b.row(b.panel("Commits", commits, icon="COMMIT", weight=2),
            b.panel("Steps", b("Column", children=T(step_row, "/steps"), spacing="small"), icon="TASK", weight=3),
            spacing="normal"),
      b.panel("Log", log, collapsed=False, icon="CONSOLE"),
      id="root", spacing="normal")

  def stg(key, title, kind, loc, ins, outs, collapsed=False):
    return {"key": key, "title": title, "kind": kind, "loc": loc, "collapsed": collapsed,
            "inputs": [{"name": n, "type": t} for n, t in ins], "outputs": [{"name": n, "type": t} for n, t in outs]}
  stages = [
      stg("src", "Checkout", "input", [20, 110], [], [("Source", "geometry")]),
      stg("lint", "Lint", "script", [200, 10], [("Source", "geometry")], [("OK", "float")]),
      stg("bl", "Build linux-x64", "converter", [200, 120], [("Source", "geometry")], [("Artifacts", "geometry")]),
      stg("bm", "Build macos-arm64", "converter", [200, 230], [("Source", "geometry")], [("Artifacts", "geometry")]),
      stg("ut", "Unit tests", "script", [400, 70], [("Artifacts", "geometry"), ("Lint", "float")], [("Report", "float")]),
      stg("it", "Integration tests", "script", [400, 210], [("Artifacts", "geometry"), ("Artifacts", "geometry")],
          [("Report", "float")]),
      stg("pkg", "Package", "group", [600, 130], [("Unit", "float"), ("Integration", "float")], [("Bundle", "geometry")]),
      stg("stg", "Deploy staging", "output", [780, 70], [("Bundle", "geometry")], [("Health", "float")]),
      stg("prd", "Deploy production", "output", [960, 150], [("Bundle", "geometry"), ("Approval", "float")], [], collapsed=False),
  ]
  links = [{"from": "src", "out": 0, "to": "lint", "in": 0}, {"from": "src", "out": 0, "to": "bl", "in": 0},
           {"from": "src", "out": 0, "to": "bm", "in": 0}, {"from": "bl", "out": 0, "to": "ut", "in": 0},
           {"from": "lint", "out": 0, "to": "ut", "in": 1}, {"from": "bl", "out": 0, "to": "it", "in": 0},
           {"from": "bm", "out": 0, "to": "it", "in": 1}, {"from": "ut", "out": 0, "to": "pkg", "in": 0},
           {"from": "it", "out": 0, "to": "pkg", "in": 1}, {"from": "pkg", "out": 0, "to": "stg", "in": 0},
           {"from": "pkg", "out": 0, "to": "prd", "in": 0}, {"from": "stg", "out": 0, "to": "prd", "in": 1}]

  def steps(p):
    def s(name, icon, start, dur):
      v = max(0, min(1, (p - start) / dur))
      return {"name": name, "icon": "CHECKMARK" if v >= 1 else icon, "progress": v,
              "text": "Passed" if v >= 1 else ("Running" if v > 0 else "Pending")}
    return [s("Lint", "FILE_SCRIPT", 0, 0.1), s("Build linux-x64", "SYSTEM", 0, 0.35), s("Build macos-arm64", "SYSTEM", 0, 0.45),
            s("Unit tests", "BUG", 0.35, 0.25), s("Integration tests", "BUG", 0.45, 0.35), s("Package", "FILE_ARCHIVE", 0.8, 0.1),
            s("Deploy staging", "ROCKET", 0.9, 0.1)]
  log_lines = ["$ bazel build //... --config=ci", "INFO: Analyzed 1,284 targets (412 packages loaded).",
               "INFO: Found 1,284 targets...", "[812 / 2,031] Compiling src/node_links.cc; 4s remote-cache",
               "[1,544 / 2,031] Linking bin/editor; 12s remote", "INFO: Build completed successfully, 2,031 total actions",
               "$ ctest --output-on-failure -j 32", "100% tests passed, 0 tests failed out of 486"]
  b.data({"branch": "main", "run": "Run #4821 · 3 min ago by @maya", "overall": 0.2, "overall_text": "Building (2/9)",
          "stages": stages, "links": links, "steps": steps(0.2), "commit_sel": 0, "log": "\n".join(log_lines[:4]),
          "commits": [{"label": "Fix socket hit-testing in node links", "icon": "COMMIT", "description": "a91f3c2 · maya"},
                      {"label": "Add ColorRamp B-Spline interpolation", "icon": "COMMIT", "description": "77e01ad · jun"},
                      {"label": "Bump vendored A2UI to v1.0", "icon": "COMMIT", "description": "c03b9e1 · priya"},
                      {"label": "Light theme tokens for menus", "icon": "COMMIT", "description": "5d2e4fa · sam"},
                      {"label": "Merge branch 'feat/pie-menu'", "icon": "BRANCH", "description": "e18aa07 · maya"}]})
  for p, txt, n in ((0.55, "Testing (5/9)", 6), (0.92, "Deploying staging (8/9)", 8)):
    b.data(steps(p), path="/steps")
    b.data(p, path="/overall")
    b.data(txt, path="/overall_text")
    b.data("\n".join(log_lines[:n]), path="/log")
  return {"name": "CI/CD pipeline", "window": "Pipeline — main #4821", "width": 1200,
          "description": "Not Blender: a build pipeline DAG drawn with NodeEditor (checkout → build → test → package → "
                         "deploy, templated from /stages), a commit ListView, step rows with ProgressBars, a monospace log "
                         "and streamed updates as stages finish.",
          "messages": b.messages()}


def drone_mission():
  b = Surface()
  wp = b("Box", id="wp_box", children=[
      b.row(b.label(P("name"), icon="PIN", bold=True), b("Spacer"),
            b("Dropdown", value=P("action"), items=["Fly through", "Hover", "Take photo", "Survey grid", "Land"],
              icons=["ROUTE", "TIMER", "CAMERA", "MOD_LATTICE", "DRONE"]),
            b("IconButton", icon="X", action=ev("waypoint_remove", name=P("name")))),
      b("VectorField", label="Position", value=P("pos"), axes="ENU", suffix=" m", precision=1,
        action=ev("waypoint_move", name=P("name"), pos=P("pos"))),
      b.row(b("NumberField", label="Speed", value=P("speed"), suffix=" m/s", min=0, max=20, precision=1),
            b("NumberField", label="Hold", value=P("hold"), suffix=" s", min=0, precision=0, integer=True), align=True),
  ], align=False)
  wp_list = b("ScrollView", child=b("Column", children=T(wp, "/waypoints"), spacing="small"), rows=16)
  left = b.col(
      b("Image", src="assets/mission_map.svg", height=13, fit="cover", alt="Mission map"),
      b.row(b("ListView", items=P("/drones"), icons=["DRONE", "DRONE", "DRONE"], rows=3, selected=P("/drone_sel"),
              weight=1, action=ev("drone_select", index=P("/drone_sel"))),
            b.col(b.label("Battery", color="muted", size="small"), b("ProgressBar", value=P("/battery"), text=P("/battery_text")),
                  b.label("Est. flight 14 min · 3.2 km", size="small"), weight=1, spacing="small")),
      weight=3, spacing="small")
  gimbal = b.panel("Gimbal",
                   b.row(b("NormalBall", value=P("/gimbal/dir"), size=4.5, action=ev("gimbal_aim", dir=P("/gimbal/dir"))),
                         b.col(b("NumberSlider", label="Zoom", value=P("/gimbal/zoom"), min=1, max=8, suffix="×", precision=1),
                               b("EnumRow", value="Photo", items=["Photo", "Video", "Thermal"]),
                               b("Checkbox", label="Lock to target", value=True), weight=1, spacing="small")),
                   icon="CAMERA")
  mission = b.panel("Mission",
                    b.prop("Name", b("TextField", value=P("/name"), icon="FLAG")),
                    b.prop("Max altitude", b("NumberField", value=P("/max_alt"), suffix=" m", min=10, max=120, integer=True)),
                    b.prop("On low battery", b("Dropdown", value="Return home", items=["Return home", "Land", "Hover"])),
                    b.prop("", b("Checkbox", label="Avoid obstacles", value=True)),
                    b.prop("", b("Checkbox", label="Geofence", value=True)),
                    icon="ROUTE")
  right = b.col(mission, gimbal, b.panel("Waypoints", wp_list, icon="PIN"),
                b.row(b("Button", text="Add waypoint", icon="ADD", action=ev("waypoint_add")),
                      b("Button", text="Upload & arm", icon="EXPORT", depress=True,
                        action=ev("mission_upload", name=P("/name"), waypoints=P("/waypoints")))),
                weight=2.4, spacing="small")
  b.row(left, right, id="root", spacing="large")
  b.data({"name": "Orchard survey — block C", "max_alt": 60, "drone_sel": 0,
          "drones": [{"label": "Kestrel-2", "description": "Ready · 97%"}, {"label": "Kestrel-4", "description": "Charging · 41%"},
                     {"label": "Osprey-1", "description": "Maintenance"}],
          "battery": 0.97, "battery_text": "97 % · 25.1 V",
          "gimbal": {"dir": [0.2, -0.45, 0.87], "zoom": 2.0},
          "waypoints": [{"name": "WP 1", "pos": [-120.0, 85.0, 40.0], "speed": 8, "hold": 0, "action": "Fly through"},
                        {"name": "WP 2", "pos": [-40.0, 140.0, 45.0], "speed": 6, "hold": 5, "action": "Take photo"},
                        {"name": "WP 3", "pos": [80.0, 150.0, 45.0], "speed": 4, "hold": 0, "action": "Survey grid"},
                        {"name": "WP 4", "pos": [150.0, 60.0, 50.0], "speed": 8, "hold": 10, "action": "Hover"},
                        {"name": "WP 5", "pos": [90.0, -40.0, 30.0], "speed": 5, "hold": 0, "action": "Take photo"},
                        {"name": "WP 6", "pos": [0.0, 0.0, 0.0], "speed": 3, "hold": 0, "action": "Land"}]})
  return {"name": "Drone mission planner", "window": "Mission Planner", "width": 1150,
          "description": "Not Blender: waypoints templated from /waypoints inside a ScrollView (VectorField with custom "
                         "ENU axes, speed and hold fields, action Dropdown with icons), a NormalBall gimbal, a drone "
                         "ListView with battery ProgressBar and a mission map Image.",
          "messages": b.messages()}


def character_creator():
  b = Surface()
  stat = lambda l, p: b("NumberSlider", label=l, value=P(p), min=1, max=20, precision=0,
                        action=ev("stat_change", stat=l, value=P(p)))
  emotes = b("PieMenu", title="Emotes", hotkey="E", text="Emote", icon="PERSON", value=P("/emote"),
             items=[{"label": "Wave", "icon": "HAND"}, {"label": "Cheer", "icon": "STAR"}, {"label": "Bow", "icon": "PERSON"},
                    {"label": "Dance", "icon": "PLAY_SOUND"}, {"label": "Laugh", "icon": "CHAT"}, {"label": "Salute", "icon": "FLAG"},
                    {"label": "Shrug", "icon": "QUESTION"}, {"label": "Taunt", "icon": "SWORD"}],
             action=ev("emote", emote=P("/emote")), description="Hold E over the window for the emote pie")
  cls = b("EnumRow", value=P("/hero/class"), items=["Warrior", "Ranger", "Mage", "Rogue"],
          icons=["SWORD", "ROUTE", "POTION", "MOON"], action=ev("class_pick", cls=P("/hero/class")))
  looks = b.panel("Appearance",
                  b.prop("Skin", b("ColorSwatch", value=P("/hero/skin"), picker="square")),
                  b.prop("Hair", b("ColorSwatch", value=P("/hero/hair"), picker="circle")),
                  b.prop("Eyes", b("ColorSwatch", value=P("/hero/eyes"))),
                  b.prop("Hairstyle", b("Dropdown", value=P("/hero/hairstyle"), items=["Short crop", "Braids", "Mohawk", "Long waves", "Bald"])),
                  b.prop("Height", b("NumberSlider", value=P("/hero/height"), min=140, max=210, suffix=" cm", precision=0)),
                  b.prop("Build", b("NumberSlider", value=P("/hero/build"), min=0, max=1, precision=2)),
                  icon="PERSON")
  stats = b.panel("Attributes",
                  b.col(stat("Strength", "/hero/str"), stat("Agility", "/hero/agi"), stat("Intellect", "/hero/int"),
                        stat("Charisma", "/hero/cha"), align=True),
                  b.row(b.label(P("/hero/points_text"), color="accent"), b("Spacer"),
                        b("Button", text="Reset", icon="LOOP_BACK", action=ev("stats_reset"))),
                  icon="CHART")
  bio = b.panel("Backstory", b("TextArea", value=P("/hero/bio"), rows=4), collapsed=True, icon="TEXT")
  left = b.col(b("Image", src="assets/portrait.svg", height=16, fit="contain", alt="Character portrait"),
               b.row(emotes, b("Spacer"), b("Toggle", label="Show gear", value=True, icon="SHIELD")),
               weight=2, spacing="small")
  right = b.col(
      b.row(b("TextField", value=P("/hero/name"), placeholder="Character name", icon="PERSON", weight=1),
            b("IDSelector", items=["Custom", "Ironclad", "Wildheart", "Starweaver"], value=P("/preset"), icon="PRESET",
              action=ev("preset", op="select", preset=P("/preset")))),
      cls, looks, stats, bio,
      b.row(b("Button", text="Randomize", icon="FILE_REFRESH", action=ev("randomize")), b("Spacer"),
            b("Button", text="Create character", icon="CHECKMARK", depress=True,
              action=ev("character_create", name=P("/hero/name"), cls=P("/hero/class"), stats={"str": P("/hero/str"),
                                                                                                 "agi": P("/hero/agi"),
                                                                                                 "int": P("/hero/int"),
                                                                                                 "cha": P("/hero/cha")}))),
      weight=3, spacing="small")
  b.row(left, right, id="root", spacing="large")
  b.data({"preset": "Starweaver", "emote": "",
          "hero": {"name": "Ilsa Vantor", "class": "Mage", "skin": [0.79, 0.56, 0.42, 1], "hair": [0.23, 0.16, 0.12, 1],
                   "eyes": "#2f6f4f", "hairstyle": "Long waves", "height": 172, "build": 0.4,
                   "str": 8, "agi": 12, "int": 18, "cha": 14, "points_text": "4 points left",
                   "bio": "Raised in the observatory of Hollowmere, Ilsa reads the stars for omens nobody else can see."}})
  return {"name": "Character creator", "window": "New Character", "width": 960,
          "description": "Not Blender: a game character creator with a class EnumRow (icons), square and circle color "
                         "pickers, attribute NumberSliders, a preset IDSelector and an emote PieMenu on the E key.",
          "messages": b.messages()}


def photo_editor():
  b = Surface()
  def sl(label, path, lo, hi, prec=2, suffix=""):
    return b("NumberSlider", label=label, value=P(path), min=lo, max=hi, precision=prec, suffix=suffix,
             action=ev("adjust", param=label, value=P(path)))
  luma = [round(0.1 + 0.9 * math.exp(-((i / 64 - 0.38) ** 2) / 0.02) + 0.5 * math.exp(-((i / 64 - 0.8) ** 2) / 0.004), 3)
          for i in range(64)]
  basic = b.panel("Light",
                  b.col(sl("Exposure", "/adj/exposure", -5, 5, 2, " EV"), sl("Contrast", "/adj/contrast", -100, 100, 0),
                        align=True),
                  b.col(sl("Highlights", "/adj/highlights", -100, 100, 0), sl("Shadows", "/adj/shadows", -100, 100, 0),
                        sl("Whites", "/adj/whites", -100, 100, 0), sl("Blacks", "/adj/blacks", -100, 100, 0), align=True),
                  icon="LIGHT_SUN")
  curve = b.panel("Tone Curve", b("CurveMapping", curves=P("/curves"), current=0, height=7), icon="SMOOTHCURVE")
  color = b.panel("Color",
                  b.prop("White Balance", b("Dropdown", value="As Shot", items=["As Shot", "Auto", "Daylight", "Cloudy", "Tungsten", "Custom"])),
                  b.col(sl("Temp", "/adj/temp", 2000, 50000, 0, " K"), sl("Tint", "/adj/tint", -150, 150, 0), align=True),
                  b.col(sl("Vibrance", "/adj/vibrance", -100, 100, 0), sl("Saturation", "/adj/saturation", -100, 100, 0), align=True),
                  icon="COLOR")
  crop = b.panel("Crop & Rotate",
                 b.prop("Aspect", b("Dropdown", value="Original", items=["Original", "1 : 1", "4 : 5", "16 : 9", "3 : 2", "Free"])),
                 b.prop("Angle", b("NumberField", value=0.8, min=-45, max=45, precision=1, suffix="°")),
                 b.prop("", b("Checkbox", label="Constrain to image", value=True)), collapsed=True, icon="FULLSCREEN_ENTER")
  right = b.col(b("Histogram", bins=P("/luma"), mode="luma", height=4),
                b.row(b.label("ISO 200  ·  35 mm  ·  f/8  ·  1/250 s", size="small", color="muted")),
                b("ScrollView", child=b.col(basic, curve, color, crop, spacing="small"), rows=22),
                weight=2, spacing="small")
  left = b.col(
      b.row(b("Toggle", label="Before / after", value=P("/compare"), icon="SPLIT"), b("Spacer"),
            b("IconButton", icon="ZOOM_OUT"), b.label("62%", size="small"), b("IconButton", icon="ZOOM_IN"),
            b("Button", text="Export", icon="EXPORT", action=ev("photo_export", adjustments=P("/adj")))),
      b("Image", src="assets/photo.png", height=20, fit="contain", alt="Lake at sunset"),
      b("ListView", items=["DSC_0412.NEF", "DSC_0413.NEF", "DSC_0414.NEF", "DSC_0415.NEF"],
        icons=["FILE_IMAGE", "FILE_IMAGE", "FILE_IMAGE", "FILE_IMAGE"], rows=2, selected=1),
      weight=3, spacing="small")
  b.row(left, right, id="root", spacing="large")
  b.data({"compare": False, "luma": luma,
          "adj": {"exposure": 0.35, "contrast": 12, "highlights": -40, "shadows": 25, "whites": 8, "blacks": -6,
                  "temp": 5600, "tint": 4, "vibrance": 18, "saturation": -4},
          "curves": [{"name": "Luminance", "color": "#dddddd", "points": [[0, 0.04], [0.25, 0.2], [0.7, 0.78], [1, 0.97]]}]})
  return {"name": "Photo editor", "window": "Develop — DSC_0413.NEF", "width": 1150,
          "description": "Not Blender: a raw photo develop module with a luma Histogram, tone CurveMapping, exposure and "
                         "color NumberSliders in a ScrollView, a filmstrip ListView and a before/after Toggle.",
          "messages": b.messages()}


def task_tracker():
  b = Surface()
  task = b("Row", id="task_row", children=[
      b("Checkbox", label=P("title"), value=P("done"), weight=3,
        action=ev("task_toggle", id=P("id"), done=P("done"))),
      b.label(P("owner"), icon="USER", color="muted", size="small", weight=1),
      b.label(P("due"), color=P("due_tone"), size="small"),
      b("Dropdown", value=P("priority"), iconOnly=True, items=["Low", "Medium", "High", "Urgent"],
        icons=["SORT_DESC", "REMOVE", "SORT_ASC", "WARNING"], description="Priority"),
  ], spacing="small")
  tasks = b("ScrollView", child=b("Column", children=T(task, "/tasks"), spacing="small"), rows=10)
  b.col(
      b.row(b.label("Sprint 42 — Catalog launch", size="title", icon="FLAG", weight=3), b("Spacer"),
            b.label(P("/dates"), color="muted", size="small")),
      b("ProgressBar", value=P("/progress"), text=P("/progress_text")),
      b.row(b("TextField", value=P("/draft"), placeholder="Add a task and press Enter", icon="ADD", weight=4,
              action=ev("task_add", title=P("/draft"))),
            b("Button", text="Add", icon="ADD", action=ev("task_add", title=P("/draft")))),
      b.row(b("Toggle", label="Mine", value=P("/filters/mine"), icon="USER"),
            b("Toggle", label="Overdue", value=P("/filters/overdue"), icon="TIMER"),
            b("Toggle", label="Hide done", value=P("/filters/hide_done"), icon="HIDE_ON"),
            b("Spacer"),
            b("SearchField", value=P("/filters/q"), placeholder="Filter tasks", action=ev("task_filter", q=P("/filters/q")))),
      tasks,
      b.row(b.panel("Milestones", b("ListView", items=P("/milestones"), rows=4), icon="FLAG", weight=1),
            b.panel("Notes", b("TextArea", value=P("/notes"), rows=5), icon="TEXT", weight=1)),
      id="root", spacing="normal")
  t = [("Finish Node socket hit-testing", "maya", "Today", "orange", "High", False),
       ("Light theme pass for menus", "sam", "Tomorrow", "muted", "Medium", False),
       ("Write showcase payloads", "jun", "Done", "green", "Medium", True),
       ("Record demo video", "priya", "Fri", "muted", "Low", False),
       ("Catalog JSON schema export", "maya", "Overdue 2d", "red", "Urgent", False),
       ("Keyboard navigation for PieMenu", "sam", "Mon", "muted", "Medium", False),
       ("Accessibility labels audit", "jun", "Done", "green", "High", True),
       ("Publish catalog to registry", "priya", "Next week", "muted", "Low", False)]
  b.data({"dates": "Nov 4 – Nov 15", "progress": 0.25, "progress_text": "2 of 8 done", "draft": "",
          "filters": {"mine": False, "overdue": False, "hide_done": False, "q": ""},
          "tasks": [{"id": i, "title": a, "owner": o, "due": d, "due_tone": tone, "priority": pr, "done": dn}
                    for i, (a, o, d, tone, pr, dn) in enumerate(t)],
          "milestones": [{"label": "Alpha components", "icon": "CHECKMARK", "description": "Oct 28"},
                         {"label": "All 48 components", "icon": "TIME_CLOCK", "description": "Nov 12"},
                         {"label": "Public demo", "icon": "FLAG", "description": "Nov 15"},
                         {"label": "Catalog v1.1", "icon": "CALENDAR", "description": "Dec"}],
          "notes": "Blockers: NodeEditor link hit-testing at 1.5× scale.\nDemo script lives in the shared doc."})
  return {"name": "Project tracker", "window": "Tasks — Sprint 42", "width": 860,
          "description": "Not Blender: a sprint board with a ScrollView of task rows templated from /tasks (Checkbox "
                         "bound to done, owner and due Labels with semantic colors, icon-only priority Dropdown), filter "
                         "Toggles, a SearchField, milestones and notes.",
          "messages": b.messages()}
