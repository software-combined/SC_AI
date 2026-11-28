# UI and UX

How every screen the router shows a person stays clear, consistent and simple.
Most people who see these screens are not technical. Paths are relative to
`router/`.

## The screens

| Screen | Owner | Notes |
|---|---|---|
| Dialogs (update notice, key window, questions, progress) | `packaging/client_dialog.py` | One dialog owner draws every popup ([installation ownership](architecture/installation.md)) |
| Local setup and model access pages | `ai_router/setup_page.py`, `ai_router/model_prompt_page.py` | Inline styles only; a loopback page fetches nothing |
| Sign-in page | `packaging/assets/signin.html` | Embeds its fonts as data |
| Public download page | `packaging/download-page/` | Colours are variables in `style.css` |
| Menu bar and tray menu | `packaging/native/menu/` | [Desktop menu and tray](start/desktop-menu.md) |

## Rules for every screen

- **One name and icon.** Use the title `SCG Router` and the bundled icon
  `packaging/assets/router-icon.png`. Never use a platform default icon.
- **Plain words.** Say "key", "ChatGPT subscription" and "restart". Never name
  router internals such as `nonce`, `loopback`, `catalogue`, `owner-only file`,
  a process or a port.
- **Name the right apps.** Name only the clients this install serves (Codex,
  Claude Code or both), in the wording and in the action. Never tell a
  Claude-only user to reopen Codex. Never offer a restart the machine cannot do.
- **Two actions at most.** The safe action ("Later" or "Cancel") is always
  there when a screen asks a question. The offered action is the default
  button. A notice with nothing to decide has one "OK" button.
- **Dialogs only.** If no dialog tool is available, the notice stays pending.
  It never opens a browser or sends a separate notification instead.
- **Never block an install.** No popup blocks or fails an install.
- **Nothing from outside.** Local pages load no external file, font or script.

## Look and feel

Use the Inter typeface for text and Space Grotesk for headings. Both are bundled
under `packaging/assets/` with their licences.

There is no shared theme file yet. The setup and model access pages use one
set of `hsl()` colours inline. The sign-in and download pages use another set,
held as CSS variables. A new page reuses the variables from the page nearest
to it. Do not add a third palette.

## Checks

`tests/test_popup_style.py` pins the shared title, the icon and the plain
vocabulary on every platform. It fails when a module restates the title or
icon, or starts a dialog tool of its own.
