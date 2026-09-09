# Changelog

## 1.3.2

Attachment thumbnails are now bounded before decode: base64 is validated strictly, capped per thumbnail and per message, and attachment counts are capped, so a hostile payload cannot exhaust memory or disk. Thumbnails are published through an exclusive temporary file and atomically renamed into place, so a planted symlink can no longer redirect the write.

## 1.3.1

`AGENTS.md` no longer ships with the plugin. It is untracked and ignored, so coding-agent instructions stay out of the tree that `omarchy plugin add` installs.

## 1.3.0

Renamed the project to Konnectarchy and the plugin id to `io.github.astorrer.konnectarchy`; old installs must be removed and the plugin re-added. Thumbnails now cache under `~/.cache/konnectarchy/`. Media control via the KDE Connect mprisremote plugin: when the phone is playing something, the panel shows a Now playing section with track, artist, and album, plus previous, play/pause, and next buttons. It disappears when nothing is playing. `t` toggles play/pause; `[` and `]` skip. `setup.sh uninstall` still removes the pre-rename autostart file.

## 1.2.21

Inbox highlight stays on the footer tools when conversations load. Compose will not send a contact name as a phone number, and a late thread fetch cannot overwrite the open chat.

## 1.2.20

Composing to someone prefers their 1:1 thread over a group they are in. Quality sweep: drop a dead icon helper and keep the SMS-app name lists in lockstep.

## 1.2.19

Message bubbles are not click targets. Only a copy chip is.

## 1.2.18

Picking a contact who already has a thread opens that thread instead of a blank compose.

## 1.2.17

New message searches synced contacts by name. A number still works if you need it.

## 1.2.16

New message and SMS app stay at the bottom of the inbox, like the reply field in a thread.

## 1.2.15

New message and SMS app sit side by side in the inbox. Left and right walk those two; down enters the list.

## 1.2.14

Clicking the phone opens the KDE Connect app.

## 1.2.13

Settings labels say a little more without filling the row.

## 1.2.12

Shorter settings labels so they fit next to the toggle.

## 1.2.11

Inbox and notification titles sit on the right, across from the back button.

## 1.2.10

The bar badge and Notifications count ignore SMS when those rows are hidden from the list.

## 1.2.9

Settings toggles flip when you click the row. The switch no longer fights the highlight for the click.

## 1.2.8

SMS is hidden from the notification list by default. It still lives in Messages. A setting brings those rows back.

## 1.2.7

Back, new message, and dismiss-all are framed buttons. A rule sits under the header and above the reply field.

## 1.2.6

Unpair asks Cancel / Unpair in the panel before dropping the phone. Cancel is selected first.

## 1.2.5

Sending the same text twice no longer knocks the first optimistic line off the thread. Copy chips share one component. A ping or file share in flight no longer drops the next action.

## 1.2.4

Copy a 2FA code or an http(s) link from a message or notification. Click the chip, or press `y`. Links are copied, not opened. The rest of the message stays put.

## 1.2.3

Going back to the inbox or the notification list jumps to the top, where the recent items are.

## 1.2.2

Keep a just-sent message on screen until the phone actually returns it. A refresh that lands too early no longer deletes it.

## 1.2.1

Sending a reply shows it in the thread immediately, then syncs with the phone. Reloading the thread is no longer required.

## 1.2.0

SMS threads show image thumbnails and file chips for attachments. Inbox previews say Photo or the file name when there is no text.

## 1.1.3

Up and down in the inbox and in a thread follow the highlight inside that list. The reply field stays put.

## 1.1.2

Arrow keys walk the button pad in two dimensions. Enter activates; Esc goes back.

## 1.1.1

Threads keep Inbox at the top and the reply field at the bottom. Only the messages scroll. Esc from the reply field returns to the inbox.

## 1.1.0

Control pad for notifications, messages, ping, ring, clipboard, and file share. Settings live in the panel. Hero line reports battery, notifications, and radio with a bit of personality. Footer shows the version and opens the project page.

## 1.0.0

Publish polish. Enter on a device opens the first action. Refresh reloads the open inbox. Dismiss-all sits at the bottom of the notification list. Optional bar badge for phone notifications.

## 0.4.0

Notification feed from the phone's KDE Connect notifications plugin.

- List active notifications in the panel (`n`, or Notifications)
- Dismiss one (`d`) or all
- Reply when the phone exposes a reply id
- Badge the bar icon while any are waiting

Desktop popups from `kdeconnectd` still appear; this is the inbox after they vanish.

## 0.3.0

Freeze of the current phone panel: pairing, ping, ring, clipboard, file share, SMS, and contact names from synced vCards.

- Look up SMS titles from `~/.local/share/kpeoplevcard/kdeconnect-<device>/`
- Split the Python helper into `connectlib/`
- Add `./tests/run`, manifest/message tests, and GitHub Actions
- Document install, Contacts permission, and what `plugin remove` does not undo
- `setup.sh uninstall` removes only the Connect autostart file

Not in 0.3: notification feed, remote input, media.

## 0.2.5

Theme-colored SMS bubbles, keyboard list follow, newest-first threads.

## 0.2.0

SMS inbox, threads, and send.

## 0.1.0

First bar widget: pair, ping, ring, clipboard, file share.
