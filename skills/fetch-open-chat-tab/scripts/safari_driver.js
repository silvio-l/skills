// JXA driver: injects extract_dom.js into Safari's frontmost tab via
// `do JavaScript`, then polls for the async result.
//
// Run as: osascript -l JavaScript safari_driver.js <path-to-extract_dom.js>
//
// `do JavaScript` evaluates synchronously and does NOT await a returned
// promise (verified empirically) — extract_dom.js therefore fires an async
// IIFE that writes its JSON result to `window.__foc_result`, and this
// driver polls that variable with small, fast, synchronous `do JavaScript`
// calls until it flips from the PENDING sentinel to a real value.
//
// Always prints exactly one line of JSON to stdout: either the extraction
// result or a {"ok": false, "reason": "..."} describing why Safari/the tab
// could not be reached at all (e.g. the Apple-Events permission is off).

function run(argv) {
  var extractDomPath = argv[0];
  if (!extractDomPath) {
    return JSON.stringify({ ok: false, reason: 'Internal error: no extract_dom.js path passed to the driver.' });
  }

  var app = Application.currentApplication();
  app.includeStandardAdditions = true;

  // Standard Additions' `read` command decodes with a legacy default
  // encoding, not UTF-8 — it silently mangled the non-ASCII em dashes in
  // extract_dom.js's error strings into mojibake (verified: bytes came back
  // double-encoded). Reading via the Foundation/NSString bridge instead
  // guarantees UTF-8.
  var jsSource;
  try {
    ObjC.import('Foundation');
    var nsstr = $.NSString.stringWithContentsOfFileEncodingError($(extractDomPath), $.NSUTF8StringEncoding, null);
    jsSource = ObjC.unwrap(nsstr);
    if (jsSource === null || jsSource === undefined) {
      throw new Error('file not found or not valid UTF-8');
    }
  } catch (e) {
    return JSON.stringify({ ok: false, reason: 'Could not read extract_dom.js at ' + extractDomPath + ': ' + e });
  }

  var safari = Application('Safari');
  var tab;
  try {
    if (!safari.running()) {
      return JSON.stringify({ ok: false, reason: 'Safari is not running.' });
    }
    var windows = safari.windows();
    if (!windows || windows.length === 0) {
      return JSON.stringify({ ok: false, reason: 'Safari has no open windows.' });
    }
    tab = windows[0].currentTab();
  } catch (e) {
    return JSON.stringify({ ok: false, reason: 'Could not access Safari\'s frontmost tab: ' + e });
  }

  var startSource =
    jsSource +
    '\nwindow.__foc_result = null;\n' +
    '(async () => {\n' +
    '  try {\n' +
    '    const r = await window.__focLib.runExtraction();\n' +
    '    window.__foc_result = JSON.stringify(r);\n' +
    '  } catch (e) {\n' +
    '    window.__foc_result = JSON.stringify({ ok: false, reason: "Uncaught JS exception during extraction: " + (e && e.message ? e.message : String(e)) });\n' +
    '  }\n' +
    '})();\n' +
    "'started'";

  try {
    safari.doJavaScript(startSource, { in: tab });
  } catch (e) {
    var msg = String(e && e.message ? e.message : e);
    if (msg.indexOf('Allow JavaScript from Apple Events') !== -1 || msg.indexOf('-1743') !== -1) {
      return JSON.stringify({
        ok: false,
        reason:
          'Safari is blocking script automation: enable it once via the menu bar — Safari > Develop > "Allow JavaScript from Apple Events" (Develop menu must be visible first: Safari > Settings > Advanced > "Show features for web developers").'
      });
    }
    return JSON.stringify({ ok: false, reason: 'Safari rejected the extraction script: ' + msg });
  }

  var pollSource = "window.__foc_result === null ? 'PENDING' : window.__foc_result";
  var deadline = Date.now() + 95000;

  while (Date.now() < deadline) {
    var value;
    try {
      value = safari.doJavaScript(pollSource, { in: tab });
    } catch (e) {
      return JSON.stringify({ ok: false, reason: 'Lost contact with the Safari tab while polling: ' + e });
    }
    if (value !== 'PENDING') {
      return value;
    }
    delay(0.4); // global Standard Additions function — a separate helper that
    // re-fetches Application.currentApplication() per call was observed to
    // intermittently throw "Mitteilung unverständlich (-1708)" under this
    // same polling loop; the bare global call does not.
  }

  return JSON.stringify({ ok: false, reason: 'Timed out after 95s waiting for the in-page extraction to finish (very long conversation, or the page stopped responding).' });
}
