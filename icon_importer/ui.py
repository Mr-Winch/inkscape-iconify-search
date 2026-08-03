"""GTK 3 icon picker used by the Inkscape extension."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import xml.etree.ElementTree as ET

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from .api import IconifyClient
from .favorites import (
    add_icon,
    contains_icon,
    create_section,
    icon_count,
    normalize_favorites,
    remove_icon,
    remove_section,
)
from .models import CollectionInfo, IconInfo, ImportChoice, SearchResult
from .svg import classify_svg_style


class IconBrowserDialog(Gtk.Dialog):
    COL_ACTIVE, COL_NAME, COL_PREFIX, COL_TOTAL = range(4)
    COL_CATEGORY, COL_PALETTE, COL_LICENSE, COL_HEIGHT = range(4, 8)

    def __init__(self, client: IconifyClient):
        super().__init__(title="Iconify — Search and Import Icons")
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=7)
        self.collections = ()
        self.collections_by_prefix = {}
        self.ui_state = self._load_ui_state()
        self.favorites = normalize_favorites(self.ui_state.get("favorites"))
        self.favorite_buttons = {}
        self.open_favorite_sections = set()
        collection_state = self.ui_state.get("collections", {})
        prefixes = collection_state.get("prefixes", ())
        if not isinstance(prefixes, (list, tuple, set)):
            prefixes = ()
        self.use_all_collections = bool(collection_state.get("use_all", True))
        self.selected_prefixes = {str(prefix) for prefix in prefixes}
        self.pending_icon_category = str(
            self.ui_state.get("filters", {}).get("icon_category", "all")
        )
        self.restoring_state = True
        self.selected_icon = None
        self.collection_browse = None
        self.search_serial = self.catalog_serial = self.suggestion_serial = 0
        self.search_timer = self.suggestion_timer = None
        self.closed = False
        self.thumbnail_size = 64
        self.result_children = []
        self.visible_result_count = 0

        self.set_default_size(1260, 820)
        self.set_resizable(True)
        self._set_window_icon()
        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self.import_button = self.add_button("_Import", Gtk.ResponseType.OK)
        self.import_button.set_sensitive(False)
        self.import_button.get_style_context().add_class("primary-action")
        action_area = self.get_action_area()
        action_area.set_border_width(12)
        action_area.set_spacing(8)
        self.set_default_response(Gtk.ResponseType.OK)
        self._install_css()
        self._build_ui()
        self.restoring_state = False
        self.connect("destroy", self._on_destroy)
        self.show_all()
        active_page = str(self.ui_state.get("active_page") or "filters")
        if active_page not in {"collections", "filters", "favorites"}:
            active_page = "filters"
        self.sidebar_stack.set_visible_child_name(active_page)
        self._update_format_controls()
        self._load_catalog()
        self.search_entry.grab_focus()
        self._queue_search(immediate=True)

    def _set_window_icon(self):
        try:
            icon = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(self._icon_path()), 32, 32, True
            )
            self.set_icon(icon)
            Gtk.Window.set_default_icon(icon)
        except (GLib.Error, OSError):
            pass

    @staticmethod
    def _icon_path():
        return Path(__file__).resolve().parent.parent / "iconify_search_icon.svg"

    def _brand_image(self, size):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(self._icon_path()), size, size, True
            )
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except (GLib.Error, OSError):
            return Gtk.Image.new_from_icon_name(
                "system-search-symbolic", Gtk.IconSize.DIALOG
            )

    def _install_css(self):
        css = b"""
        .icon-importer-root { padding: 0; }
        .icon-title { font-size: 28px; font-weight: 700; }
        .section-title { font-size: 17px; font-weight: 700; }
        .subsection-title { font-size: 14px; font-weight: 700; }
        .side-tabs button label { font-size: 14px; font-weight: 600; }
        .field-label { font-size: 11px; font-weight: 600; opacity: 0.80; }
        .selection-summary { font-size: 12px; font-weight: 600; }
        .dim-label { opacity: 0.68; }
        .accent-label { color: #2f80ed; font-weight: 700; }
        .card {
          background-color: @theme_base_color;
          border: 1px solid alpha(@theme_fg_color, 0.14);
          border-radius: 8px;
        }
        .search-card { padding: 10px; }
        .side-tabs button { padding: 8px 14px; }
        .primary-action {
          color: #ffffff;
          background-image: none;
          background-color: #2f80ed;
          border-color: #2f80ed;
          text-shadow: none;
          box-shadow: none;
        }
        .primary-action:hover { background-color: #3f8ff0; }
        .primary-action:active { background-color: #246dc9; }
        .icon-importer-root flowboxchild {
          margin: 1px;
          border: 1px solid transparent;
          border-radius: 8px;
        }
        .icon-importer-root flowboxchild:hover {
          background-color: alpha(@theme_fg_color, 0.07);
          border-color: alpha(@theme_fg_color, 0.16);
        }
        .icon-importer-root flowboxchild:selected {
          background-color: alpha(#2f80ed, 0.26);
          border-color: #2f80ed;
        }
        .icon-tile { padding: 4px; }
        .favorite-star { padding: 0 3px; min-width: 20px; min-height: 20px; }
        .icon-grid { background-color: shade(@theme_bg_color, 0.96); }
        .section-separator {
          background-color: alpha(@theme_fg_color, 0.14);
          min-height: 1px;
        }
        .icon-importer-root treeview.view header button { padding: 5px 7px; }
        .icon-importer-root scrollbar slider { min-width: 8px; min-height: 8px; }
        """
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _load_ui_state(self):
        cache = getattr(self.client, "cache", None)
        stored = cache.get_setting("ui_state", {}) if cache is not None else {}
        if not isinstance(stored, dict):
            return {"filters": {}, "collections": {}, "favorites": {"sections": []}}
        state = dict(stored)
        if not isinstance(state.get("filters"), dict):
            state["filters"] = {}
        if not isinstance(state.get("collections"), dict):
            state["collections"] = {}
        state["favorites"] = normalize_favorites(state.get("favorites"))
        return state

    def _state_int(self, key, default, minimum, maximum):
        try:
            value = int(round(float(self.ui_state.get(key, default))))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    @staticmethod
    def _active_id(combo):
        return combo.get_active_id() or "all"

    def _current_filter_state(self):
        icon_category = self._active_id(self.icon_category_combo)
        if icon_category == "all" and self.pending_icon_category != "all":
            icon_category = self.pending_icon_category
        return {
            "category": self._active_id(self.category_combo),
            "palette": self._active_id(self.palette_combo),
            "style": self._active_id(self.style_combo),
            "license": self._active_id(self.license_combo),
            "grid": self._active_id(self.grid_combo),
            "icon_category": icon_category,
            "similar": self.similar_check.get_active(),
            "aliases": self.aliases_check.get_active(),
            "hidden": self.hidden_check.get_active(),
        }

    def _save_ui_state(self):
        if self.restoring_state:
            return
        cache = getattr(self.client, "cache", None)
        if cache is None:
            return
        state = {
            "import_size": self.size_spin.get_value_as_int(),
            "result_limit": self.limit_spin.get_value_as_int(),
            "zoom": int(self.zoom_scale.get_value()),
            "filters": self._current_filter_state(),
            "collections": {
                "use_all": self.use_all_collections,
                "prefixes": sorted(self.selected_prefixes),
            },
            "favorites": normalize_favorites(self.favorites),
            "active_page": (
                self.sidebar_stack.get_visible_child_name()
                if hasattr(self, "sidebar_stack") else "filters"
            ),
        }
        self.ui_state = state
        cache.put_setting("ui_state", state)

    def _update_filter_marker(self):
        if not hasattr(self, "filters_page"):
            return
        filters = self._current_filter_state()
        active = (
            any(filters[key] != "all" for key in (
                "category", "palette", "style", "license", "grid",
                "icon_category",
            ))
            or not filters["similar"]
            or filters["aliases"]
            or filters["hidden"]
        )
        title = "Filters  •" if active else "Filters"
        self.sidebar_stack.child_set_property(
            self.filters_page, "title", title
        )

    def _on_filter_changed(self, *_args):
        if self.restoring_state:
            return
        self.pending_icon_category = "all"
        self._update_filter_marker()
        self._save_ui_state()
        self._queue_search()

    def _on_import_size_changed(self, *_args):
        self._save_ui_state()
    def _build_ui(self):
        content = self.get_content_area()
        content.set_spacing(0)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(18)
        root.get_style_context().add_class("icon-importer-root")
        content.pack_start(root, True, True, 0)
        self.root_context = root.get_style_context()

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        brand = self._brand_image(52)
        brand.set_valign(Gtk.Align.CENTER)
        header.pack_start(brand, False, False, 0)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label="Iconify Search")
        title.set_xalign(0)
        title.get_style_context().add_class("icon-title")
        subtitle = Gtk.Label(
            label="Browse open-source icon collections and import clean SVG or PNG"
        )
        subtitle.set_xalign(0)
        subtitle.get_style_context().add_class("dim-label")
        title_box.pack_start(title, False, False, 0)
        title_box.pack_start(subtitle, False, False, 0)
        header.pack_start(title_box, True, True, 0)
        self.theme_toggle = Gtk.ToggleButton()
        self.theme_toggle.set_size_request(40, 40)
        self.theme_toggle.set_valign(Gtk.Align.CENTER)
        prefer_dark = self._load_theme_preference()
        self.theme_toggle.set_active(prefer_dark)
        self.theme_toggle.connect("toggled", self._on_theme_toggled)
        header.pack_end(self.theme_toggle, False, False, 0)
        root.pack_start(header, False, False, 0)
        self._apply_theme(prefer_dark, refresh=False)

        search_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_card.set_border_width(10)
        search_card.get_style_context().add_class("card")
        search_card.get_style_context().add_class("search-card")
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(
            "Search icons — try arrow, camera, user, chart…"
        )
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._queue_search, True)
        search_card.pack_start(self.search_entry, True, True, 0)
        search_button = Gtk.Button(label="Search")
        search_button.set_size_request(92, -1)
        search_button.get_style_context().add_class("primary-action")
        search_button.connect("clicked", self._queue_search, True)
        search_card.pack_start(search_button, False, False, 0)
        root.pack_start(search_card, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        body.pack_start(self._build_filter_sidebar(), False, False, 0)
        body.pack_start(self._build_results_panel(), True, True, 0)
        body.pack_start(self._build_import_sidebar(), False, False, 0)
        root.pack_start(body, True, True, 0)
    def _build_filter_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(340, -1)
        sidebar.get_style_context().add_class("card")

        self.sidebar_stack = Gtk.Stack()
        self.sidebar_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.sidebar_stack.set_transition_duration(140)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.sidebar_stack)
        switcher.set_homogeneous(True)
        switcher.set_halign(Gtk.Align.FILL)
        switcher.set_hexpand(True)
        switcher.get_style_context().add_class("side-tabs")
        sidebar.pack_start(switcher, False, False, 0)
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("section-separator")
        sidebar.pack_start(separator, False, False, 0)

        self.collections_page = self._build_collections_page()
        self.filters_page = self._build_filters_page()
        self.favorites_page = self._build_favorites_page()
        self.sidebar_stack.add_titled(
            self.collections_page, "collections", "Collections"
        )
        self.sidebar_stack.add_titled(
            self.filters_page, "filters", "Filters"
        )
        self.sidebar_stack.add_titled(
            self.favorites_page, "favorites", "Favorites"
        )
        self.sidebar_stack.set_visible_child_name("filters")
        self.sidebar_stack.connect(
            "notify::visible-child-name", self._on_sidebar_page_changed
        )
        sidebar.pack_start(self.sidebar_stack, True, True, 0)
        self._update_filter_marker()
        self._update_favorites_marker()
        return sidebar

    def _build_collections_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(12)
        self.catalog_label = Gtk.Label(label="Loading icon collections…")
        self.catalog_label.set_xalign(0)
        self.catalog_label.get_style_context().add_class("section-title")
        page.pack_start(self.catalog_label, False, False, 0)

        self.collection_search = Gtk.SearchEntry()
        self.collection_search.set_placeholder_text("Find a collection")
        self.collection_search.connect(
            "search-changed", self._refilter_collections
        )
        page.pack_start(self.collection_search, False, False, 0)

        self.collection_store = Gtk.ListStore(
            bool, str, str, int, str, bool, str, int
        )
        self.collection_filter = self.collection_store.filter_new()
        self.collection_filter.set_visible_func(self._collection_visible)
        self.collection_tree = Gtk.TreeView(model=self.collection_filter)
        self.collection_tree.set_tooltip_column(self.COL_NAME)
        self.collection_tree.set_enable_search(False)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_collection_toggled)
        use_column = Gtk.TreeViewColumn("Use", toggle, active=self.COL_ACTIVE)
        use_column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.collection_tree.append_column(use_column)
        name_renderer = Gtk.CellRendererText()
        name_renderer.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
        name_renderer.set_property("wrap-width", 215)
        name_column = Gtk.TreeViewColumn(
            "Collection", name_renderer, text=self.COL_NAME
        )
        name_column.set_expand(True)
        name_column.set_resizable(True)
        name_column.set_min_width(205)
        self.collection_tree.append_column(name_column)
        count_renderer = Gtk.CellRendererText()
        count_renderer.set_property("xalign", 1.0)
        count_column = Gtk.TreeViewColumn(
            "Icons", count_renderer, text=self.COL_TOTAL
        )
        count_column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        self.collection_tree.append_column(count_column)
        collection_scroll = Gtk.ScrolledWindow()
        collection_scroll.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        collection_scroll.set_shadow_type(Gtk.ShadowType.IN)
        collection_scroll.add(self.collection_tree)
        page.pack_start(collection_scroll, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, callback, tooltip in (
            ("All", self._use_all, "Search every collection"),
            ("Visible", self._select_visible, "Select collections visible above"),
            ("None", self._clear_collections, "Clear all collection selections"),
        ):
            button = Gtk.Button(label=label)
            button.set_tooltip_text(tooltip)
            button.connect("clicked", callback)
            actions.pack_start(button, True, True, 0)
        page.pack_start(actions, False, False, 0)
        return page

    def _build_filters_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(12)
        heading = Gtk.Label(label="Refine results")
        heading.set_xalign(0)
        heading.get_style_context().add_class("section-title")
        page.pack_start(heading, False, False, 0)
        help_label = Gtk.Label(
            label="Collection filters are applied before searching Iconify."
        )
        help_label.set_xalign(0)
        help_label.set_line_wrap(True)
        help_label.get_style_context().add_class("dim-label")
        page.pack_start(help_label, False, False, 0)

        filters_state = self.ui_state.get("filters", {})
        self.category_combo = self._combo("All collection categories")
        self.palette_combo = self._fixed_combo((
            ("all", "All palettes"),
            ("mono", "Monotone"),
            ("color", "Multicolor"),
        ))
        self.style_combo = self._fixed_combo((
            ("all", "All icon styles"),
            ("stroke", "Outline / stroke"),
            ("fill", "Filled / solid"),
            ("mixed", "Mixed fill + stroke"),
            ("color", "Multicolor"),
        ))
        self.license_combo = self._combo("All licenses")
        self.grid_combo = self._combo("All grid sizes")
        self.icon_category_combo = self._combo("All icon categories")
        self.icon_category_combo.set_sensitive(False)
        self.palette_combo.set_active_id(
            str(filters_state.get("palette", "all"))
        )
        self.style_combo.set_active_id(
            str(filters_state.get("style", "all"))
        )
        fields = (
            ("Collection category", self.category_combo),
            ("Palette", self.palette_combo),
            ("Icon style", self.style_combo),
            ("License", self.license_combo),
            ("Grid", self.grid_combo),
            ("Icon category", self.icon_category_combo),
        )
        for label, widget in fields:
            widget.set_hexpand(True)
            widget.connect("changed", self._on_filter_changed)
            page.pack_start(self._field(label, widget), False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.get_style_context().add_class("section-separator")
        page.pack_start(separator, False, False, 2)
        self.similar_check = Gtk.CheckButton(label="Include similar names")
        self.similar_check.set_active(bool(filters_state.get("similar", True)))
        self.aliases_check = Gtk.CheckButton(
            label="Include aliases when browsing"
        )
        self.aliases_check.set_active(bool(filters_state.get("aliases", False)))
        self.hidden_check = Gtk.CheckButton(
            label="Include hidden legacy icons"
        )
        self.hidden_check.set_active(bool(filters_state.get("hidden", False)))
        for check in (
            self.similar_check,
            self.aliases_check,
            self.hidden_check,
        ):
            check.connect("toggled", self._on_filter_changed)
            page.pack_start(check, False, False, 0)

        pagination = Gtk.Grid(column_spacing=8, row_spacing=8)
        self.limit_spin = Gtk.SpinButton.new_with_range(32, 999, 8)
        self.limit_spin.set_value(
            self._state_int("result_limit", 120, 32, 999)
        )
        self.limit_spin.connect("value-changed", self._on_limit_changed)
        self.start_spin = Gtk.SpinButton.new_with_range(
            0, max(0, self.limit_spin.get_value_as_int() - 1), 1
        )
        self.start_spin.connect("value-changed", self._queue_search)
        pagination.attach(self._label("Result limit"), 0, 0, 1, 1)
        pagination.attach(self.limit_spin, 1, 0, 1, 1)
        pagination.attach(self._label("Start offset"), 0, 1, 1, 1)
        pagination.attach(self.start_spin, 1, 1, 1, 1)
        page.pack_start(pagination, False, False, 0)
        self._setup_completion()
        scroll.add_with_viewport(page)
        return scroll

    def _build_favorites_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.favorites_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10
        )
        self.favorites_box.set_border_width(12)
        scroll.add(self.favorites_box)
        self._render_favorites_page()
        return scroll

    def _render_favorites_page(self):
        if not hasattr(self, "favorites_box"):
            return
        for child in self.favorites_box.get_children():
            self.favorites_box.remove(child)

        heading = Gtk.Label(label="Favorite icons")
        heading.set_xalign(0)
        heading.get_style_context().add_class("section-title")
        self.favorites_box.pack_start(heading, False, False, 0)

        help_label = Gtk.Label(
            label="Use the star on any search result to add it to a section."
        )
        help_label.set_xalign(0)
        help_label.set_line_wrap(True)
        help_label.get_style_context().add_class("dim-label")
        self.favorites_box.pack_start(help_label, False, False, 0)

        sections = self.favorites["sections"]
        if not sections:
            empty = Gtk.Label(label="No favorites saved yet")
            empty.set_xalign(0)
            empty.set_margin_top(8)
            empty.get_style_context().add_class("dim-label")
            self.favorites_box.pack_start(empty, False, False, 0)

        for section in sections:
            expander = Gtk.Expander(
                label=f'{section["name"]}  ({len(section["icons"])})'
            )
            expander.set_expanded(section["id"] in self.open_favorite_sections)
            expander.connect(
                "notify::expanded", self._on_favorite_expanded, section["id"]
            )
            section_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=4
            )
            section_box.set_margin_start(8)
            section_box.set_margin_top(6)
            section_box.set_margin_bottom(6)

            if not section["icons"]:
                empty_section = Gtk.Label(label="This section is empty")
                empty_section.set_xalign(0)
                empty_section.get_style_context().add_class("dim-label")
                section_box.pack_start(empty_section, False, False, 4)

            for full_name in section["icons"]:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                open_button = Gtk.Button(label=full_name)
                open_button.set_relief(Gtk.ReliefStyle.NONE)
                open_button.set_halign(Gtk.Align.FILL)
                open_button.set_hexpand(True)
                open_button.get_child().set_xalign(0)
                open_button.set_tooltip_text("Show and select this icon")
                open_button.connect(
                    "clicked", self._open_favorite_icon, full_name
                )
                row.pack_start(open_button, True, True, 0)
                remove_button = Gtk.Button.new_from_icon_name(
                    "edit-delete-symbolic", Gtk.IconSize.MENU
                )
                remove_button.set_relief(Gtk.ReliefStyle.NONE)
                remove_button.set_tooltip_text("Remove this icon")
                remove_button.connect(
                    "clicked", self._remove_favorite_icon,
                    section["id"], full_name
                )
                row.pack_start(remove_button, False, False, 0)
                section_box.pack_start(row, False, False, 0)

            delete_button = Gtk.Button(label="Delete section")
            delete_button.set_halign(Gtk.Align.START)
            delete_button.set_margin_top(4)
            delete_button.connect(
                "clicked", self._delete_favorite_section,
                section["id"], section["name"]
            )
            section_box.pack_start(delete_button, False, False, 0)
            expander.add(section_box)
            self.favorites_box.pack_start(expander, False, False, 0)

        self.favorites_box.show_all()
        self._update_favorites_marker()

    def _on_sidebar_page_changed(self, *_args):
        self._save_ui_state()

    def _update_favorites_marker(self):
        if not hasattr(self, "favorites_page"):
            return
        count = icon_count(self.favorites)
        title = f"Favorites  {count}" if count else "Favorites"
        self.sidebar_stack.child_set_property(
            self.favorites_page, "title", title
        )

    def _on_favorite_expanded(self, expander, _property, section_id):
        if expander.get_expanded():
            self.open_favorite_sections.add(section_id)
        else:
            self.open_favorite_sections.discard(section_id)

    def _on_add_favorite_clicked(self, _button, icon):
        dialog = Gtk.Dialog(
            title="Add to favorites", transient_for=self,
            modal=True, destroy_with_parent=True
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        save_button = dialog.add_button("_Save", Gtk.ResponseType.OK)
        save_button.get_style_context().add_class("primary-action")
        content = dialog.get_content_area()
        content.set_border_width(16)
        content.set_spacing(10)

        prompt = Gtk.Label(label=f"Save {icon.full_name} in:")
        prompt.set_xalign(0)
        content.pack_start(prompt, False, False, 0)

        section_combo = Gtk.ComboBoxText()
        for section in self.favorites["sections"]:
            section_combo.append(section["id"], section["name"])
        if self.favorites["sections"]:
            section_combo.set_active(0)
        else:
            section_combo.set_sensitive(False)
        content.pack_start(section_combo, False, False, 0)

        separator = Gtk.Label(label="or create a new section")
        separator.set_xalign(0)
        separator.get_style_context().add_class("dim-label")
        content.pack_start(separator, False, False, 0)
        new_section = Gtk.Entry()
        new_section.set_placeholder_text("New section name")
        new_section.set_activates_default(True)
        content.pack_start(new_section, False, False, 0)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            section_name = new_section.get_text().strip()
            section_id = section_combo.get_active_id()
            if section_name:
                self.favorites, section_id = create_section(
                    self.favorites, section_name
                )
            if section_id:
                self.favorites = add_icon(
                    self.favorites, section_id, icon.full_name
                )
                self.open_favorite_sections.add(section_id)
                self._favorites_changed()
            else:
                warning = Gtk.MessageDialog(
                    transient_for=self, modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Enter a name for the new section.",
                )
                warning.run()
                warning.destroy()
        dialog.destroy()

    def _favorites_changed(self):
        self._save_ui_state()
        self._render_favorites_page()
        self._refresh_favorite_buttons()

    def _refresh_favorite_buttons(self):
        for full_name, buttons in tuple(self.favorite_buttons.items()):
            label = "★" if contains_icon(self.favorites, full_name) else "☆"
            live_buttons = []
            for button in buttons:
                if button.get_parent() is not None:
                    button.set_label(label)
                    live_buttons.append(button)
            if live_buttons:
                self.favorite_buttons[full_name] = live_buttons
            else:
                self.favorite_buttons.pop(full_name, None)

    def _remove_favorite_icon(self, _button, section_id, full_name):
        self.favorites = remove_icon(self.favorites, section_id, full_name)
        self.open_favorite_sections.add(section_id)
        self._favorites_changed()

    def _delete_favorite_section(self, _button, section_id, section_name):
        confirm = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.CANCEL,
            text=f'Delete the section “{section_name}”?',
        )
        confirm.add_button("_Delete", Gtk.ResponseType.OK)
        response = confirm.run()
        confirm.destroy()
        if response == Gtk.ResponseType.OK:
            self.favorites = remove_section(self.favorites, section_id)
            self.open_favorite_sections.discard(section_id)
            self._favorites_changed()

    def _open_favorite_icon(self, _button, full_name):
        if ":" not in full_name:
            return
        prefix, name = full_name.split(":", 1)
        collection = self.collections_by_prefix.get(prefix)
        if collection is None:
            collection = CollectionInfo(prefix=prefix, name=prefix)
        icon = IconInfo(full_name, prefix, name, collection)
        self.search_serial += 1
        serial = self.search_serial
        result = SearchResult((icon,), 1, 0, 120, {prefix: collection})
        self._render_results(result, serial)
        children = self.flowbox.get_children()
        if children:
            self.flowbox.select_child(children[0])

    @staticmethod
    def _field(label_text, widget):
        field = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.get_style_context().add_class("field-label")
        field.pack_start(label, False, False, 0)
        field.pack_start(widget, False, False, 0)
        return field
    def _build_results_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel.set_size_request(500, -1)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Icons")
        title.set_xalign(0)
        title.get_style_context().add_class("section-title")
        header.pack_start(title, False, False, 0)
        self.selection_label = Gtk.Label(label="No icons selected")
        self.selection_label.set_xalign(0)
        self.selection_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.selection_label.get_style_context().add_class("accent-label")
        self.selection_label.get_style_context().add_class("selection-summary")
        self.selection_label.set_width_chars(18)
        self.selection_label.set_max_width_chars(24)
        header.pack_start(self.selection_label, True, True, 4)
        self.clear_selection_button = Gtk.Button(label="Clear selection")
        self.clear_selection_button.set_sensitive(False)
        self.clear_selection_button.set_tooltip_text(
            "Deselect every selected icon"
        )
        self.clear_selection_button.connect(
            "clicked", self._clear_icon_selection
        )
        header.pack_end(self.clear_selection_button, False, False, 0)
        self.zoom_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 32, 128, 8
        )
        self.zoom_scale.set_value(
            self._state_int("zoom", 64, 32, 128)
        )
        self.zoom_scale.set_draw_value(False)
        self.zoom_scale.set_size_request(150, -1)
        self.zoom_scale.set_tooltip_text("Change icon preview size")
        self.zoom_scale.connect("value-changed", self._on_zoom_changed)
        header.pack_end(self.zoom_scale, False, False, 0)
        zoom_label = Gtk.Label(label="Zoom")
        zoom_label.get_style_context().add_class("dim-label")
        header.pack_end(zoom_label, False, False, 0)
        panel.pack_start(header, False, False, 0)

        overlay = Gtk.Overlay()
        overlay.get_style_context().add_class("card")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_activate_on_single_click(False)
        self.flowbox.set_row_spacing(4)
        self.flowbox.set_column_spacing(4)
        self.flowbox.set_border_width(0)
        self.flowbox.set_min_children_per_line(3)
        self.flowbox.set_max_children_per_line(12)
        self.flowbox.get_style_context().add_class("icon-grid")
        self.flowbox.connect(
            "selected-children-changed", self._on_selection_changed
        )
        self.flowbox.connect("child-activated", self._on_child_activated)
        scroll.add(self.flowbox)
        overlay.add(scroll)
        self.empty_state = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8
        )
        self.empty_state.set_halign(Gtk.Align.CENTER)
        self.empty_state.set_valign(Gtk.Align.CENTER)
        empty_icon = Gtk.Image.new_from_icon_name(
            "system-search-symbolic", Gtk.IconSize.DIALOG
        )
        empty_title = Gtk.Label()
        empty_title.set_markup("<b>Search the Iconify catalog</b>")
        empty_help = Gtk.Label(
            label="Type at least two characters, or select one collection to browse."
        )
        empty_help.get_style_context().add_class("dim-label")
        self.empty_state.pack_start(empty_icon, False, False, 0)
        self.empty_state.pack_start(empty_title, False, False, 0)
        self.empty_state.pack_start(empty_help, False, False, 0)
        overlay.add_overlay(self.empty_state)
        overlay.set_overlay_pass_through(self.empty_state, True)
        panel.pack_start(overlay, True, True, 0)

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.status_label = Gtk.Label(label="Loading Iconify collections…")
        self.status_label.set_xalign(0)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.status_label.get_style_context().add_class("dim-label")
        status.pack_start(self.spinner, False, False, 0)
        status.pack_start(self.status_label, True, True, 0)
        panel.pack_start(status, False, False, 0)
        return panel

    def _build_import_sidebar(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.set_size_request(290, -1)
        card.set_hexpand(False)
        card.get_style_context().add_class("card")
        options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        options.set_border_width(18)
        card.pack_start(options, True, True, 0)
        heading = Gtk.Label(label="Import")
        heading.set_xalign(0)
        heading.get_style_context().add_class("section-title")
        options.pack_start(heading, False, False, 0)
        hint = Gtk.Label(label="Options apply to every selected icon.")
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        hint.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        hint.set_width_chars(30)
        hint.set_max_width_chars(30)
        hint.get_style_context().add_class("dim-label")
        options.pack_start(hint, False, False, 0)

        format_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        svg_label = Gtk.Label(label="SVG")
        format_box.pack_start(svg_label, False, False, 0)
        self.format_switch = Gtk.Switch()
        self.format_switch.set_valign(Gtk.Align.CENTER)
        self.format_switch.connect(
            "notify::active", self._update_format_controls
        )
        format_box.pack_start(self.format_switch, False, False, 0)
        format_box.pack_start(Gtk.Label(label="PNG"), False, False, 0)

        self.png_spin = Gtk.SpinButton.new_with_range(16, 4096, 16)
        self.png_spin.set_value(256)
        self.png_spin.set_width_chars(4)
        self.png_spin.set_max_width_chars(5)
        self.png_label = Gtk.Label(label="PNG resolution")
        self.png_label.set_xalign(0)
        self.png_label.get_style_context().add_class("field-label")
        self.png_box = self._unit_box(self.png_spin, "px")
        png_field = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        png_field.pack_start(self.png_label, False, False, 0)
        png_field.pack_start(self.png_box, False, False, 0)

        format_grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        format_grid.set_column_homogeneous(True)
        format_grid.attach(self._field("Format", format_box), 0, 0, 1, 1)
        format_grid.attach(png_field, 1, 0, 1, 1)
        options.pack_start(format_grid, False, False, 0)

        self.size_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        self.size_spin.set_value(
            self._state_int("import_size", 48, 1, 4096)
        )
        self.size_spin.set_width_chars(4)
        self.size_spin.set_max_width_chars(5)
        self.size_spin.connect("value-changed", self._on_import_size_changed)

        self.color_button = Gtk.ColorButton()
        color = Gdk.RGBA()
        if not color.parse(self._load_color_preference()):
            color.parse("#111827")
        self.color_button.set_rgba(color)
        self.color_button.set_hexpand(True)
        self.color_button.set_size_request(-1, 36)
        self.color_button.connect("color-set", self._on_color_changed)

        appearance_grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        appearance_grid.set_column_homogeneous(True)
        appearance_grid.attach(
            self._field("Import size", self._unit_box(self.size_spin, "px")),
            0, 0, 1, 1,
        )
        appearance_grid.attach(
            self._field("Icon color", self.color_button), 1, 0, 1, 1
        )
        options.pack_start(appearance_grid, False, False, 0)

        self.stroke_spin = Gtk.SpinButton.new_with_range(10, 400, 5)
        self.stroke_spin.set_value(100)
        options.pack_start(
            self._field(
                "Stroke scale", self._unit_box(self.stroke_spin, "%")
            ),
            False,
            False,
            0,
        )
        self.preserve_check = Gtk.CheckButton(
            label="Preserve original colors"
        )
        self.preserve_check.connect("toggled", self._on_preserve_toggled)
        options.pack_start(self.preserve_check, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(4)
        separator.get_style_context().add_class("section-separator")
        options.pack_start(separator, False, False, 0)
        label = Gtk.Label(label="Source and license")
        label.set_xalign(0)
        label.get_style_context().add_class("subsection-title")
        options.pack_start(label, False, False, 0)
        self.license_label = Gtk.Label(
            label="Select an icon to see license details."
        )
        self.license_label.set_xalign(0)
        self.license_label.set_yalign(0)
        self.license_label.set_line_wrap(True)
        self.license_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.license_label.set_width_chars(30)
        self.license_label.set_max_width_chars(30)
        self.license_label.set_selectable(True)
        self.license_label.get_style_context().add_class("dim-label")
        options.pack_start(self.license_label, False, False, 0)
        return card
    @staticmethod
    def _label(text):
        label = Gtk.Label(label=text); label.set_xalign(0); return label

    @staticmethod
    def _unit_box(widget, unit):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.pack_start(widget, True, True, 0)
        box.pack_start(Gtk.Label(label=unit), False, False, 0)
        return box

    @staticmethod
    def _combo(label):
        combo = Gtk.ComboBoxText(); combo.append("all", label); combo.set_active_id("all")
        return combo

    @staticmethod
    def _fixed_combo(items):
        combo = Gtk.ComboBoxText()
        for item_id, label in items: combo.append(item_id, label)
        combo.set_active_id("all")
        return combo

    def _setup_completion(self):
        self.suggestion_store = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion()
        completion.set_model(self.suggestion_store)
        completion.set_text_column(0)
        completion.set_minimum_key_length(2)
        self.search_entry.set_completion(completion)

    def _load_catalog(self):
        self.catalog_serial += 1
        serial = self.catalog_serial
        self.spinner.start()
        future = self.executor.submit(self.client.list_collections)
        future.add_done_callback(
            lambda item: GLib.idle_add(self._finish_catalog, serial, item)
        )

    def _finish_catalog(self, serial, future):
        if self.closed or serial != self.catalog_serial:
            return False
        previous_restoring = self.restoring_state
        self.restoring_state = True
        try:
            self.collections = future.result()
        except Exception as exc:
            self.spinner.stop()
            self.catalog_label.set_text("Collections unavailable")
            self.status_label.set_text(str(exc))
            self.restoring_state = previous_restoring
            self._update_filter_marker()
            return False
        self.spinner.stop()
        self.collections_by_prefix = {
            item.prefix: item for item in self.collections
        }
        if self.use_all_collections:
            self.selected_prefixes.clear()
        else:
            self.selected_prefixes.intersection_update(
                self.collections_by_prefix
            )
        self.collection_store.clear()
        self.collection_store.append([
            self.use_all_collections,
            f"All collections ({len(self.collections)})",
            "",
            sum(item.total for item in self.collections),
            "",
            False,
            "",
            0,
        ])
        for item in self.collections:
            self.collection_store.append([
                item.prefix in self.selected_prefixes,
                f"{item.name}  [{item.prefix}]",
                item.prefix,
                item.total,
                item.category,
                item.palette,
                item.license_spdx or item.license_title,
                item.height,
            ])
        self.catalog_label.set_text(
            f"Icon collections ({len(self.collections)})"
        )
        categories = sorted(
            {item.category for item in self.collections}, key=str.casefold
        )
        licenses = sorted({
            item.license_spdx or item.license_title
            for item in self.collections
        } - {""}, key=str.casefold)
        heights = sorted({
            item.height for item in self.collections if item.height
        })
        self._replace_combo(
            self.category_combo, "All collection categories", categories
        )
        self._replace_combo(self.license_combo, "All licenses", licenses)
        self._replace_combo(
            self.grid_combo,
            "All grid sizes",
            (f"{height}px" for height in heights),
            ids=(str(height) for height in heights),
        )
        filters = self.ui_state.get("filters", {})
        for combo, key in (
            (self.category_combo, "category"),
            (self.license_combo, "license"),
            (self.grid_combo, "grid"),
        ):
            combo.set_active_id(str(filters.get(key, "all")))
            if combo.get_active_id() is None:
                combo.set_active_id("all")
        self.restoring_state = previous_restoring
        self._sync_collection_checks()
        self._update_filter_marker()
        self._selection_filters_changed(restore_icon_category=True)
        return False
    @staticmethod
    def _replace_combo(combo, all_label, values, ids=None):
        values = tuple(values)
        item_ids = tuple(ids) if ids is not None else values
        combo.remove_all()
        combo.append("all", all_label)
        for item_id, value in zip(item_ids, values):
            combo.append(str(item_id), str(value))
        combo.set_active_id("all")

    def _collection_visible(self, model, tree_iter, _data):
        prefix = model.get_value(tree_iter, self.COL_PREFIX)
        if not prefix:
            return True
        query = self.collection_search.get_text().strip().casefold()
        name = model.get_value(tree_iter, self.COL_NAME).casefold()
        return not query or query in name

    def _refilter_collections(self, *_args):
        self.collection_filter.refilter()

    def _on_collection_toggled(self, _renderer, path_string):
        filtered_path = Gtk.TreePath.new_from_string(path_string)
        child_path = self.collection_filter.convert_path_to_child_path(filtered_path)
        tree_iter = self.collection_store.get_iter(child_path)
        prefix = self.collection_store.get_value(tree_iter, self.COL_PREFIX)
        if not prefix:
            self.use_all_collections = True
            self.selected_prefixes.clear()
        else:
            self.use_all_collections = False
            if prefix in self.selected_prefixes:
                self.selected_prefixes.remove(prefix)
            else:
                self.selected_prefixes.add(prefix)
        self._sync_collection_checks()
        self._selection_filters_changed()

    def _sync_collection_checks(self):
        for row in self.collection_store:
            prefix = row[self.COL_PREFIX]
            row[self.COL_ACTIVE] = (
                self.use_all_collections if not prefix
                else prefix in self.selected_prefixes
            )

    def _use_all(self, *_args):
        self.use_all_collections = True
        self.selected_prefixes.clear()
        self._sync_collection_checks()
        self._selection_filters_changed()

    def _select_visible(self, *_args):
        visible = {
            row[self.COL_PREFIX] for row in self.collection_filter
            if row[self.COL_PREFIX]
        }
        if visible:
            self.use_all_collections = False
            self.selected_prefixes = visible
            self._sync_collection_checks()
            self._selection_filters_changed()

    def _clear_collections(self, *_args):
        self.use_all_collections = False
        self.selected_prefixes.clear()
        self._sync_collection_checks()
        self._selection_filters_changed()

    def _selection_filters_changed(self, restore_icon_category=False):
        if not restore_icon_category:
            self.pending_icon_category = "all"
        previous_restoring = self.restoring_state
        self.restoring_state = True
        self.collection_browse = None
        self._replace_combo(
            self.icon_category_combo, "All icon categories", ()
        )
        self.icon_category_combo.set_sensitive(False)
        self.restoring_state = previous_restoring

        one_selected = (
            not self.use_all_collections
            and len(self.selected_prefixes) == 1
        )
        if one_selected:
            prefix = next(iter(self.selected_prefixes))
            future = self.executor.submit(
                self.client.browse_collection, prefix, True
            )
            future.add_done_callback(
                lambda item: GLib.idle_add(
                    self._finish_icon_categories, prefix, item
                )
            )
        else:
            self.pending_icon_category = "all"
        self._update_filter_marker()
        self._save_ui_state()
        self._queue_search(immediate=True)

    def _finish_icon_categories(self, prefix, future):
        if self.closed or prefix not in self.selected_prefixes:
            return False
        try:
            self.collection_browse = future.result()
        except Exception:
            return False
        categories = sorted(
            self.collection_browse.categories, key=str.casefold
        )
        previous_restoring = self.restoring_state
        self.restoring_state = True
        self._replace_combo(
            self.icon_category_combo, "All icon categories", categories
        )
        self.icon_category_combo.set_sensitive(bool(categories))
        self.icon_category_combo.set_active_id(self.pending_icon_category)
        if self.icon_category_combo.get_active_id() is None:
            self.icon_category_combo.set_active_id("all")
        self.pending_icon_category = "all"
        self.restoring_state = previous_restoring
        self._update_filter_marker()
        self._save_ui_state()
        self._queue_search(immediate=True)
        return False
    def _on_search_changed(self, *_args):
        self._queue_search()
        if self.suggestion_timer is not None:
            GLib.source_remove(self.suggestion_timer)
        self.suggestion_timer = GLib.timeout_add(250, self._start_suggestions)

    def _start_suggestions(self):
        self.suggestion_timer = None
        text = self.search_entry.get_text().strip()
        if len(text) < 2 or " " in text:
            self.suggestion_store.clear()
            return False
        self.suggestion_serial += 1
        serial = self.suggestion_serial
        future = self.executor.submit(self.client.suggest_keywords, text, False)
        future.add_done_callback(
            lambda item: GLib.idle_add(self._finish_suggestions, serial, item)
        )
        return False

    def _finish_suggestions(self, serial, future):
        if self.closed or serial != self.suggestion_serial:
            return False
        self.suggestion_store.clear()
        try:
            suggestions = future.result()
        except Exception:
            return False
        for suggestion in suggestions[:20]:
            self.suggestion_store.append([suggestion])
        return False

    def _on_limit_changed(self, *_args):
        limit = self.limit_spin.get_value_as_int()
        self.start_spin.set_range(0, max(0, limit - 1))
        if self.start_spin.get_value_as_int() >= limit:
            self.start_spin.set_value(0)
        self._save_ui_state()
        self._queue_search()

    def _effective_prefixes(self):
        category = self.category_combo.get_active_id() or "all"
        palette = self.palette_combo.get_active_id() or "all"
        license_name = self.license_combo.get_active_id() or "all"
        grid = self.grid_combo.get_active_id() or "all"
        if not self.collections:
            return None, None
        candidates = list(self.collections) if self.use_all_collections else [
            self.collections_by_prefix[prefix] for prefix in self.selected_prefixes
            if prefix in self.collections_by_prefix
        ]
        if category != "all":
            candidates = [item for item in candidates if item.category == category]
        if palette == "mono":
            candidates = [item for item in candidates if not item.palette]
        elif palette == "color":
            candidates = [item for item in candidates if item.palette]
        if license_name != "all":
            candidates = [item for item in candidates if (
                item.license_spdx or item.license_title
            ) == license_name]
        if grid != "all":
            candidates = [item for item in candidates if item.height == int(grid)]
        only_api_category = (
            self.use_all_collections and category != "all"
            and palette == license_name == grid == "all"
        )
        if only_api_category:
            return None, category
        if self.use_all_collections and len(candidates) == len(self.collections):
            return None, None
        return tuple(item.prefix for item in candidates), None

    def _queue_search(self, *_args, immediate=False):
        immediate = immediate or bool(_args and _args[-1] is True)
        if self.search_timer is not None:
            GLib.source_remove(self.search_timer)
        self.search_timer = GLib.timeout_add(
            1 if immediate else 400, self._start_search
        )

    def _start_search(self):
        self.search_timer = None
        query = self.search_entry.get_text().strip()
        prefixes, api_category = self._effective_prefixes()
        if prefixes == ():
            self.spinner.stop()
            self._clear_results()
            self.status_label.set_text("No collections match the selected filters.")
            return False
        one_selected = not self.use_all_collections and len(self.selected_prefixes) == 1
        if len(query) < 2 and not one_selected:
            self.spinner.stop()
            self._clear_results()
            self.status_label.set_text(
                "Type two characters, or select one collection to browse it."
            )
            return False
        self.search_serial += 1
        serial = self.search_serial
        self.spinner.start()
        self.status_label.set_text("Searching Iconify…")
        spec = {
            "query": query, "prefixes": prefixes, "category": api_category,
            "limit": self.limit_spin.get_value_as_int(),
            "start": self.start_spin.get_value_as_int(),
            "similar": self.similar_check.get_active(),
            "icon_category": self.icon_category_combo.get_active_id() or "all",
            "aliases": self.aliases_check.get_active(),
            "hidden": self.hidden_check.get_active(),
            "one_prefix": next(iter(self.selected_prefixes)) if one_selected else None,
        }
        future = self.executor.submit(self._perform_search, spec)
        future.add_done_callback(
            lambda item: GLib.idle_add(self._finish_search, serial, item)
        )
        return False

    def _perform_search(self, spec):
        query, prefix = spec["query"], spec["one_prefix"]
        category = spec["icon_category"]
        if len(query) < 2 and prefix:
            browse = self.client.browse_collection(prefix, True)
            names = list(browse.categories.get(category, ())) \
                if category != "all" else list(browse.icons)
            if len(query) == 1:
                char_name = browse.chars.get(format(ord(query), "x"))
                names = [char_name] if char_name else []
            if spec["aliases"]:
                names.extend(browse.aliases)
            if spec["hidden"]:
                names.extend(browse.hidden)
            names = list(dict.fromkeys(name for name in names if name))
            total, start = len(names), spec["start"]
            names = names[start:start + spec["limit"]]
            collection = self.collections_by_prefix.get(
                prefix, CollectionInfo(prefix, prefix)
            )
            icons = tuple(IconInfo(
                f"{prefix}:{name}", prefix, name, collection
            ) for name in names)
            return SearchResult(
                icons, total, start, spec["limit"], {prefix: collection}
            )
        result = self.client.search(
            query, limit=spec["limit"], start=spec["start"],
            prefixes=spec["prefixes"], category=spec["category"],
            similar=spec["similar"],
        )
        if prefix and category != "all":
            browse = self.client.browse_collection(prefix, False)
            allowed = set(browse.categories.get(category, ()))
            icons = tuple(icon for icon in result.icons if icon.name in allowed)
            return SearchResult(
                icons, len(icons), result.start, result.limit, result.collections
            )
        return result

    def _finish_search(self, serial, future):
        if self.closed or serial != self.search_serial:
            return False
        self.spinner.stop()
        try:
            result = future.result()
        except Exception as exc:
            self._clear_results()
            self.status_label.set_text(str(exc))
            return False
        self._render_results(result, serial)
        return False

    def _render_results(self, result, serial):
        self._clear_results()
        self.visible_result_count = len(result.icons)
        suffix = "+" if result.total >= result.limit else ""
        self.status_label.set_text(
            f"{len(result.icons)} shown · {result.total}{suffix} matches"
        )
        if result.icons:
            self.empty_state.hide()
        else:
            self.empty_state.show_all()
        preview_size = int(self.zoom_scale.get_value())
        for icon in result.icons:
            child = Gtk.FlowBoxChild()
            child.icon_info = icon
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            tile.set_border_width(2)
            tile.get_style_context().add_class("icon-tile")
            image = Gtk.Image()
            image.set_size_request(preview_size, preview_size)
            image.original_pixbuf = None
            child.image_widget = image
            label = Gtk.Label(label=icon.name)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_width_chars(10)
            label.set_max_width_chars(10)
            label.set_tooltip_text(icon.full_name)
            tile.pack_start(image, True, True, 0)
            label_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=2
            )
            label_row.pack_start(label, True, True, 0)
            favorite_button = Gtk.Button(
                label="★" if contains_icon(self.favorites, icon.full_name)
                else "☆"
            )
            favorite_button.set_relief(Gtk.ReliefStyle.NONE)
            favorite_button.set_tooltip_text("Add to favorites")
            favorite_button.get_style_context().add_class("favorite-star")
            favorite_button.connect(
                "clicked", self._on_add_favorite_clicked, icon
            )
            self.favorite_buttons.setdefault(icon.full_name, []).append(
                favorite_button
            )
            label_row.pack_start(favorite_button, False, False, 0)
            tile.pack_start(label_row, False, False, 0)
            click_target = Gtk.EventBox()
            click_target.set_visible_window(False)
            click_target.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            click_target.connect(
                "button-press-event", self._on_icon_tile_clicked, child
            )
            click_target.add(tile)
            child.add(click_target)
            self.flowbox.add(child)
            color = None if icon.collection.palette else self._thumbnail_color()
            future = self.executor.submit(
                self.client.fetch_thumbnail,
                icon.full_name,
                max(128, preview_size),
                color,
            )
            future.add_done_callback(
                lambda item, row=child, info=icon: GLib.idle_add(
                    self._set_thumbnail, serial, row, info, item
                )
            )
        self.flowbox.show_all()
    def _set_thumbnail(self, serial, child, icon, future):
        if self.closed or serial != self.search_serial:
            return False
        try:
            svg_data = future.result()
            if not self._style_matches(icon, svg_data):
                child.hide()
                self.visible_result_count = max(0, self.visible_result_count - 1)
                self.status_label.set_text(
                    f"{self.visible_result_count} shown after style filtering"
                )
                return False
            loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
            loader.write(svg_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf is not None:
                child.image_widget.original_pixbuf = pixbuf
                child.image_widget.set_from_pixbuf(
                    self._scale_pixbuf(pixbuf, int(self.zoom_scale.get_value()))
                )
        except Exception:
            child.image_widget.set_from_icon_name(
                "image-missing", Gtk.IconSize.DIALOG
            )
        return False

    def _style_matches(self, icon, svg_data):
        wanted = self.style_combo.get_active_id() or "all"
        if wanted == "all":
            return True
        if wanted == "color":
            return icon.collection.palette
        if icon.collection.palette:
            return False
        return classify_svg_style(svg_data) == wanted

    @staticmethod
    def _scale_pixbuf(pixbuf, size):
        width, height = pixbuf.get_width(), pixbuf.get_height()
        if not width or not height:
            return pixbuf
        ratio = min(size / width, size / height)
        return pixbuf.scale_simple(
            max(1, int(width * ratio)),
            max(1, int(height * ratio)),
            GdkPixbuf.InterpType.BILINEAR,
        )

    def _on_zoom_changed(self, scale):
        size = int(scale.get_value())
        for child in self.flowbox.get_children():
            image = getattr(child, "image_widget", None)
            if image is None:
                continue
            image.set_size_request(size, size)
            pixbuf = getattr(image, "original_pixbuf", None)
            if pixbuf is not None:
                image.set_from_pixbuf(self._scale_pixbuf(pixbuf, size))
        self._save_ui_state()

    def _clear_results(self):
        self.selected_icon = None
        self.visible_result_count = 0
        self.favorite_buttons = {}
        self.flowbox.unselect_all()
        for child in self.flowbox.get_children():
            self.flowbox.remove(child)
        self.import_button.set_sensitive(False)
        self.clear_selection_button.set_sensitive(False)
        self.selection_label.set_text("No icons selected")
        self.selection_label.set_tooltip_text(None)
        self.license_label.set_markup("<small>No icon selected</small>")
        self.empty_state.show_all()

    def _on_icon_tile_clicked(self, _widget, event, child):
        if event.button != 1:
            return False
        if event.type == Gdk.EventType.BUTTON_PRESS:
            self._toggle_icon_selection(child)
        return True

    def _toggle_icon_selection(self, child):
        if child.is_selected():
            self.flowbox.unselect_child(child)
        else:
            self.flowbox.select_child(child)

    def _clear_icon_selection(self, *_args):
        self.flowbox.unselect_all()

    def _on_selection_changed(self, flowbox):
        selected = flowbox.get_selected_children()
        self.clear_selection_button.set_sensitive(bool(selected))
        if not selected:
            self.selected_icon = None
            self.import_button.set_sensitive(False)
            self.selection_label.set_text("No icons selected")
            self.selection_label.set_tooltip_text(None)
            self.license_label.set_markup("<small>No icon selected</small>")
            return
        self._show_selection(selected)

    def _on_child_activated(self, _flowbox, child):
        self._toggle_icon_selection(child)

    def _show_selection(self, children):
        icons = [
            child.icon_info for child in children
            if getattr(child, "icon_info", None) is not None
        ]
        if not icons:
            return
        self.selected_icon = icons[0]
        if len(icons) == 1:
            icon = icons[0]
            self.selection_label.set_text(icon.full_name)
            self.selection_label.set_tooltip_text(icon.full_name)
            collection = icon.collection
            license_name = (
                collection.license_spdx
                or collection.license_title
                or "Unknown"
            )
            details = f"{collection.name}\nLicense: {license_name}"
            if collection.license_url:
                details += f"\n{collection.license_url}"
            self.license_label.set_text(details)
        else:
            self.selection_label.set_text(f"{len(icons)} icons selected")
            self.selection_label.set_tooltip_text(
                "\n".join(icon.full_name for icon in icons)
            )
            self.license_label.set_text(
                f"{len(icons)} icons selected. Each imported object retains "
                "its collection license metadata."
            )
        self.import_button.set_sensitive(True)

    def _on_theme_toggled(self, button):
        dark = button.get_active()
        cache = getattr(self.client, "cache", None)
        if cache is not None:
            cache.put_setting("dark_theme", dark)
        self._apply_theme(dark, refresh=True)

    def _load_theme_preference(self):
        cache = getattr(self.client, "cache", None)
        if cache is not None:
            stored = cache.get_setting("dark_theme")
            if isinstance(stored, bool):
                return stored
        try:
            config_root = Path(
                os.environ.get("APPDATA") or (Path.home() / ".config")
            )
            preferences = config_root / "inkscape" / "preferences.xml"
            theme = ET.parse(preferences).getroot().find(".//*[@id='theme']")
            if theme is not None:
                value = theme.get(
                    "preferDarkTheme", theme.get("darkTheme")
                )
                if value is not None:
                    return value.strip().lower() in {"1", "true", "yes"}
        except (OSError, ET.ParseError):
            pass
        settings = Gtk.Settings.get_default()
        return bool(settings.get_property(
            "gtk-application-prefer-dark-theme"
        )) if settings else False

    def _apply_theme(self, dark, refresh):
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", dark)
        self.root_context.remove_class("icon-importer-light")
        self.root_context.remove_class("icon-importer-dark")
        self.root_context.add_class(
            "icon-importer-dark" if dark else "icon-importer-light"
        )
        icon_name = (
            "weather-clear-symbolic" if dark
            else "weather-clear-night-symbolic"
        )
        self.theme_toggle.set_image(
            Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        )
        self.theme_toggle.set_always_show_image(True)
        self.theme_toggle.set_tooltip_text(
            "Switch to light theme" if dark else "Switch to dark theme"
        )
        if refresh and hasattr(self, "flowbox") and self.flowbox.get_children():
            self._queue_search(immediate=True)
    def _thumbnail_color(self):
        return "#f4f7fb" if self.theme_toggle.get_active() else "#18202a"

    def _update_format_controls(self, *_args):
        is_png = self.format_switch.get_active()
        self.png_label.set_sensitive(is_png)
        self.png_box.set_sensitive(is_png)

    def _on_preserve_toggled(self, button):
        self.color_button.set_sensitive(not button.get_active())

    def _load_color_preference(self):
        cache = getattr(self.client, "cache", None)
        stored = cache.get_setting("icon_color") if cache is not None else None
        return stored if isinstance(stored, str) else "#111827"

    def _on_color_changed(self, *_args):
        cache = getattr(self.client, "cache", None)
        if cache is not None:
            cache.put_setting("icon_color", self._selected_color())

    def _selected_color(self):
        rgba = self.color_button.get_rgba()
        return "#{:02x}{:02x}{:02x}".format(
            round(rgba.red * 255),
            round(rgba.green * 255),
            round(rgba.blue * 255),
        )

    def run_and_get_choices(self):
        response = self.run()
        selected = self.flowbox.get_selected_children()
        if response != Gtk.ResponseType.OK or not selected:
            return ()
        color = self._selected_color()
        self._on_color_changed()
        return tuple(
            ImportChoice(
                icon=child.icon_info,
                import_format=(
                    "png" if self.format_switch.get_active() else "svg"
                ),
                size_px=self.size_spin.get_value(),
                png_pixels=self.png_spin.get_value_as_int(),
                color=color,
                stroke_scale=self.stroke_spin.get_value() / 100.0,
                preserve_colors=self.preserve_check.get_active(),
            )
            for child in selected
            if getattr(child, "icon_info", None) is not None
        )

    def _on_destroy(self, *_args):
        self._on_color_changed()
        self._save_ui_state()
        self.closed = True
        if self.search_timer is not None:
            GLib.source_remove(self.search_timer)
            self.search_timer = None
        self.executor.shutdown(wait=False)
