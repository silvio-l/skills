// lan-computer-use agent for macOS. Runs in the user's GUI session, listens on 127.0.0.1 only and answers
// newline-delimited JSON requests that carry a random token (written to state.json in the state directory).
// Same protocol as the Windows agent. Coordinates are global screen points (top-left origin of the main display).
// Built by setup.sh with `swiftc -O -swift-version 5`; needs Accessibility (+ Screen Recording for shot/ocr)
// for the process that starts it (locally: the terminal app).
import AppKit
import ApplicationServices
import Carbon
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

let VERSION = "1"
typealias Dict = [String: Any]

struct AgentError: Error { let msg: String; init(_ m: String) { msg = m } }

var token = ""
var build = ""
var idleMinutes = 30.0
var stateDir = ""
var lastRequest = Date()
var refs: [String: AXUIElement] = [:]
var refCounter = 0
var shotScale = 1.0, shotOrigin = CGPoint.zero, haveShot = false
let eventSource = CGEventSource(stateID: .hidSystemState)

// ---------- argument helpers ----------
func str(_ a: Dict, _ k: String, _ d: String = "") -> String {
    guard let v = a[k], !(v is NSNull) else { return d }
    if let s = v as? String { return s }
    return "\(v)"
}
func num(_ a: Dict, _ k: String, _ d: Double) -> Double {
    guard let v = a[k] else { return d }
    if let n = v as? NSNumber { return n.doubleValue }
    if let s = v as? String, let x = Double(s) { return x }
    return d
}
func int(_ a: Dict, _ k: String, _ d: Int) -> Int { Int(num(a, k, Double(d))) }
func bool(_ a: Dict, _ k: String) -> Bool { (a[k] as? Bool) ?? false }
func has(_ a: Dict, _ k: String) -> Bool { if let v = a[k], !(v is NSNull) { return true }; return false }
func ok() -> Dict { ["ok": true] }
func fail(_ m: String) -> Dict { ["ok": false, "error": m] }
func sleepMs(_ ms: Int) { if ms > 0 { usleep(useconds_t(ms) * 1000) } }
func clip(_ s: String?, _ n: Int) -> String {
    guard var s = s else { return "" }
    s = s.replacingOccurrences(of: "\r", with: " ").replacingOccurrences(of: "\n", with: " ").trimmingCharacters(in: .whitespaces)
    return s.count > n ? String(s.prefix(n - 1)) + "…" : s
}
func rectArr(_ r: CGRect) -> [Int] { [Int(r.minX.rounded()), Int(r.minY.rounded()), Int(r.width.rounded()), Int(r.height.rounded())] }

// ---------- server ----------
func runAgent() -> Int32 {
    let argv = CommandLine.arguments
    var i = 1
    while i + 1 < argv.count {
        switch argv[i] {
        case "--idle": idleMinutes = Double(argv[i + 1]) ?? 30
        case "--build": build = argv[i + 1]
        case "--dir": stateDir = argv[i + 1]
        default: break
        }
        i += 2
    }
    if stateDir.isEmpty { stateDir = NSHomeDirectory() + "/Library/Caches/lan-computer-use" }
    try? FileManager.default.createDirectory(atPath: stateDir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    let lockFd = open(stateDir + "/agent.lock", O_CREAT | O_RDWR, 0o600)
    if lockFd < 0 || flock(lockFd, LOCK_EX | LOCK_NB) != 0 { return 2 }
    signal(SIGPIPE, SIG_IGN)
    AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 2.0)
    var bytes = [UInt8](repeating: 0, count: 32)
    guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { return 3 }
    token = bytes.map { String(format: "%02x", $0) }.joined()

    let fd = socket(AF_INET, SOCK_STREAM, 0)
    var yes: Int32 = 1
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
    var addr = sockaddr_in()
    addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = 0
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    let rc = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
    }
    guard rc == 0, listen(fd, 8) == 0 else { return 3 }
    var len = socklen_t(MemoryLayout<sockaddr_in>.size)
    _ = withUnsafeMutablePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(fd, $0, &len) }
    }
    let port = Int(UInt16(bigEndian: addr.sin_port))
    let stateFile = stateDir + "/state.json"
    let state: Dict = ["port": port, "token": token, "pid": Int(getpid()), "build": build, "version": VERSION]
    let tmp = stateFile + ".tmp"
    guard let data = try? JSONSerialization.data(withJSONObject: state),
          FileManager.default.createFile(atPath: tmp, contents: data, attributes: [.posixPermissions: 0o600]),
          rename(tmp, stateFile) == 0 else { return 3 }

    // the first accurate Vision request loads its model (~20 s); do that now, off the request path
    DispatchQueue.global(qos: .utility).async { prewarmVision() }

    var quit = false
    while !quit {
        // let AppKit process workspace notifications so running-application data stays fresh
        _ = CFRunLoopRunInMode(CFRunLoopMode.defaultMode, 0, true)
        var pfd = pollfd(fd: fd, events: Int16(POLLIN), revents: 0)
        overlayTick()
        if poll(&pfd, 1, 1000) <= 0 {
            if Date().timeIntervalSince(lastRequest) > idleMinutes * 60 { break }
            continue
        }
        let c = accept(fd, nil, nil)
        if c < 0 { continue }
        var one: Int32 = 1
        setsockopt(c, IPPROTO_TCP, TCP_NODELAY, &one, socklen_t(MemoryLayout<Int32>.size))
        setsockopt(c, SOL_SOCKET, SO_NOSIGPIPE, &one, socklen_t(MemoryLayout<Int32>.size))
        var tv = timeval(tv_sec: 60, tv_usec: 0)
        setsockopt(c, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        quit = serve(c)
        close(c)
    }
    close(fd)
    // remove the state file only while it still describes this process
    if let d = FileManager.default.contents(atPath: stateFile),
       let s = try? JSONSerialization.jsonObject(with: d) as? Dict, (s["pid"] as? Int) == Int(getpid()) {
        unlink(stateFile)
    }
    return 0
}

func tokenOk(_ t: String) -> Bool {
    let a = Array(t.utf8), b = Array(token.utf8)
    if a.count != b.count { return false }
    var diff: UInt8 = 0
    for i in 0..<a.count { diff |= a[i] ^ b[i] }
    return diff == 0
}

func sendLine(_ c: Int32, _ obj: Dict) -> Bool {
    guard var data = try? JSONSerialization.data(withJSONObject: obj) else { return false }
    data.append(0x0A)
    return data.withUnsafeBytes { raw -> Bool in
        var off = 0
        while off < raw.count {
            let n = write(c, raw.baseAddress! + off, raw.count - off)
            if n <= 0 { return false }
            off += n
        }
        return true
    }
}

// one connection, any number of request lines; returns true when the agent should exit
func serve(_ c: Int32) -> Bool {
    var buf = Data()
    var chunk = [UInt8](repeating: 0, count: 65536)
    while true {
        while let nl = buf.firstIndex(of: 0x0A) {
            let line = buf.subdata(in: buf.startIndex..<nl)
            buf.removeSubrange(buf.startIndex...nl)
            if line.allSatisfy({ $0 == 0x20 || $0 == 0x0D || $0 == 0x09 }) { continue }
            lastRequest = Date()
            var resp: Dict
            var quit = false, badToken = false
            do {
                guard let req = try JSONSerialization.jsonObject(with: line) as? Dict else { throw AgentError("request must be a JSON object") }
                if !tokenOk(str(req, "token")) { resp = fail("bad token"); badToken = true }
                else {
                    let cmd = str(req, "cmd")
                    if cmd == "quit" { quit = true; resp = ok() } else { resp = try dispatch(cmd, req) }
                }
            } catch let e as AgentError { resp = fail(e.msg) } catch { resp = fail("\(error)") }
            if !sendLine(c, resp) { return false }
            if quit { return true }
            if badToken { return false }
        }
        let n = read(c, &chunk, chunk.count)
        if n <= 0 { return false }
        buf.append(chunk, count: n)
    }
}

func dispatch(_ cmd: String, _ a: Dict) throws -> Dict {
    _ = CFRunLoopRunInMode(CFRunLoopMode.defaultMode, 0, true)
    if cmd == "task" { return taskCmd(a) }
    if let label = actionLabel(cmd, a) {
        actionText = label; actionAt = Date()
        if !overlayOn { overlayOn = true; overlayStart = Date() }
        overlayTick()
    }
    switch cmd {
    case "hello": return hello()
    case "windows": return windowsCmd(a)
    case "snapshot": return try snapshot(a)
    case "find": return try find(a)
    case "wait": return try waitCmd(a)
    case "shot": return try shot(a)
    case "ocr": return try ocrCmd(a)
    case "click": return try click(a)
    case "move": return try moveCmd(a)
    case "drag": return try drag(a)
    case "scroll": return try scroll(a)
    case "press": return try press(a)
    case "set-value": return try setValue(a)
    case "focus": return try focusCmd(a)
    case "type": return try typeCmd(a)
    case "key": return try keyCmd(a)
    case "activate": return try activateCmd(a)
    case "launch": return try launch(a)
    default: throw AgentError("unknown command '\(cmd)'")
    }
}

// ---------- overlay ----------
// A small, click-through status panel in the top-right corner so the person at the machine sees that it is being
// controlled, what happens right now and how long it will last. Texts follow the
// system language (German or English). sharingType = .none keeps it out of every
// screen capture, the agent's own shots included (and out of screen sharing: it is for the person at the machine).
let german = (Locale.preferredLanguages.first ?? "").lowercased().hasPrefix("de")
func tr(_ de: String, _ en: String) -> String { german ? de : en }
var overlayPanel: NSPanel? = nil
var overlayLabel: NSTextField? = nil
var overlayOn = false
var overlayStart = Date()
var taskText = ""
var taskEnd: Date? = nil
var actionText = ""
var actionAt = Date()

func mmss(_ t: Double) -> String { let s = max(0, Int(t.rounded())); return String(format: "%d:%02d", s / 60, s % 60) }

func actionLabel(_ cmd: String, _ a: Dict) -> String? {
    let tgt = has(a, "ref") ? " " + str(a, "ref") : (has(a, "x") ? " @\(int(a, "x", 0)),\(int(a, "y", 0))" : "")
    switch cmd {
    case "hello": return tr("verbunden", "connected")
    case "windows", "snapshot", "find": return tr("liest die Oberfläche", "reading the UI")
    case "wait": return tr("wartet", "waiting")
    case "shot": return tr("macht einen Screenshot", "taking a screenshot")
    case "ocr": return tr("liest Text auf dem Bildschirm", "reading screen text")
    case "click": return tr("klickt", "clicking") + tgt
    case "move": return tr("bewegt die Maus", "moving the mouse") + tgt
    case "drag": return tr("zieht", "dragging")
    case "scroll": return tr("scrollt", "scrolling") + tgt
    case "press": return tr("betätigt", "pressing") + tgt
    case "set-value": return tr("setzt einen Wert", "setting a value") + tgt
    case "focus": return tr("fokussiert", "focusing") + tgt
    case "type": let n = str(a, "text").count; return tr("tippt \(n) Zeichen", "typing \(n) characters")
    case "key": let k = (a["keys"] as? [Any])?.map { "\($0)" }.joined(separator: " ") ?? ""; return tr("drückt ", "pressing ") + clip(k, 30)
    case "activate": return tr("holt ein Fenster nach vorn", "bringing a window to front")
    case "launch": return tr("startet ", "launching ") + clip((str(a, "target") as NSString).lastPathComponent, 30)
    default: return nil
    }
}

// compact: bold header, optional task, current action, one small line with run time, ETA and idle end
func overlayText() -> NSAttributedString {
    let now = Date()
    let white = NSColor(white: 0.96, alpha: 1), dim = NSColor(white: 0.72, alpha: 1)
    let out = NSMutableAttributedString()
    func add(_ t: String, _ size: CGFloat, _ w: NSFont.Weight, _ c: NSColor) {
        out.append(NSAttributedString(string: t, attributes: [.font: NSFont.monospacedDigitSystemFont(ofSize: size, weight: w), .foregroundColor: c]))
    }
    add(tr("Claude steuert diesen Rechner", "Claude is controlling this computer"), 13, .semibold, white)
    if !taskText.isEmpty { add("\n" + clip(taskText, 60), 12, .regular, white) }
    if !actionText.isEmpty {
        add("\n▸ " + clip(actionText, 40) + " · " + tr("vor ", "") + mmss(now.timeIntervalSince(actionAt)) + tr("", " ago"), 12, .regular, white)
    }
    var meta = [tr("läuft ", "running ") + mmss(now.timeIntervalSince(overlayStart))]
    if let end = taskEnd {
        let left = end.timeIntervalSince(now)
        meta.append(left >= 0 ? tr("noch ca. ", "about ") + mmss(left) + tr("", " left") : tr("überzogen +", "overdue +") + mmss(-left))
    }
    meta.append(tr("Auto-Ende ", "auto-stop ") + mmss(idleMinutes * 60 - now.timeIntervalSince(lastRequest)))
    add("\n" + meta.joined(separator: " · "), 11, .regular, dim)
    return out
}

var overlayIcon: NSImageView? = nil

func makeOverlay() {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    app.finishLaunching()
    let p = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 300, height: 70), styleMask: [.borderless, .nonactivatingPanel],
                    backing: .buffered, defer: false)
    p.level = .screenSaver
    p.isOpaque = false
    p.backgroundColor = .clear
    p.hasShadow = true
    p.ignoresMouseEvents = true
    p.hidesOnDeactivate = false
    p.isReleasedWhenClosed = false
    p.sharingType = .none
    p.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle, .fullScreenAuxiliary]
    // fixed dark plate with a yellow rim: reads as a warning on light and dark desktops alike
    let bg = NSView(frame: p.contentView!.bounds)
    bg.wantsLayer = true
    bg.layer?.backgroundColor = NSColor(white: 0.11, alpha: 0.94).cgColor
    bg.layer?.cornerRadius = 9
    bg.layer?.borderWidth = 1.5
    bg.layer?.borderColor = NSColor.systemYellow.cgColor
    bg.autoresizingMask = [.width, .height]
    let icon = NSImageView(frame: .zero)
    if let img = NSImage(systemSymbolName: "exclamationmark.triangle.fill", accessibilityDescription: nil) {
        let cfg = NSImage.SymbolConfiguration(pointSize: 20, weight: .semibold).applying(.init(paletteColors: [.black, .systemYellow]))
        icon.image = img.withSymbolConfiguration(cfg)
    }
    bg.addSubview(icon)
    let l = NSTextField(labelWithString: "")
    l.maximumNumberOfLines = 0
    l.lineBreakMode = .byTruncatingTail
    bg.addSubview(l)
    p.contentView = bg
    overlayPanel = p
    overlayLabel = l
    overlayIcon = icon
}

func overlayTick() {
    // drain AppKit events so the panel stays responsive to the window server
    while let e = NSApp?.nextEvent(matching: .any, until: nil, inMode: .default, dequeue: true) { NSApp.sendEvent(e) }
    guard overlayOn else { return }
    if overlayPanel == nil { makeOverlay() }
    guard let p = overlayPanel, let l = overlayLabel else { return }
    l.attributedStringValue = overlayText()
    let width: CGFloat = 300, pad: CGFloat = 9, iconW: CGFloat = 26
    let textW = width - 2 * pad - iconW - 8
    let th = ceil(l.sizeThatFits(NSSize(width: textW, height: 400)).height)
    let h = th + 2 * pad
    let vf = (NSScreen.screens.first ?? NSScreen.main)?.visibleFrame ?? NSRect(x: 0, y: 0, width: 800, height: 600)
    p.setFrame(NSRect(x: vf.maxX - width - 10, y: vf.maxY - h - 10, width: width, height: h), display: false)
    l.frame = NSRect(x: pad + iconW + 8, y: pad, width: textW, height: th)
    overlayIcon?.frame = NSRect(x: pad, y: h - pad - iconW, width: iconW, height: iconW)
    if !p.isVisible { p.orderFrontRegardless() }
    p.displayIfNeeded()
    CATransaction.flush()
}

func overlayHide() {
    overlayPanel?.orderOut(nil)
    CATransaction.flush()
}

func taskCmd(_ a: Dict) -> Dict {
    if bool(a, "done") {
        taskText = ""; taskEnd = nil; actionText = ""
        overlayOn = false
        overlayHide()
        return ["ok": true, "overlay": "hidden"]
    }
    if has(a, "text") { taskText = str(a, "text") }
    if has(a, "eta") { let e = num(a, "eta", 0); taskEnd = e > 0 ? Date().addingTimeInterval(e) : nil }
    if !overlayOn { overlayOn = true; overlayStart = Date() }
    overlayTick()
    return ["ok": true, "overlay": "shown"]
}

// ---------- session state ----------
func desktopState() -> String {
    guard let d = CGSessionCopyCurrentDictionary() as? [String: Any] else { return "(no GUI session)" }
    if (d["CGSSessionScreenIsLocked"] as? Bool) == true { return "locked" }
    if let on = d["kCGSSessionOnConsoleKey"] as? Bool, !on { return "(session not on console)" }
    return "normal"
}

func requireInput() throws {
    let d = desktopState()
    if d != "normal" { throw AgentError("screen is \(d): stop and ask the user") }
    if !AXIsProcessTrusted() {
        throw AgentError("Accessibility permission missing for the app that started the agent (System Settings > Privacy & Security > Accessibility)")
    }
}

func mainDisplayRect() -> CGRect { CGDisplayBounds(CGMainDisplayID()) }

func hello() -> Dict {
    var r = ok()
    r["os"] = "macos"
    r["os_version"] = ProcessInfo.processInfo.operatingSystemVersionString
    r["user"] = NSUserName()
    r["host"] = Host.current().localizedName ?? ProcessInfo.processInfo.hostName
    r["desktop"] = desktopState()
    r["screen"] = rectArr(mainDisplayRect())
    var displays: [Dict] = []
    var ids = [CGDirectDisplayID](repeating: 0, count: 16)
    var count: UInt32 = 0
    if CGGetActiveDisplayList(16, &ids, &count) == .success {
        for id in ids.prefix(Int(count)) {
            var d: Dict = ["id": Int(id), "rect": rectArr(CGDisplayBounds(id)), "main": CGDisplayIsMain(id) != 0]
            if let m = CGDisplayCopyDisplayMode(id), m.width > 0 { d["scale"] = Double(m.pixelWidth) / Double(m.width) }
            displays.append(d)
        }
    }
    r["displays"] = displays
    r["version"] = VERSION; r["build"] = build; r["pid"] = Int(getpid())
    r["units"] = "pt"
    r["permissions"] = ["accessibility": AXIsProcessTrusted(), "screen": CGPreflightScreenCaptureAccess()]
    return r
}

// ---------- AX helpers ----------
func axAttr(_ e: AXUIElement, _ name: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, name as CFString, &v) == .success ? v : nil
}
func axElem(_ v: AnyObject?) -> AXUIElement? {
    guard let v = v, CFGetTypeID(v) == AXUIElementGetTypeID() else { return nil }
    return (v as! AXUIElement)
}
func axString(_ e: AXUIElement, _ name: String) -> String? { axAttr(e, name) as? String }
func axPoint(_ v: AnyObject?) -> CGPoint? {
    guard let v = v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var p = CGPoint.zero
    return AXValueGetValue(v as! AXValue, .cgPoint, &p) ? p : nil
}
func axSize(_ v: AnyObject?) -> CGSize? {
    guard let v = v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
    var s = CGSize.zero
    return AXValueGetValue(v as! AXValue, .cgSize, &s) ? s : nil
}
func axFrame(_ e: AXUIElement) -> CGRect? {
    guard let p = axPoint(axAttr(e, "AXPosition")), let s = axSize(axAttr(e, "AXSize")) else { return nil }
    return CGRect(origin: p, size: s)
}
func axMulti(_ e: AXUIElement, _ names: [String]) -> [String: AnyObject] {
    var out: CFArray?
    var res: [String: AnyObject] = [:]
    guard AXUIElementCopyMultipleAttributeValues(e, names as CFArray, AXCopyMultipleAttributeOptions(rawValue: 0), &out) == .success,
          let arr = out as? [AnyObject] else { return res }
    for (i, v) in arr.enumerated() where i < names.count {
        if v is NSNull { continue }
        if CFGetTypeID(v) == AXValueGetTypeID() && AXValueGetType(v as! AXValue) == .axError { continue }
        res[names[i]] = v
    }
    return res
}
func valueString(_ v: AnyObject?) -> String? {
    guard let v = v else { return nil }
    if let s = v as? String { return s }
    if let n = v as? NSNumber { return n.stringValue }
    if let a = v as? NSAttributedString { return a.string }
    if let u = v as? URL { return u.absoluteString }
    return nil
}
func pidOf(_ e: AXUIElement) -> pid_t { var p: pid_t = 0; AXUIElementGetPid(e, &p); return p }

let roleMap: [String: String] = [
    "AXButton": "button", "AXCheckBox": "checkbox", "AXRadioButton": "radio", "AXTextField": "textfield",
    "AXTextArea": "textfield", "AXStaticText": "text", "AXLink": "link", "AXPopUpButton": "popup",
    "AXComboBox": "combobox", "AXMenuButton": "menubutton", "AXTabGroup": "tablist", "AXRadioGroup": "radiogroup",
    "AXRow": "row", "AXCell": "cell", "AXImage": "image", "AXGroup": "group", "AXScrollArea": "scrollarea",
    "AXWebArea": "document", "AXHeading": "heading", "AXSlider": "slider", "AXMenuItem": "menuitem",
    "AXMenuBarItem": "menubaritem", "AXMenu": "menu", "AXMenuBar": "menubar", "AXList": "list", "AXTable": "table",
    "AXOutline": "tree", "AXToolbar": "toolbar", "AXSheet": "sheet", "AXSplitGroup": "group", "AXSplitter": "splitter",
    "AXLayoutArea": "group", "AXLayoutItem": "group", "AXWindow": "window", "AXDisclosureTriangle": "disclosure",
    "AXProgressIndicator": "progressbar", "AXBusyIndicator": "busy", "AXScrollBar": "scrollbar",
    "AXValueIndicator": "valueindicator", "AXColumn": "column", "AXIncrementor": "stepper", "AXUnknown": "unknown",
    "AXDateField": "datefield", "AXColorWell": "colorwell", "AXDialog": "dialog", "AXApplication": "application"]
let structuralRoles: Set<String> = ["group", "scrollarea", "unknown", "splitter", "column", "valueindicator"]
let actionableRoles: Set<String> = ["button", "checkbox", "radio", "tab", "textfield", "link", "popup", "combobox",
                                    "menubutton", "menuitem", "menubaritem", "slider", "disclosure", "stepper", "datefield", "searchfield"]

func roleName(_ role: String?, _ subrole: String?) -> String {
    if subrole == "AXTabButton" { return "tab" }
    if subrole == "AXSearchField" { return "searchfield" }
    if subrole == "AXSwitch" { return "checkbox" }
    if subrole == "AXApplicationDialog" || subrole == "AXDialog" || subrole == "AXSystemDialog" { return "dialog" }
    guard let role = role else { return "unknown" }
    if let m = roleMap[role] { return m }
    return role.hasPrefix("AX") ? String(role.dropFirst(2)).lowercased() : role.lowercased()
}

let nodeAttrs = ["AXRole", "AXSubrole", "AXTitle", "AXDescription", "AXValue", "AXIdentifier", "AXDOMIdentifier",
                 "AXPosition", "AXSize", "AXEnabled", "AXFocused", "AXSelected", "AXExpanded", "AXPlaceholderValue",
                 "AXHelp", "AXChildren"]

struct NodeData {
    var info: Dict
    var emit: Bool
    var children: [AXUIElement]
    var frame: CGRect?
    var name: String
    var value: String
    var id: String
    var role: String
    var actionable: Bool
}

func nodeData(_ e: AXUIElement) -> NodeData {
    let m = axMulti(e, nodeAttrs)
    let rawRole = m["AXRole"] as? String, sub = m["AXSubrole"] as? String
    let role = roleName(rawRole, sub)
    let isPassword = sub == "AXSecureTextField"
    let rawValue = valueString(m["AXValue"])
    var name = (m["AXTitle"] as? String) ?? ""
    if name.isEmpty { name = (m["AXDescription"] as? String) ?? "" }
    if name.isEmpty, let sr = sub, let w = windowButtonNames[sr] { name = w }
    var value: String? = nil
    if role == "text" { if name.isEmpty { name = rawValue ?? "" } }
    else if let v = rawValue, !v.isEmpty, role != "window", role != "heading" { value = isPassword ? "(hidden)" : clip(v, 120) }
    if name.isEmpty { name = (m["AXPlaceholderValue"] as? String) ?? "" }
    if name.isEmpty { name = (m["AXHelp"] as? String) ?? "" }
    var frame: CGRect? = nil
    if let p = axPoint(m["AXPosition"]), let s = axSize(m["AXSize"]), s.width > 0, s.height > 0 { frame = CGRect(origin: p, size: s) }
    var id = (m["AXIdentifier"] as? String) ?? ""
    if id.isEmpty { id = (m["AXDOMIdentifier"] as? String) ?? "" }
    var flags: [String] = []
    if let en = m["AXEnabled"] as? Bool, !en { flags.append("disabled") }
    if let f = m["AXFocused"] as? Bool, f { flags.append("focused") }
    if isPassword { flags.append("password") }
    if role == "checkbox" || role == "radio", let n = m["AXValue"] as? NSNumber {
        flags.append(n.intValue == 1 ? "checked" : n.intValue == 0 ? "unchecked" : "mixed")
        value = nil
    }
    if let s = m["AXSelected"] as? Bool, s { flags.append("selected") }
    // WebKit reports AXExpanded=false on every node; "collapsed" only where it is meaningful
    if let x = m["AXExpanded"] as? Bool {
        if x { flags.append("expanded") }
        else if ["row", "treeitem", "combobox", "popup", "disclosure", "menubutton", "outline"].contains(role) { flags.append("collapsed") }
    }
    let actionable = actionableRoles.contains(role)
    let emit = !(structuralRoles.contains(role) && name.isEmpty && value == nil && id.isEmpty)
        && !(role == "text" && name.isEmpty)
    var info: Dict = ["role": role, "name": clip(name, 100)]
    if let v = value, v != clip(name, 100) { info["value"] = v }
    if !id.isEmpty && !isGeneratedId(id) { info["id"] = clip(id, 60) }
    if let f = frame { info["rect"] = rectArr(f) }
    if !flags.isEmpty { info["flags"] = flags }
    let kids = (m["AXChildren"] as? [AnyObject] ?? []).compactMap { axElem($0) }
    return NodeData(info: info, emit: emit, children: kids, frame: frame, name: name, value: rawValue ?? "", id: id, role: role, actionable: actionable)
}

let windowButtonNames = ["AXCloseButton": "close window", "AXMinimizeButton": "minimize window",
                         "AXZoomButton": "zoom window", "AXFullScreenButton": "full screen"]

func isGeneratedId(_ id: String) -> Bool {
    let digits = id.filter { $0.isNumber }.count
    return digits == id.count || (id.count >= 32 && digits > id.count / 3)
}

func addRef(_ e: AXUIElement) -> String {
    refCounter += 1
    let r = "e\(refCounter)"
    refs[r] = e
    return r
}
func getRef(_ a: Dict) throws -> AXUIElement {
    let r = str(a, "ref")
    guard let e = refs[r] else { throw AgentError("unknown ref '\(r)' - refs are reset by every snapshot") }
    return e
}

// ---------- windows ----------
struct Win {
    var id: Int
    var pid: pid_t
    var title: String
    var owner: String
    var rect: CGRect
    var layer: Int
}

let ignoredOwners: Set<String> = ["Window Server", "Dock", "Control Center", "SystemUIServer", "Spotlight",
                                  "WindowManager", "Wallpaper", "TextInputMenuAgent", "Screenshot"]

func axWindows(_ pid: pid_t) -> [(AXUIElement, CGRect?, String)] {
    let app = AXUIElementCreateApplication(pid)
    let list = (axAttr(app, "AXWindows") as? [AnyObject] ?? []).compactMap { axElem($0) }
    return list.map { ($0, axFrame($0), axString($0, "AXTitle") ?? "") }
}

func framesMatch(_ a: CGRect?, _ b: CGRect) -> Bool {
    guard let a = a else { return false }
    return abs(a.minX - b.minX) < 3 && abs(a.minY - b.minY) < 3 && abs(a.width - b.width) < 3 && abs(a.height - b.height) < 3
}

func cgWindows(all: Bool) -> [Win] {
    guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]
    else { return [] }
    var axCache: [pid_t: [(AXUIElement, CGRect?, String)]] = [:]
    var out: [Win] = []
    for w in list {
        let layer = w[kCGWindowLayer as String] as? Int ?? 0
        let pid = pid_t(w[kCGWindowOwnerPID as String] as? Int ?? 0)
        let owner = w[kCGWindowOwnerName as String] as? String ?? ""
        guard let bd = w[kCGWindowBounds as String] as? NSDictionary,
              let r = CGRect(dictionaryRepresentation: bd as CFDictionary) else { continue }
        let alpha = w[kCGWindowAlpha as String] as? Double ?? 1
        if pid == getpid() { continue }
        if !all {
            if alpha <= 0.01 || r.width < 40 || r.height < 30 { continue }
            if layer != 0 && (ignoredOwners.contains(owner) || r.width < 120 || r.height < 60) { continue }
        }
        var title = w[kCGWindowName as String] as? String ?? ""
        if title.isEmpty && pid > 0 {
            if axCache[pid] == nil { axCache[pid] = axWindows(pid) }
            title = axCache[pid]!.first(where: { framesMatch($0.1, r) })?.2 ?? ""
        }
        out.append(Win(id: w[kCGWindowNumber as String] as? Int ?? 0, pid: pid, title: title, owner: owner, rect: r, layer: layer))
    }
    return out
}

func appName(_ pid: pid_t, _ fallback: String) -> String { NSRunningApplication(processIdentifier: pid)?.localizedName ?? fallback }

func appMatches(_ pid: pid_t, _ owner: String, _ q: String) -> Bool {
    let q = q.lowercased()
    if owner.lowercased() == q { return true }
    guard let ra = NSRunningApplication(processIdentifier: pid) else { return false }
    if ra.localizedName?.lowercased() == q || ra.bundleIdentifier?.lowercased() == q { return true }
    if ra.executableURL?.lastPathComponent.lowercased() == q { return true }
    if let b = ra.bundleURL?.deletingPathExtension().lastPathComponent.lowercased(), b == q { return true }
    return false
}

func focusedApp() -> AXUIElement? { axElem(axAttr(AXUIElementCreateSystemWide(), "AXFocusedApplication")) }
func frontPid() -> pid_t? {
    if let app = focusedApp() { return pidOf(app) }
    return NSWorkspace.shared.frontmostApplication?.processIdentifier
}

func winInfo(_ w: Win) -> Dict {
    let ra = NSRunningApplication(processIdentifier: w.pid)
    var d: Dict = ["title": w.title, "app": ra?.localizedName ?? w.owner, "pid": Int(w.pid), "handle": w.id,
                   "rect": rectArr(w.rect), "minimized": false, "foreground": frontPid() == w.pid]
    if let b = ra?.bundleIdentifier { d["bundle"] = b }
    if w.layer != 0 { d["layer"] = w.layer }
    return d
}

func windowsCmd(_ a: Dict) -> Dict {
    var r = ok()
    let fp = frontPid()
    var seenFront = false
    r["windows"] = cgWindows(all: bool(a, "all")).map { w -> Dict in
        var d = winInfo(w)
        d["foreground"] = !seenFront && w.pid == fp && w.layer == 0
        if d["foreground"] as? Bool == true { seenFront = true }
        return d
    }
    return r
}

// window selection: handle, title substring and/or app (name, bundle id or executable) - default: front window
func pickWindow(_ a: Dict) throws -> Win {
    let wins = cgWindows(all: false)
    if has(a, "handle") {
        let h = int(a, "handle", 0)
        guard let w = wins.first(where: { $0.id == h }) else { throw AgentError("no on-screen window with handle \(h)") }
        return w
    }
    let title = str(a, "window"), app = str(a, "app")
    if title.isEmpty && app.isEmpty {
        if let fp = frontPid(), let w = wins.first(where: { $0.pid == fp && $0.layer == 0 }) ?? wins.first(where: { $0.pid == fp }) { return w }
        if let w = wins.first(where: { $0.layer == 0 }) { return w }
        throw AgentError("no foreground window")
    }
    for w in wins { // front to back: the first match is the topmost
        if !title.isEmpty && w.title.range(of: title, options: [.caseInsensitive, .diacriticInsensitive]) == nil { continue }
        if !app.isEmpty && !appMatches(w.pid, w.owner, app) { continue }
        return w
    }
    var what = ""
    if !title.isEmpty { what += " title '\(title)'" }
    if !app.isEmpty { what += " app '\(app)'" }
    throw AgentError("no on-screen window matches\(what) (minimized or hidden windows: use activate --app)")
}

func axWindow(for w: Win) -> AXUIElement? {
    let list = axWindows(w.pid)
    if let m = list.first(where: { framesMatch($0.1, w.rect) }) { return m.0 }
    if !w.title.isEmpty, let m = list.first(where: { $0.2 == w.title }) { return m.0 }
    return list.first?.0
}

var manualAXSet: Set<pid_t> = []
func axRoot(for w: Win) -> AXUIElement {
    if !manualAXSet.contains(w.pid) { // Chromium/Electron expose their tree only on request
        AXUIElementSetAttributeValue(AXUIElementCreateApplication(w.pid), "AXManualAccessibility" as CFString, kCFBooleanTrue)
        manualAXSet.insert(w.pid)
    }
    return axWindow(for: w) ?? AXUIElementCreateApplication(w.pid)
}

func bringToFront(pid: pid_t, window: AXUIElement?) {
    let app = AXUIElementCreateApplication(pid)
    if let w = window {
        AXUIElementSetAttributeValue(w, "AXMinimized" as CFString, kCFBooleanFalse)
        AXUIElementPerformAction(w, "AXRaise" as CFString)
        AXUIElementSetAttributeValue(w, "AXMain" as CFString, kCFBooleanTrue)
    }
    AXUIElementSetAttributeValue(app, "AXFrontmost" as CFString, kCFBooleanTrue)
    for _ in 0..<20 {
        if frontPid() == pid { return }
        sleepMs(25)
    }
    NSRunningApplication(processIdentifier: pid)?.activate(options: [.activateAllWindows])
    for _ in 0..<20 {
        if frontPid() == pid { return }
        sleepMs(25)
    }
}

func runningApp(_ q: String) -> NSRunningApplication? {
    let ql = q.lowercased()
    return NSWorkspace.shared.runningApplications.first {
        $0.localizedName?.lowercased() == ql || $0.bundleIdentifier?.lowercased() == ql
            || $0.executableURL?.lastPathComponent.lowercased() == ql
    }
}

func activateCmd(_ a: Dict) throws -> Dict {
    try requireInput()
    var pid: pid_t
    var axw: AXUIElement? = nil
    var title = ""
    do {
        let w = try pickWindow(a)
        pid = w.pid; axw = axWindow(for: w); title = w.title
    } catch let e as AgentError {
        // minimized or hidden: activate the app and restore its first window
        guard has(a, "app"), let ra = runningApp(str(a, "app")) else { throw e }
        pid = ra.processIdentifier
        ra.unhide()
        let wl = axWindows(pid)
        let wt = str(a, "window")
        axw = (wt.isEmpty ? wl.first : wl.first { $0.2.range(of: wt, options: .caseInsensitive) != nil })?.0
        title = axw.flatMap { axString($0, "AXTitle") } ?? ""
    }
    bringToFront(pid: pid, window: axw)
    if frontPid() != pid { throw AgentError("macOS refused to bring '\(title)' (\(appName(pid, "?"))) to the front") }
    sleepMs(int(a, "settle", 120))
    return post()
}

// ---------- post state ----------
func postState() -> Dict {
    var p: Dict = [:]
    if let app = focusedApp() {
        p["app"] = appName(pidOf(app), "?")
        if let w = axElem(axAttr(app, "AXFocusedWindow")) { p["window"] = axString(w, "AXTitle") ?? "" }
        if let f = axElem(axAttr(app, "AXFocusedUIElement")) {
            let n = nodeData(f)
            p["focus_role"] = n.role
            p["focus_name"] = clip(n.name, 60)
        }
    }
    p["desktop"] = desktopState()
    return p
}
func post() -> Dict { var r = ok(); r["post"] = postState(); return r }

// ---------- snapshot / find / wait ----------
func snapshot(_ a: Dict) throws -> Dict {
    let w = try pickWindow(a)
    let maxNodes = int(a, "max", 250), maxDepth = int(a, "depth", 150)
    let all = bool(a, "all"), interactive = bool(a, "interactive")
    var nodes: [Dict] = []
    var truncated = false
    // WebKit (WKWebView, Tauri) and Chromium build their AX tree lazily: the first walk can see an empty web area
    // or only the window buttons while `find` a moment later sees everything. Walk again briefly in that case.
    let chrome = Set(windowButtonNames.values)
    for attempt in 0..<5 {
        refs.removeAll(); refCounter = 0; nodes = []; truncated = false; emptyWebArea = false
        walk(axRoot(for: w), depth: 0, level: 0, maxDepth: maxDepth, maxNodes: maxNodes, clipRect: all ? nil : w.rect,
             interactive: interactive, nodes: &nodes, truncated: &truncated)
        let content = nodes.contains { !chrome.contains($0["name"] as? String ?? "") }
        if (content && !emptyWebArea) || attempt == 4 { break }
        sleepMs(150)
    }
    var r = ok()
    r["window"] = winInfo(w)
    r["nodes"] = nodes
    r["truncated"] = truncated
    return r
}

// interactive mode (-i): only what can be clicked or typed into, as a flat list - far fewer tokens
var emptyWebArea = false // set by walk when a web area has no children yet (lazy AX tree)
let interactiveExtra: Set<String> = ["row", "treeitem", "listitem", "cell"]

// label of a nameless row/cell/button: its descendant texts (Finder, Mail and most tables put it there)
func descendantText(_ e: AXUIElement, limit: Int = 3) -> String {
    var parts: [String] = []
    var stack: [(AXUIElement, Int)] = [(e, 0)]
    var visited = 0
    while let (x, d) = stack.popLast(), parts.count < limit, visited < 60 {
        visited += 1
        let kids = (axAttr(x, "AXChildren") as? [AnyObject] ?? []).compactMap { axElem($0) }
        for k in kids.reversed() { if d < 4 { stack.append((k, d + 1)) } }
        if d == 0 { continue }
        let m = axMulti(x, ["AXRole", "AXValue", "AXTitle", "AXDescription"])
        var s = (m["AXTitle"] as? String) ?? ""
        if s.isEmpty, m["AXRole"] as? String == "AXStaticText" || m["AXRole"] as? String == "AXTextField" { s = valueString(m["AXValue"]) ?? "" }
        if s.isEmpty, m["AXRole"] as? String == "AXImage" { s = "" } // icons only add noise
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty && !parts.contains(t) { parts.append(t) }
    }
    return parts.joined(separator: " | ")
}

func walk(_ e: AXUIElement, depth: Int, level: Int, maxDepth: Int, maxNodes: Int, clipRect: CGRect?,
          interactive: Bool = false, inRow: Bool = false, parentRole: String = "",
          nodes: inout [Dict], truncated: inout Bool) {
    if nodes.count >= maxNodes { truncated = true; return }
    let n = nodeData(e)
    if let c = clipRect, let f = n.frame, !f.intersects(c) { return } // scrolled out of the window
    if n.role == "document" && n.children.isEmpty && axString(e, "AXRole") == "AXWebArea" { emptyWebArea = true }
    if interactive && n.role == "scrollbar" { return } // use the scroll command instead
    var childDepth = depth
    var rowEmitted = inRow
    // -i: a row (or an item of a list/collection view) stands for its cells and labels
    let listItem = parentRole == "list" && !inRow && ["group", "image", "text", "cell"].contains(n.role)
    let extra = (interactiveExtra.contains(n.role) || listItem) && !(inRow && (n.role == "cell" || n.role == "row"))
    let wanted = !interactive || (n.actionable && (n.frame != nil || !n.name.isEmpty)) || extra
    if (n.emit || (interactive && listItem)) && n.role != "window" && wanted {
        var info = n.info
        if interactive && n.name.isEmpty && n.value.isEmpty {
            let t = descendantText(e)
            if !t.isEmpty { info["name"] = clip(t, 100) }
        }
        // tables report AXFocused on every row/cell while the table has focus, collection items report
        // AXEnabled=false although they can be clicked - noise, not state
        if ["row", "cell"].contains(n.role) || listItem, var fl = info["flags"] as? [String] {
            fl.removeAll { $0 == "focused" || (listItem && $0 == "disabled") }
            info["flags"] = fl.isEmpty ? nil : fl
        }
        info["ref"] = addRef(e)
        info["depth"] = interactive ? 0 : depth
        nodes.append(info)
        childDepth = depth + 1
        if n.role == "row" || listItem { rowEmitted = true }
    }
    if level >= maxDepth { return }
    for k in n.children {
        walk(k, depth: childDepth, level: level + 1, maxDepth: maxDepth, maxNodes: maxNodes, clipRect: clipRect,
             interactive: interactive, inRow: rowEmitted, parentRole: n.role, nodes: &nodes, truncated: &truncated)
        if truncated { return }
    }
}

func searchRoots(_ a: Dict) throws -> [(AXUIElement, CGRect?)] {
    let w = try pickWindow(a)
    return [(axRoot(for: w), w.rect)]
}

func search(_ a: Dict, limit: Int) throws -> [(AXUIElement, NodeData)] {
    let text = str(a, "text"), role = str(a, "role").lowercased(), id = str(a, "id")
    let exact = bool(a, "exact")
    var found: [(AXUIElement, NodeData)] = []
    var visited = 0
    for (root, clipRect) in try searchRoots(a) {
        var stack = [root]
        while let e = stack.popLast(), found.count < limit, visited < 20000 {
            visited += 1
            let n = nodeData(e)
            if !bool(a, "all"), let c = clipRect, let f = n.frame, !f.intersects(c) { continue }
            func hit(_ s: String) -> Bool {
                exact ? s.compare(text, options: [.caseInsensitive, .diacriticInsensitive]) == .orderedSame
                    : s.range(of: text, options: [.caseInsensitive, .diacriticInsensitive]) != nil
            }
            let m = (text.isEmpty || hit(n.name) || (n.role != "text" && hit(n.value)))
                && (role.isEmpty || n.role == role) && (id.isEmpty || n.id == id)
            if m && (!text.isEmpty || !role.isEmpty || !id.isEmpty) && n.role != "window" { found.append((e, n)) }
            stack.append(contentsOf: n.children.reversed())
        }
    }
    return found
}

func hitInfo(_ h: (AXUIElement, NodeData)) -> Dict {
    var info = h.1.info
    info["ref"] = addRef(h.0)
    info["depth"] = 0
    return info
}

func find(_ a: Dict) throws -> Dict {
    let hits = try search(a, limit: int(a, "max", 20))
    var r = ok()
    r["nodes"] = hits.map(hitInfo)
    return r
}

func waitCmd(_ a: Dict) throws -> Dict {
    let timeout = num(a, "timeout", 10)
    let gone = bool(a, "gone")
    let start = Date()
    while true {
        let hits = (try? search(a, limit: 1)) ?? []
        let waited = (Date().timeIntervalSince(start) * 100).rounded() / 100
        if !gone, let h = hits.first { var r = ok(); r["nodes"] = [hitInfo(h)]; r["waited"] = waited; return r }
        if gone && hits.isEmpty { var r = ok(); r["waited"] = waited; return r }
        if Date().timeIntervalSince(start) >= timeout {
            throw AgentError("timeout after \(timeout) s waiting for \(gone ? "disappearance" : "element")")
        }
        sleepMs(150)
    }
}

// ---------- screenshot / OCR ----------
// what to capture: a screen rectangle (points) and, for a whole window, its id so occluded windows work too
func captureRegion(_ a: Dict) throws -> (CGRect, Int?) {
    if has(a, "ref") {
        guard let f = axFrame(try getRef(a)) else { throw AgentError("element has no on-screen frame") }
        return (f, nil)
    }
    if has(a, "window") || has(a, "app") || has(a, "handle") || bool(a, "foreground") {
        let w = try pickWindow(a)
        return (w.rect, w.id)
    }
    if has(a, "region"), let r = a["region"] as? [NSNumber], r.count == 4 {
        return (CGRect(x: r[0].doubleValue, y: r[1].doubleValue, width: r[2].doubleValue, height: r[3].doubleValue), nil)
    }
    return (mainDisplayRect(), nil)
}

// what is visible in a screen rectangle (points), at full pixel resolution
func capture(_ rect: CGRect, window: Int? = nil) throws -> CGImage {
    if !CGPreflightScreenCaptureAccess() {
        throw AgentError("Screen Recording permission missing for the app that started the agent (System Settings > Privacy & Security > Screen & System Audio Recording)")
    }
    let r = rect.integral
    if r.width < 1 || r.height < 1 { throw AgentError("empty capture region") }
    let tmp = NSTemporaryDirectory() + "lcu-\(getpid())-\(UUID().uuidString).png"
    defer { unlink(tmp) }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    if let wid = window {
        p.arguments = ["-x", "-o", "-t", "png", "-l", String(wid), tmp]   // window content only, even when covered
    } else {
        p.arguments = ["-x", "-t", "png", "-R", "\(Int(r.minX)),\(Int(r.minY)),\(Int(r.width)),\(Int(r.height))", tmp]
    }
    p.standardOutput = FileHandle.nullDevice
    p.standardError = FileHandle.nullDevice
    try p.run()
    p.waitUntilExit()
    // read the bytes and decode now: ImageIO decodes lazily and the deferred unlink would pull the file away
    guard p.terminationStatus == 0, let bytes = try? Data(contentsOf: URL(fileURLWithPath: tmp)),
          let src = CGImageSourceCreateWithData(bytes as CFData, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary)
    else { throw AgentError("screencapture failed") }
    return img
}

func encodePNG(_ img: CGImage, maxSide: Int) throws -> (Data, Int, Int) {
    var out = img
    let side = max(img.width, img.height)
    if maxSide > 0 && side > maxSide {
        let s = Double(maxSide) / Double(side)
        let w = max(1, Int((Double(img.width) * s).rounded())), h = max(1, Int((Double(img.height) * s).rounded()))
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)
        else { throw AgentError("cannot scale image") }
        ctx.interpolationQuality = .high
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
        guard let scaled = ctx.makeImage() else { throw AgentError("cannot scale image") }
        out = scaled
    }
    let data = NSMutableData()
    guard let dest = CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil) else { throw AgentError("png encoder") }
    CGImageDestinationAddImage(dest, out, nil)
    guard CGImageDestinationFinalize(dest) else { throw AgentError("png encoder") }
    return (data as Data, out.width, out.height)
}

func shot(_ a: Dict) throws -> Dict {
    let (rect, wid) = try captureRegion(a)
    let img = try capture(rect, window: wid)
    let (png, w, h) = try encodePNG(img, maxSide: int(a, "max", 1280))
    let scale = Double(rect.integral.width) / Double(w) // screen points per image pixel
    shotScale = scale; shotOrigin = rect.integral.origin; haveShot = true
    var r = ok()
    r["png"] = png.base64EncodedString()
    r["width"] = w; r["height"] = h
    r["scale"] = (scale * 10000).rounded() / 10000
    r["origin"] = [Int(rect.integral.minX), Int(rect.integral.minY)]
    return r
}

func ocrItems(_ a: Dict, _ query: String) throws -> ([Dict], CGRect) {
    let (region, wid) = try captureRegion(a)
    let rect = region.integral
    let img = try capture(rect, window: wid)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = bool(a, "fast") ? .fast : .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["de-DE", "en-US"]
    try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    var items: [Dict] = []
    for obs in req.results ?? [] {
        guard let cand = obs.topCandidates(1).first else { continue }
        var bb = obs.boundingBox
        if !query.isEmpty {
            guard let range = cand.string.range(of: query, options: [.caseInsensitive, .diacriticInsensitive]) else { continue }
            if let sub = try? cand.boundingBox(for: range) { bb = sub.boundingBox } // just the matched words
        }
        let x = rect.minX + bb.minX * rect.width, y = rect.minY + (1 - bb.maxY) * rect.height
        let w = bb.width * rect.width, h = bb.height * rect.height
        items.append(["text": cand.string, "conf": (Double(cand.confidence) * 100).rounded() / 100,
                      "rect": rectArr(CGRect(x: x, y: y, width: w, height: h)),
                      "center": [Int((x + w / 2).rounded()), Int((y + h / 2).rounded())]])
    }
    items.sort {
        let ra = $0["rect"] as! [Int], rb = $1["rect"] as! [Int]
        return abs(ra[1] - rb[1]) > 6 ? ra[1] < rb[1] : ra[0] < rb[0]
    }
    return (items, rect)
}

func prewarmVision() {
    // real text, so the recognizer (not only the detector) gets loaded
    guard let ctx = CGContext(data: nil, width: 320, height: 64, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return }
    ctx.setFillColor(gray: 1, alpha: 1)
    ctx.fill(CGRect(x: 0, y: 0, width: 320, height: 64))
    let font = CTFontCreateWithName("Helvetica" as CFString, 28, nil)
    let text = NSAttributedString(string: "Warmup Größe 123",
                                  attributes: [NSAttributedString.Key(kCTFontAttributeName as String): font,
                                               NSAttributedString.Key(kCTForegroundColorAttributeName as String): CGColor(gray: 0, alpha: 1)])
    ctx.textPosition = CGPoint(x: 10, y: 20)
    CTLineDraw(CTLineCreateWithAttributedString(text), ctx)
    guard let img = ctx.makeImage() else { return }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["de-DE", "en-US"]
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
}

func ocrCmd(_ a: Dict) throws -> Dict {
    let (items, rect) = try ocrItems(a, str(a, "text"))
    var r = ok()
    r["items"] = items
    r["region"] = rectArr(rect)
    return r
}

// ---------- input ----------
func point(_ a: Dict, _ xk: String, _ yk: String) throws -> CGPoint {
    let x = num(a, xk, 0), y = num(a, yk, 0)
    if bool(a, "img") {
        if !haveShot { throw AgentError("--img needs a screenshot first") }
        return CGPoint(x: shotOrigin.x + x * shotScale, y: shotOrigin.y + y * shotScale)
    }
    if bool(a, "local") { // window-local: offset by the window's top-left corner
        let r = try pickWindow(a).rect
        return CGPoint(x: r.minX + x, y: r.minY + y)
    }
    return CGPoint(x: x, y: y)
}

func center(_ e: AXUIElement) throws -> CGPoint {
    guard let f = axFrame(e), f.width > 0, f.height > 0 else { throw AgentError("element has no on-screen position (offscreen or collapsed)") }
    return CGPoint(x: f.midX, y: f.midY)
}

func target(_ a: Dict) throws -> CGPoint {
    if has(a, "ref") { return try center(try getRef(a)) }
    if has(a, "x") && has(a, "y") { return try point(a, "x", "y") }
    return CGEvent(source: nil)?.location ?? .zero
}

func mouseEvent(_ type: CGEventType, _ p: CGPoint, _ btn: CGMouseButton, clicks: Int64 = 1) {
    guard let e = CGEvent(mouseEventSource: eventSource, mouseType: type, mouseCursorPosition: p, mouseButton: btn) else { return }
    e.setIntegerValueField(.mouseEventClickState, value: clicks)
    e.post(tap: .cghidEventTap)
}

func moveMouse(_ p: CGPoint) {
    mouseEvent(.mouseMoved, p, .left)
    sleepMs(15)
}

func pt(_ p: CGPoint) -> [Int] { [Int(p.x.rounded()), Int(p.y.rounded())] }

func click(_ a: Dict) throws -> Dict {
    try requireInput()
    let p = try target(a)
    var down = CGEventType.leftMouseDown, up = CGEventType.leftMouseUp, btn = CGMouseButton.left
    switch str(a, "button", "left") {
    case "right": down = .rightMouseDown; up = .rightMouseUp; btn = .right
    case "middle": down = .otherMouseDown; up = .otherMouseUp; btn = .center
    default: break
    }
    moveMouse(p)
    let count = bool(a, "double") ? 2 : 1
    for i in 1...count {
        mouseEvent(down, p, btn, clicks: Int64(i))
        mouseEvent(up, p, btn, clicks: Int64(i))
        if i < count { sleepMs(40) }
    }
    sleepMs(int(a, "settle", 120))
    var r = post()
    r["at"] = pt(p)
    return r
}

func moveCmd(_ a: Dict) throws -> Dict {
    try requireInput()
    let p = try target(a)
    moveMouse(p)
    sleepMs(int(a, "settle", 80))
    var r = post(); r["at"] = pt(p); return r
}

func drag(_ a: Dict) throws -> Dict {
    try requireInput()
    let p1 = try point(a, "x", "y"), p2 = try point(a, "x2", "y2")
    moveMouse(p1)
    mouseEvent(.leftMouseDown, p1, .left)
    sleepMs(60)
    let steps = 12
    for i in 1...steps {
        let t = CGFloat(i) / CGFloat(steps)
        mouseEvent(.leftMouseDragged, CGPoint(x: p1.x + (p2.x - p1.x) * t, y: p1.y + (p2.y - p1.y) * t), .left)
        sleepMs(15)
    }
    sleepMs(60)
    mouseEvent(.leftMouseUp, p2, .left)
    sleepMs(int(a, "settle", 150))
    return post()
}

func scroll(_ a: Dict) throws -> Dict {
    try requireInput()
    if has(a, "ref") || has(a, "x") { moveMouse(try target(a)) }
    let dy = int(a, "dy", 0), dx = int(a, "dx", 0)
    // one notch = 3 lines, positive dy scrolls down (content moves up), positive dx scrolls right
    for _ in 0..<max(abs(dy), abs(dx)) {
        let w1: Int32 = dy == 0 ? 0 : (dy > 0 ? -3 : 3)
        let w2: Int32 = dx == 0 ? 0 : (dx > 0 ? -3 : 3)
        CGEvent(scrollWheelEvent2Source: eventSource, units: .line, wheelCount: 2, wheel1: w1, wheel2: w2, wheel3: 0)?.post(tap: .cghidEventTap)
        sleepMs(12)
    }
    sleepMs(int(a, "settle", 120))
    return post()
}

func isWeb(_ e: AXUIElement) -> Bool {
    var cur: AXUIElement? = e
    for _ in 0..<40 {
        guard let c = cur else { return false }
        if axString(c, "AXRole") == "AXWebArea" { return true }
        cur = axElem(axAttr(c, "AXParent"))
    }
    return false
}

func requireNotPassword(_ e: AXUIElement?, _ a: Dict) throws {
    if bool(a, "password_ok") { return }
    if let e = e, axString(e, "AXSubrole") == "AXSecureTextField" {
        throw AgentError("target is a password field: the user enters secrets (pass --password-ok only with explicit consent)")
    }
    if IsSecureEventInputEnabled() {
        throw AgentError("secure keyboard entry is active (password field or terminal setting): typing is blocked by macOS")
    }
}

func press(_ a: Dict) throws -> Dict {
    try requireInput()
    let e = try getRef(a)
    var how = "ax press"
    if AXUIElementPerformAction(e, "AXPress" as CFString) != .success {
        let p = try center(e)
        moveMouse(p)
        mouseEvent(.leftMouseDown, p, .left); mouseEvent(.leftMouseUp, p, .left)
        how = "click (no press action)"
    }
    sleepMs(int(a, "settle", 150))
    var r = post(); r["how"] = how; return r
}

func setValue(_ a: Dict) throws -> Dict {
    try requireInput()
    let e = try getRef(a)
    try requireNotPassword(e, a)
    let text = str(a, "text")
    var how: String
    var settable = DarwinBoolean(false)
    if !isWeb(e), AXUIElementIsAttributeSettable(e, "AXValue" as CFString, &settable) == .success, settable.boolValue,
       AXUIElementSetAttributeValue(e, "AXValue" as CFString, text as CFString) == .success {
        how = "ax value"
    } else {
        // web views ignore programmatic values for their input events: focus, select all, type
        AXUIElementSetAttributeValue(e, "AXFocused" as CFString, kCFBooleanTrue)
        sleepMs(40)
        try sendCombo(["cmd", "a"])
        if text.isEmpty { try sendCombo(["backspace"]) } else { typeText(text) }
        how = "select-all + type"
    }
    sleepMs(int(a, "settle", 80))
    var r = post(); r["how"] = how; return r
}

func focusCmd(_ a: Dict) throws -> Dict {
    try requireInput()
    let e = try getRef(a)
    AXUIElementSetAttributeValue(e, "AXFocused" as CFString, kCFBooleanTrue)
    sleepMs(int(a, "settle", 80))
    return post()
}

func typeCmd(_ a: Dict) throws -> Dict {
    try requireInput()
    var targetEl: AXUIElement? = nil
    if has(a, "ref") {
        targetEl = try getRef(a)
        AXUIElementSetAttributeValue(targetEl!, "AXFocused" as CFString, kCFBooleanTrue)
        sleepMs(40)
    } else if let app = focusedApp() {
        targetEl = axElem(axAttr(app, "AXFocusedUIElement"))
    }
    try requireNotPassword(targetEl, a)
    typeText(str(a, "text"))
    sleepMs(int(a, "settle", 80))
    return post()
}

func postKey(_ code: CGKeyCode, down: Bool, flags: CGEventFlags) {
    guard let e = CGEvent(keyboardEventSource: eventSource, virtualKey: code, keyDown: down) else { return }
    e.flags = flags
    e.post(tap: .cghidEventTap)
}

// one grapheme per event: web views and Electron drop all but the first character of longer unicode strings
func typeText(_ s: String) {
    for ch in s {
        if ch == "\r" { continue }
        if ch == "\n" || ch == "\r\n" { postKey(36, down: true, flags: []); postKey(36, down: false, flags: []); sleepMs(8); continue }
        if ch == "\t" { postKey(48, down: true, flags: []); postKey(48, down: false, flags: []); sleepMs(8); continue }
        let units = Array(String(ch).utf16)
        for down in [true, false] {
            guard let e = CGEvent(keyboardEventSource: eventSource, virtualKey: 0, keyDown: down) else { continue }
            e.flags = []
            e.keyboardSetUnicodeString(stringLength: units.count, unicodeString: units)
            e.post(tap: .cghidEventTap)
        }
        sleepMs(3)
    }
}

let namedKeys: [String: CGKeyCode] = [
    "enter": 36, "return": 36, "tab": 48, "space": 49, "backspace": 51, "delete": 117, "esc": 53, "escape": 53,
    "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "capslock": 57, "insert": 114, "help": 114,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101, "f10": 109,
    "f11": 103, "f12": 111, "f13": 105, "f14": 107, "f15": 113, "f16": 106, "f17": 64, "f18": 79, "f19": 80, "f20": 90]
let modifierKeys: [String: (CGEventFlags, CGKeyCode)] = [
    "cmd": (.maskCommand, 55), "mod": (.maskCommand, 55), "win": (.maskCommand, 55),
    "ctrl": (.maskControl, 59), "alt": (.maskAlternate, 58), "shift": (.maskShift, 56), "fn": (.maskSecondaryFn, 63)]

var charKeys: [String: (CGKeyCode, Bool)] = [:]
func buildKeymap() {
    guard charKeys.isEmpty,
          let src = TISCopyCurrentKeyboardLayoutInputSource()?.takeRetainedValue(),
          let ptr = TISGetInputSourceProperty(src, kTISPropertyUnicodeKeyLayoutData) else { return }
    let data = Unmanaged<CFData>.fromOpaque(ptr).takeUnretainedValue() as Data
    let keypad: Set<Int> = [65, 67, 69, 71, 75, 76, 78, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92]
    let order = (0..<128).filter { !keypad.contains($0) } + keypad.sorted()
    data.withUnsafeBytes { raw in
        guard let layout = raw.bindMemory(to: UCKeyboardLayout.self).baseAddress else { return }
        for shift in [false, true] {
            for code in order {
                var dead: UInt32 = 0
                var length = 0
                var chars = [UniChar](repeating: 0, count: 4)
                let st = UCKeyTranslate(layout, UInt16(code), UInt16(kUCKeyActionDown), shift ? 2 : 0, UInt32(LMGetKbdType()),
                                        OptionBits(kUCKeyTranslateNoDeadKeysMask), &dead, 4, &length, &chars)
                guard st == noErr, length > 0 else { continue }
                let s = String(utf16CodeUnits: chars, count: length)
                if charKeys[s] == nil { charKeys[s] = (CGKeyCode(code), shift) }
            }
        }
    }
}

func keyFor(_ k: String) throws -> (CGKeyCode, CGEventFlags) {
    if let c = namedKeys[k] { return (c, []) }
    buildKeymap()
    let ch = k == "plus" ? "+" : k == "minus" ? "-" : k
    if let (c, shift) = charKeys[ch] { return (c, shift ? .maskShift : []) }
    if ch.count == 1, let (c, shift) = charKeys[ch.lowercased()] { return (c, shift ? .maskShift : []) }
    throw AgentError("unknown key '\(k)' for the current keyboard layout")
}

func sendCombo(_ keys: [String]) throws {
    var flags: CGEventFlags = []
    var mods: [(CGEventFlags, CGKeyCode)] = []
    var main: (CGKeyCode, CGEventFlags)? = nil
    for k in keys {
        if let m = modifierKeys[k] { mods.append(m) } else { main = try keyFor(k) }
    }
    for m in mods { flags.insert(m.0); postKey(m.1, down: true, flags: flags) }
    if let (code, extra) = main {
        let f = flags.union(extra)
        postKey(code, down: true, flags: f)
        sleepMs(15)
        postKey(code, down: false, flags: f)
    } else {
        sleepMs(15)
    }
    for m in mods.reversed() { flags.remove(m.0); postKey(m.1, down: false, flags: flags) }
}

func keyCmd(_ a: Dict) throws -> Dict {
    try requireInput()
    guard let keys = a["keys"] as? [Any], !keys.isEmpty else { throw AgentError("key needs keys") }
    let names = keys.map { "\($0)".lowercased() }
    for _ in 0..<max(1, int(a, "times", 1)) { try sendCombo(names); sleepMs(30) }
    sleepMs(int(a, "settle", 120))
    return post()
}

// ---------- launch ----------
func launch(_ a: Dict) throws -> Dict {
    try requireInput()
    let tgt = str(a, "target")
    if tgt.isEmpty { throw AgentError("launch needs a target") }
    var args: [String]
    if tgt.hasPrefix("/") || tgt.hasPrefix("~") || tgt.hasSuffix(".app") { args = [(tgt as NSString).expandingTildeInPath] }
    else if tgt.contains(".") && !tgt.contains(" ") { args = ["-b", tgt] }
    else { args = ["-a", tgt] }
    let extra = str(a, "args").split(separator: " ").map(String.init)
    if !extra.isEmpty { args += ["--args"] + extra }
    let before = Set(cgWindows(all: false).map { $0.id })
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
    p.arguments = args
    let errPipe = Pipe()
    p.standardError = errPipe
    p.standardOutput = FileHandle.nullDevice
    try p.run()
    p.waitUntilExit()
    if p.terminationStatus != 0 {
        let msg = String(data: errPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        throw AgentError("open failed: \(clip(msg, 200))")
    }
    let timeout = num(a, "timeout", 15), waitTitle = str(a, "wait")
    let start = Date()
    var found: Win? = nil
    while Date().timeIntervalSince(start) < timeout && found == nil {
        for w in cgWindows(all: false) where w.layer == 0 {
            if !waitTitle.isEmpty { if w.title.range(of: waitTitle, options: .caseInsensitive) != nil { found = w; break } }
            else if !before.contains(w.id) { found = w; break }
        }
        if found == nil { sleepMs(150) }
    }
    var r = ok()
    if let w = found {
        bringToFront(pid: w.pid, window: axWindow(for: w))
        sleepMs(int(a, "settle", 200))
        r["window"] = winInfo(w)
    } else {
        r["note"] = "no new window within \(timeout) s (an already running app may reuse its window)"
    }
    r["post"] = postState()
    return r
}

exit(runAgent())
