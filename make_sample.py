"""Build a small sample project to explore Plotweaver with: python make_sample.py <folder>"""
import sys
from pathlib import Path

from plotweaver.model import Project

root = Path(sys.argv[1] if len(sys.argv) > 1 else "Sample Project")
p = Project.new_project(root, "The Ember Crown")
pe = p.project_entity
p.save(pe, {"type": "project", "title": "The Ember Crown", "author": "You", "genre": "fantasy-ish romance",
            "target_words": 90000}, "Premise: a disgraced courier inherits a crumbling border keep — "
       "and the four women who already live there.\n")

def mk(t, name, parent=None, meta=None, body=""):
    path = p.create(t, name, p.get(parent) if parent else None, meta=meta)
    e = p.get(path)
    if body:
        p.save(e, body=body)
    return path

kael = mk("character", "Kael Dunmore", meta={"role": "protagonist", "age": "26", "aliases": ["Kael"],
          "traits": ["black hair", "stubble", "courier's limp"]},
          body="Ex-royal courier. Dry humor, terrible at accepting help.\n\n## Arc\nFrom drifter to lord of [[Emberkeep]].")
mk("character", "Sera Vale", meta={"role": "love interest", "aliases": ["Sera"], "affiliation": ["[[The Ash Wardens]]"],
   "traits": ["copper braid", "grey eyes", "tall", "burn scar on left hand"],
   "appearance": "Broad-shouldered and weathered. Wears a warden's coat two sizes too big —\nit was her father's."},
   body="Keep's quartermaster. Pretends not to recognize Kael.")
mk("character", "Lysandra", meta={"role": "love interest", "species": "half-fae",
   "traits": ["silver hair", "ember-gold eyes", "petite", "barefoot always"]},
   body="Bound to the keep's hearthstone. Curious, blunt.")
mk("character", "Brannoc", meta={"role": "antagonist"}, body="Kael's old commander.")
keep = mk("place", "Emberkeep", body="A border keep with a living hearth.")
mk("place", "The Gilded Stag", meta={"parent": "[[Thornwick]]"}, body="Inn on the pass road.")
mk("place", "Thornwick", body="Market town below [[Emberkeep]].")
mk("codex", "The Ash Wardens", meta={"category": "faction"}, body="Disbanded order that once held the pass.")
mk("codex", "Hearthbinding", meta={"category": "magic"}, body="How [[Lysandra]] is tied to the keep.")

mk("character", "Maren Holt", meta={"role": "love interest", "traits": ["short dark curls", "freckles", "always armed"]},
   body="Thornwick's sheriff. Thinks Kael is trouble.")

p1 = mk("part", "Part One - Arrival")
p2 = mk("part", "Part Two - The Keep")
drafts = root / "drafts"; drafts.mkdir(exist_ok=True)
K, S, L, M = "[[Kael Dunmore]]", "[[Sera Vale]]", "[[Lysandra]]", "[[Maren Holt]]"
book = [  # part, chapter, scene, meta, notes
    (p1, "The Pass Road", "Gate at Dusk", {"status": "drafted", "pov": K, "location": "[[Emberkeep]]",
        "characters": [K, S], "threads": ["main", "sera"], "heat": 1, "tags": ["opening"],
        "summary": "Sera refuses to open the gate.", "story_date": "Day 1, dusk"},
        "Beats:\n- Kael arrives soaked\n- [[Sera]] pretends not to know him\n- The hearth flares when he touches the gate"),
    (p1, "The Gilded Stag", "The Innkeeper", {"status": "outlined", "pov": K, "location": "[[The Gilded Stag]]",
        "characters": [K, M], "threads": ["main", "maren"], "tags": ["flashback"]},
        "Flashback: how Kael lost his post. Mentions [[Brannoc]] and a debt to the [[Silver Hand]]. #needs-research"),
    (p1, "Hearthlight", "Through the Fireplace", {"status": "outlined", "pov": K, "characters": [K, L],
        "threads": ["main", "lysandra"], "heat": 2, "summary": "Lysandra introduces herself — through the fireplace."}, ""),
    (p1, "Inventory", "Inventory", {"status": "idea", "pov": K, "characters": [K, S], "threads": ["sera"], "heat": 1},
        "- Sera walks him through what's left\n- argument over the grain stores\n- she almost laughs"),
    (p1, "Sheriff's Visit", "Sheriff's Visit", {"status": "idea", "pov": K, "characters": [K, M, S],
        "threads": ["maren", "main"], "summary": "Maren arrives with a warrant — for the keep, not Kael."}, ""),
    (p2, "Bound", "Bound", {"status": "idea", "pov": K, "characters": [K, L], "threads": ["lysandra"], "heat": 3,
        "tags": ["magic"]}, "How [[Hearthbinding]] works, told badly by Lysandra."),
    (p2, "Ledgers", "Ledgers", {"status": "idea", "pov": K, "characters": [K, S], "threads": ["sera", "main"]}, ""),
    (p2, "Old Debts", "Old Debts", {"status": "idea", "pov": K, "characters": [K], "threads": ["main"],
        "tags": ["flashback"]}, "[[Brannoc]]'s letter arrives."),
    (p2, "Market Day", "Market Day", {"status": "idea", "pov": K, "characters": [K, S], "threads": ["sera"], "heat": 2}, ""),
    (p2, "Ash and Iron", "Ash and Iron", {"status": "idea", "pov": K, "characters": [K, S, M], "threads": ["main"],
        "tags": ["fight"], "heat": 1}, ""),
    (p2, "Ash and Iron", "Aftermath", {"status": "idea", "pov": S, "characters": [S, K], "threads": ["sera"], "heat": 4},
        "Sera's POV for the first time."),
    (p2, "Embers", "Banked Coals", {"status": "idea", "pov": K, "characters": [K, L, S, M], "threads": ["main"]}, ""),
]
(drafts / "gate.txt").write_text("Rain came sideways off the pass. " * 40, encoding="utf-8")
(drafts / "innkeeper.txt").write_text("The Stag smelled of wet dog and old beer. " * 30, encoding="utf-8")
chapters = {}
for part, ch, sc, meta, notes in book:
    if ch not in chapters:
        chapters[ch] = mk("chapter", f"Chapter {len(chapters) + 1}", part)
    if sc:
        mk("scene", sc, chapters[ch], meta=meta, body=notes)
gate = p.resolve("Gate at Dusk"); m = dict(gate.meta); m["prose"] = "drafts/gate.txt"; p.save(gate, m)
inn = p.resolve("The Innkeeper"); m = dict(inn.meta); m["prose"] = "drafts/innkeeper.txt"; m["status"] = "drafted"; p.save(inn, m)
print("Sample project written to", root.resolve())
