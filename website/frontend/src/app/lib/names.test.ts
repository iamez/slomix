import { describe, expect, it } from 'vitest';
import { normalizeMapKey, stripEtColors as fromGeo } from './geo/mapTransforms';
import { stripEtColors } from './names';

describe('stripEtColors', () => {
  it("matches the backend's own strip_et_colors cases", () => {
    // Quoted from tests/unit/test_et_constants.py — one name must clean to
    // one string on every surface, so the SPA pins the backend's fixtures.
    expect(stripEtColors('^1Red')).toBe('Red');
    expect(stripEtColors('^1R^7e^3d')).toBe('Red');
    expect(stripEtColors('^1^2^3Name')).toBe('Name');
    expect(stripEtColors('Name^7')).toBe('Name');
    expect(stripEtColors('^1^2^3')).toBe('');
    expect(stripEtColors('^aGreen^ZBlue')).toBe('GreenBlue');
    expect(stripEtColors('')).toBe('');
  });

  it('removes colour tokens and keeps everything else', () => {
    expect(stripEtColors('^1bronze^7')).toBe('bronze');
    expect(stripEtColors('^4.^7lgz')).toBe('.lgz');
    // Letter codes are codes too (^a–^z, ^A–^Z) — without a letter case a
    // digits-only character class would pass every assertion above.
    expect(stripEtColors('^abronze^Ztail')).toBe('bronzetail');
    // Clan brackets, dots and spaces are NOT colour codes.
    expect(stripEtColors("[TWK]CUJO & It's squAziii")).toBe("[TWK]CUJO & It's squAziii");
  });

  it('leaves every real caret-bearing name on the corpus untouched', () => {
    // ⛔ This is the test that separates the two semantics that live in this
    // repo's history — the backend's own cases above CANNOT: `\^[0-9a-zA-Z]`
    // and mapTransforms' old `\^.` agree on every one of them. Measured on
    // the corpus (94 player names): all six names containing a caret pair it
    // with a NON-alphanumeric, so the canonical class changes none of them,
    // while `\^.` mangles all six. (Per the engine's Q_IsColorString `^<`
    // IS a colour code — but changing 6 of 94 displayed names is a product
    // decision, not one panel's; see names.ts.)
    const corpusCaretNames = [
      '^<ABD-AL-KL3M3N',
      "'^/fnx",
      '//^?/M.Gekku',
      '//^?/M.rAzzdOG',
      '//^?/M.Demonslayer',
      'one^>4ass.squAze',
    ];
    for (const name of corpusCaretNames) {
      expect(stripEtColors(name)).toBe(name);
    }
  });

  it('is the copy normalizeMapKey uses — one semantics, not two', () => {
    // geo/mapTransforms used to hand-roll `\^.` here; the discriminating
    // input is `^`+non-alnum, on which the two classes disagree. Behavioral,
    // not source-matching, so a reintroduced local copy fails this rather
    // than slipping past a prose grep. (Measured 2026-08-31: the semantic
    // change is EMPTY for maps — 0 of 20 distinct map_names in `rounds`
    // contain a caret, 0 in player_comprehensive_stats, 0 in
    // map_transforms.json — so this pins semantics, it moves no key.)
    expect(normalizeMapKey('^1Etl_Supply^7 ')).toBe('etl_supply');
    expect(normalizeMapKey('^<odd')).toBe('^<odd');
    // FUNCTION IDENTITY through the re-export, not behaviour on a sample:
    // a fresh local copy in mapTransforms that normalizeMapKey happens not
    // to call would pass every behavioural line above — the identity check
    // fails the moment the module exports anything but the one canonical
    // function.
    expect(fromGeo).toBe(stripEtColors);
  });

  it('agrees with the backend on the doubled-caret edge', () => {
    // Backend re.sub(r'\^[0-9a-zA-Z]') on '^^11' removes the INNER pair and
    // leaves '^1' — the leading caret is followed by a caret, which is not in
    // the class. The same input must clean the same way here, or one name
    // renders two ways across surfaces.
    expect(stripEtColors('^^11')).toBe('^1');
  });
});
