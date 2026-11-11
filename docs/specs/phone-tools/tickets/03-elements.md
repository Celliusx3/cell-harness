# 03 A bot reads the screen as a list of elements

**Status.** done

**What to build.** The image's `android` helper runs each command with the
environment of Android's zygote, so `uiautomator` starts. `list_elements` dumps
the UI tree and returns each element with text or a description: its text,
description, resource id, whether it is clickable, and its centre in
screenshot pixels.

**Checks.** A unit test turns a recorded `uiautomator` dump into the list. On
the real phone, on Pinduoduo's results, the list holds the prices a screenshot
shows.

**Blocked by.** none
