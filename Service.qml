import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import "Model.js" as Model

Item {
  id: root

  property var settings: ({})

  property bool installed: false
  property bool running: false
  property string announcedName: ""
  property var devices: []
  property var conversations: []
  property var messages: []
  property var notifications: []
  property var contacts: []
  property var _smsQueue: []
  property var _actionQueue: []
  property bool smsLoading: false
  property bool smsHasMore: true
  property string smsDeviceId: ""
  property var smsThreadId: null
  property bool refreshing: false
  property string actionStatus: ""
  property string lastError: ""
  property string daemonPath: ""

  property int _desired: -1
  readonly property bool active: _desired === -1 ? running : (_desired === 1)
  readonly property var primary: Model.primaryDevice(devices)
  readonly property bool busy: statusProcess.running || actionProcess.running || pickerProcess.running || smsProcess.running || settleTimer.running
  readonly property int refreshIntervalSec: intSetting("refreshIntervalSec", 8, 3, 120)
  readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("connect.py").toString().replace(/^file:\/\//, ""))
  readonly property string setupPath: decodeURIComponent(Qt.resolvedUrl("setup.sh").toString().replace(/^file:\/\//, ""))

  property bool _reloadNotifications: false
  property string _notifyDeviceId: ""
  property bool _reloadThread: false

  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  function intSetting(name, fallback, min, max) {
    var n = parseInt(String(setting(name, fallback)), 10)
    if (!isFinite(n)) n = fallback
    if (n < min) n = min
    if (n > max) n = max
    return n
  }

  function helper(args) {
    return ["python3", helperPath].concat(args)
  }

  function refresh() {
    if (statusProcess.running || helperPath === "") return
    refreshing = true
    statusProcess.command = helper(["status"])
    statusProcess.running = true
  }

  function applyStatus(raw) {
    var parsed = Model.parseStatus(raw)
    if (!parsed.ok && parsed.lastError) {
      lastError = parsed.lastError
      return
    }
    installed = parsed.installed === true
    running = parsed.running === true
    if (_desired !== -1 && running === (_desired === 1)) _desired = -1
    announcedName = String(parsed.announcedName || "")
    daemonPath = String(parsed.daemonPath || "")
    devices = parsed.devices || []
    if (parsed.error) lastError = String(parsed.error)
    else lastError = ""
  }

  function runAction(args, label) {
    if (actionProcess.running) {
      _actionQueue.push({ args: args, label: label || "" })
      if (label) {
        actionStatus = label
        actionStatusTimer.restart()
      }
      return
    }
    if (label) {
      actionStatus = label
      actionStatusTimer.restart()
    }
    actionProcess.command = helper(args)
    actionProcess.running = true
  }

  function startDaemon() {
    _desired = 1
    runAction(["start"], "Starting…")
  }

  function stopDaemon() {
    _desired = 0
    runAction(["stop"], "Stopping…")
  }

  function toggleRunning() {
    if (active) stopDaemon()
    else startDaemon()
  }

  function ping(id) { runAction(["ping", id], "Pinging…") }
  function ring(id) { runAction(["ring", id], "Ringing…") }
  function pair(id) { runAction(["pair", id], "Requesting pair…") }
  function unpair(id) { runAction(["unpair", id], "Unpairing…") }
  function accept(id) { runAction(["accept", id], "Accepting…") }
  function reject(id) { runAction(["reject", id], "Declining…") }
  function sendClipboard(id) { runAction(["send-clipboard", id], "Sending clipboard…") }
  function mediaAction(id, action) { runAction(["media-action", id, action], "") }

  function openKdeConnect() {
    actionStatus = "Opening KDE Connect…"
    actionStatusTimer.restart()
    Quickshell.execDetached(["uwsm-app", "--", "kdeconnect-app"])
  }

  function copyToClipboard(text, hint) {
    var value = String(text || "")
    if (value === "") return
    Quickshell.execDetached(["wl-copy", "--", value])
    actionStatus = hint || "Copied"
    actionStatusTimer.restart()
  }

  function runSms(kind, args, seedMessages) {
    lastError = ""
    if (kind === "thread" && seedMessages) messages = seedMessages
    var job = { kind: kind, args: args, threadId: String(smsThreadId || "") }
    if (smsProcess.running) {
      _smsQueue.push(job)
      smsLoading = true
      return
    }
    smsLoading = true
    smsProcess._kind = kind
    smsProcess._threadId = job.threadId
    smsProcess.command = helper(args)
    smsProcess.running = true
  }

  function loadConversations(id) {
    if (!id) return
    runSms("conversations", ["conversations", id])
  }

  function loadContacts(id) {
    if (!id) return
    runSms("contacts", ["contacts", id])
  }

  function mergeMessages(incoming) {
    messages = Model.mergeSmsMessages(messages, incoming)
  }

  function appendOutgoing(text) {
    var body = String(text || "").trim()
    if (body === "") return
    var pending = {
      id: -Date.now(),
      body: body,
      fromMe: true,
      date: Date.now(),
      type: 2,
      read: 1,
      threadId: smsThreadId,
      addresses: [],
      attachmentCount: 0,
      attachments: [],
      pending: true
    }
    messages = messages.concat([pending])
  }

  function dropPending() {
    var rows = []
    for (var i = 0; i < messages.length; i++) {
      if (messages[i] && messages[i].pending) continue
      rows.push(messages[i])
    }
    messages = rows
  }

  function refreshThread() {
    if (!smsDeviceId || smsThreadId === undefined || smsThreadId === null || smsThreadId === "") return
    runSms("refresh", ["conversation", smsDeviceId, String(smsThreadId), "0", "12"])
  }

  function loadThread(id, threadId, seed) {
    if (!id || threadId === undefined || threadId === null || threadId === "") return
    smsDeviceId = id
    smsThreadId = threadId
    smsHasMore = true
    lastError = ""
    _smsQueue = _smsQueue.filter(function(item) { return item.kind !== "older" && item.kind !== "thread" })
    messages = (seed && (seed.body || seed.attachmentCount)) ? [seed] : []
    loadOlder(id, threadId)
  }

  function loadOlder(id, threadId) {
    if (!id || threadId === undefined || threadId === null || threadId === "") return
    if (smsHasMore === false) return
    var have = 0
    for (var i = 0; i < messages.length; i++) {
      if (messages[i] && messages[i].pending) continue
      have += 1
    }
    runSms("older", ["conversation", id, String(threadId), String(have), String(have + 12)])
  }

  function smsReply(id, threadId, text) {
    smsDeviceId = id
    smsThreadId = threadId
    appendOutgoing(text)
    _reloadThread = true
    runAction(["sms-reply", id, String(threadId), text], "Sending…")
  }

  function smsSend(id, number, text) {
    runAction(["sms-send", id, number, text], "Sending…")
  }

  function smsApp(id) {
    runAction(["sms-app", id], "Opening messages…")
  }

  function loadNotifications(id) {
    if (!id) return
    runSms("notifications", ["notifications", id])
  }

  function dropNotification(nid) {
    var nidStr = String(nid)
    var keep = []
    for (var i = 0; i < notifications.length; i++) {
      if (String((notifications[i] && notifications[i].id) || "") !== nidStr) keep.push(notifications[i])
    }
    if (keep.length !== notifications.length) notifications = keep
  }

  function dismissNotification(id, nid) {
    if (!id || nid === undefined || nid === null || nid === "") return
    _notifyDeviceId = id
    _reloadNotifications = true
    dropNotification(nid)
    runAction(["notification-dismiss", id, String(nid)], "Dismissing…")
  }

  function dismissAllNotifications(id) {
    if (!id) return
    _notifyDeviceId = id
    _reloadNotifications = true
    notifications = []
    runAction(["notification-dismiss", id, "--all"], "Dismissing…")
  }

  function replyNotification(id, nid, text) {
    if (!id || nid === undefined || nid === null || nid === "") return
    _notifyDeviceId = id
    _reloadNotifications = true
    runAction(["notification-reply", id, String(nid), text], "Sending…")
  }

  function shareFile(id) {
    if (pickerProcess.running || !id) return
    pickerProcess.command = ["omarchy-file-select", "--title", "Send to phone", "--multiple"]
    pickerProcess.running = true
    pickerProcess._deviceId = id
  }

  function setup() {
    if (settleTimer.running) return
    actionStatus = "Opening installer…"
    actionStatusTimer.restart()
    Quickshell.execDetached(["omarchy-launch-floating-terminal-with-presentation", setupPath])
    settleTimer.ticks = 0
    settleTimer.running = true
  }

  Timer {
    id: refreshTimer
    interval: root.refreshIntervalSec * 1000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Timer {
    id: actionStatusTimer
    interval: 2200
    repeat: false
    onTriggered: root.actionStatus = ""
  }

  Timer {
    id: delayedRefresh
    interval: 800
    repeat: false
    onTriggered: root.refresh()
  }

  Timer {
    id: threadRefreshTimer
    interval: 1200
    repeat: false
    onTriggered: root.refreshThread()
  }

  Timer {
    id: settleTimer
    interval: 2000
    repeat: true
    running: false
    property int ticks: 0
    onTriggered: {
      ticks += 1
      root.refresh()
      if ((root.installed && root.running) || ticks >= 8) {
        ticks = 0
        settleTimer.running = false
      }
    }
  }

  Process {
    id: statusProcess
    running: false
    command: []
    stdout: StdioCollector { id: statusStdout; waitForEnd: true }
    stderr: StdioCollector { id: statusStderr; waitForEnd: true }
    onExited: function() {
      root.refreshing = false
      root.applyStatus(statusStdout.text)
    }
  }

  Process {
    id: actionProcess
    running: false
    command: []
    stdout: StdioCollector { id: actionStdout; waitForEnd: true }
    stderr: StdioCollector { id: actionStderr; waitForEnd: true }
    onExited: function() {
      var parsed = Model.parseStatus(actionStdout.text)
      if (parsed && parsed.ok === false && (parsed.error || parsed.lastError)) {
        root.lastError = String(parsed.error || parsed.lastError)
        root.actionStatus = ""
        root._desired = -1
        if (root._reloadThread) root.dropPending()
        root._reloadThread = false
      } else {
        root.lastError = ""
      }
      delayedRefresh.restart()
      if (root._reloadNotifications && root._notifyDeviceId) {
        root._reloadNotifications = false
        root.loadNotifications(root._notifyDeviceId)
      }
      if (root._reloadThread) {
        root._reloadThread = false
        threadRefreshTimer.restart()
      }
      if (root._actionQueue.length > 0) {
        var queued = root._actionQueue.shift()
        root.runAction(queued.args, queued.label)
      }
    }
  }

  Process {
    id: pickerProcess
    property string _deviceId: ""
    running: false
    command: []
    stdout: StdioCollector { id: pickerStdout; waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) return
      var lines = String(pickerStdout.text || "").split("\n")
      for (var i = 0; i < lines.length; i++) {
        var path = lines[i].trim()
        if (path !== "") root.runAction(["share-file", pickerProcess._deviceId, path], "Sending file…")
      }
    }
  }

  Process {
    id: smsProcess
    property string _kind: ""
    property string _threadId: ""
    running: false
    command: []
    stdout: StdioCollector { id: smsStdout; waitForEnd: true }
    onExited: function() {
      var parsed = Model.parseStatus(smsStdout.text)
      var kind = smsProcess._kind
      var staleThread = (kind === "thread" || kind === "refresh" || kind === "older")
        && String(smsProcess._threadId || "") !== String(root.smsThreadId || "")
      if (parsed && parsed.ok === false) {
        var err = String(parsed.error || parsed.lastError || "SMS failed")
        if (err.toLowerCase().indexOf("timeout") === -1) root.lastError = err
      } else if (!staleThread) {
        root.lastError = ""
        if (kind === "conversations") root.conversations = parsed.conversations || []
        else if (kind === "contacts") root.contacts = parsed.contacts || []
        else if (kind === "notifications") root.notifications = parsed.notifications || []
        else if (kind === "thread") root.messages = parsed.messages || []
        else if (kind === "refresh") root.mergeMessages(parsed.messages || [])
        else if (kind === "older") {
          var before = root.messages.length
          root.mergeMessages(parsed.messages || [])
          if (root.messages.length <= before) root.smsHasMore = false
        }
      }
      if (root._smsQueue.length > 0) {
        var next = root._smsQueue.shift()
        root.smsProcess._kind = next.kind
        root.smsProcess._threadId = next.threadId || ""
        root.smsProcess.command = root.helper(next.args)
        root.smsProcess.running = true
        return
      }
      root.smsLoading = false
    }
  }
}
