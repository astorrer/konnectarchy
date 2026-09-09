var PLUGIN_VERSION = "1.3.3"
var PROJECT_URL = "https://github.com/astorrer/konnectarchy"

function scrollFlickToItem(flick, item, margin) {
  if (!flick || !item) return
  var m = margin || 8
  var point = item.mapToItem(flick.contentItem, 0, 0)
  if (!point) return
  var top = point.y
  var bottom = top + Math.max(item.height || 0, item.implicitHeight || 0)
  var viewTop = flick.contentY
  var viewBottom = viewTop + flick.height
  var maxY = Math.max(0, flick.contentHeight - flick.height)
  if (top < viewTop + m) flick.contentY = Math.max(0, top - m)
  else if (bottom > viewBottom - m) flick.contentY = Math.min(maxY, bottom + m - flick.height)
}

function parseStatus(raw) {
  var text = String(raw || "").trim()
  if (text === "") return { ok: false, lastError: "Empty status" }
  try {
    var parsed = JSON.parse(text)
  } catch (error) {
    return { ok: false, lastError: "Could not read Konnectarchy status" }
  }
  if (!parsed || typeof parsed !== "object") return { ok: false, lastError: "Bad status payload" }
  parsed.ok = parsed.ok !== false
  parsed.devices = parsed.devices instanceof Array ? parsed.devices : []
  return parsed
}

function typeIcon(type) {
  var value = String(type || "").toLowerCase()
  if (value === "tablet") return "󰓹"
  if (value === "desktop" || value === "laptop") return "󰌢"
  if (value === "tv") return "󰠹"
  return "󰄜"
}

function batteryText(device) {
  if (!device || typeof device.battery !== "number" || device.battery < 0) return ""
  return device.battery + "%" + (device.charging ? " charging" : "")
}

function deviceMeta(device, hideSms) {
  if (!device) return ""
  if (device.pairRequestedByPeer) return "Wants to pair"
  if (device.pairRequested) return "Pairing requested"
  if (!device.paired) return device.reachable ? "Nearby · not paired" : "Not paired"
  if (!device.reachable) return "Unavailable"
  var parts = []
  var battery = batteryText(device)
  if (battery) parts.push(battery)
  if (device.networkType) parts.push(String(device.networkType))
  var notes = notificationBadgeCount(device, hideSms)
  if (notes > 0) parts.push(notes === 1 ? "1 notification" : notes + " notifications")
  return parts.length ? parts.join(" · ") : "Connected"
}

function primaryDevice(devices) {
  if (!devices || devices.length === 0) return null
  for (var i = 0; i < devices.length; i++) {
    if (devices[i].paired && devices[i].reachable) return devices[i]
  }
  for (var j = 0; j < devices.length; j++) {
    if (devices[j].pairRequestedByPeer) return devices[j]
  }
  return devices[0]
}

function notificationBadgeCount(device, hideSms) {
  if (!device) return 0
  var total = typeof device.notificationCount === "number" ? device.notificationCount : 0
  if (!hideSms || !device.hasSms) return total
  var sms = typeof device.smsNotificationCount === "number" ? device.smsNotificationCount : 0
  return Math.max(0, total - sms)
}

function mediaState(device) {
  if (!device || !device.media || device.media.hasMedia !== true) return null
  return device.media
}

function mediaMeta(media) {
  if (!media) return ""
  var parts = []
  var artist = String(media.artist || "").trim()
  var album = String(media.album || "").trim()
  if (artist) parts.push(artist)
  if (album) parts.push(album)
  return parts.join(" · ")
}

function actionRows(device, hideSms) {
  if (!device) return []
  var rows = []
  if (device.pairRequestedByPeer) {
    rows = [
      { id: "accept", label: "Accept", icon: "󰄬", kind: "choice" },
      { id: "reject", label: "Decline", icon: "󰅖", kind: "choice" }
    ]
  } else if (!device.paired) {
    rows = [{ id: "pair", label: "Request pairing", icon: "󰌹", kind: "choice" }]
  } else if (!device.reachable) {
    rows = [{ id: "unpair", label: "Unpair", icon: "󰌺", kind: "danger" }]
  } else {
    var notifyLabel = "Notifications"
    var count = notificationBadgeCount(device, hideSms)
    if (count > 0) notifyLabel = "Notifications (" + count + ")"
    rows = [
      { id: "notifications", label: notifyLabel, icon: "󰎕", kind: "inbox" },
      { id: "messages", label: "Messages", icon: "󰍥", kind: "inbox" },
      { id: "ping", label: "Ping", icon: "󰐷", kind: "tool" },
      { id: "ring", label: "Ring", icon: "󰂜", kind: "tool" },
      { id: "clipboard", label: "Clipboard", icon: "󰅌", kind: "tool" },
      { id: "file", label: "File", icon: "󰈔", kind: "tool" },
      { id: "unpair", label: "Unpair", icon: "󰌺", kind: "danger" }
    ]
    var media = mediaState(device)
    if (media) {
      rows.unshift(
        { id: "media-previous", label: "Previous", icon: "󰒮", kind: "media" },
        { id: "media-toggle", label: media.isPlaying ? "Pause" : "Play", icon: media.isPlaying ? "󰏤" : "󰐊", kind: "media" },
        { id: "media-next", label: "Next", icon: "󰒭", kind: "media" }
      )
    }
  }
  for (var i = 0; i < rows.length; i++) rows[i].index = i
  return rows
}

function actionsOfKind(actions, kind) {
  var rows = []
  var list = actions || []
  for (var i = 0; i < list.length; i++) {
    if (list[i] && list[i].kind === kind) rows.push(list[i])
  }
  return rows
}

function indexInKind(actions, kind, globalIndex) {
  var n = 0
  var list = actions || []
  for (var i = 0; i < list.length; i++) {
    if (!list[i] || list[i].kind !== kind) continue
    if (i === globalIndex) return n
    n++
  }
  return 0
}

function kindColumns(kind, count) {
  var n = Math.max(1, count || 1)
  if (kind === "media") return Math.min(3, n)
  if (kind === "inbox" || kind === "choice") return Math.min(2, n)
  if (kind === "danger") return 1
  return n
}

function kindRange(actions, index) {
  var list = actions || []
  if (list.length === 0) return { start: 0, count: 0, kind: "" }
  var i = Math.max(0, Math.min(list.length - 1, index | 0))
  var kind = list[i].kind
  var start = i
  while (start > 0 && list[start - 1].kind === kind) start--
  var end = i
  while (end + 1 < list.length && list[end + 1].kind === kind) end++
  return { start: start, count: end - start + 1, kind: kind }
}

function indexInGroupColumn(actions, indexInGroup, col, fromEnd) {
  var range = kindRange(actions, indexInGroup)
  if (range.count <= 0) return 0
  var cols = kindColumns(range.kind, range.count)
  var c = Math.max(0, Math.min(cols - 1, col | 0))
  var row = fromEnd ? Math.ceil(range.count / cols) - 1 : 0
  var local = row * cols + c
  if (local >= range.count) local = range.count - 1
  return range.start + local
}

function moveActionIndex(actions, current, dx, dy) {
  var list = actions || []
  if (list.length === 0) return 0
  var i = Math.max(0, Math.min(list.length - 1, current | 0))
  if (!dx && !dy) return i
  var range = kindRange(list, i)
  var cols = kindColumns(range.kind, range.count)
  var local = i - range.start
  var row = Math.floor(local / cols)
  var col = local % cols
  var rows = Math.ceil(range.count / cols)
  if (dx && !dy) {
    var nextCol = col + dx
    var nextLocal = row * cols + nextCol
    if (nextCol >= 0 && nextCol < cols && nextLocal < range.count) return range.start + nextLocal
    return i
  }
  if (dy) {
    var nextRow = row + dy
    if (nextRow >= 0 && nextRow < rows) {
      var stepped = nextRow * cols + col
      if (stepped >= range.count) stepped = range.count - 1
      return range.start + stepped
    }
    if (dy > 0) {
      var after = range.start + range.count
      if (after >= list.length) return i
      return indexInGroupColumn(list, after, col, false)
    }
    if (range.start === 0) return -1
    return indexInGroupColumn(list, range.start - 1, col, true)
  }
  return i
}

function heroPhrases(device, hideSms) {
  if (!device || !device.paired || !device.reachable) return []
  var name = String(device.name || "the phone")
  var short = name.split(" ")[0] || name
  var phrases = []
  var battery = device.battery
  var charging = device.charging === true
  if (typeof battery === "number" && battery >= 0) {
    if (charging) phrases.push(short + " is sipping wall power at " + battery + "%")
    else if (battery <= 12) phrases.push(short + " is running on fumes · " + battery + "%")
    else if (battery >= 90) phrases.push(short + " is topped up at " + battery + "%")
    else phrases.push(short + " is wandering at " + battery + "%")
  }
  var n = notificationBadgeCount(device, hideSms)
  if (n > 0)
    phrases.push(n === 1 ? "One note is waiting in the pocket" : n + " notes waiting in the pocket")
  else phrases.push("Inbox is quiet. For now.")
  var net = String(device.networkType || "")
  if (net) phrases.push("On " + net + ", still in range")
  phrases.push("Ready to ping " + short)
  return phrases
}

function looksLikePhone(text) {
  var digits = String(text || "").replace(/[\s\-()+]/g, "")
  return digits.length >= 7 && /^\d+$/.test(digits)
}

function canonicalizePhone(number) {
  var text = String(number || "").replace(/[\s\-()+]/g, "").replace(/^0+/, "")
  return text || String(number || "")
}

function phonesMatch(left, right) {
  var first = canonicalizePhone(left)
  var second = canonicalizePhone(right)
  if (!first || !second) return false
  var longer = first.length >= second.length ? first : second
  var shorter = first.length >= second.length ? second : first
  if (shorter.length <= 6 && longer.length > 6) return false
  return longer.slice(longer.length - shorter.length) === shorter
}

function contactPhones(contact) {
  var phones = contact && contact.phones
  if (phones && typeof phones.length === "number" && phones.length > 0) return phones
  if (contact && contact.phone) return [contact.phone]
  return []
}

function findConversationForPhones(conversations, phones) {
  var list = conversations || []
  var nums = phones || []
  var group = null
  var i
  var a
  var p
  var hit
  for (i = 0; i < list.length; i++) {
    var addresses = (list[i] && list[i].addresses) || []
    hit = false
    for (a = 0; a < addresses.length; a++) {
      for (p = 0; p < nums.length; p++) {
        if (phonesMatch(addresses[a], nums[p])) {
          hit = true
          break
        }
      }
      if (hit) break
    }
    if (!hit) continue
    if (addresses.length <= 1) return list[i]
    if (!group) group = list[i]
  }
  return group
}

function findConversationForContact(conversations, contact) {
  return findConversationForPhones(conversations, contactPhones(contact))
}

function contactLabel(contact) {
  if (!contact) return ""
  var name = String(contact.name || "").trim()
  if (name) return name
  return String(contact.phone || "")
}

function filterContacts(contacts, query) {
  var list = contacts || []
  var q = String(query || "").replace(/\s+/g, " ").trim().toLowerCase()
  var rows = []
  var i
  var j
  for (i = 0; i < list.length; i++) {
    var contact = list[i]
    if (!contact) continue
    if (!q) {
      rows.push(contact)
      continue
    }
    var name = String(contact.name || "").toLowerCase()
    var hit = name.indexOf(q) !== -1
    var phones = contact.phones
    if (!hit && String(contact.phone || "").toLowerCase().indexOf(q) !== -1) hit = true
    if (!hit && phones && typeof phones.length === "number") {
      for (j = 0; j < phones.length; j++) {
        if (String(phones[j] || "").toLowerCase().indexOf(q) !== -1) {
          hit = true
          break
        }
      }
    }
    if (hit) rows.push(contact)
  }
  return rows
}

function conversationTitle(conversation) {
  if (!conversation) return "Unknown"
  if (conversation.title) return String(conversation.title)
  var names = conversation.names
  if (names && typeof names.length === "number" && names.length > 0) return names.join(", ")
  var addresses = conversation.addresses
  if (!addresses || typeof addresses.length !== "number") addresses = []
  if (addresses.length === 0) return "Unknown"
  return addresses.map(String).join(", ")
}

function attachmentPreviewLabel(item) {
  if (!item) return "Attachment"
  if (item.kind === "image" || (item.mime && String(item.mime).indexOf("image/") === 0)) return "Photo"
  var label = String(item.label || item.name || "").trim()
  if (label) return label
  return "Attachment"
}

function attachmentSummary(item) {
  var atts = item && item.attachments
  if (atts && typeof atts.length === "number" && atts.length > 0) {
    if (atts.length === 1) return attachmentPreviewLabel(atts[0])
    return atts.length + " attachments"
  }
  if (item && item.attachmentCount > 0) return "Attachment"
  return ""
}

function previewText(conversation) {
  var body = String((conversation && conversation.body) || "").replace(/\s+/g, " ").trim()
  if (body) return body
  return attachmentSummary(conversation)
}

function messageText(message) {
  return String((message && message.body) || "")
}

function messageAttachments(message) {
  var atts = message && message.attachments
  if (atts && typeof atts.length === "number") return atts
  return []
}

function mergeSmsMessages(existing, incoming) {
  var current = existing || []
  var next = incoming || []
  var byId = {}
  var knownIds = {}
  var claimed = {}
  var i
  var j
  for (i = 0; i < current.length; i++) {
    if (current[i] && current[i].pending) continue
    knownIds[String(current[i].id)] = true
    byId[String(current[i].id)] = current[i]
  }
  for (i = 0; i < next.length; i++) byId[String(next[i].id)] = next[i]
  for (i = 0; i < current.length; i++) {
    var pending = current[i]
    if (!pending || !pending.pending) continue
    var body = String(pending.body || "").trim()
    var matched = false
    for (j = 0; j < next.length; j++) {
      var real = next[j]
      if (!real || !real.fromMe) continue
      if (String(real.body || "").trim() !== body) continue
      if (knownIds[String(real.id)]) continue
      if (claimed[String(real.id)]) continue
      claimed[String(real.id)] = true
      matched = true
      break
    }
    if (!matched) byId[String(pending.id)] = pending
  }
  var rows = []
  for (var key in byId) rows.push(byId[key])
  rows.sort(function(a, b) { return (a.date || 0) - (b.date || 0) })
  return rows
}

var COPY_CUE_RE = /\b(codes?|otp|pin|passcodes?|passwords?|verif(?:y|ication)|authenticators?|2fa|two[\s-]?factor|one[\s-]?time|security[ -]?codes?|login[ -]?codes?|confirmation|auth(?:entication)?[ -]?codes?)\b/i

function trimCopyUrl(url) {
  var value = String(url || "")
  while (/[.,;:!?']$/.test(value)) value = value.slice(0, -1)
  if (/\)$/.test(value) && value.indexOf("(") === -1) value = value.slice(0, -1)
  return value
}

function copyLinkLabel(url) {
  var match = String(url || "").match(/^https?:\/\/([^/:]+)/i)
  var host = match ? match[1] : ""
  if (host.indexOf("www.") === 0) host = host.slice(4)
  if (host) return "Copy " + host
  return "Copy link"
}

function maskCopyUrls(text) {
  return String(text || "").replace(/https?:\/\/[^\s<>"']+/gi, function(url) {
    var blank = ""
    for (var i = 0; i < url.length; i++) blank += " "
    return blank
  })
}

function copyCueRanges(text) {
  var ranges = []
  var re = new RegExp(COPY_CUE_RE.source, "gi")
  var match
  while ((match = re.exec(text))) {
    ranges.push({ start: match.index, end: match.index + match[0].length })
  }
  return ranges
}

function copyCueDistance(ranges, start, end) {
  var best = Infinity
  for (var i = 0; i < ranges.length; i++) {
    var cue = ranges[i]
    if (end < cue.start) best = Math.min(best, cue.start - end)
    else if (start > cue.end) best = Math.min(best, start - cue.end)
    else best = 0
  }
  return best
}

function copyLooksLikeYear(value) {
  return /^(19|20)\d{2}$/.test(value)
}

function copyLooksLikeDate(value) {
  return value.length === 8 && /^(19|20)\d{6}$/.test(value)
}

function copyPhoneContext(text, start, length) {
  var i = start
  var j = start + length
  while (i > 0 && /\d/.test(text.charAt(i - 1))) i--
  while (j < text.length && /\d/.test(text.charAt(j))) j++
  if (j - i >= 9) return true
  if (i > 0 && text.charAt(i - 1) === "+") return true
  return false
}

function copyNormalizeDigits(value) {
  return String(value || "").replace(/[\s-]/g, "")
}

function copyLinks(text) {
  var rows = []
  var seen = {}
  var re = /https?:\/\/[^\s<>"']+/gi
  var match
  while ((match = re.exec(text))) {
    var url = trimCopyUrl(match[0])
    if (!url || seen[url]) continue
    if (!/^https?:\/\/\S/i.test(url)) continue
    seen[url] = true
    rows.push({ kind: "link", value: url, label: copyLinkLabel(url) })
    if (rows.length >= 2) break
  }
  return rows
}

function copyCodes(text) {
  var raw = String(text || "")
  var trimmed = raw.replace(/^\s+|\s+$/g, "")
  var seen = {}
  var found = []

  function consider(value, start, length, force, scoreBias) {
    var digits = copyNormalizeDigits(value)
    if (!digits || seen[digits]) return
    if (copyPhoneContext(raw, start, length)) return
    if (copyLooksLikeYear(digits) || copyLooksLikeDate(digits)) return
    var cues = copyCueRanges(raw)
    var distance = copyCueDistance(cues, start, start + length)
    if (!force && !(distance <= 56)) return
    seen[digits] = true
    found.push({
      kind: "code",
      value: digits,
      label: "Copy " + digits,
      distance: force ? -1 : distance,
      bias: scoreBias || 0
    })
  }

  var whole = trimmed.match(/^(?:G-)?(\d{3}[\s-]\d{3}|\d{6}|\d{8})$/i)
  if (whole) {
    consider(whole[1], raw.indexOf(whole[1]), whole[1].length, true, 0)
    return found
  }

  var match
  var re = /G-(\d{6})/gi
  while ((match = re.exec(raw))) {
    consider(match[1], match.index, match[0].length, true, 0)
  }

  re = /(^|[^\d])(\d{3}[\s-]\d{3})(?!\d)/g
  while ((match = re.exec(raw))) {
    consider(match[2], match.index + match[1].length, match[2].length, false, 0)
  }

  re = /(^|[^\d])(\d{6,8})(?!\d)/g
  while ((match = re.exec(raw))) {
    consider(match[2], match.index + match[1].length, match[2].length, false, match[2].length === 6 ? 0 : 1)
  }

  re = /(^|[^\d])(\d{4})(?!\d)/g
  while ((match = re.exec(raw))) {
    consider(match[2], match.index + match[1].length, match[2].length, false, 2)
  }

  re = /\b([A-Z0-9]{6,8})\b/gi
  while ((match = re.exec(raw))) {
    var token = match[1]
    if (!/[A-Z]/i.test(token) || !/\d/.test(token)) continue
    if (/^\d+$/.test(token)) continue
    if (seen[token.toUpperCase()] || seen[token]) continue
    var cues = copyCueRanges(raw)
    var distance = copyCueDistance(cues, match.index, match.index + token.length)
    if (!(distance <= 56)) continue
    seen[token] = true
    seen[token.toUpperCase()] = true
    found.push({
      kind: "code",
      value: token,
      label: "Copy " + token,
      distance: distance,
      bias: 0
    })
  }

  found.sort(function(a, b) {
    if (a.distance !== b.distance) return a.distance - b.distance
    return a.bias - b.bias
  })
  if (found.length <= 1) return found
  return [found[0]]
}

function copySnippets(text) {
  var raw = String(text || "")
  if (raw.replace(/\s+/g, "") === "") return []
  var codes = copyCodes(maskCopyUrls(raw))
  var links = copyLinks(raw)
  var rows = []
  var i
  for (i = 0; i < codes.length; i++) {
    rows.push({ kind: codes[i].kind, value: codes[i].value, label: codes[i].label })
  }
  for (i = 0; i < links.length && rows.length < 3; i++) rows.push(links[i])
  return rows
}

function primaryCopySnippet(snippets) {
  var rows = snippets || []
  var i
  for (i = 0; i < rows.length; i++) {
    if (rows[i] && rows[i].kind === "code") return rows[i]
  }
  return rows.length ? rows[0] : null
}

function messageCopySnippets(message) {
  return copySnippets(messageText(message))
}

function notificationCopyText(item) {
  if (!item) return ""
  var parts = []
  var title = String(item.title || "").trim()
  var text = String(item.text || "").trim()
  var ticker = String(item.ticker || "").trim()
  if (title) parts.push(title)
  if (text && text !== title) parts.push(text)
  if (ticker && ticker !== title && ticker !== text) parts.push(ticker)
  return parts.join("\n")
}

function notificationCopySnippets(item) {
  return copySnippets(notificationCopyText(item))
}

function formatSmsTime(ms) {
  var n = Number(ms)
  if (!isFinite(n) || n <= 0) return ""
  var date = new Date(n)
  var now = new Date()
  var sameDay = date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate()
  if (sameDay) {
    var hours = date.getHours()
    var minutes = date.getMinutes()
    var suffix = hours >= 12 ? "PM" : "AM"
    hours = hours % 12
    if (hours === 0) hours = 12
    return hours + ":" + (minutes < 10 ? "0" : "") + minutes + " " + suffix
  }
  return (date.getMonth() + 1) + "/" + date.getDate()
}

function notificationTitle(item) {
  if (!item) return "Notification"
  var title = String(item.title || "").trim()
  if (title) return title
  var ticker = String(item.ticker || "").trim()
  if (ticker) return ticker
  return String(item.appName || "Notification")
}

function notificationPreview(item) {
  var text = String((item && item.text) || "").replace(/\s+/g, " ").trim()
  if (text) return text
  return String((item && item.ticker) || "").replace(/\s+/g, " ").trim()
}

function notificationMeta(item) {
  if (!item) return ""
  var app = String(item.appName || "").trim()
  if (item.canReply) return app ? app + " · reply" : "Reply"
  return app
}

var SMS_APP_NAMES = {
  "messages": true,
  "google messages": true,
  "messaging": true,
  "samsung messages": true,
  "textra": true,
  "qksms": true,
  "pulse": true,
  "pulse sms": true
}

function isSmsNotification(item) {
  if (item && item.sms === true) return true
  if (item && item.sms === false) return false
  var name = String((item && item.appName) || "").replace(/\s+/g, " ").trim().toLowerCase()
  if (!name) return false
  if (SMS_APP_NAMES[name]) return true
  return /\bsms\b/.test(name)
}

function visibleNotifications(items, hideSms) {
  var list = items || []
  if (!hideSms) return list
  var rows = []
  for (var i = 0; i < list.length; i++) {
    if (!isSmsNotification(list[i])) rows.push(list[i])
  }
  return rows
}


