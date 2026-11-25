"""Beam Designer: a small Tkinter beam analysis desktop application."""

from __future__ import annotations

import math
import json
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Callable


MIN_SPAN = 4.0
MAX_SPAN = 40.0
COLORS = {
    "ink": "#17283f", "muted": "#64758b", "line": "#dce5ef",
    "canvas": "#f4f7fb", "white": "#ffffff", "navy": "#183657",
    "blue": "#2874c6", "teal": "#0e9488", "green": "#18764d",
    "green_bg": "#e8f6ee", "red": "#b43b40", "red_bg": "#fff0ef",
    "grid": "#e9eef4", "purple": "#7857b5",
}

MATERIALS = {
    "Steel W-shapes": {
        "E": 29000.0, "Fb": 30.0, "id": "steel",
        "sections": {
            "W8x10": {"d": 7.89, "bf": 3.940, "tf": .205, "tw": .170, "Ix": 30.8, "Sx": 7.81, "weight": 10},
            "W10x12": {"d": 9.87, "bf": 3.960, "tf": .210, "tw": .190, "Ix": 53.8, "Sx": 10.9, "weight": 12},
            "W12x26": {"d": 12.22, "bf": 6.490, "tf": .380, "tw": .230, "Ix": 204, "Sx": 33.4, "weight": 26},
            "W14x22": {"d": 13.74, "bf": 5.000, "tf": .335, "tw": .230, "Ix": 199, "Sx": 29.0, "weight": 22},
            "W16x26": {"d": 15.69, "bf": 5.500, "tf": .345, "tw": .250, "Ix": 301, "Sx": 38.4, "weight": 26},
            "W18x35": {"d": 17.70, "bf": 6.000, "tf": .425, "tw": .300, "Ix": 510, "Sx": 57.6, "weight": 35},
            "W21x44": {"d": 20.66, "bf": 6.500, "tf": .450, "tw": .350, "Ix": 843, "Sx": 81.6, "weight": 44},
            "W24x55": {"d": 23.57, "bf": 7.005, "tf": .505, "tw": .395, "Ix": 1350, "Sx": 114, "weight": 55},
        },
    },
    "Douglas Fir-Larch No. 2": {
        "E": 1600.0, "Fb": .900, "id": "lumber",
        "sections": {
            "2x8": {"b": 1.50, "d": 7.25, "Ix": 47.63, "Sx": 13.14},
            "2x10": {"b": 1.50, "d": 9.25, "Ix": 98.93, "Sx": 21.39},
            "2x12": {"b": 1.50, "d": 11.25, "Ix": 177.98, "Sx": 31.64},
        },
    },
}


@dataclass
class Load:
    kind: str
    magnitude: float
    position: float = 0.0
    start: float = 0.0
    end: float = 0.0
    id: int = 0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def peak_abs(function: Callable[[float], float], length: float, breaks: list[float]) -> tuple[float, float]:
    """Find a peak with dense sampling and local golden-section refinement."""
    count = max(1200, math.ceil(length * 12))
    positions = {length * i / count for i in range(count + 1)}
    for point in breaks:
        positions.update((clamp(point, 0, length), clamp(point - .001, 0, length), clamp(point + .001, 0, length)))
    samples = sorted(positions)
    best_x, best_y = 0.0, function(0.0)

    def consider(x: float) -> None:
        nonlocal best_x, best_y
        value = function(x)
        if abs(value) > abs(best_y):
            best_x, best_y = x, value

    for x in samples:
        consider(x)
    ratio = (math.sqrt(5) - 1) / 2
    absolute = lambda x: abs(function(x))
    for i in range(1, len(samples) - 1):
        if absolute(samples[i]) < absolute(samples[i - 1]) or absolute(samples[i]) < absolute(samples[i + 1]):
            continue
        left, right = samples[i - 1], samples[i + 1]
        first, second = right - ratio * (right - left), left + ratio * (right - left)
        for _ in range(48):
            if absolute(first) < absolute(second):
                left, first = first, second
                second = left + ratio * (right - left)
            else:
                right, second = second, first
                first = right - ratio * (right - left)
        consider((left + right) / 2)
    return best_x, best_y


class BeamDesigner:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Beam Designer")
        root.geometry("1450x980")
        root.minsize(1080, 760)
        root.configure(bg=COLORS["canvas"])

        self.support = tk.StringVar(value="Simply supported")
        self.span = tk.DoubleVar(value=20.0)
        self.material = tk.StringVar(value="Steel W-shapes")
        self.section = tk.StringVar(value="W12x26")
        self.limit = tk.IntVar(value=360)
        self.loads = [Load("uniform", 1.0, start=0, end=20, id=1)]
        self.next_load_id = 2
        self.current_file: str | None = None
        self.drag_load: Load | None = None
        self.cursor_ratio: float | None = None
        self.analysis: dict = {}
        self.load_rows: list[tk.Frame] = []
        self._build_style()
        self._build_ui()
        self._refresh()

    def _build_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["canvas"])
        style.configure("Card.TFrame", background=COLORS["white"])
        style.configure("TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=("Helvetica", 10))
        style.configure("Card.TLabel", background=COLORS["white"], foreground=COLORS["ink"], font=("Helvetica", 10))
        style.configure("Muted.TLabel", background=COLORS["white"], foreground=COLORS["muted"], font=("Helvetica", 9))
        style.configure("Title.TLabel", font=("Helvetica", 22, "bold"), foreground=COLORS["navy"], background=COLORS["canvas"])
        style.configure("Section.TLabel", font=("Helvetica", 12, "bold"), foreground=COLORS["navy"], background=COLORS["white"])
        style.configure("Metric.TLabel", font=("Helvetica", 20, "bold"), foreground=COLORS["navy"], background=COLORS["white"])
        style.configure("TButton", padding=(10, 7), font=("Helvetica", 9, "bold"))
        style.configure("Accent.TButton", background=COLORS["blue"], foreground="white")
        style.map("Accent.TButton", background=[("active", "#1f5fa5")])
        style.configure("TCombobox", padding=5)

    def _card(self, parent: tk.Widget, **kwargs) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=14, **kwargs)
        return frame

    def _build_ui(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Save", command=self.save_design, accelerator="⌘S" if self.root.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl+S")
        file_menu.add_command(label="Open…", command=self.open_design, accelerator="⌘O" if self.root.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl+O")
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menubar)
        self.root.bind("<Command-s>", lambda _e: self.save_design())
        self.root.bind("<Command-o>", lambda _e: self.open_design())
        self.root.bind("<Control-s>", lambda _e: self.save_design())
        self.root.bind("<Control-o>", lambda _e: self.open_design())

        self.app_canvas = tk.Canvas(self.root, bg=COLORS["canvas"], highlightthickness=0)
        self.app_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.app_canvas.yview)
        self.app_canvas.configure(yscrollcommand=self.app_scrollbar.set)
        self.app_scrollbar.pack(side="right", fill="y")
        self.app_canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.app_canvas)
        self.content_window = self.app_canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda _e: self.app_canvas.configure(scrollregion=self.app_canvas.bbox("all")))
        self.app_canvas.bind("<Configure>", lambda e: self.app_canvas.itemconfigure(self.content_window, width=e.width))
        header = ttk.Frame(self.content, padding=(24, 18, 24, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Beam Designer", style="Title.TLabel").pack(side="left")
        self.example_label = ttk.Label(header, text="●  Example loaded", foreground=COLORS["green"])
        self.example_label.pack(side="right", anchor="e")

        self.main = ttk.Frame(self.content, padding=(18, 0, 18, 16))
        self.main.pack(fill="both", expand=True)
        self.main.columnconfigure(0, weight=0, minsize=345)
        self.main.columnconfigure(1, weight=1)
        self.main.rowconfigure(0, weight=1)
        self.sidebar = ttk.Frame(self.main, width=345)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.sidebar.grid_propagate(False)
        self.right = ttk.Frame(self.main)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(2, weight=1)
        self.right.rowconfigure(3, weight=1)
        self._build_sidebar()
        self._build_results()
        self._build_beam_canvas()
        self._build_plot_canvases()
        self.root.bind_class("BeamDesignerScroll", "<MouseWheel>", self._on_mousewheel)
        self.root.bind_class("BeamDesignerScroll", "<Button-4>", self._on_mousewheel)
        self.root.bind_class("BeamDesignerScroll", "<Button-5>", self._on_mousewheel)
        self._install_scroll_bindings(self.root)

    def _build_sidebar(self) -> None:
        setup = self._card(self.sidebar)
        setup.pack(fill="x", pady=(0, 10))
        ttk.Label(setup, text="Beam setup", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self._field_label(setup, "Support type")
        support = ttk.Combobox(setup, textvariable=self.support, state="readonly", values=("Simply supported", "Cantilever"))
        support.pack(fill="x", pady=(3, 9))
        support.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        span_head = ttk.Frame(setup, style="Card.TFrame")
        span_head.pack(fill="x")
        ttk.Label(span_head, text="Span", style="Card.TLabel").pack(side="left")
        self.span_entry = ttk.Spinbox(span_head, from_=MIN_SPAN, to=MAX_SPAN, increment=.25, textvariable=self.span, width=8, command=self._on_span)
        self.span_entry.pack(side="right")
        self.span_entry.bind("<Return>", lambda _e: self._on_span())
        self.span_entry.bind("<FocusOut>", lambda _e: self._on_span())
        ttk.Label(span_head, text="ft", style="Card.TLabel").pack(side="right", padx=(0, 6))
        self.span_scale = ttk.Scale(setup, from_=MIN_SPAN, to=MAX_SPAN, variable=self.span, command=lambda _v: self._on_span())
        self.span_scale.pack(fill="x", pady=(5, 8))

        self._field_label(setup, "Material")
        material_box = ttk.Combobox(setup, textvariable=self.material, state="readonly", values=tuple(MATERIALS))
        material_box.pack(fill="x", pady=(3, 8))
        material_box.bind("<<ComboboxSelected>>", self._on_material)
        self._field_label(setup, "Section")
        self.section_box = ttk.Combobox(setup, textvariable=self.section, state="readonly")
        self.section_box.pack(fill="x", pady=(3, 8))
        self.section_box.bind("<<ComboboxSelected>>", lambda _e: self._refresh())
        self.properties_label = ttk.Label(setup, text="", style="Muted.TLabel", justify="left")
        self.properties_label.pack(fill="x", pady=(1, 5))
        self.preview = tk.Canvas(setup, height=145, bg=COLORS["white"], highlightthickness=1, highlightbackground=COLORS["line"])
        self.preview.pack(fill="x", pady=(4, 9))
        limits = ttk.Frame(setup, style="Card.TFrame")
        limits.pack(fill="x")
        ttk.Label(limits, text="Deflection limit", style="Card.TLabel").pack(side="left")
        for value in (240, 360):
            ttk.Radiobutton(limits, text=f"L/{value}", variable=self.limit, value=value, command=self._refresh).pack(side="right", padx=(6, 0))
        self.state_label = ttk.Label(setup, text="", style="Muted.TLabel", wraplength=300)
        self.state_label.pack(anchor="w", pady=(8, 0))

        loads = self._card(self.sidebar)
        loads.pack(fill="both", expand=True)
        head = ttk.Frame(loads, style="Card.TFrame")
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="Loads", style="Section.TLabel").pack(side="left")
        self.load_count = ttk.Label(head, text="", style="Muted.TLabel")
        self.load_count.pack(side="right")
        controls = ttk.Frame(loads, style="Card.TFrame")
        controls.pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Add point load", style="Accent.TButton", command=lambda: self._add_load("point")).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(controls, text="Add uniform load", command=lambda: self._add_load("uniform")).pack(side="left", expand=True, fill="x", padx=(4, 0))
        editor_wrap = ttk.Frame(loads, style="Card.TFrame")
        editor_wrap.pack(fill="both", expand=True)
        self.load_canvas = tk.Canvas(editor_wrap, bg=COLORS["white"], highlightthickness=0)
        load_scroll = ttk.Scrollbar(editor_wrap, orient="vertical", command=self.load_canvas.yview)
        self.load_canvas.configure(yscrollcommand=load_scroll.set)
        self.load_canvas.pack(side="left", fill="both", expand=True)
        load_scroll.pack(side="right", fill="y")
        self.load_editor = ttk.Frame(self.load_canvas, style="Card.TFrame")
        self.load_window = self.load_canvas.create_window((0, 0), window=self.load_editor, anchor="nw")
        self.load_editor.bind("<Configure>", lambda _e: self.load_canvas.configure(scrollregion=self.load_canvas.bbox("all")))
        self.load_canvas.bind("<Configure>", lambda e: self.load_canvas.itemconfigure(self.load_window, width=e.width))
    def _field_label(self, parent: tk.Widget, text: str) -> None:
        ttk.Label(parent, text=text, style="Card.TLabel").pack(anchor="w", pady=(2, 0))

    def _build_results(self) -> None:
        cards = ttk.Frame(self.right)
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            cards.columnconfigure(i, weight=1)
        self.metric_widgets = {}
        specs = [("moment", "MAX MOMENT", "kip-ft"), ("shear", "MAX SHEAR", "kips"), ("stress", "BENDING STRESS", "ksi"), ("deflection", "MAX DEFLECTION", "in")]
        for col, (key, title, unit) in enumerate(specs):
            card = self._card(cards)
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 5 if col < 3 else 0))
            ttk.Label(card, text=title, style="Muted.TLabel").pack(anchor="w")
            value = ttk.Label(card, text="—", style="Metric.TLabel")
            value.pack(anchor="w", pady=(7, 0))
            detail = ttk.Label(card, text="", style="Muted.TLabel")
            detail.pack(anchor="w", pady=(2, 6))
            status = ttk.Label(card, text="", style="Muted.TLabel") if key in ("stress", "deflection") else None
            if status:
                status.pack(anchor="w")
            self.metric_widgets[key] = (value, detail, status)
        self.reaction_label = ttk.Label(self.right, text="", foreground=COLORS["navy"], background=COLORS["canvas"], font=("Helvetica", 10, "bold"))
        self.reaction_label.grid(row=1, column=0, sticky="w", pady=(0, 8), padx=8)

    def _make_canvas(self, parent: tk.Widget, height: int) -> tk.Canvas:
        return tk.Canvas(parent, height=height, bg=COLORS["white"], highlightthickness=1, highlightbackground=COLORS["line"])

    def _build_beam_canvas(self) -> None:
        card = self._card(self.right)
        card.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)
        title = ttk.Frame(card, style="Card.TFrame")
        title.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(title, text="Beam and loading", style="Section.TLabel").pack(side="left")
        self.beam_title = ttk.Label(title, text="", style="Muted.TLabel")
        self.beam_title.pack(side="right")
        self.beam_canvas = self._make_canvas(card, 225)
        self.beam_canvas.grid(row=1, column=0, sticky="nsew")
        self.beam_canvas.bind("<Configure>", lambda _e: self._draw_beam())
        self.beam_canvas.bind("<ButtonPress-1>", self._start_drag)
        self.beam_canvas.bind("<B1-Motion>", self._drag_motion)
        self.beam_canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.beam_canvas.bind("<Motion>", self._update_cursor_from_event)
        self.beam_canvas.bind("<Leave>", self._hide_cursor)

    def _build_plot_canvases(self) -> None:
        row = ttk.Frame(self.right)
        row.grid(row=3, column=0, sticky="nsew")
        for i in range(3):
            row.columnconfigure(i, weight=1)
        self.plots = {}
        for i, (key, title) in enumerate((("shear", "Shear force"), ("moment", "Bending moment"), ("deflection", "Deflection"))):
            card = self._card(row)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 5 if i < 2 else 0))
            ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w", pady=(0, 7))
            canvas = self._make_canvas(card, 200)
            canvas.pack(fill="both", expand=True)
            canvas.bind("<Configure>", lambda _e, name=key: self._draw_plot(name))
            canvas.bind("<Motion>", self._update_cursor_from_event)
            canvas.bind("<Leave>", self._hide_cursor)
            self.plots[key] = canvas

        ttk.Label(self.content, text="ASD · D + L service loads · Self-weight excluded · A pass is not a complete structural design approval", foreground=COLORS["muted"], background=COLORS["canvas"], font=("Helvetica", 9)).pack(anchor="e", padx=24, pady=(0, 10))

    def _on_mousewheel(self, event) -> str:
        """Scroll the load editor under the pointer, or the full app otherwise."""
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        in_load_editor = False
        while widget is not None:
            if widget is self.load_canvas:
                in_load_editor = True
                break
            widget = getattr(widget, "master", None)
        target = self.load_canvas if in_load_editor else self.app_canvas
        number = getattr(event, "num", None)
        if number == 4:
            units = -1
        elif number == 5:
            units = 1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return "break"
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        target.yview_scroll(units, "units")
        return "break"

    def _design_data(self) -> dict:
        loads = []
        for load in self.loads:
            entry = {"type": load.kind, "magnitude": load.magnitude}
            if load.kind == "point":
                entry["position_ft"] = load.position
            else:
                entry["start_ft"] = load.start
                entry["end_ft"] = load.end
            loads.append(entry)
        return {
            "format": "beam-designer",
            "version": 1,
            "beam": {
                "support_type": self.support.get(),
                "span_ft": self.span.get(),
                "material": self.material.get(),
                "section": self.section.get(),
                "deflection_limit": self.limit.get(),
            },
            "loads": loads,
        }

    def save_design(self) -> None:
        path = self.current_file
        if path is None:
            path = filedialog.asksaveasfilename(
                title="Save Beam Design",
                defaultextension=".json",
                filetypes=(("Beam design JSON", "*.json"), ("All files", "*")),
            )
            if not path:
                return
        try:
            with open(path, "w", encoding="utf-8") as design_file:
                json.dump(self._design_data(), design_file, indent=2)
                design_file.write("\n")
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror("Could not save design", str(exc), parent=self.root)
            return
        self.current_file = path
        self.root.title(f"Beam Designer — {path.rsplit('/', 1)[-1]}")

    @staticmethod
    def _finite_number(value, label: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be a number.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number.") from exc
        if not math.isfinite(number):
            raise ValueError(f"{label} must be finite.")
        return number

    def _parse_design(self, data: dict) -> tuple[dict, list[Load]]:
        if not isinstance(data, dict) or data.get("format") != "beam-designer" or data.get("version") != 1:
            raise ValueError("This is not a supported Beam Designer file.")
        beam = data.get("beam")
        if not isinstance(beam, dict):
            raise ValueError("The file is missing beam settings.")
        support = beam.get("support_type")
        if support not in ("Simply supported", "Cantilever"):
            raise ValueError("The support type in this file is not supported.")
        span = self._finite_number(beam.get("span_ft"), "Span")
        if not MIN_SPAN <= span <= MAX_SPAN:
            raise ValueError(f"Span must be between {MIN_SPAN:g} and {MAX_SPAN:g} ft.")
        material_name = beam.get("material")
        if not isinstance(material_name, str) or material_name not in MATERIALS:
            raise ValueError("The material in this file is not supported.")
        section = beam.get("section")
        if not isinstance(section, str) or section not in MATERIALS[material_name]["sections"]:
            raise ValueError("The section does not belong to the selected material.")
        limit_value = self._finite_number(beam.get("deflection_limit"), "Deflection limit")
        if limit_value not in (240, 360):
            raise ValueError("Deflection limit must be L/240 or L/360.")
        limit = int(limit_value)

        saved_loads = data.get("loads")
        if not isinstance(saved_loads, list):
            raise ValueError("The file must contain a loads list.")
        loads = []
        for index, entry in enumerate(saved_loads, start=1):
            if not isinstance(entry, dict):
                raise ValueError(f"Load {index} is invalid.")
            kind = entry.get("type")
            if kind not in ("point", "uniform"):
                raise ValueError(f"Load {index} has an unsupported type.")
            magnitude = self._finite_number(entry.get("magnitude"), f"Load {index} magnitude")
            if magnitude < 0:
                raise ValueError(f"Load {index} magnitude cannot be negative.")
            if kind == "point":
                position = self._finite_number(entry.get("position_ft"), f"Load {index} position")
                if not 0 <= position <= span:
                    raise ValueError(f"Load {index} position must be within the beam span.")
                loads.append(Load(kind, magnitude, position=position, id=index))
            else:
                start = self._finite_number(entry.get("start_ft"), f"Load {index} start")
                end = self._finite_number(entry.get("end_ft"), f"Load {index} end")
                if not 0 <= start <= end <= span:
                    raise ValueError(f"Load {index} start and end must be within the beam span and ordered.")
                loads.append(Load(kind, magnitude, start=start, end=end, id=index))
        return {
            "support": support,
            "span": span,
            "material": material_name,
            "section": section,
            "limit": limit,
        }, loads

    def open_design(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Beam Design",
            filetypes=(("Beam design JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as design_file:
                settings, loads = self._parse_design(json.load(design_file))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Could not open design", str(exc), parent=self.root)
            return
        self.support.set(settings["support"])
        self.span.set(settings["span"])
        self.material.set(settings["material"])
        self.section.set(settings["section"])
        self.limit.set(settings["limit"])
        self.loads = loads
        self.next_load_id = len(loads) + 1
        self.current_file = path
        self.root.title(f"Beam Designer — {path.rsplit('/', 1)[-1]}")
        self._refresh()

    def _install_scroll_bindings(self, parent: tk.Widget) -> None:
        """Catch wheel events before widget-class bindings can consume them."""
        tags = parent.bindtags()
        if "BeamDesignerScroll" not in tags:
            parent.bindtags((tags[0], "BeamDesignerScroll", *tags[1:]))
        for child in parent.winfo_children():
            self._install_scroll_bindings(child)

    def _on_material(self, _event=None) -> None:
        sections = tuple(MATERIALS[self.material.get()]["sections"])
        self.section_box.configure(values=sections)
        self.section.set("W12x26" if "W12x26" in sections else sections[0])
        self._refresh()

    def _on_span(self) -> None:
        try:
            value = float(self.span.get())
        except (ValueError, tk.TclError):
            return
        value = clamp(value, MIN_SPAN, MAX_SPAN)
        self.span.set(value)
        for load in self.loads:
            if load.kind == "point":
                load.position = clamp(load.position, 0, value)
            else:
                load.start = clamp(load.start, 0, value)
                load.end = clamp(load.end, load.start, value)
        self._refresh()

    def _add_load(self, kind: str) -> None:
        span = self.span.get()
        if kind == "point":
            item = Load(kind, 10.0, position=span if self.support.get() == "Cantilever" else span / 2, id=self.next_load_id)
        else:
            item = Load(kind, 1.0, start=0, end=span, id=self.next_load_id)
        self.next_load_id += 1
        self.loads.append(item)
        self._refresh()

    def _remove_load(self, item: Load) -> None:
        self.loads.remove(item)
        self._refresh()

    def _draw_load_editor(self) -> None:
        for child in self.load_editor.winfo_children():
            child.destroy()
        self.load_count.configure(text=f"{len(self.loads)} load{'s' if len(self.loads) != 1 else ''}")
        if not self.loads:
            ttk.Label(self.load_editor, text="No loads. Add a point or uniform load to begin.", style="Muted.TLabel", wraplength=280).pack(anchor="w", pady=10)
            self._install_scroll_bindings(self.load_editor)
            return
        for index, item in enumerate(self.loads, 1):
            row = ttk.Frame(self.load_editor, style="Card.TFrame", padding=(0, 5))
            row.pack(fill="x", pady=(0, 5))
            top = ttk.Frame(row, style="Card.TFrame")
            top.pack(fill="x")
            accent = COLORS["blue"] if item.kind == "point" else COLORS["teal"]
            tk.Label(top, text="●", fg=accent, bg=COLORS["white"]).pack(side="left", padx=(0, 5))
            ttk.Label(top, text=f"{index:02d}  {'Point load' if item.kind == 'point' else 'Uniform load'}", style="Card.TLabel", font=("Helvetica", 9, "bold")).pack(side="left")
            ttk.Button(top, text="Remove", command=lambda load=item: self._remove_load(load)).pack(side="right")
            fields = ttk.Frame(row, style="Card.TFrame")
            fields.pack(fill="x", pady=(6, 0))
            definitions = [("magnitude", "Magnitude", "kips" if item.kind == "point" else "kip/ft")]
            if item.kind == "point":
                definitions.append(("position", "Position", "ft"))
            else:
                definitions += [("start", "Start", "ft"), ("end", "End", "ft")]
            for col, (field, label, unit) in enumerate(definitions):
                fields.columnconfigure(col, weight=1)
                cell = ttk.Frame(fields, style="Card.TFrame")
                cell.grid(row=0, column=col, sticky="ew", padx=(0, 5))
                ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
                variable = tk.StringVar(value=f"{getattr(item, field):g}")
                entry = ttk.Entry(cell, textvariable=variable, width=9)
                entry.pack(fill="x", pady=(2, 0))
                entry.bind("<Return>", lambda _e, load=item, name=field, var=variable: self._commit_load_field(load, name, var))
                entry.bind("<FocusOut>", lambda _e, load=item, name=field, var=variable: self._commit_load_field(load, name, var))
                ttk.Label(cell, text=unit, style="Muted.TLabel").pack(anchor="e")
        self._install_scroll_bindings(self.load_editor)

    def _commit_load_field(self, item: Load, field: str, variable: tk.StringVar) -> None:
        try:
            value = float(variable.get())
            if not math.isfinite(value):
                raise ValueError
        except (ValueError, tk.TclError):
            self._draw_load_editor()
            return
        if field == "magnitude":
            setattr(item, field, max(0.0, value))
        elif field == "position":
            item.position = clamp(value, 0, self.span.get())
        elif field == "start":
            item.start = clamp(value, 0, self.span.get())
            item.end = max(item.start, item.end)
        elif field == "end":
            item.end = clamp(value, 0, self.span.get())
            item.start = min(item.start, item.end)
        self._refresh()

    def _section(self) -> tuple[dict, dict]:
        material = MATERIALS[self.material.get()]
        return material, material["sections"][self.section.get()]

    def _analyze(self) -> dict:
        span_in = self.span.get() * 12
        cantilever = self.support.get() == "Cantilever"
        material, section = self._section()
        points = [(load.magnitude, load.position * 12) for load in self.loads if load.kind == "point"]
        uniforms = [(load.magnitude / 12, load.start * 12, load.end * 12) for load in self.loads if load.kind == "uniform"]
        total, total_moment = 0.0, 0.0
        for magnitude, x in points:
            total += magnitude
            total_moment += magnitude * x
        for intensity, start, end in uniforms:
            force = intensity * max(0, end - start)
            total += force
            total_moment += force * (start + end) / 2
        fixed_moment = -total_moment if cantilever else 0.0
        reaction_left = total if cantilever else total - total_moment / span_in
        reaction_right = 0.0 if cantilever else total_moment / span_in

        def pos(value: float) -> float:
            return max(0.0, value)

        def shear(x: float, include_at=True) -> float:
            value = reaction_left
            for magnitude, location in points:
                if location < x or (include_at and location == x):
                    value -= magnitude
            for intensity, start, end in uniforms:
                value -= intensity * clamp(x - start, 0, end - start)
            return value

        def moment(x: float) -> float:
            value = fixed_moment + reaction_left * x
            for magnitude, location in points:
                value -= magnitude * pos(x - location)
            for intensity, start, end in uniforms:
                value -= intensity / 2 * (pos(x - start) ** 2 - pos(x - end) ** 2)
            return value

        rigidity = material["E"] * section["Ix"]

        def integrated(x: float) -> float:
            value = -(fixed_moment * x**2 / 2 + reaction_left * x**3 / 6)
            for magnitude, location in points:
                value += magnitude * pos(x - location) ** 3 / 6
            for intensity, start, end in uniforms:
                value += intensity / 24 * (pos(x - start) ** 4 - pos(x - end) ** 4)
            return value / rigidity

        slope = 0.0 if cantilever else -integrated(span_in) / span_in
        deflection = lambda x: integrated(x) + slope * x
        breakpoints = [x for _, x in points] + [x for _, start, end in uniforms for x in (start, end)]
        shear_candidates = {0.0, span_in}
        for point in breakpoints:
            shear_candidates.update((clamp(point, 0, span_in), clamp(point - .001, 0, span_in), clamp(point + .001, 0, span_in)))
        shear_x = max(shear_candidates, key=lambda x: abs(shear(x)))
        shear_y = shear(shear_x)
        mx, my = peak_abs(moment, span_in, breakpoints)
        dx, dy = peak_abs(deflection, span_in, breakpoints)
        return {
            "span_in": span_in, "left": reaction_left, "right": reaction_right,
            "fixed_moment": fixed_moment, "shear": (shear_x, shear_y),
            "moment": (mx, my), "deflection": (dx, dy),
            "stress": abs(my) / section["Sx"], "allowable": material["Fb"],
            "limit": span_in / self.limit.get(), "shear_at": shear,
            "moment_at": moment, "deflection_at": deflection,
            "breakpoints": breakpoints,
        }

    def _refresh(self) -> None:
        if self.material.get() not in MATERIALS:
            self.material.set("Steel W-shapes")
        sections = tuple(MATERIALS[self.material.get()]["sections"])
        self.section_box.configure(values=sections)
        if self.section.get() not in sections:
            self.section.set(sections[0])
        self.span.set(clamp(float(self.span.get()), MIN_SPAN, MAX_SPAN))
        self.analysis = self._analyze()
        self._draw_load_editor()
        self._draw_preview()
        self._update_metrics()
        self._draw_beam()
        for key in self.plots:
            self._draw_plot(key)
        point_count = sum(load.kind == "point" for load in self.loads)
        uniform_count = len(self.loads) - point_count
        self.state_label.configure(text=f"Current case · {self.support.get()} · {self.span.get():g} ft · {self.section.get()} · L/{self.limit.get()} · {point_count} point, {uniform_count} uniform")
        example = self.support.get() == "Simply supported" and self.span.get() == 20 and self.material.get() == "Steel W-shapes" and self.section.get() == "W12x26" and self.limit.get() == 360 and len(self.loads) == 1 and self.loads[0].kind == "uniform" and self.loads[0].magnitude == 1 and self.loads[0].start == 0 and self.loads[0].end == 20
        self.example_label.configure(text="●  Example loaded" if example else "●  Custom beam case", foreground=COLORS["green"] if example else COLORS["muted"])

    def _update_metrics(self) -> None:
        a = self.analysis
        moment_x, moment_y = a["moment"]
        shear_x, shear_y = a["shear"]
        deflection_x, deflection_y = a["deflection"]
        stress_pass = a["stress"] <= a["allowable"]
        deflection_pass = abs(deflection_y) <= a["limit"]
        self.metric_widgets["moment"][0].configure(text=f"{abs(moment_y) / 12:.2f}")
        self.metric_widgets["moment"][1].configure(text=f"At {moment_x / 12:.2f} ft")
        self.metric_widgets["shear"][0].configure(text=f"{abs(shear_y):.2f}")
        self.metric_widgets["shear"][1].configure(text=f"At {shear_x / 12:.2f} ft")
        precision = 3 if a["allowable"] < 1 else 2
        self.metric_widgets["stress"][0].configure(text=f"{a['stress']:.{precision}f}")
        self.metric_widgets["stress"][1].configure(text=f"Allowable: {a['allowable']:.{precision}f} ksi · At {moment_x / 12:.2f} ft")
        self._status(self.metric_widgets["stress"][2], stress_pass)
        self.metric_widgets["deflection"][0].configure(text=f"{abs(deflection_y):.3f}")
        self.metric_widgets["deflection"][1].configure(text=f"At {deflection_x / 12:.2f} ft · Limit {a['limit']:.3f} in · L/{self.limit.get()}")
        self._status(self.metric_widgets["deflection"][2], deflection_pass)
        if self.support.get() == "Cantilever":
            reaction = f"Fixed-end reaction: {a['left']:.2f} kips   ·   Fixed-end moment: {abs(a['fixed_moment']) / 12:.2f} kip-ft"
        else:
            reaction = f"Left reaction: {a['left']:.2f} kips   ·   Right reaction: {a['right']:.2f} kips"
        self.reaction_label.configure(text=reaction)
        self.beam_title.configure(text=f"{self.support.get()} · {self.span.get():g} ft · {self.section.get()}")

    def _status(self, label: ttk.Label | None, passed: bool) -> None:
        if label:
            label.configure(text="PASS" if passed else "FAIL", foreground=COLORS["green"] if passed else COLORS["red"], background=COLORS["green_bg"] if passed else COLORS["red_bg"], padding=(7, 2))

    def _draw_preview(self) -> None:
        c = self.preview
        c.delete("all")
        material, section = self._section()
        width = c.winfo_width()
        if width < 80:
            width = 300
        cx, top = width * .52, 18
        scale = min(8.0, 100 / section["d"])
        depth = section["d"] * scale
        if "bf" in section:
            flange_w = section["bf"] * scale
            tf, tw = section["tf"] * scale, section["tw"] * scale
            c.create_rectangle(cx - flange_w / 2, top, cx + flange_w / 2, top + tf, fill="#dceafa", outline=COLORS["blue"], width=2)
            c.create_rectangle(cx - tw / 2, top + tf, cx + tw / 2, top + depth - tf, fill="#dceafa", outline=COLORS["blue"], width=1)
            c.create_rectangle(cx - flange_w / 2, top + depth - tf, cx + flange_w / 2, top + depth, fill="#dceafa", outline=COLORS["blue"], width=2)
            c.create_text(cx + flange_w / 2 + 18, top + depth / 2, text=f"d = {section['d']:g} in", fill=COLORS["muted"], anchor="w", font=("Helvetica", 8))
            c.create_text(cx, top - 4, text=f"bf = {section['bf']:g} in", fill=COLORS["muted"], anchor="s", font=("Helvetica", 8))
            c.create_text(cx + 30, top + tf / 2, text=f"tf {section['tf']:g}", fill=COLORS["muted"], anchor="w", font=("Helvetica", 7))
            c.create_text(cx + 16, top + depth / 2, text=f"tw {section['tw']:g}", fill=COLORS["muted"], anchor="w", font=("Helvetica", 7))
        else:
            b = section["b"] * scale
            c.create_rectangle(cx - b / 2, top, cx + b / 2, top + depth, fill="#dceafa", outline=COLORS["blue"], width=2)
            c.create_text(cx + b / 2 + 18, top + depth / 2, text=f"d = {section['d']:g} in", fill=COLORS["muted"], anchor="w", font=("Helvetica", 8))
            c.create_text(cx, top - 4, text=f"b = {section['b']:g} in", fill=COLORS["muted"], anchor="s", font=("Helvetica", 8))
        c.create_text(8, 130, anchor="w", fill=COLORS["muted"], text=f"{self.material.get()} · E {material['E']:g} ksi · Fb {material['Fb']:g} ksi · Sx {section['Sx']:g} in³ · Ix {section['Ix']:g} in⁴", font=("Helvetica", 8))
        if "weight" in section:
            c.create_text(8, 142, anchor="w", fill=COLORS["muted"], text=f"Section weight {section['weight']} lb/ft · self-weight excluded", font=("Helvetica", 8))

    def _draw_beam(self) -> None:
        c = self.beam_canvas
        if not c.winfo_exists():
            return
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 190)
        left, right = 68.0, w - 34.0
        beam_y = min(130.0, h * .62)
        self.beam_geometry = (left, right, beam_y)
        to_x = lambda ft: left + clamp(ft / self.span.get(), 0, 1) * (right - left)
        # load labels and uniform-load arrows
        for load in (item for item in self.loads if item.kind == "uniform"):
            x1, x2 = to_x(load.start), to_x(load.end)
            if x2 - x1 < 2:
                continue
            c.create_line(x1, 45, x2, 45, fill="#9bd8cf", dash=(4, 4), width=2)
            count = max(2, int((x2 - x1) / 42) + 1)
            for i in range(count):
                x = x1 + (x2 - x1) * i / (count - 1)
                c.create_line(x, 49, x, beam_y - 9, fill=COLORS["teal"], width=1.5, arrow="last")
            c.create_text((x1 + x2) / 2, 25, text=f"{load.magnitude:g} kip/ft", fill=COLORS["teal"], font=("Helvetica", 9, "bold"))
        for load in (item for item in self.loads if item.kind == "point"):
            x = to_x(load.position)
            c.create_line(x, 50, x, beam_y - 8, fill=COLORS["blue"], width=2, arrow="last")
            c.create_text(x, 27, text=f"{load.magnitude:g} kips", fill=COLORS["blue"], font=("Helvetica", 9, "bold"))
            c.create_oval(x - 9, beam_y - 8, x + 9, beam_y + 10, fill="white", outline=COLORS["blue"], width=2, tags=(f"load-{load.id}", "point_handle"))
        c.create_line(left, beam_y, right, beam_y, fill=COLORS["navy"], width=7)
        if self.support.get() == "Cantilever":
            c.create_rectangle(left - 17, beam_y - 28, left - 4, beam_y + 30, fill="#eaf3fc", outline=COLORS["blue"], width=2)
            for y in range(int(beam_y - 25), int(beam_y + 28), 9):
                c.create_line(left - 17, y, left - 29, y + 8, fill="#9db0c4", width=1.4)
        else:
            for x in (left, right):
                c.create_polygon(x, beam_y + 5, x - 16, beam_y + 31, x + 16, beam_y + 31, fill="#eaf3fc", outline=COLORS["blue"], width=1.5)
                c.create_line(x - 26, beam_y + 33, x + 26, beam_y + 33, fill="#9db0c4", width=2)
        c.create_line(left, beam_y + 48, right, beam_y + 48, fill="#9aaabe", arrow="both")
        c.create_text(left, beam_y + 62, text="0 ft", fill=COLORS["muted"], font=("Helvetica", 8))
        c.create_text((left + right) / 2, beam_y + 62, text=f"{self.span.get():g} ft span", fill=COLORS["navy"], font=("Helvetica", 9, "bold"))
        c.create_text(right, beam_y + 62, text=f"{self.span.get():g} ft", fill=COLORS["muted"], font=("Helvetica", 8))
        if self.cursor_ratio is not None:
            x = left + self.cursor_ratio * (right - left)
            c.create_line(x, 15, x, beam_y + 43, fill="#53657c", dash=(1, 3), width=2, tags="cursor")

    def _draw_plot(self, key: str) -> None:
        c = self.plots.get(key)
        if not c or not c.winfo_exists():
            return
        c.delete("all")
        w, h = max(c.winfo_width(), 250), max(c.winfo_height(), 150)
        left, right, top, bottom = 38.0, w - 14.0, 24.0, h - 28.0
        mid = (top + bottom) / 2
        plot_h = (bottom - top) / 2 - 3
        self.plot_geometry = getattr(self, "plot_geometry", {})
        self.plot_geometry[key] = (left, right, top, bottom)
        a = self.analysis
        if key == "shear":
            value_at = a["shear_at"]
            peak = max(abs(a["shear"][1]), .01)
            unit = "k"
            color = COLORS["blue"]
        elif key == "moment":
            value_at = lambda x: a["moment_at"](x) / 12
            peak = max(abs(a["moment"][1]) / 12, .01)
            unit = "kip-ft"
            color = COLORS["purple"]
        else:
            value_at = a["deflection_at"]
            peak = max(abs(a["deflection"][1]), a["limit"], .001)
            unit = "in"
            color = COLORS["teal"]
        scale = peak * (1.16 if key != "deflection" else 1.30)
        span = a["span_in"]
        x_at = lambda x: left + x / span * (right - left)
        y_at = lambda v: mid + (1 if key == "deflection" else -1) * v / scale * plot_h
        c.create_line(left, top, left, bottom, fill=COLORS["line"])
        c.create_line(left, mid, right, mid, fill="#95a5b7", width=1)
        c.create_line(right, top, right, bottom, fill=COLORS["line"])
        c.create_text(left, bottom + 13, text="0", fill=COLORS["muted"], anchor="w", font=("Helvetica", 8))
        c.create_text(right, bottom + 13, text=f"{self.span.get():g} ft", fill=COLORS["muted"], anchor="e", font=("Helvetica", 8))
        c.create_text(left + 2, top - 10, text=f"+{scale:.3g} {unit}", fill=COLORS["muted"], anchor="w", font=("Helvetica", 7))
        c.create_text(left + 2, bottom + 1, text=f"−{scale:.3g}", fill=COLORS["muted"], anchor="w", font=("Helvetica", 7))
        if key == "deflection":
            limit_y = y_at(a["limit"])
            c.create_line(left, limit_y, right, limit_y, fill=COLORS["red"], dash=(4, 3))
            c.create_text(right - 2, limit_y - 5, text=f"L/{self.limit.get()}", fill=COLORS["red"], anchor="e", font=("Helvetica", 8))
        count = max(140, min(800, int(span * 2)))
        positions = {span * i / count for i in range(count + 1)}
        positions.update(clamp(x, 0, span) for x in a["breakpoints"])
        xs = sorted(positions)
        if key == "shear":
            coords = []
            for x in xs:
                coords.extend((x_at(x), y_at(value_at(x, include_at=False))))
                if any(abs(x - p) < 1e-7 for _, p in self._point_loads_inch()):
                    coords.extend((x_at(x), y_at(value_at(x, include_at=True))))
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=2, tags="curve")
        else:
            coords = []
            for x in xs:
                coords.extend((x_at(x), y_at(value_at(x))))
            if len(coords) >= 4:
                area = [left, mid, *coords, right, mid]
                c.create_polygon(*area, fill="#e9f1fc" if key == "moment" else "#e4f4f1", outline="", stipple="gray50")
                c.create_line(*coords, fill=color, width=2)
        px = x_at(self.cursor_ratio * span) if self.cursor_ratio is not None else None
        if px is not None:
            c.create_line(px, top, px, bottom, fill="#53657c", dash=(1, 3), width=2, tags="cursor")

    def _point_loads_inch(self) -> list[tuple[float, float]]:
        return [(load.magnitude, load.position * 12) for load in self.loads if load.kind == "point"]

    def _start_drag(self, event) -> None:
        item_id = self.beam_canvas.find_closest(event.x, event.y)
        tags = self.beam_canvas.gettags(item_id)
        if "point_handle" in tags:
            for load in self.loads:
                if f"load-{load.id}" in tags:
                    self.drag_load = load
                    return

    def _drag_motion(self, event) -> None:
        if self.drag_load is None:
            self._update_cursor_from_event(event)
            return
        left, right, _ = self.beam_geometry
        ratio = clamp((event.x - left) / (right - left), 0, 1)
        raw = ratio * self.span.get()
        self.drag_load.position = clamp(round(raw * 4) / 4, 0, self.span.get())
        self._refresh()

    def _end_drag(self, _event) -> None:
        self.drag_load = None

    def _update_cursor_from_event(self, event) -> None:
        widget = event.widget
        if widget is self.beam_canvas:
            left, right, _ = self.beam_geometry
            ratio = clamp((event.x - left) / (right - left), 0, 1)
        else:
            key = next((name for name, canvas in self.plots.items() if canvas is widget), None)
            if key is None:
                return
            left, right, _, _ = self.plot_geometry.get(key, (38, max(widget.winfo_width() - 14, 39), 0, 0))
            ratio = clamp((event.x - left) / (right - left), 0, 1)
        self.cursor_ratio = ratio
        self._draw_beam()
        for name in self.plots:
            self._draw_plot(name)

    def _hide_cursor(self, _event) -> None:
        self.cursor_ratio = None
        self._draw_beam()
        for name in self.plots:
            self._draw_plot(name)


def main() -> None:
    root = tk.Tk()
    BeamDesigner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
