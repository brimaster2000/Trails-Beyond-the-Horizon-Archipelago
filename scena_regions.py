# Which story chapter each map (scena) first becomes reachable in.
# Region names match the game's own chapter names (t_chapter.tbl).
# Chests in a scena mapped to None are left out of the seed until someone confirms where they belong.
# Hand-edited: unlike data.py, this file is not generated.

PROLOGUE = "Prologue"
ACT_I_PARTS = ["Act I - A", "Act I - B", "Act I - C"]  # the game's Act I Part 1 / 2 / 3
ACT_I_A, ACT_I_B, ACT_I_C = ACT_I_PARTS
ACT_II_ROUTES = [
    "Act II - Rean Route 1",
    "Act II - Kevin Route 1",
    "Act II - Van Route 1",
    "Act II - Rean Route 2",
    "Act II - Van Route 2",
    "Act II - Van Route 3",
]
ACT_III_ROUTES = [
    "Act III - Kevin Route 2",
    "Act III - Van Route 4",
    "Act III - Van Route 5",
    "Act III - Rean Route 3",
    "Act III - Kevin Route 3",
    "Act III - Van Route 6",
]
FINALE = "Finale"
STORY_REGIONS = [PROLOGUE, *ACT_I_PARTS, *ACT_II_ROUTES, *ACT_III_ROUTES, FINALE]

R1, K1, V1, R2, V2, V3 = ACT_II_ROUTES
K2, V4, V5, R3, K3, V6 = ACT_III_ROUTES

# The game's own route order (sys_event.dat EV_NEXT_CHAPTER_END): the Time Chart only offers the routes of the
# current wave, and the next wave opens once every route of this one is finished.
WAVES = [[ACT_I_A], [ACT_I_B], [ACT_I_C], [R1, K1, V1], [R2, V2], [V3], [K2, V4], [V5], [R3, K3, V6], [FINALE]]

# Chapter ids (global_work(12) / t_chapter) of each story item; the game patch gates chapter c on flag 41000 + c.
# They double as the story items' AP item ids.
CHAPTER_IDS = {
    ACT_I_A: 1, ACT_I_B: 2, ACT_I_C: 3, R1: 4, K1: 5, V1: 6, R2: 10, V2: 11, V3: 12,
    K2: 13, V4: 14, V5: 15, R3: 16, K3: 17, V6: 18, FINALE: 19,
}
# The Intermission (chapter 9) has no item: the game plays it once every Wave 1 route is finished.
INTERMISSION = "Intermission"
INTERMISSION_AFTER_WAVE = 3  # index in WAVES of [R1, K1, V1]

# Chapter id -> the region it belongs to (quests record their chapter in t_quest).
CHAPTER_REGION = {chapter: name for name, chapter in CHAPTER_IDS.items()} | {0: PROLOGUE, 9: INTERMISSION}
# Grim Garten bounties (chapter 65535 in t_quest) -> the route that first offers them (Neoseeker 4SPG list). They come
# well after their domain opens: the Third Domain Bounty only appears in Van Route 3 (a seed put Rean Route 1 there).
GRIM_GARTEN_BOUNTY_REGION = {57: R2, 59: V3, 62: V5, 64: V6}

# Source: the area list per act from the Neoseeker walkthrough (supplied by Brimaster2000), plus NoobFeed for Act I parts.
SCENA_REGION: dict[str, str | None] = {
    "d6010": PROLOGUE,  # VAR-halla Sector
    "m2000": ACT_I_A,  # Seiden Waterworks (Part 1)
    "d6500": ACT_I_A,  # Western Outskirts (Part 1)
    "c2400": ACT_I_A,  # Edith - Lèvre District (Part 1)
    "d6600": ACT_I_B,  # Underground Culvert (Part 2)
    "c1200": ACT_I_B,  # Blacklight District (Part 2)
    "d6700": ACT_I_C,  # Junction Area (Part 3)
    "m4100": R1,  # Auge Canyon (revisited in Rean 2)
    "d7010": V1,  # Cursed Labyrinth
    "m3200": K1,  # Sandsea (revisited in Kevin 2)
    "m3101": K1,  # Tharbad Underground Waterway
    "m4000": R2,  # Rare Metal Mine
    "d7200": R2,  # Astrological Workshop Ruins
    "d7100": V2,  # Dirke Memorial Park - Historical Conservation Area
    "m7200": V2,  # Reserve Railway Track
    "d7500": V4,  # Anchorville - Southern Outskirts
    "d7600": V4,  # General Hospital - Underground Production Lab
    "d7710": K2,  # Antikythera Tower Ruins
    "d7800": V5,  # Anchorville Logistics Center
    "t7400": V5,  # Anchorville Logistics Center - Exterior
    "m5100": R3,  # Pubu Pass
    "m5210": R3,  # Kunlun Trail
    "d7900": V6,  # Ruined City Hall
    "m1210": K3,  # Creil Outskirts
    "m1110": K3,  # Creil Hills
    "m1100": K3,  # Hillside (its chests have no known opened flag yet, so they stay out of seeds for now)
    "d8000": FINALE,  # Presidential Underground CC - L1
    "d8010": FINALE,  # Presidential Underground CC - L2
    "d8020": FINALE,  # Presidential Underground CC - L3

    # Probably a Daybreak II leftover: not in the act list, and its chests are never opened in a full save.
    "d0309": None,  # Coral Archipelago: Alternate

    # Never included: debug map, and randomly generated dungeons whose table chests are empty
    # (Grim Garten is handled per domain in locations.py instead).
    "a0000": None,
    "d0100": None,  # Floating Isles
    "d0110": None,  # Floating Isles
}

# Single chests that only become reachable in a later chapter than the rest of their map (confirmed in play).
CHEST_REGION_OVERRIDES: dict[str, str] = {
    "Sandsea Chest 8": K2,  # Treasure07: Sandsea part only open in Kevin Route 2
    "Sandsea Chest 9": K2,  # Treasure08
}

# Grim Garten domain number -> the chapters that open it (any one of them is enough). Source: the Neoseeker 4SPG list
# (each domain's first clear SP is listed under the route that opens it). Where a wave lets you pick the route order,
# only the listed route counts, to stay safe.
GRIM_GARTEN_DOMAINS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th"]
GRIM_GARTEN_DOMAIN_REGIONS: dict[int, list[str]] = {
    1: [ACT_I_B],
    2: [ACT_I_C],  # Frosted Gorge
    3: [INTERMISSION],  # needs all three wave 1 routes
    4: [R2],
    5: [V3],
    6: [V4],
    7: [V5],
    8: [V6],
    9: [FINALE],
}
