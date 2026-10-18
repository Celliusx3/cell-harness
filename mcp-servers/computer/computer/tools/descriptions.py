"""The model's only documentation."""

from __future__ import annotations

NAVIGATE_DESCRIPTION = (
    "Open a web page in Chrome on the computer, starting the computer first if it is stopped. "
    "args: { url: string } — a full address starting with http:// or https://. Returns "
    "{ url, title } of the page that loaded, not its content: call browser_read_page next to "
    "read it. Use this for a site you need to click through, fill in or sign into; a plain "
    "question of fact is cheaper with a web search. Every bot shares this one computer and its "
    "Chrome, so a page or a sign-in you find there may be another bot's."
)

READ_PAGE_DESCRIPTION = (
    "Read the page open in the computer's Chrome. args: {}. Returns { url, title, content }: "
    "content is the page's visible words, cut at 12,000 characters, then up to 80 elements you "
    'can act on, one per line as - role "name" [ref], with a field\'s current value after it. '
    "Pass a ref to browser_act. A ref lasts only until the next browser_navigate, "
    "browser_read_page or browser_act; after any of those, use the refs from the newest result. "
    "Content inside frames is not listed."
)

SCREENSHOT_DESCRIPTION = (
    "App-only: the screen preview on a browser_navigate card calls this; do not call it. To read "
    "the open page, call browser_read_page. args: {}. Returns one PNG image of the whole screen, "
    "starting the computer first if it is stopped."
)

SCREEN_SESSION_DESCRIPTION = (
    "App-only: the person's Computer page calls this to watch the screen live, or to take "
    "control of it; do not call it. To read the open page, call browser_read_page. args: "
    '{ mode: "view" | "control" }. Returns { mode, held_until }, and a link to the live '
    "screen for the Computer page."
)

RELEASE_CONTROL_DESCRIPTION = (
    "App-only: the person's Computer page calls this to hand the screen back; do not call it. "
    "args: {}. Returns { mode, held_until }."
)

HELD_BY_PERSON = (
    "The person has taken control of the computer's screen, so this did nothing. Do not use "
    "the browser until they hand it back: tell them what you need from the page, then wait "
    "for their next message."
)

ACT_DESCRIPTION = (
    "Click, fill or type on elements of the open page, in order, then read the page again. "
    'args: { actions: [{ kind: "click" | "fill" | "type", ref: string, text?: string }] } — '
    "1 to 24 actions; each ref from the newest browser_read_page or browser_act result; text "
    "is required for fill, which replaces a field's value, and for type, which adds to it. "
    "There is no Enter key: to submit a form, click its button. Returns { url, title, content, "
    "actions_completed }: the page after the actions, as browser_read_page returns it, and how "
    "many actions ran. When an action fails, the error says how many completed and whether the "
    "failed one may have taken effect; call browser_read_page before going on, and never repeat "
    "an action that completed. When a page asks for a password, a captcha or a payment, stop: "
    "the person has to do that step."
)

TERMINAL_SESSION_DESCRIPTION = (
    "App-only: the person's Computer page calls this to open a shell on the computer while "
    "they hold control; do not call it. args: {}. Returns a link to the shell for the Computer "
    "page."
)

FILE_LIST_DESCRIPTION = (
    "App-only: the person's Computer page calls this to list a folder in the computer's home; "
    "do not call it. args: { path: string } — relative to the home folder, empty for the home "
    "folder itself. Returns { path, entries: [{ path, kind, size }] }."
)

FILE_READ_DESCRIPTION = (
    "App-only: the person's Computer page calls this to preview a text file from the "
    "computer's home; do not call it. args: { path: string }. Returns { path, content }."
)

FILE_DOWNLOAD_DESCRIPTION = (
    "App-only: the person's Computer page calls this to download a file from the computer's "
    "home; do not call it. args: { path: string }. Returns { path, content_base64 }."
)

FILE_UPLOAD_DESCRIPTION = (
    "App-only: the person's Computer page calls this to put a file in the computer's home "
    "while they hold control; do not call it. args: { path: string, content_base64: string }. "
    "Returns { path, size }."
)

KEEP_AWAKE_DESCRIPTION = (
    "App-only: the person's Computer page calls this every minute while it is open, so the "
    "computer does not stop for being idle; do not call it. args: {}. Returns {}."
)

SHELL_DESCRIPTION = (
    "Runs a command in your computer (Debian Linux with Python 3 and uv; the chat's files are "
    "at the same paths as you were told) and answers its output and exit code. A command still "
    "running after 15 seconds answers status `running` with how long it has run and its output "
    "so far; call shell again with the same arguments to wait for it, and its finished result "
    "comes once. Pass any text the command reads, such as JSON, as `stdin`, never inside the "
    "command."
)

COMMAND_DESCRIPTION = "The command, as `sh` runs it."

STDIN_DESCRIPTION = (
    "Text the command reads on its standard input. Put JSON or any text with quotes here."
)

CWD_DESCRIPTION = "The absolute folder to run in; your home folder when left out."
