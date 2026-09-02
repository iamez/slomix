# Prompt: retrospektivni audit tehničnega dolga (prvi task nove seje)

Naredi retrospektivni audit. Vir: git log zadnjih N tednov (commit po
commit), vsi docs/*.md, HANDOFF fajli, ter `grep -rnE "TODO|FIXME|HACK|XXX"`
po kodi. Za vsak commit ali TODO ugotovi: ali je pokrit v PLAN.md/BACKLOG.md?
Ali je bil planiran ali ad hoc? Rezultat: docs/AUDIT.md s tabelo:
item | vir (commit/koda/doc) | status (dokumentirano / nedokumentirano /
kontradiktorno s planom) | izvedljivost (trivialno / srednje / potrebuje
redesign / opusti) | predlagana prioriteta. Posebej označi stvari, kjer je
koda drugačna od tega, kar dokumentacija trdi. Nič ne popravljaj — samo
poročaj, owner odloča.
