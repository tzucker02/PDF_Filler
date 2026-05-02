from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import sys
import webbrowser

import toga
from pypdf import PdfReader, PdfWriter
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

APP_VERSION = "1.1.1"
APP_URL = "https://software.zuckerscharff.com"
APP_GITHUB_URL = "https://github.com/tzucker02/PythonCode/blob/main/README.md"
PDF_NAME = "Student Recommendation Form.pdf"
CSV_NAME = "students.csv"
DEFAULT_LABEL = "Student Recommendation Form"


class PDFFillerApp(toga.App):
    @staticmethod
    def _parse_path(value: str) -> Path | None:
        text = (value or "").strip()
        if not text:
            return None
        return Path(text)

    @staticmethod
    def _first_selection(selected):
        if not selected:
            return None
        if isinstance(selected, (list, tuple)):
            return selected[0] if selected else None
        return selected

    @staticmethod
    def _is_android_runtime() -> bool:
        if sys.platform == "android":
            return True
        # Chaquopy can report Linux-like platform values; environment flags are reliable.
        return bool(os.environ.get("ANDROID_STORAGE") or os.environ.get("ANDROID_ROOT"))

    def startup(self):
        self.is_mobile_ui = self._is_android_runtime()
        if self.is_mobile_ui:
            self.main_window = toga.MainWindow(title="PDF Form Filler")
        else:
            self.main_window = toga.MainWindow(title="PDF Form Filler", size=(980, 680))

        self.template_input = toga.TextInput(style=Pack(flex=1, padding=(0, 8, 0, 8)))
        self.csv_input = toga.TextInput(style=Pack(flex=1, padding=(0, 8, 0, 8)))
        self.output_input = toga.TextInput(style=Pack(flex=1, padding=(0, 8, 0, 8)))
        self.aliases_input = toga.TextInput(style=Pack(flex=1, padding=(0, 8, 0, 8)))
        label_style = Pack(flex=1, padding=(0, 8, 0, 8)) if self.is_mobile_ui else Pack(width=360, padding=(0, 8, 0, 8))
        self.label_input = toga.TextInput(value=DEFAULT_LABEL, style=label_style)
        self.strict_switch = toga.Switch("Strict field matching", value=False, style=Pack(padding=(2, 0, 0, 16)))
        self.soundex_switch = toga.Switch("Use Soundex fallback", value=True, style=Pack(padding=(2, 0, 0, 0)))
        output_log_style = Pack(flex=1, padding=(0, 0, 0, 0)) if self.is_mobile_ui else Pack(height=260, padding=(0, 0, 0, 0))
        self.output_log = toga.MultilineTextInput(readonly=True, style=output_log_style)
        self.open_folder_btn = toga.Button(
            "Open Output Folder",
            on_press=self._on_open_folder_pressed,
            enabled=False,
            style=Pack(padding=(6, 0, 0, 0), height=40),
        )

        content = toga.Box(
            children=[
                self._path_row("Template PDF", self.template_input, self.on_browse_template),
                self._path_row("CSV Data", self.csv_input, self.on_browse_csv),
                self._path_row("Output Folder", self.output_input, self.on_browse_output),
                self._aliases_row(),
                self._options_row(),
                self._actions_row(),
                toga.Label("Output", style=Pack(padding=(8, 0, 6, 0), font_size=12)),
                self.output_log,
                self.open_folder_btn,
            ],
            style=Pack(direction=COLUMN, padding=12),
        )

        self.form_content = content
        self.form_scroll = toga.ScrollContainer(content=content, horizontal=False, style=Pack(flex=1))
        if self.is_mobile_ui:
            self.main_window.content = self.form_scroll
        else:
            self.main_window.content = content
        self._autofill_paths()
        self.main_window.show()
        if not self.is_mobile_ui:
            self._center_main_window()
        self.commands.add(
            toga.Command(
                self.on_about_pressed,
                text="About",
                group=toga.Group.HELP,
                id=toga.Command.ABOUT,
            )
        )

    def _show_main_content(self) -> None:
        self.main_window.content = self.form_scroll if self.is_mobile_ui else self.form_content

    def _center_main_window(self) -> None:
        try:
            if not self.screens:
                return
            screen_width, screen_height = self.screens[0].size
            window_width, window_height = self.main_window.size
            pos_x = max(int((screen_width - window_width) / 2), 0)
            pos_y = max(int((screen_height - window_height) / 2), 0)
            self.main_window.position = (pos_x, pos_y)
        except Exception:
            pass

    def _about_lines(self):
        version = APP_VERSION
        author = "Thomas Zucker-Scharff"
        return [
            str(self.formal_name),
            f"Build: {version}",
            f"Author: {author}",
            "",
            "Copyright:",
            "© 2026 by the Author (unless otherwise stated)",
            f"URL: {APP_URL}",
            f"Author/Software Github: {APP_GITHUB_URL}",
        ]

    async def on_about_pressed(self, widget):
        open_links = await self.main_window.question_dialog(
            "About",
            "\n".join(self._about_lines()) + "\n\nOpen links now?",
        )
        if open_links:
            if self._is_android_runtime():
                try:
                    from java import jclass  # type: ignore
                    Intent = jclass("android.content.Intent")
                    Uri = jclass("android.net.Uri")
                    activity = self.app._impl.native
                    for url in (APP_URL, APP_GITHUB_URL):
                        intent = Intent(Intent.ACTION_VIEW)
                        intent.setData(Uri.parse(url))
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_DOCUMENT)
                        intent.addFlags(Intent.FLAG_ACTIVITY_MULTIPLE_TASK)
                        activity.startActivity(intent)
                except Exception as exc:
                    self._log(f"Open URL failed: {exc}")
                    await self._notify_error(
                        "Open Links Failed",
                        "Could not open links automatically.\n\n"
                        f"Open manually:\n{APP_URL}\n{APP_GITHUB_URL}",
                    )
            else:
                opened_main = False
                opened_github = False
                try:
                    opened_main = bool(webbrowser.open(APP_URL))
                    opened_github = bool(webbrowser.open(APP_GITHUB_URL))
                except Exception as exc:
                    await self._notify_error("Open Links Failed", f"Could not open links: {exc}")
                    return

                if not (opened_main and opened_github):
                    await self._notify_error(
                        "Open Links Failed",
                        "Device did not open one or more links automatically.\n\n"
                        f"Open manually:\n{APP_URL}\n{APP_GITHUB_URL}",
                    )

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(name).lower())

    @staticmethod
    def _soundex(value: str) -> str:
        # Basic Soundex implementation for fuzzy column-to-field fallback.
        text = re.sub(r"[^A-Za-z]", "", str(value or "")).upper()
        if not text:
            return ""
        first = text[0]
        mappings = {
            "B": "1", "F": "1", "P": "1", "V": "1",
            "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
            "D": "3", "T": "3",
            "L": "4",
            "M": "5", "N": "5",
            "R": "6",
        }
        encoded = []
        previous = mappings.get(first, "")
        for ch in text[1:]:
            digit = mappings.get(ch, "")
            if digit != previous and digit:
                encoded.append(digit)
            previous = digit
        return (first + "".join(encoded) + "000")[:4]

    @staticmethod
    def _safe_part(value: str, fallback: str) -> str:
        text = str(value or fallback).strip()
        text = re.sub(r"[\\/:*?\"<>|]", "", text)
        text = re.sub(r"\s+", "_", text)
        return text or fallback

    def _candidate_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if getattr(sys, "frozen", False):
            dirs.append(Path(sys.executable).parent)
        dirs.append(Path.cwd())
        dirs.append(Path.home() / "Documents" / "studentforms")
        dirs.append(Path.home() / "Documents")
        seen = set()
        ordered: list[Path] = []
        for d in dirs:
            key = str(d.resolve()) if d.exists() else str(d)
            if key not in seen:
                seen.add(key)
                ordered.append(d)
        return ordered

    def _find_input_dir(self) -> Path | None:
        for d in self._candidate_dirs():
            if (d / CSV_NAME).exists() and (d / PDF_NAME).exists():
                return d
        return None

    def _autofill_paths(self) -> None:
        input_dir = self._find_input_dir()
        if input_dir is None:
            return
        self.template_input.value = str(input_dir / PDF_NAME)
        self.csv_input.value = str(input_dir / CSV_NAME)
        self.output_input.value = str(input_dir / "filled")

    @staticmethod
    def _field_names_from_pdf(template_pdf: Path) -> set[str]:
        fields = PdfReader(str(template_pdf)).get_fields() or {}
        return set(fields.keys())

    @staticmethod
    def _load_aliases(path_value: str) -> dict[str, str]:
        if not path_value.strip():
            return {}
        alias_path = Path(path_value)
        if not alias_path.exists():
            raise FileNotFoundError(f"Aliases JSON not found: {alias_path}")
        raw = json.loads(alias_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Aliases JSON must be an object of key-value pairs.")
        aliases: dict[str, str] = {}
        for key, value in raw.items():
            aliases[str(key)] = str(value)
        return aliases

    def _log(self, text: str) -> None:
        current = self.output_log.value or ""
        self.output_log.value = f"{current}{text}\n"

    async def _notify_error(self, title: str, message: str) -> None:
        self._log(f"ERROR - {title}: {message}")
        try:
            await self.main_window.error_dialog(title, message)
        except Exception:
            pass

    async def _notify_info(self, title: str, message: str) -> None:
        self._log(f"{title}: {message}")
        try:
            await self.main_window.info_dialog(title, message)
        except Exception:
            pass

    def _show_android_browser(self, title: str, target_input: toga.TextInput, select_folder: bool, file_types: list[str] | None = None) -> None:
        start_text = (target_input.value or "").strip()
        start = Path(start_text) if start_text else (Path("/sdcard") if Path("/sdcard").exists() else Path.cwd())
        if not start.exists():
            start = Path("/sdcard") if Path("/sdcard").exists() else Path.cwd()
        if start.is_file():
            start = start.parent

        self._browser_state = {
            "title": title,
            "target_input": target_input,
            "select_folder": select_folder,
            "allowed": {ext.lower().lstrip(".") for ext in (file_types or [])},
            "current": start,
        }
        self._render_android_browser()

    def _render_android_browser(self) -> None:
        state = self._browser_state
        current: Path = state["current"]
        allowed: set[str] = state["allowed"]
        select_folder: bool = state["select_folder"]

        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception as exc:
            self._log(f"Browse Error: Cannot open {current}: {exc}")
            self._show_main_content()
            return

        children: list = [
            toga.Label(str(state["title"]), style=Pack(font_size=14, padding=(0, 0, 6, 0))),
            toga.Label(f"Folder: {current}", style=Pack(padding=(0, 0, 8, 0))),
            toga.Box(
                children=[
                    toga.Button("Up", on_press=self.on_browser_up_pressed, style=Pack(width=80, padding=(0, 8, 0, 0))),
                    toga.Button("Cancel", on_press=self.on_browser_cancel_pressed, style=Pack(width=90)),
                ],
                style=Pack(direction=ROW, padding=(0, 0, 8, 0)),
            ),
        ]

        if select_folder:
            children.append(toga.Button("Select This Folder", on_press=self.on_browser_select_current_pressed, style=Pack(padding=(0, 0, 8, 0), height=40)))
            self._browser_new_folder_input = toga.TextInput(
                placeholder="New folder name…",
                style=Pack(flex=1, padding=(0, 8, 0, 0)),
            )
            children.append(
                toga.Box(
                    children=[
                        self._browser_new_folder_input,
                        toga.Button("+", on_press=self._on_browser_create_folder, style=Pack(width=50)),
                    ],
                    style=Pack(direction=ROW, padding=(0, 0, 10, 0)),
                )
            )

        for path in entries:
            if path.is_dir():
                children.append(
                    toga.Button(
                        f"[DIR] {path.name}",
                        on_press=self._make_browser_entry_handler(path),
                        style=Pack(padding=(0, 0, 6, 0), height=38),
                    )
                )
            else:
                if select_folder:
                    continue
                view_mode = state.get("view_mode", False)
                if not view_mode and allowed and path.suffix.lower().lstrip(".") not in allowed:
                    continue
                children.append(
                    toga.Button(
                        f"[FILE] {path.name}",
                        on_press=self._make_browser_entry_handler(path),
                        style=Pack(padding=(0, 0, 6, 0), height=38),
                    )
                )

        browser_content = toga.Box(children=children, style=Pack(direction=COLUMN, padding=12))
        self.main_window.content = toga.ScrollContainer(content=browser_content, horizontal=False, style=Pack(flex=1))

    def _on_browser_create_folder(self, widget) -> None:
        name = (getattr(self, "_browser_new_folder_input", None) and self._browser_new_folder_input.value or "").strip()
        if not name:
            self._log("New folder: enter a name first.")
            return
        # Strip path-unsafe characters
        safe = re.sub(r'[\\/:*?"<>|]', "", name).strip()
        if not safe:
            self._log("New folder: name contains only invalid characters.")
            return
        new_dir = self._browser_state["current"] / safe
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._log(f"New folder failed: {exc}")
            return
        self._browser_new_folder_input.value = ""
        self._browser_state["current"] = new_dir
        self._render_android_browser()

    def _make_browser_entry_handler(self, path: Path):
        def _handler(widget):
            self._on_browser_entry_pressed(path)

        return _handler

    def _on_browser_entry_pressed(self, path: Path) -> None:
        if path.is_dir():
            self._browser_state["current"] = path
            self._render_android_browser()
            return
        # View mode: open the file rather than setting an input field
        if self._browser_state.get("view_mode"):
            self._open_file_on_android(path)
            return
        target: toga.TextInput = self._browser_state["target_input"]
        target.value = str(path)
        self._show_main_content()

    def _open_file_on_android(self, path: Path) -> None:
        """Open a file using Android ACTION_VIEW intent via Chaquopy."""
        mime_map = {
            "pdf": "application/pdf",
            "csv": "text/csv",
            "json": "application/json",
            "txt": "text/plain",
        }
        mime = mime_map.get(path.suffix.lower().lstrip("."), "*/*")
        try:
            from java import jclass  # type: ignore
            Intent = jclass("android.content.Intent")
            FileProvider = jclass("androidx.core.content.FileProvider")
            File = jclass("java.io.File")
            activity = self.app._impl.native
            authority = "com.owner.pdf-filler.fileprovider"
            file_obj = File(str(path))
            uri = FileProvider.getUriForFile(activity, authority, file_obj)
            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(uri, mime)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(intent)
        except Exception as exc:
            self._log(f"Open file failed: {exc}")

    async def on_browser_up_pressed(self, widget):
        current: Path = self._browser_state["current"]
        if current.parent != current:
            self._browser_state["current"] = current.parent
        self._render_android_browser()

    async def on_browser_cancel_pressed(self, widget):
        self._show_main_content()

    async def on_browser_select_current_pressed(self, widget):
        current: Path = self._browser_state["current"]
        target: toga.TextInput = self._browser_state["target_input"]
        target.value = str(current)
        self._show_main_content()

    async def on_browser_entry_pressed(self, path: Path):
        self._on_browser_entry_pressed(path)

    def _path_row(self, label: str, input_box: toga.TextInput, browse_handler) -> toga.Box:
        if self.is_mobile_ui:
            return toga.Box(
                children=[
                    toga.Label(label, style=Pack(padding=(4, 0, 2, 0))),
                    toga.Box(
                        children=[
                            input_box,
                            toga.Button("Browse", on_press=browse_handler, style=Pack(width=90)),
                        ],
                        style=Pack(direction=ROW, alignment="center"),
                    ),
                ],
                style=Pack(direction=COLUMN, padding=(0, 0, 10, 0)),
            )
        return toga.Box(
            children=[
                toga.Label(label, style=Pack(width=120, padding=(8, 0, 0, 0))),
                input_box,
                toga.Button("Browse", on_press=browse_handler, style=Pack(width=100)),
            ],
            style=Pack(direction=ROW, padding=(0, 0, 8, 0), alignment="center"),
        )

    def _aliases_row(self) -> toga.Box:
        if self.is_mobile_ui:
            return toga.Box(
                children=[
                    toga.Label("Aliases JSON (CSV -> PDF map)", style=Pack(padding=(4, 0, 2, 0))),
                    self.aliases_input,
                    toga.Box(
                        children=[
                            toga.Button("Browse", on_press=self.on_browse_aliases, style=Pack(width=100, padding=(0, 8, 0, 0))),
                            toga.Button("Clear", on_press=self.on_clear_aliases, style=Pack(width=90)),
                        ],
                        style=Pack(direction=ROW, padding=(6, 0, 0, 0)),
                    ),
                ],
                style=Pack(direction=COLUMN, padding=(0, 0, 10, 0)),
            )
        return toga.Box(
            children=[
                toga.Label("Aliases JSON (CSV -> PDF map)", style=Pack(width=210, padding=(8, 0, 0, 0))),
                self.aliases_input,
                toga.Button("Browse", on_press=self.on_browse_aliases, style=Pack(width=100, padding=(0, 8, 0, 0))),
                toga.Button("Clear", on_press=self.on_clear_aliases, style=Pack(width=90)),
            ],
            style=Pack(direction=ROW, padding=(0, 0, 8, 0), alignment="center"),
        )

    def _options_row(self) -> toga.Box:
        if self.is_mobile_ui:
            return toga.Box(
                children=[
                    toga.Label("Output PDF Label", style=Pack(padding=(4, 0, 2, 0))),
                    self.label_input,
                    self.strict_switch,
                    self.soundex_switch,
                ],
                style=Pack(direction=COLUMN, padding=(0, 0, 10, 0)),
            )
        return toga.Box(
            children=[
                toga.Label("Output PDF Label", style=Pack(width=120, padding=(8, 0, 0, 0))),
                self.label_input,
                self.strict_switch,
                self.soundex_switch,
            ],
            style=Pack(direction=ROW, padding=(0, 0, 10, 0), alignment="center"),
        )

    def _actions_row(self) -> toga.Box:
        if self.is_mobile_ui:
            return toga.Box(
                children=[
                    toga.Button("List Fields", on_press=self.on_list_fields, style=Pack(padding=(0, 0, 8, 0), height=40)),
                    toga.Button("Fill From CSV", on_press=self.on_fill_from_csv, style=Pack(padding=(0, 0, 8, 0), height=40)),
                    toga.Button("Generate CSV Template", on_press=self.on_generate_csv_template, style=Pack(height=40)),
                    toga.Button("Exit App", on_press=self.on_exit_app, style=Pack(padding=(8, 0, 0, 0), height=40)),
                ],
                style=Pack(direction=COLUMN, padding=(0, 0, 10, 0)),
            )
        return toga.Box(
            children=[
                toga.Button("List Fields", on_press=self.on_list_fields, style=Pack(width=100, padding=(0, 8, 0, 0))),
                toga.Button("Fill From CSV", on_press=self.on_fill_from_csv, style=Pack(width=120)),
                toga.Button("Generate CSV Template", on_press=self.on_generate_csv_template, style=Pack(width=170, padding=(0, 0, 0, 8))),
                toga.Button("Exit App", on_press=self.on_exit_app, style=Pack(width=100, padding=(0, 0, 0, 8))),
            ],
            style=Pack(direction=ROW, padding=(0, 0, 8, 0)),
        )

    @staticmethod
    def _fill_single_form(template_pdf: Path, output_pdf: Path, form_data: dict[str, str]) -> None:
        reader = PdfReader(str(template_pdf))
        writer = PdfWriter()
        writer.append(reader)
        writer.update_page_form_field_values(writer.pages[0], form_data, auto_regenerate=True)
        with output_pdf.open("wb") as f:
            writer.write(f)

    async def on_browse_template(self, widget):
        if self.is_mobile_ui:
            try:
                selected = await self.main_window.open_file_dialog(title="Select Template PDF", file_types=["pdf"])
                selected = self._first_selection(selected)
                if selected:
                    self.template_input.value = str(selected)
                    return
            except Exception as exc:
                self._log(f"Native picker failed: {exc}")
            self._show_android_browser("Select Template PDF", self.template_input, select_folder=False, file_types=["pdf"])
            return
        selected = await self.main_window.open_file_dialog(title="Select Template PDF", file_types=["pdf"])
        if selected:
            self.template_input.value = str(selected)

    async def on_browse_csv(self, widget):
        if self.is_mobile_ui:
            try:
                selected = await self.main_window.open_file_dialog(title="Select CSV Data", file_types=["csv"])
                selected = self._first_selection(selected)
                if selected:
                    self.csv_input.value = str(selected)
                    return
            except Exception as exc:
                self._log(f"Native picker failed: {exc}")
            self._show_android_browser("Select CSV Data", self.csv_input, select_folder=False, file_types=["csv"])
            return
        selected = await self.main_window.open_file_dialog(title="Select CSV Data", file_types=["csv"])
        if selected:
            self.csv_input.value = str(selected)

    async def on_browse_output(self, widget):
        if self.is_mobile_ui:
            try:
                selected = await self.main_window.select_folder_dialog(title="Select Output Folder")
                selected = self._first_selection(selected)
                if selected:
                    self.output_input.value = str(selected)
                    return
            except Exception as exc:
                self._log(f"Native picker failed: {exc}")
            self._show_android_browser("Select Output Folder", self.output_input, select_folder=True)
            return
        selected = await self.main_window.select_folder_dialog(title="Select Output Folder")
        if selected:
            self.output_input.value = str(selected)

    async def on_browse_aliases(self, widget):
        if self.is_mobile_ui:
            try:
                selected = await self.main_window.open_file_dialog(title="Select Aliases JSON", file_types=["json"])
                selected = self._first_selection(selected)
                if selected:
                    self.aliases_input.value = str(selected)
                    return
            except Exception as exc:
                self._log(f"Native picker failed: {exc}")
            self._show_android_browser("Select Aliases JSON", self.aliases_input, select_folder=False, file_types=["json"])
            return
        selected = await self.main_window.open_file_dialog(title="Select Aliases JSON", file_types=["json"])
        if selected:
            self.aliases_input.value = str(selected)

    async def on_clear_aliases(self, widget):
        self.aliases_input.value = ""

    async def on_exit_app(self, widget):
        try:
            if self.main_window is not None:
                self.main_window.close()
        except Exception:
            pass
        try:
            self.exit()
        except Exception:
            pass
        if self.is_mobile_ui:
            # Explicit Android fallback: ensure the app can be closed from the button.
            os._exit(0)

    async def on_list_fields(self, widget):
        try:
            if self.is_mobile_ui:
                self._log("List Fields pressed")
            self.output_log.value = ""
            template_path = self._parse_path(self.template_input.value or "")
            if template_path is None or (not template_path.exists()) or (not template_path.is_file()):
                await self._notify_error("Missing Template PDF", "Please select a valid Template PDF first.")
                return

            fields = sorted(self._field_names_from_pdf(template_path))
            self._log(f"PDF fields ({len(fields)}):")
            for name in fields:
                self._log(f"- {name}")
        except Exception as exc:
            await self._notify_error("List Fields Failed", str(exc))

    async def on_fill_from_csv(self, widget):
        try:
            if self.is_mobile_ui:
                self._log("Fill From CSV pressed")
            self.output_log.value = ""
            template_path = self._parse_path(self.template_input.value or "")
            csv_path = self._parse_path(self.csv_input.value or "")
            output_dir = self._parse_path(self.output_input.value or "")
            output_label = (self.label_input.value or DEFAULT_LABEL).strip() or DEFAULT_LABEL
            strict = bool(self.strict_switch.value)
            use_soundex = bool(self.soundex_switch.value)

            if template_path is None or (not template_path.exists()) or (not template_path.is_file()):
                await self._notify_error("Missing Template PDF", "Please select a valid Template PDF.")
                return
            if csv_path is None or (not csv_path.exists()) or (not csv_path.is_file()):
                await self._notify_error("Missing CSV Data", "Please select a valid CSV file.")
                return
            if output_dir is None:
                await self._notify_error("Missing Output Folder", "Please select a valid Output Folder.")
                return
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

            pdf_fields = self._field_names_from_pdf(template_path)
            normalized_pdf_fields = {self._normalize(name): name for name in pdf_fields}
            soundex_pdf_fields: dict[str, str] = {}
            if use_soundex:
                for name in pdf_fields:
                    sx = self._soundex(name)
                    if sx and sx not in soundex_pdf_fields:
                        soundex_pdf_fields[sx] = name

            try:
                aliases = self._load_aliases(self.aliases_input.value or "")
            except Exception as exc:
                await self._notify_error("Invalid Aliases JSON", str(exc))
                return

            alias_norm = {self._normalize(k): v for k, v in aliases.items()}

            created = 0
            self._log(f"Template PDF: {template_path}")
            self._log(f"CSV Data: {csv_path}")
            self._log(f"Output Folder: {output_dir}")
            self._log(f"Strict field matching: {'ON' if strict else 'OFF'}")
            self._log(f"Use Soundex fallback: {'ON' if use_soundex else 'OFF'}")

            with csv_path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    await self._notify_error("CSV Error", "CSV file has no header row.")
                    return

                header_to_target: dict[str, str] = {}
                for header in reader.fieldnames:
                    norm = self._normalize(header)
                    target = alias_norm.get(norm)
                    if not target:
                        target = normalized_pdf_fields.get(norm, "")
                    if not target and use_soundex:
                        target = soundex_pdf_fields.get(self._soundex(header), "")
                    if not target and strict:
                        await self._notify_error(
                            "Strict Matching Error",
                            f"CSV column '{header}' does not map to a PDF field.",
                        )
                        return
                    if target:
                        header_to_target[header] = target

                for row in reader:
                    form_data: dict[str, str] = {}
                    for header, value in row.items():
                        target = header_to_target.get(header)
                        if target:
                            form_data[target] = value or ""

                    if strict:
                        missing_required = sorted(name for name in form_data if name not in pdf_fields)
                        if missing_required:
                            await self._notify_error(
                                "Strict Matching Error",
                                "Mapped fields do not exist in PDF: " + ", ".join(missing_required),
                            )
                            return

                    student_part = self._safe_part(row.get("student_name", "student"), "student")
                    class_part = self._safe_part(row.get("class_name", "class"), "class")
                    output_name = f"{student_part}-{class_part} - {output_label}.pdf"
                    output_pdf = output_dir / output_name
                    self._fill_single_form(template_path, output_pdf, form_data)
                    created += 1
                    self._log(f"Created: {output_pdf.name}")

            self._log(f"Done. {created} form(s) created.")
            await self._notify_info("Completed", f"Created {created} form(s).")
            if self.is_mobile_ui:
                self._enable_open_folder_btn(output_dir)
        except Exception as exc:
            await self._notify_error("Fill From CSV Failed", str(exc))

    async def on_generate_csv_template(self, widget):
        try:
            if self.is_mobile_ui:
                self._log("Generate CSV Template pressed")
            self.output_log.value = ""
            template_path = self._parse_path(self.template_input.value or "")
            if template_path is None or (not template_path.exists()) or (not template_path.is_file()):
                await self._notify_error("Missing Template PDF", "Please select a valid Template PDF first.")
                return

            fields = sorted(self._field_names_from_pdf(template_path))
            if not fields:
                await self._notify_error("No Fields Found", "The selected PDF does not expose fillable fields.")
                return

            if self.is_mobile_ui:
                base = self._parse_path(self.output_input.value or "")
                if base is None:
                    await self._notify_error("Missing Output Folder", "Please select an Output Folder first.")
                    return
                base.mkdir(parents=True, exist_ok=True)
                output_csv = base / "pdf_fields_template.csv"
            else:
                save_path = await self.main_window.save_file_dialog(
                    title="Save CSV Template",
                    suggested_filename="pdf_fields_template.csv",
                    file_types=["csv"],
                )
                if not save_path:
                    self._log("CSV template generation canceled.")
                    return
                output_csv = Path(str(save_path))

            with output_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(fields)

            self._log(f"CSV template created: {output_csv}")
            await self._notify_info("CSV Template Created", f"Saved template to:\n{output_csv}")
            if self.is_mobile_ui:
                self._enable_open_folder_btn(output_csv.parent)
        except Exception as exc:
            await self._notify_error("Generate CSV Template Failed", str(exc))


    def _enable_open_folder_btn(self, folder: Path) -> None:
        self._open_folder_target = folder
        self.open_folder_btn.text = f"Open Output Folder: {folder.name}"
        self.open_folder_btn.enabled = True

    def _on_open_folder_pressed(self, widget) -> None:
        folder = getattr(self, "_open_folder_target", None)
        if folder:
            self._open_folder_on_android(folder)

    def _add_open_folder_button(self, folder: Path) -> None:
        """Legacy stub — replaced by _enable_open_folder_btn."""
        self._enable_open_folder_btn(folder)

    def _open_folder_on_android(self, folder: Path) -> None:
        """Browse the output folder in view mode so the user can tap files to open them."""
        self._browser_state = {
            "title": f"Output: {folder.name}",
            "target_input": None,
            "select_folder": False,
            "allowed": set(),
            "current": folder,
            "view_mode": True,
        }
        self._render_android_browser()


def main():
    return PDFFillerApp()
