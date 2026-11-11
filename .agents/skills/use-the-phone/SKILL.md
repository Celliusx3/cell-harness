---
name: use-the-phone
description: Use the Android phone that every bot shares. Use when the user asks to install or open an Android app, try an app, do something in an app rather than on a website, or attaches an APK file.
---

# Use the phone

The phone is one Android phone, shared by every bot, with no Google Play. Apps
come from APK files the user attaches to the chat. You see it only through
screenshots, so look before every action and check the screenshot each action
returns.

## Workflow

0. **Select the tools first.** Your first call is
   `get_function_details({ names: ["phone__list_elements", "phone__screenshot", "phone__install_app", "phone__open_app", "phone__open_url", "phone__tap", "phone__double_tap", "phone__long_press", "phone__swipe", "phone__type_text", "phone__press_key", "phone__list_apps", "phone__foreground_app", "phone__terminate_app"] })`.
   Every action returns a screenshot, and a script cannot carry an image, so
   call them directly, one at a time, never inside `execute_typescript`.
1. **Read before you look.** `phone__list_elements({})` gives the screen as
   text: each element's words, its id, whether it can be tapped, and its
   centre. Use it for words, prices, links and tap targets. Take
   `phone__screenshot({})` when you need the picture, or when the list is
   empty, as it is in games and drawn screens. The first call starts the
   phone, which takes a few seconds.
2. **Install, when the user attached an APK.** `phone__install_app({ path })`
   with the path the chat gave for the file. It answers with the app's
   package name. There is no store to search: an app the user has no APK for
   cannot be installed, so say so and ask for the file.
   `phone__list_apps({})` names what is installed.
3. **Open.** `phone__open_app({ package })`, or `phone__open_url({ url })` for
   a link. An app that does not claim its links opens them in the browser,
   which may offer to open the app: tap that.
4. **Act, one step at a time.** `phone__tap({ x, y })` an element's centre.
   `phone__long_press` opens a menu such as Copy, Paste or Share, and
   `phone__double_tap` zooms or selects a word. To type, tap the field, then
   `phone__type_text({ text })`. To paste what you copied, tap the field, then
   `phone__press_key({ key: "paste" })`. To see more of a list,
   `phone__swipe` from low on the screen to high. To go back,
   `phone__press_key({ key: "back" })`.
5. **Check every result.** Each action returns a new screenshot. Aim the next
   tap from it or from a new element list, never from an older one: typing or
   a loading page moves buttons, and a tap aimed from an old screenshot
   presses whatever is there now.
6. **When an app is stuck,** `phone__terminate_app({ package })` closes it, and
   `phone__open_app` opens it again. `phone__foreground_app({})` names the app
   on screen.

## Gotchas

- Only ASCII can be typed. For Chinese or other scripts, tell the user and
  ask them to take control of the phone and type it.
- You cannot read the clipboard. To give the user a link you copied, tap a
  text field in a notes app, paste it, and read it with
  `phone__list_elements`.
- An app that wants a Google account or Google Play services may refuse to
  run or keep asking to sign in. Say so; there is no Google account here.
- `phone__uninstall_app` and `phone__clear_app_data` lose the app's data and
  its sign-in. Ask the user first, and before any action that buys, sends,
  posts or deletes something for them, with `ask_user`, and act only after
  they answer yes.

## Answer

Say what you did and what the phone shows now, in a few lines. When an action
did not do what you expected, say so and show what the screenshot shows.
