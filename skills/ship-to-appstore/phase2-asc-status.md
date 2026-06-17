# Phase 2 — ASC Status + Credential Discovery

> **Stub — implemented in slice 03.**

This phase determines the current state of the app record in App Store Connect
and discovers the credentials needed to query or update it.

Planned strategies (most to least intrusive):
1. Check for `~/.appstoreconnect/private_keys/` API key files.
2. Check for `fastlane/Appfile` or `fastlane/Matchfile` for team/bundle config.
3. Check for `Spacefile` or `Xcode Cloud` workflow files.
4. If none found, ask the user for credentials or App Store Connect access.

ASC status to collect:
- Does the app record exist for this bundle ID?
- What is the current live version?
- Is there a build in "Ready for Review" or "In Review"?
- What metadata is missing (screenshots, description, keywords, etc.)?

Slice 03 will implement this phase in full, including the multi-strategy
credential discovery and adaptive ASC querying.
