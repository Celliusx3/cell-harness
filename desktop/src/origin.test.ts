import assert from "node:assert/strict";
import { test } from "node:test";

import { APP_URL, isAppOrigin, isBrowserLink, isPermissionGranted } from "./origin";

test("the window opens on the page server, on this Mac only", () => {
  assert.equal(APP_URL, "http://127.0.0.1:4887");
});

test("every page on the page server is the app's own", () => {
  assert.ok(isAppOrigin("http://127.0.0.1:4887/chat/abc?x=1"));
  assert.ok(isAppOrigin("http://127.0.0.1:4887/"));
});

test("another port, host or scheme is not the app", () => {
  assert.ok(!isAppOrigin("http://127.0.0.1:4886/api/bots"));
  assert.ok(!isAppOrigin("http://localhost:4887/"));
  assert.ok(!isAppOrigin("https://127.0.0.1:4887/"));
  assert.ok(!isAppOrigin("https://example.com/"));
  assert.ok(!isAppOrigin("null"));
});

test("only a web link is handed to the default browser", () => {
  assert.ok(isBrowserLink("https://example.com/a"));
  assert.ok(isBrowserLink("http://example.com/a"));
  assert.ok(!isBrowserLink("file:///etc/passwd"));
  assert.ok(!isBrowserLink("javascript:alert(1)"));
  assert.ok(!isBrowserLink("x-apple.systempreferences:com.apple.preference.security"));
  assert.ok(!isBrowserLink("not a url"));
});

test("the app's own pages may write the clipboard", () => {
  assert.ok(isPermissionGranted("clipboard-sanitized-write", "http://127.0.0.1:4887/"));
  assert.ok(isPermissionGranted("clipboard-sanitized-write", "http://127.0.0.1:4887/chat/abc"));
});

test("a clipboard write from another origin is refused", () => {
  assert.ok(!isPermissionGranted("clipboard-sanitized-write", "https://example.com/"));
  assert.ok(!isPermissionGranted("clipboard-sanitized-write", "http://127.0.0.1:4886/"));
});

test("location, the camera and every other permission stay off for the app too", () => {
  for (const permission of ["geolocation", "media", "notifications", "clipboard-read", "openExternal"]) {
    assert.ok(!isPermissionGranted(permission, "http://127.0.0.1:4887/"), permission);
  }
});
