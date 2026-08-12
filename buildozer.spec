
[app]

# (str) Title of your application
title = Рабочий календарь

# (str) Package name
package.name = workcalendar

# (str) Package domain (needed for Android)
package.domain = org.workcalendar

# (str) Source code where main.py lives
source.dir = .

# (list) List of source files to include
source.include_exts = py,png,jpg,kv,atlas,db

# (str) Version
version = 0.1.0

# (list) Python requirements
requirements = python3,kivy==2.3.1

# (str) Orientation
orientation = portrait

# (bool) Fullscreen
fullscreen = 0

# (str) Android API to target
android.api = 35

# (str) Minimum Android API
android.minapi = 23

# (str) Android permissions
android.permissions = VIBRATE

# (str) Presplash
# presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon
# icon.filename = %(source.dir)s/data/icon.png

# (bool) Launch in background
android.accept_sdk_license = True

# (str) Python-for-Android bootstrap
p4a.bootstrap = sdl2

[buildozer]

# (str) Build directory
build_dir = .buildozer

# (str) Output directory
bin_dir = bin

# (bool) Warn if log level is not verbose
warn_on_root = 1

# (str) Log level
log_level = 2
