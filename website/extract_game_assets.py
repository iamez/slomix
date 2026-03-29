#!/usr/bin/env python3
"""Extract and convert ET:Legacy game assets (TGA→PNG) from pk3 files."""

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

ETMAIN = Path(__file__).parent.parent / "etmain"
OUT = Path(__file__).parent / "assets" / "game"

PAK0 = ETMAIN / "pak0.pk3"

# ── Assets to extract from pak0.pk3 ─────────────────────────────────────

WEAPON_ICONS = {
    "icons/iconw_knife_1_select.tga": "knife",
    "icons/iconw_luger_1_select.tga": "luger",
    "icons/iconw_colt_1_select.tga": "colt",
    "icons/iconw_MP40_1_select.tga": "mp40",
    "icons/iconw_thompson_1_select.tga": "thompson",
    "icons/iconw_sten_1_select.tga": "sten",
    "icons/iconw_fg42_1_select.tga": "fg42",
    "icons/iconw_mg42_1_select.tga": "mg42",
    "icons/iconw_browning_1_select.tga": "browning",
    "icons/iconw_kar98_1_select.tga": "kar98",
    "icons/iconw_m1_garand_1_select.tga": "m1_garand",
    "icons/iconw_mauser_1_select.tga": "mauser",
    "icons/iconw_panzerfaust_1_select.tga": "panzerfaust",
    "icons/iconw_flamethrower_1_select.tga": "flamethrower",
    "icons/iconw_mortar_1_select.tga": "mortar",
    "icons/iconw_grenade_1_select.tga": "grenade",
    "icons/iconw_pineapple_1_select.tga": "pineapple",
    "icons/iconw_dynamite_1_select.tga": "dynamite",
    "icons/iconw_landmine_1_select.tga": "landmine",
    "icons/iconw_satchel_1_select.tga": "satchel",
    "icons/iconw_smokegrenade_1_select.tga": "smoke_grenade",
    "icons/iconw_syringe_1_select.tga": "syringe",
    "icons/iconw_ammopack_1_select.tga": "ammo_pack",
    "icons/iconw_medheal_select.tga": "med_pack",
    "icons/iconw_pliers_1_select.tga": "pliers",
    "icons/iconw_binoculars_1_select.tga": "binoculars",
    "icons/iconw_radio_1_select.tga": "field_radio",
    "icons/iconw_silencer_1_select.tga": "silenced_pistol",
    "icons/iconw_kar98_gren_1_select.tga": "kar98_rifle_grenade",
    "icons/iconw_m1_garand_gren_1_select.tga": "m1_garand_rifle_grenade",
    "icons/iconw_syringe2_1_select.tga": "poison_syringe",
}

CLASS_ICONS = {
    "gfx/limbo/ic_soldier.tga": "soldier",
    "gfx/limbo/ic_medic.tga": "medic",
    "gfx/limbo/ic_engineer.tga": "engineer",
    "gfx/limbo/ic_fieldops.tga": "fieldops",
    "gfx/limbo/ic_covertops.tga": "covertops",
}

CLASS_SKILLS = {
    "gfx/limbo/skill_soldier.tga": "skill_soldier",
    "gfx/limbo/skill_medic.tga": "skill_medic",
    "gfx/limbo/skill_engineer.tga": "skill_engineer",
    "gfx/limbo/skill_fieldops.tga": "skill_fieldops",
    "gfx/limbo/skill_covops.tga": "skill_covertops",
    "gfx/limbo/ic_battlesense.tga": "skill_battlesense",
    "gfx/limbo/ic_lightweap.tga": "skill_lightweapons",
}

MEDALS = {
    "gfx/limbo/medal_back.tga": "medal_back",
    "gfx/limbo/medals00.tga": "medal_accuracy",
    "gfx/limbo/medals01.tga": "medal_battle_sense",
    "gfx/limbo/medals02.tga": "medal_engineer",
    "gfx/limbo/medals03.tga": "medal_explosives",
    "gfx/limbo/medals04.tga": "medal_first_aid",
    "gfx/limbo/medals05.tga": "medal_light_weapons",
    "gfx/limbo/medals06.tga": "medal_signals",
}

TEAM_ASSETS = {
    "gfx/limbo/flag_allied.tga": "flag_allied",
    "gfx/limbo/flag_axis.tga": "flag_axis",
    "gfx/limbo/but_team_allied.tga": "button_allied",
    "gfx/limbo/but_team_axis.tga": "button_axis",
}

RANKS = {}
for i in range(2, 12):
    RANKS[f"gfx/hud/ranks/rank{i}.tga"] = f"rank_{i:02d}"

CLASS_PORTRAITS = {
    "models/players/hud/allied_soldier.tga": "allied_soldier",
    "models/players/hud/allied_medic.tga": "allied_medic",
    "models/players/hud/allied_engineer.tga": "allied_engineer",
    "models/players/hud/allied_field.tga": "allied_fieldops",
    "models/players/hud/allied_cvops.tga": "allied_covertops",
    "models/players/hud/axis_soldier.tga": "axis_soldier",
    "models/players/hud/axis_medic.tga": "axis_medic",
    "models/players/hud/axis_engineer.tga": "axis_engineer",
    "models/players/hud/axis_field.tga": "axis_fieldops",
    "models/players/hud/axis_cvops.tga": "axis_covertops",
}

LOGO = {
    "ui/assets/et_logo.tga": "et_logo",
}


def convert_tga_to_png(tga_bytes: bytes, output_path: Path) -> bool:
    """Convert TGA image bytes to PNG, preserving alpha."""
    try:
        img = Image.open(io.BytesIO(tga_bytes))
        # Flip vertically — TGA files from ET are often stored bottom-up
        if hasattr(img, 'tag_v2') or img.mode in ('RGBA', 'RGB'):
            pass  # Pillow handles TGA orientation automatically
        img.save(output_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"  WARN: Could not convert → {e}")
        return False


def extract_category(zf: zipfile.ZipFile, mapping: dict, category: str) -> int:
    """Extract and convert a category of assets."""
    out_dir = OUT / category
    out_dir.mkdir(parents=True, exist_ok=True)

    names_lower = {n.lower(): n for n in zf.namelist()}
    count = 0

    for src_path, dst_name in mapping.items():
        actual_name = names_lower.get(src_path.lower())
        if not actual_name:
            print(f"  SKIP: {src_path} (not found in pk3)")
            continue

        dst_path = out_dir / f"{dst_name}.png"
        if dst_path.exists():
            print(f"  EXISTS: {dst_path.name}")
            count += 1
            continue

        data = zf.read(actual_name)
        if convert_tga_to_png(data, dst_path):
            size = dst_path.stat().st_size
            print(f"  OK: {dst_name}.png ({size:,} bytes)")
            count += 1

    return count


def extract_map_levelshots() -> int:
    """Extract map levelshots from all pk3 files."""
    out_dir = OUT / "levelshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for pk3_path in sorted(ETMAIN.glob("*.pk3")):
        try:
            with zipfile.ZipFile(pk3_path, 'r') as zf:
                for name in zf.namelist():
                    nl = name.lower()
                    if not nl.startswith("levelshots/"):
                        continue
                    if nl.endswith("_cc.tga") or nl.endswith("_cc.jpg"):
                        continue  # Skip command map versions
                    if not (nl.endswith(".tga") or nl.endswith(".jpg")):
                        continue

                    map_name = Path(name).stem
                    dst_path = out_dir / f"{map_name}.png"

                    if dst_path.exists():
                        continue

                    data = zf.read(name)
                    if nl.endswith(".jpg"):
                        try:
                            img = Image.open(io.BytesIO(data))
                            img.save(dst_path, "PNG", optimize=True)
                            print(f"  OK: {map_name}.png (from {pk3_path.name})")
                            count += 1
                        except Exception as e:
                            print(f"  WARN: {map_name} → {e}")
                    else:
                        if convert_tga_to_png(data, dst_path):
                            print(f"  OK: {map_name}.png (from {pk3_path.name})")
                            count += 1
        except zipfile.BadZipFile:
            print(f"  SKIP: {pk3_path.name} (bad zip)")

    return count


def main():
    if not PAK0.exists():
        print(f"ERROR: pak0.pk3 not found at {PAK0}")
        sys.exit(1)

    print(f"Opening {PAK0.name} ({PAK0.stat().st_size / 1024 / 1024:.0f} MB)...")

    with zipfile.ZipFile(PAK0, 'r') as zf:
        total = 0

        print("\n── Weapon Icons ──")
        total += extract_category(zf, WEAPON_ICONS, "weapons")

        print("\n── Class Icons ──")
        total += extract_category(zf, CLASS_ICONS, "classes")

        print("\n── Class Skill Icons ──")
        total += extract_category(zf, CLASS_SKILLS, "classes")

        print("\n── Class Portraits ──")
        total += extract_category(zf, CLASS_PORTRAITS, "classes")

        print("\n── Medals ──")
        total += extract_category(zf, MEDALS, "medals")

        print("\n── Ranks ──")
        total += extract_category(zf, RANKS, "ranks")

        print("\n── Team Assets ──")
        total += extract_category(zf, TEAM_ASSETS, "teams")

        print("\n── ET Logo ──")
        total += extract_category(zf, LOGO, "teams")

    print("\n── Map Levelshots (all pk3s) ──")
    total += extract_map_levelshots()

    print(f"\n✓ Done — {total} assets extracted to {OUT}/")

    # Summary
    for subdir in sorted(OUT.iterdir()):
        if subdir.is_dir():
            files = list(subdir.glob("*.png"))
            print(f"  {subdir.name}/: {len(files)} files")


if __name__ == "__main__":
    main()
