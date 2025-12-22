#!/usr/bin/env python3
"""
SimpleSlideshow - A simple GNOME wallpaper slideshow configurator.

Dependencies (Ubuntu/Debian):
    sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
"""

import gi
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import subprocess

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, Adw, Gio, Gdk, GdkPixbuf, GLib


APP_ID = "com.github.simpleslideshow"
APP_NAME = "SimpleSlideshow"

# Directories for GNOME wallpaper configuration
BACKGROUNDS_DIR = Path.home() / ".local/share/backgrounds/simpleslideshow"
PROPERTIES_DIR = Path.home() / ".local/share/gnome-background-properties"
SLIDESHOW_XML = BACKGROUNDS_DIR / "slideshow.xml"
PROPERTIES_XML = PROPERTIES_DIR / "simpleslideshow.xml"


class ImageRow(Gtk.Box):
    """A row displaying an image thumbnail with remove button."""

    def __init__(self, image_path: str, on_remove: callable, on_move_up: callable, on_move_down: callable):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.image_path = image_path
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        # Thumbnail
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(image_path, 80, 60, True)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            thumbnail = Gtk.Image.new_from_paintable(texture)
        except Exception:
            thumbnail = Gtk.Image.new_from_icon_name("image-missing")
            thumbnail.set_pixel_size(60)

        thumbnail.set_size_request(80, 60)
        self.append(thumbnail)

        # Filename label
        label = Gtk.Label(label=Path(image_path).name)
        label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        label.set_hexpand(True)
        label.set_xalign(0)
        self.append(label)

        # Move up button
        up_btn = Gtk.Button.new_from_icon_name("go-up-symbolic")
        up_btn.set_tooltip_text("Move up")
        up_btn.add_css_class("flat")
        up_btn.connect("clicked", lambda _: on_move_up(self))
        self.append(up_btn)

        # Move down button
        down_btn = Gtk.Button.new_from_icon_name("go-down-symbolic")
        down_btn.set_tooltip_text("Move down")
        down_btn.add_css_class("flat")
        down_btn.connect("clicked", lambda _: on_move_down(self))
        self.append(down_btn)

        # Remove button
        remove_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        remove_btn.set_tooltip_text("Remove")
        remove_btn.add_css_class("flat")
        remove_btn.connect("clicked", lambda _: on_remove(self))
        self.append(remove_btn)


class WallpapererWindow(Adw.ApplicationWindow):
    """Main application window."""

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(600, 850)
        self.set_size_request(500, 650)  # Minimum size

        self.image_rows: list[ImageRow] = []

        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Content box with margins
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        main_box.append(content)

        # Add images button
        add_btn = Gtk.Button(label="Add Images")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self.on_add_images)
        content.append(add_btn)

        # Images list in a scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(100)

        frame = Gtk.Frame()
        frame.set_child(scrolled)
        content.append(frame)

        self.images_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self.images_box)

        # Placeholder when no images
        self.placeholder = Gtk.Label(label="No images added yet")
        self.placeholder.add_css_class("dim-label")
        self.placeholder.set_margin_top(40)
        self.placeholder.set_margin_bottom(40)
        self.images_box.append(self.placeholder)

        # Settings group
        settings_group = Adw.PreferencesGroup(title="Slideshow Settings")
        content.append(settings_group)

        # Duration per image
        duration_row = Adw.ActionRow(title="Duration per image", subtitle="How long each image is displayed")
        self.duration_spin = Gtk.SpinButton.new_with_range(1, 999, 1)
        self.duration_spin.set_value(5)
        self.duration_spin.set_digits(0)
        self.duration_spin.set_valign(Gtk.Align.CENTER)
        duration_row.add_suffix(self.duration_spin)

        # Duration unit dropdown
        self.duration_unit = Gtk.DropDown.new_from_strings(["minutes", "hours", "days"])
        self.duration_unit.set_selected(0)
        self.duration_unit.set_valign(Gtk.Align.CENTER)
        duration_row.add_suffix(self.duration_unit)
        settings_group.add(duration_row)

        # Apply button
        self.apply_btn = Gtk.Button(label="Apply Wallpaper")
        self.apply_btn.add_css_class("suggested-action")
        self.apply_btn.add_css_class("pill")
        self.apply_btn.set_sensitive(False)
        self.apply_btn.connect("clicked", self.on_apply)
        content.append(self.apply_btn)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("dim-label")
        content.append(self.status_label)

    def on_add_images(self, button):
        """Open file chooser to add images."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Images")

        # Filter for images
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Images")
        filter_images.add_mime_type("image/jpeg")
        filter_images.add_mime_type("image/png")
        filter_images.add_mime_type("image/webp")
        filter_images.add_mime_type("image/bmp")
        filter_images.add_mime_type("image/gif")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_images)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_images)

        dialog.open_multiple(self, None, self.on_files_selected)

    def on_files_selected(self, dialog, result):
        """Handle selected files."""
        try:
            files = dialog.open_multiple_finish(result)
            for i in range(files.get_n_items()):
                file = files.get_item(i)
                path = file.get_path()
                if path:
                    self.add_image(path)
        except GLib.Error:
            pass  # User cancelled

    def add_image(self, path: str):
        """Add an image to the list."""
        # Remove placeholder if present
        if self.placeholder.get_parent():
            self.images_box.remove(self.placeholder)

        row = ImageRow(path, self.remove_image, self.move_image_up, self.move_image_down)
        self.image_rows.append(row)
        self.images_box.append(row)
        self.update_apply_button()

    def remove_image(self, row: ImageRow):
        """Remove an image from the list."""
        self.image_rows.remove(row)
        self.images_box.remove(row)

        if not self.image_rows:
            self.images_box.append(self.placeholder)

        self.update_apply_button()

    def move_image_up(self, row: ImageRow):
        """Move an image up in the list."""
        idx = self.image_rows.index(row)
        if idx > 0:
            self.image_rows.remove(row)
            self.image_rows.insert(idx - 1, row)
            self.rebuild_images_box()

    def move_image_down(self, row: ImageRow):
        """Move an image down in the list."""
        idx = self.image_rows.index(row)
        if idx < len(self.image_rows) - 1:
            self.image_rows.remove(row)
            self.image_rows.insert(idx + 1, row)
            self.rebuild_images_box()

    def rebuild_images_box(self):
        """Rebuild the images box after reordering."""
        # Remove all children
        while child := self.images_box.get_first_child():
            self.images_box.remove(child)

        # Re-add in order
        for row in self.image_rows:
            self.images_box.append(row)

    def update_apply_button(self):
        """Enable/disable apply button based on image count."""
        has_images = len(self.image_rows) >= 1
        self.apply_btn.set_sensitive(has_images)

    def on_apply(self, button):
        """Generate XML files and apply wallpaper."""
        if SLIDESHOW_XML.exists():
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Overwrite existing slideshow?",
                body="A slideshow configuration already exists. Do you want to replace it?",
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("overwrite", "Overwrite")
            dialog.set_response_appearance("overwrite", Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel")
            dialog.connect("response", self.on_overwrite_response)
            dialog.present()
        else:
            self.do_apply()

    def on_overwrite_response(self, dialog, response):
        """Handle overwrite confirmation response."""
        if response == "overwrite":
            self.do_apply()

    def do_apply(self):
        """Generate XML files and apply wallpaper."""
        try:
            self.generate_slideshow_xml()
            self.generate_properties_xml()
            self.apply_wallpaper()
            self.status_label.set_text("Wallpaper slideshow applied successfully!")
            self.status_label.remove_css_class("error")
        except Exception as e:
            self.status_label.set_text(f"Error: {e}")
            self.status_label.add_css_class("error")

    def generate_slideshow_xml(self):
        """Generate the slideshow configuration XML."""
        BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

        # Convert duration to seconds based on selected unit
        duration_value = self.duration_spin.get_value()
        unit_index = self.duration_unit.get_selected()
        if unit_index == 0:  # minutes
            duration_seconds = duration_value * 60
        elif unit_index == 1:  # hours
            duration_seconds = duration_value * 3600
        else:  # days
            duration_seconds = duration_value * 86400

        # Build XML
        root = ET.Element("background")

        # Start time (in the past)
        starttime = ET.SubElement(root, "starttime")
        ET.SubElement(starttime, "year").text = "2024"
        ET.SubElement(starttime, "month").text = "01"
        ET.SubElement(starttime, "day").text = "01"
        ET.SubElement(starttime, "hour").text = "00"
        ET.SubElement(starttime, "minute").text = "00"
        ET.SubElement(starttime, "second").text = "00"

        # Add elements for each image
        image_paths = [row.image_path for row in self.image_rows]

        for i, path in enumerate(image_paths):
            static = ET.SubElement(root, "static")
            ET.SubElement(static, "duration").text = f"{duration_seconds:.1f}"
            ET.SubElement(static, "file").text = path


        # Write formatted XML
        xml_str = ET.tostring(root, encoding="unicode")
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
        # Remove extra blank lines
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        pretty_xml = "\n".join(lines[1:])  # Skip XML declaration

        SLIDESHOW_XML.write_text(pretty_xml)

    def generate_properties_xml(self):
        """Generate the background properties XML to register with GNOME."""
        PROPERTIES_DIR.mkdir(parents=True, exist_ok=True)

        root = ET.Element("wallpapers")
        wallpaper = ET.SubElement(root, "wallpaper", deleted="false")
        ET.SubElement(wallpaper, "name").text = "SimpleSlideshow"
        ET.SubElement(wallpaper, "filename").text = str(SLIDESHOW_XML)
        ET.SubElement(wallpaper, "options").text = "zoom"

        # Write formatted XML
        xml_str = ET.tostring(root, encoding="unicode")
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        pretty_xml = "\n".join(lines[1:])

        PROPERTIES_XML.write_text(pretty_xml)

    def apply_wallpaper(self):
        """Apply the wallpaper using gsettings."""
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background",
            "picture-uri", f"file://{SLIDESHOW_XML}"
        ], check=True)
        subprocess.run([
            "gsettings", "set", "org.gnome.desktop.background",
            "picture-uri-dark", f"file://{SLIDESHOW_XML}"
        ], check=True)


class WallpapererApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = WallpapererWindow(self)
        win.present()


def main():
    app = WallpapererApp()
    app.run()


if __name__ == "__main__":
    main()
