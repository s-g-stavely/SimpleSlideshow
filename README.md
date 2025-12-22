# SimpleSlideshow

A simple application to create and configure desktop wallpaper slideshowson Ubuntu/GNOME. Select images, set duration and timing, and apply.

I created this because I couldn't find an easy way to set up a wallpaperslideshow. It's mostly written with Claude.

It has been tested on Ubuntu 24.04.

![Example Screenshot](./example_screenshot.png)

## Installation

### Ubuntu 

```bash
# Install dependencies
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Run the app
./simpleslideshow.py
```

## How it works

It generates GNOME-compatible XML configuration files:

- `~/.local/share/backgrounds/simpleslideshow/slideshow.xml` - Slideshow definition
- `~/.local/share/gnome-background-properties/simpleslideshow.xml` - Registers the slideshow with GNOME

See the details of these files at:
https://help.ubuntu.com/community/SlideshowWallpapers
