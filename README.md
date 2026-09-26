# Chrono Trigger DS: Kajar Retranslation Port

> **The DS port is feature-complete, but minor runtime or layout bugs may still turn up in playtesting. Please report reproducible errors. The original-transfer variant is a preservation build and does not rewrite KWhazit's translation; prose cleanup belongs in the separate polished faithful variant.**

Chrono Trigger DS: Kajar Retranslation Port brings the KWhazit / Chrono Compendium English retranslation of Chrono Trigger to the Nintendo DS version.

For many years, this historically important retranslation existed mainly as a Super Nintendo ROM-hack project and as comparison scripts. This patch ports that work into the DS script structure, updates DS tables and extras where matching source terminology exists, and keeps DS-only material intact where there is no original SNES/Kajar counterpart.

This is not a new localization and not a rewrite for modern English flavor. The goal is to make the DS version playable with the Kajar / Chrono Compendium translation philosophy: closer to the Japanese script, closer to the original names and terminology, and less dependent on inherited English adaptation choices.

## Current status

- Platform: Nintendo DS
- Base game: Chrono Trigger DS, US version
- Patch type: English text patch
- Primary release format: BPS
- Variants: original Kajar transfer and polished faithful

No ROM is included. You must provide your own legally obtained clean Chrono Trigger DS ROM.

## Credits

- Original English retranslation: KWhazit
- Chrono Compendium retranslation project, script presentation, editing, and release work: Chrono Compendium / Kajar Laboratories contributors, including ZeaLitY
- DS porting, text mapping, ROM hacking, text extraction/repacking workflow, DS build tooling, and release patch preparation: rsc-pl

This project depends on the historical work done by KWhazit and the Chrono Compendium community. KWhazit's retranslation was one of the major early attempts to make Chrono Trigger's Japanese script readable in English with original terminology, tone, names, and script details exposed instead of hidden behind broad localization choices.

## Why this patch exists

Chrono Trigger has several English scripts, each created under different constraints and with different goals.

The original SNES localization is famous and very readable, but it was produced under 1990s cartridge-space, deadline, and Nintendo of America content restrictions. It uses many renamed characters and locations, compresses or reshapes lines, changes some cultural or religious texture, and sometimes replaces the original wording with a stronger English adaptation.

The DS English script is more modern and often clearer, but it is still an official localization. It keeps many established localized names, smooths or rewrites lines, replaces some Japanese relationship/address nuance with ordinary English titles, and does not try to reproduce KWhazit's source-facing translation choices.

The KWhazit / Chrono Compendium retranslation had a different purpose. It was built for readers who wanted to see what the Japanese script was saying more directly: original names, original relationship terms, original item and location concepts, and many details that were compressed, renamed, or reinterpreted elsewhere.

Until now, that experience was tied mainly to the SNES version. This patch exists because the DS version has useful additions, a different script structure, extra menus, extras/library content, and broader availability, but it never had a direct port of the Kajar/Chrono Compendium retranslation.

## Who this patch is for

This patch is for players who:

- want to play Chrono Trigger DS with KWhazit / Chrono Compendium terminology;
- prefer source-faithful translation over localization-heavy rewriting;
- want names such as Sara, Jyaki, Bosch, Gasch, Hasch, Vinnegar, Mayonnay, Soysaw, Grandleon, and Dinomen restored;
- want alcohol, item, monster, location, and lore terminology closer to the Kajar script;
- want relationship/address nuance such as -sama, -san, and Ane-ue preserved where the port uses it;
- are interested in the historical Chrono Compendium retranslation and want it playable on DS;
- want either the historical Kajar transfer or a smoother faithful version that keeps the same terminology and source-facing approach.

It is probably not for players who prefer the official English scripts as separate adaptations, or who want every line rewritten into idiomatic modern English regardless of the Japanese source.

## What this patch changes

The patch ports the Kajar / Chrono Compendium text into Chrono Trigger DS by mapping the original retranslation against the DS script structure.

It changes:

- main story dialogue;
- location names;
- character and NPC names;
- enemy and monster names;
- item and equipment names;
- item descriptions where source-backed;
- tech names and descriptions where source-backed;
- chapter titles;
- Library / Extras / encyclopedia terminology where matching Kajar/original terminology exists;
- music, ending, source-list, quiz, and metadata labels where exposed to the player and source-backed.

It preserves:

- DS control codes and runtime structure;
- DS choice scaffolding;
- DS name tokens;
- DS-only content that has no clear SNES/Kajar counterpart;
- non-English DS language slots, which are outside the scope of this English patch;
- debug/developer labels, unless they intersect with visible player-facing terminology.

## Why KWhazit's translation matters historically

KWhazit's work was not just a list of renamed terms. It was a large comparison and retranslation effort that treated the Japanese script as the authority and documented differences between the Japanese and English versions.

The Chrono Compendium / Kajar Laboratories project gave English-speaking Chrono Trigger fans a way to examine the game outside the inherited official-localization frame. That mattered especially for Zeal terminology, Magus/Jyaki/Sara relationship details, the Three Philosophers/Gurus, alcohol and item names, enemy and location names, chapter titles, and scenes where the official script added or removed implication.

This DS port is built as a preservation and accessibility project for that translation tradition. It does not replace KWhazit's work; it makes that work playable in another version of the game.

## Examples

These examples are taken from the DS script mapped against the Kajar/Chrono Compendium transfer. They are not typo fixes. They show the kinds of changes this patch cares about: terminology, characterization, cultural/address nuance, alcohol wording, censorship/sanitization, and lines whose meaning or emphasis changes.

### 1. Schala / Janus restored to Sara / Jyaki

```text
Official DS:
Elder: When the disaster struck, an eerie black portal
materialized before young Lord Janus. Melchior tried
to save the boy prince, but succeeded only in getting
himself dragged in as well.

Kajar DS Port:
Elder: At the time of the great disaster,
something like a black distortion appeared......
Bosch, trying to save Jyaki-sama, who was
about to be sucked in, was also.....
```

This restores the Kajar names and the respectful address form. It also changes the scene back toward the original phrasing: less polished narration, more direct report of what happened.

### 2. Sibling address: Schala becomes Ane-ue

```text
Official DS:
Janus: Schala!

Kajar DS Port:
Jyaki: Ane-ue!
```

This preserves how Jyaki addresses his older sister. Plain-name replacement removes relationship texture that is explicit in the original address.

### 3. The Three Gurus become the Three Philosophers

```text
Official DS:
Belthasar, the Guru of Reason
Gaspar, the Guru of Time
Melchior

Kajar DS Port:
Gasch, the Philosopher of Reason
Hasch, the Philosopher of Time
Bosch
```

The patch restores the Kajar/Chrono Compendium naming system across dialogue, profiles, item text, Library entries, and metadata.

### 4. Fiendlord terminology returns to Magus

```text
Official DS:
The Fiendlord's army laid waste to Zenan Bridge.

Kajar DS Port:
The bridge across Zenan was destroyed by
Magus's army.
```

The patch avoids treating Magus as a localized title that must be replaced by Fiendlord.

### 5. Ozzie / Flea / Slash restored

```text
Official DS:
Ozzie
Flea
Slash

Kajar DS Port:
Vinnegar
Mayonnay
Soysaw
```

These names are restored across enemy names, item names, battle labels, source lists, and dialogue. Examples include Vinnegar Underpants, Mayonnay's Bra, and Soysaw.

### 6. Masamune restored to Grandleon

```text
Official DS:
The Masamune

Kajar DS Port:
Fight! Grandleon
```

The weapon and related metadata are synchronized to Grandleon, matching the Kajar terminology instead of the inherited official-localization name.

### 7. Reptites restored to Dinomen

```text
Official DS:
Ayla: Ioka village fight reptite.
Leader name Azala. Azala very smart.

Kajar DS Port:
Ayla: Aylas fighting Dinomen.
Dinomen leader called Azarla.
Azarla very smart......
```

This restores both the race name and Azarla's name, while keeping Ayla's direct speech style.

### 8. Mammon Machine / Ocean Palace terminology

```text
Official DS:
The Queen has installed the Mammon Machine in
the Ocean Palace in an attempt to absorb Lavos's
energy.

Kajar DS Port:
The Queen intends to set up the Demonic Vessel
in the Ocean Floor Palace and extract yet more
energy from Lavos.
```

Zeal terminology is one of the major areas where this patch restores the Kajar naming framework.

### 9. Black Omen restored to Black Dream

```text
Official DS:
Mother: Ah, such beautiful weather!
The Black Omen is sparkling in the sun!
What a great day for doing laundry!

Kajar DS Port:
Jina: Nice weather again today.
The Black Dream is glittering, illuminated by
the sun.
Looks like it's going to be good laundry weather.
```

This example shows both terminology and character text. The port keeps Kajar's Jina and Black Dream.

### 10. End of Time restored to The Farthest Reaches of Time

```text
Official DS:
Return to the End of Time?

Kajar DS Port:
Return to the Farthest Reaches
of Time?
```

The longer Kajar term required layout-aware line handling in DS menus and prompts.

### 11. Alcohol wording restored

```text
Official DS:
Ayla: This, only special time drink!
Good drink! Name skull-smash!
Next day, skull feel like smash!

Kajar DS Port:
Ayla: Drinking? Crono!
This sake, drink at special time.
Cocktail called Rock Crash.
Delicious, intense!
```

Alcohol-related text is one of the areas where older English releases often softened, generalized, or renamed wording. This patch restores sake and the Kajar phrasing where applicable.

### 12. Toma's Spirits restored to Toma's Sake

```text
Official DS:
Toma's Spirits

Kajar DS Port:
Toma's Sake
```

The change is small on screen, but it reflects the patch's approach: preserve the source-facing term instead of using a generalized English substitute.

### 13. Sanitized item wording restored

```text
Official DS:
Alluring Top
Flea Bustier
Ozzie Pants

Kajar DS Port:
Captivating Bra
Mayonnay's Bra
Vinnegar Underpants
```

The point is not to make the script cruder. The point is to avoid softening or renaming item text when the Kajar/source-facing version is more specific.

### 14. Dream Team restored to Dream Project

```text
Official DS:
Congratulations on finishing the game!
You're now a member of the Dream Team!

Kajar DS Port:
Well done! You've cleared the game.
You're one of the Dream Project members too.
Congratulations!!
```

The DS line is natural English. The Kajar line preserves the original development-room framing and terminology.

### 15. Zeal social terms restored

```text
Official DS:
The Enlightened Ones
the Earthbound Ones

Kajar DS Port:
People of the Light
People of the Earth
```

This changes the texture of Zeal. The official terms read like formal fantasy categories; the Kajar terms preserve the source-facing social contrast more directly.

## DS-specific handling

The DS version contains content that did not exist in the original SNES script, including extra areas, extra items, Wireless/Arena-related text, Library/Extras data, and other metadata.

The port handles this conservatively:

- if a DS line has a clear Kajar/original counterpart, it is mapped;
- if a DS-only line exposes a known Kajar term, that term is synchronized;
- if a DS-only line has no source counterpart, the original-transfer variant keeps the DS wording;
- the polished faithful variant may smooth DS-only wording without changing established names, lore, or address nuance.

## Variants

### Original Kajar transfer

This is the preservation-oriented version. It keeps the KWhazit / Chrono Compendium transfer as closely as the DS script structure allows, including literal or stiff wording that belongs to the historical translation. Runtime and layout fixes are still applied where the DS version requires them.

### Polished faithful

The polished faithful version is complete and remains separate from the preservation build. It smooths lines that read too stiffly in English, fixes obvious grammar and flow problems, and cleans up DS-only dialogue where appropriate. It keeps the same names, terminology, lore, honorific/address choices, control structure, and source-facing translation philosophy.

The two variants are maintained independently so the historical transfer is not overwritten by later prose cleanup.

## Future plans

### PC port

The DS version is the first target. A PC port is planned later.

The project is structured so the same variant text table can feed both DS and PC outputs.

## Building from source

The repository contains a self-contained Nintendo DS text/build toolchain written with the Python standard library. A normal build does **not** require Chrono Translator, pre-generated text dumps, pre-generated binary MSG folders, `pip`, a virtual environment, or third-party Python packages.

Required private input:

- a clean **Chrono Trigger DS (US), revision 0** ROM — **CRC32 `B3836946`**.

By default, place it at:

```text
.local/roms/clean/ChronoTrigger.nds
```

You can also point the build at another path with `CT_CLEAN_ROM`.

Build both variants:

```bash
./Build.sh all
```

Or build one variant:

```bash
./Build.sh original
./Build.sh polished
```

Generated ROMs, binary MSG files, BPS/UPS patches, checksums, and build reports are written under `.local/` and are ignored by Git. The build validates all 75 DS `TEXT .msg` resources with a reversible binary round trip and checks `{SEL}` choice-row layout before producing a ROM.

The current reproducibility gates are:

```text
Original Kajar Transfer:
9b1bc7bce15476443586e61728e7871fb7553797507cc094663a8f365c665682

Polished Faithful:
ac797534555d811ec22a79391f5c8540aa1597c215e806922eb3f08e3b9a6b9e
```

For the full source/build QA pass:

```bash
python3 tools/validate_project.py --rom .local/roms/clean/ChronoTrigger.nds
```

The native dumper can also recreate Chrono Translator-compatible text directly from the ROM:

```bash
python3 tools/platform_ds/dump_text.py \
  --rom .local/roms/clean/ChronoTrigger.nds \
  --output-dir .local/dumps/clean_us
```

BPS and UPS are generated entirely in Python. Classic IPS is automatically skipped because the DS ROM is outside the safe classic IPS size/range. XDELTA is optional and is generated only when `xdelta3` is available; it is not required for the normal build.

## Installation

Exact release instructions may change depending on the public package format.

General process:

1. Obtain a clean US Chrono Trigger DS ROM from your own cartridge.
2. Verify that the clean ROM matches the CRC32 listed with the release.
3. Apply the BPS for the variant you want (unpack the release archive first) with a compatible patching tool. The [Romhack Plaza patcher](https://romhackplaza.org/patch/) is one option.
4. Run the patched ROM in a DS emulator, flashcart, or compatible hardware setup.

Do not ask for ROMs. Do not distribute ROMs.

## Known scope notes

- This is an English patch.
- Non-English DS slots are outside the current scope.
- The original-transfer variant retains DS-only text unless there is a clear source-backed reason to change it; the polished faithful variant may smooth that wording without changing established terminology or lore.

## Historical references

- KWhazit's Chrono Trigger translation pages: [https://kwhazit.ucoz.net/trans/ct/index.html](https://kwhazit.ucoz.net/trans/ct/index.html)
- Chrono Compendium retranslation page: [https://www.chronocompendium.com/Term/Retranslation.html](https://www.chronocompendium.com/Term/Retranslation.html)
- Chrono Compendium translation overview: [https://www.chronocompendium.com/Term/Chrono_Trigger_Translations.html](https://www.chronocompendium.com/Term/Chrono_Trigger_Translations.html)
- Original SNES retranslation patch listing: [https://www.romhacking.net/translations/1198/](https://www.romhacking.net/translations/1198/)

## Distribution note

Release packages distribute patch files and documentation only. The source repository contains translation text and build tooling, but never a ROM.
