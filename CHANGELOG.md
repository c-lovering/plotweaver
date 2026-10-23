# Changelog

## Unreleased

**Relationships**
- Characters have a **Relationships** field: who with, kind, intensity 0–5, since/until (a chapter,
  scene or chapter number) and a note. Stored as a `relationships:` list in the character's
  properties. Each one belongs to the pair, and the other character's note lists it too.
- New **Relationships** tab (`Ctrl+4`). Harem layout puts the protagonist in the center with love
  interests on a ring, so relationships between the women show as chords across it. Intensity is
  line thickness, one-way kinds get arrows, and each link shows the pair's shared scenes
  (red when they've never shared one).
- **As of** chapter slider: relationships appear when they start, and ended ones turn dashed.
- Dotted lines for pairs who share scenes but have no relationship yet; draggable layout
  remembered per project.

## 0.4.0 — first public release

**Outlining**
- Parts → chapters → scenes, stored as plain Markdown with YAML properties (Obsidian-compatible).
- New Chapter always creates its first scene; inserting "Chapter N" can renumber later chapters.
- Drag to reorder in the sidebar or on the corkboard; Outline → Renumber Chapters.
- Characters (role, traits, appearance, portrait + gallery), places (nested), codex, notes.
- `[[Wikilinks]]` with autocomplete, linked mentions, unresolved-link list, rename updates links.
- Tags (property or inline `#tags`), with `#tag` filtering everywhere.

**Views**
- Corkboard: cards in reading order, color by status/POV/thread/tag, drag chapters or scenes.
- Screen-time matrix: chapters × characters, POV marks, long-absence warnings, per-character stats.
- "In this scene" panel with portraits and key traits.

**Drafts**
- Link each scene to a draft file (txt/md/odt/docx/rtf) written in FocusWriter or anything else;
  live word counts in the sidebar, totals per chapter/part, project progress in the status bar.

**App**
- Light and dark themes.
- Windows portable zip and installer; Linux AppImage.
