import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "Model.js" as Model

ColumnLayout {
  id: root
  property var service: null
  property var device: null
  property string page: "list"
  property var current: null
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property string fontFamily: Style.font.family
  property bool cursorActive: false
  property int listIndex: 0
  property string draft: ""
  property string copiedHint: ""
  property bool hideSmsNotifications: true

  readonly property var allNotifications: service ? (service.notifications || []) : []
  readonly property bool hideSms: hideSmsNotifications && !!(device && device.hasSms)
  readonly property var notifications: Model.visibleNotifications(allNotifications, hideSms)
  readonly property int hiddenSmsCount: Math.max(0, allNotifications.length - notifications.length)
  readonly property bool loading: service ? service.smsLoading === true : false
  readonly property string deviceId: device ? String(device.id || "") : ""
  readonly property bool editorFocused: draftField.activeFocus
  readonly property bool hasDismissable: {
    for (var i = 0; i < notifications.length; i++) {
      if (notifications[i] && notifications[i].dismissable) return true
    }
    return false
  }

  signal backRequested()
  signal releaseEditor()

  onNotificationsChanged: listIndex = Math.max(listMin(), Math.min(listMax(), listIndex))

  spacing: Style.space(10)

  function openList() {
    page = "list"
    current = null
    draft = ""
    listIndex = 0
    cursorActive = true
    if (deviceId !== "") service.loadNotifications(deviceId)
    releaseEditor()
    scrollToTop()
  }

  function openReply(item) {
    current = item
    page = "reply"
    draft = ""
    cursorActive = true
    Qt.callLater(function() { if (draftField) draftField.forceActiveFocus() })
  }

  function listMin() {
    return hasDismissable ? -1 : 0
  }

  function listMax() {
    if (notifications.length === 0) return 0
    return notifications.length - 1
  }

  function currentItem() {
    if (page === "reply") return draftField
    if (hasDismissable && listIndex < 0) return dismissAllRow
    if (notifRepeater) return notifRepeater.itemAt(listIndex)
    return backButton
  }

  function notificationAtCursor() {
    if (listIndex < 0 || listIndex >= notifications.length) return null
    return notifications[listIndex]
  }

  function moveList(dy) {
    if (dy === 0) return
    cursorActive = true
    if (page === "reply") return
    listIndex = Math.max(listMin(), Math.min(listMax(), listIndex + dy))
  }

  function scrollCursorIntoView() {
    var item = currentItem()
    if (!item || item === draftField || item === backButton || item === dismissAllRow) return
    Qt.callLater(function() { Model.scrollFlickToItem(notifyFlick, item, Style.space(8)) })
  }

  function scrollToTop() {
    Qt.callLater(function() {
      Qt.callLater(function() {
        if (root.page !== "list") return
        notifyFlick.contentY = 0
      })
    })
  }

  function copySnippet(item) {
    if (!item || !item.value || !service) return
    var hint = item.kind === "code" ? "Copied " + item.value : "Copied link"
    service.copyToClipboard(item.value, hint)
    copiedHint = hint
    copyHintTimer.restart()
  }

  function copyPrimary() {
    var item = page === "reply" ? current : notificationAtCursor()
    copySnippet(Model.primaryCopySnippet(Model.notificationCopySnippets(item)))
  }

  function activateList() {
    if (page === "reply") {
      sendDraft()
      return
    }
    if (hasDismissable && listIndex < 0) {
      dismissAllVisible()
      return
    }
    var item = notificationAtCursor()
    if (!item) return
    if (item.canReply) openReply(item)
  }

  function dismissItem(item) {
    if (!service || !deviceId || !item || !item.dismissable) return
    service.dismissNotification(deviceId, item.id)
  }

  function dismissCurrent() {
    if (page !== "list" || !service) return
    if (hasDismissable && listIndex < 0) {
      dismissAllVisible()
      return
    }
    dismissItem(notificationAtCursor())
  }

  function dismissAllVisible() {
    if (!service || !deviceId) return
    if (hiddenSmsCount === 0) {
      service.dismissAllNotifications(deviceId)
      return
    }
    for (var i = 0; i < notifications.length; i++) {
      if (notifications[i] && notifications[i].dismissable)
        service.dismissNotification(deviceId, notifications[i].id)
    }
  }

  function sendDraft() {
    var text = String(draft || "").trim()
    if (!service || !deviceId || !current || text === "") return
    service.replyNotification(deviceId, current.id, text)
    draft = ""
    openList()
  }

  RowLayout {
    Layout.fillWidth: true
    spacing: Style.space(8)

    Button {
      id: backButton
      text: root.page === "list" ? "Devices" : "Notifications"
      iconText: "󰁍"
      bordered: true
      foreground: root.foreground
      fontFamily: root.fontFamily
      onClicked: {
        if (root.page === "list") root.backRequested()
        else root.openList()
      }
    }

    Text {
      Layout.fillWidth: true
      horizontalAlignment: Text.AlignRight
      text: root.page === "reply" ? Model.notificationTitle(root.current) : "Notifications"
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      elide: Text.ElideRight
    }
  }

  PanelSeparator {
    Layout.fillWidth: true
    foreground: root.foreground
  }

  Text {
    visible: root.loading && root.page === "list"
    Layout.fillWidth: true
    text: "Loading…"
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  Text {
    visible: root.copiedHint !== ""
    Layout.fillWidth: true
    text: root.copiedHint
    color: root.dim
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  Timer {
    id: copyHintTimer
    interval: 1800
    repeat: false
    onTriggered: root.copiedHint = ""
  }

  Button {
    id: dismissAllRow
    visible: root.hasDismissable && root.page === "list"
    Layout.fillWidth: true
    leftAlign: true
    text: "Dismiss all"
    iconText: "󰆴"
    bordered: true
    foreground: root.foreground
    fontFamily: root.fontFamily
    hasCursor: root.cursorActive && root.page === "list" && root.listIndex < 0
    onClicked: root.dismissAllVisible()
    onHovered: function(on) { if (on) { root.cursorActive = true; root.listIndex = -1 } }
  }

  PanelSeparator {
    visible: root.hasDismissable && root.page === "list"
    Layout.fillWidth: true
    foreground: root.foreground
  }

  Flickable {
    id: notifyFlick
    Layout.fillWidth: true
    Layout.fillHeight: true
    contentWidth: width
    contentHeight: listColumn.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick
    interactive: contentHeight > height
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    Column {
      id: listColumn
      visible: root.page === "list"
      width: notifyFlick.width
      spacing: Style.space(6)

    Text {
      visible: !root.loading && root.notifications.length === 0
      width: parent.width
      text: root.hiddenSmsCount > 0 ? "SMS is in Messages." : "No notifications from the phone right now."
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }

    Repeater {
      id: notifRepeater
      model: root.notifications
      CursorSurface {
        id: notifRow
        required property var modelData
        required property int index
        width: parent.width
        hasCursor: root.cursorActive && root.page === "list" && root.listIndex === index
        foreground: root.foreground
        readonly property var snips: Model.notificationCopySnippets(modelData)
        implicitHeight: notifInner.implicitHeight + Style.spacing.rowPaddingX
        RowLayout {
          id: notifInner
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: Style.space(10)
          anchors.rightMargin: Style.space(10)
          spacing: Style.space(8)
          Item {
            Layout.fillWidth: true
            implicitHeight: textCol.implicitHeight
            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onEntered: {
                root.cursorActive = true
                root.listIndex = notifRow.index
              }
              onClicked: {
                root.listIndex = notifRow.index
                if (notifRow.modelData && notifRow.modelData.canReply) root.openReply(notifRow.modelData)
              }
            }
            ColumnLayout {
              id: textCol
              width: parent.width
              spacing: Style.space(1)
              RowLayout {
                Layout.fillWidth: true
                Text {
                  textFormat: Text.PlainText
                  text: Model.notificationTitle(notifRow.modelData)
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  elide: Text.ElideRight
                  Layout.fillWidth: true
                }
                Text {
                  visible: !!(notifRow.modelData && notifRow.modelData.canReply)
                  text: "Reply"
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
              Text {
                textFormat: Text.PlainText
                text: Model.notificationMeta(notifRow.modelData)
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
                Layout.fillWidth: true
              }
              Text {
                textFormat: Text.PlainText
                text: Model.notificationPreview(notifRow.modelData)
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
              }
              Repeater {
                model: notifRow.snips
                CopyChip {
                  required property var modelData
                  snippet: modelData
                  Layout.fillWidth: true
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  onActivated: {
                    root.listIndex = notifRow.index
                    root.copySnippet(modelData)
                  }
                }
              }
            }
          }
          PanelActionButton {
            visible: !!(notifRow.modelData && notifRow.modelData.dismissable)
            iconText: "󰅖"
            tooltipText: "Dismiss"
            foreground: root.foreground
            fontFamily: root.fontFamily
            Layout.alignment: Qt.AlignTop
            hasCursor: root.cursorActive && root.page === "list" && root.listIndex === notifRow.index
            onClicked: {
              root.listIndex = notifRow.index
              root.dismissItem(notifRow.modelData)
            }
            onHovered: function(on) {
              if (!on) return
              root.cursorActive = true
              root.listIndex = notifRow.index
            }
          }
        }
      }
    }
    }
  }

  PanelSeparator {
    visible: root.page === "reply"
    Layout.fillWidth: true
    foreground: root.foreground
  }

  Column {
    visible: root.page === "reply"
    Layout.fillWidth: true
    spacing: Style.space(8)

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: Model.notificationPreview(root.current)
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      wrapMode: Text.WordWrap
    }

    Repeater {
      model: Model.notificationCopySnippets(root.current)
      CopyChip {
        required property var modelData
        snippet: modelData
        width: parent.width
        foreground: root.foreground
        fontFamily: root.fontFamily
        onActivated: root.copySnippet(modelData)
      }
    }

    RowLayout {
      width: parent.width
      spacing: Style.space(6)
      TextField {
        id: draftField
        Layout.fillWidth: true
        foreground: root.foreground
        placeholderText: "Reply"
        text: root.draft
        onTextChanged: if (text !== root.draft) root.draft = text
        onAccepted: root.sendDraft()
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            event.accepted = true
            draftField.focus = false
            root.openList()
          }
        }
      }
      PanelActionButton {
        iconText: "󰒊"
        foreground: root.foreground
        fontFamily: root.fontFamily
        enabled: String(root.draft || "").trim() !== ""
        onClicked: root.sendDraft()
      }
    }
  }
}
