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
   `get_function_details({ names: ["phone__screenshot", "phone__install_app", "phone__open_app", "phone__tap", "phone__swipe", "phone__type_text", "phone__press_key"] })`.
   Every one of them returns a screenshot, and a script cannot carry an image,
   so call them directly, one at a time, never inside `execute_typescript`.
1. **Look.** `phone__screenshot({})`. The first call starts the phone, which
   takes a few seconds.
2. **Install, when the user attached an APK.** `phone__install_app({ path })`
   with the path the chat gave for the file. It answers with the app's
   package name; keep it for step 3. There is no store to search: an app the
   user has no APK for cannot be installed, so say so and ask for the file.
3. **Open.** `phone__open_app({ package })`.
4. **Act, one step at a time.** Find the button or field in the latest
   screenshot and `phone__tap({ x, y })` its centre, in that screenshot's
   pixels. To type, tap the field, then `phone__type_text({ text })`. To see
   more of a list, `phone__swipe` from low on the screen to high. To go back,
   `phone__press_key({ key: "back" })`.
5. **Check every result.** Each action returns a new screenshot. Aim the next
   tap from it, never from an older one: typing or a loading page moves
   buttons, and a tap aimed from an old screenshot presses whatever is there
   now.

## Gotchas

- Only ASCII can be typed. For Chinese or other scripts, tell the user and
  ask them to take control of the phone and type it.
- An app that wants a Google account or Google Play services may refuse to
  run or keep asking to sign in. Say so; there is no Google account here.
- Before an action that buys, sends, posts or deletes something for the user,
  ask them with `ask_user` first and act only after they answer yes.

## Answer

Say what you did and what the phone shows now, in a few lines. When an action
did not do what you expected, say so and show what the screenshot shows.
