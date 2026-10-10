"""
Demand & Supply Mapping — Phase 1 matching engine.
Encodes the anchor/accessory/persona rules, band/location logic, and
skill-completeness gradient agreed in demand-supply-mapping-requirements.md.
"""
import re
import pandas as pd

# ---------------------------------------------------------------------------
# Band ladder
# ---------------------------------------------------------------------------
BAND_LADDER = ['E1.1', 'E1.2', 'E2.1', 'E2.2', 'E3.1', 'E3.2']
BAND_INDEX = {b: i for i, b in enumerate(BAND_LADDER)}

def band_index(sub_band):
    """Return ladder index, or None if outside the defined E1.1-E3.2 ladder
    (parked item #9 — E0/E2.3 and anything above E3.2)."""
    if sub_band in BAND_INDEX:
        return BAND_INDEX[sub_band]
    return None

# ---------------------------------------------------------------------------
# Location tiers
# ---------------------------------------------------------------------------
NV_CITIES = {'Vijayawada', 'Madurai', 'Lucknow', 'Gandhi Nagar', 'Nagpur'}
# Everything else observed in-scope is Prime; HFHYD is a known typo for Hyderabad (Prime).
CITY_ALIASES = {'HFHYD': 'Hyderabad'}

def normalize_city(city):
    if pd.isna(city):
        return None
    city = str(city).strip()
    return CITY_ALIASES.get(city, city)

def location_tier(city):
    city = normalize_city(city)
    if city is None:
        return None
    return 'NV' if city in NV_CITIES else 'Prime'

# ---------------------------------------------------------------------------
# SUPPLY-SIDE CLASSIFICATION — lookup table (Skill Cluster is a closed,
# curated ~28-value set: a lookup problem, not a parsing problem).
# Each entry: (persona, sub_persona, core_set_label, named_accessories,
#              completeness_tier, note)
# ---------------------------------------------------------------------------
# completeness tiers: 'Core only' | 'Core + Partial' | 'Core + Rich'
#
# Cross-persona matching (a Java/.NET employee's named frontend/mobile
# accessory being used to propose them against a standalone Frontend
# demand) has been REMOVED from the design entirely — a single named
# accessory never verified the rest of a real frontend stack (HTML/CSS/
# JS/TS), and it contributed zero rows to real output anyway. There is
# no cross_persona_accessory field anywhere in this table any more.
#
# REST / RESTful API is no longer tracked as an independent named
# accessory — knowing Spring or Spring Boot implies knowing REST, so it
# isn't a separately confirmable skill. Entries that used to list REST
# (alone, or alongside another accessory) have it removed, and their
# 'completeness' tier is recomputed from what's actually left in
# named_accessories (0 -> Core only, 1 -> Core + Partial, 2+ -> Core +
# Rich) rather than left overstating richness that REST used to supply.
#
# framework_confirmed (Fullstack Java / Fullstack .NET entries only):
# unlike REST, the actual web framework (Spring Boot for Java; Web API /
# MVC / Entity Framework for .NET) is NOT implied just by knowing the
# base language — a real Java developer can genuinely have never
# touched Spring Boot (e.g. "Java, SQL"). This flag records whether that
# specific entry's literal text actually confirms the framework, so
# build_matches.py can tell "Java, Spring Boot" apart from "Java, SQL"
# instead of treating persona match alone as sufficient. Deliberately
# NOT set on Frontend/parked/unclassified entries — not applicable there.

SUPPLY_TABLE = {
    "Java, Spring Boot, REST": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "Java, Spring Boot, REST, Microservices": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["Microservices"], completeness="Core + Partial", status="Reviewed"),
    "HTML, CSS, JavaScript, Redux, React.js": dict(
        persona="Frontend", sub_persona="React",
        named_accessories=["Redux"], completeness="Core + Partial", status="Reviewed"),
    "HTML, CSS, Javascript, TypeScript, Angular": dict(
        persona="Frontend", sub_persona="Angular",
        named_accessories=["TypeScript"], completeness="Core + Partial", status="Reviewed"),
    "HTML, CSS, Javascript, TypeSript, Angular": dict(   # typo variant
        persona="Frontend", sub_persona="Angular",
        named_accessories=["TypeScript"], completeness="Core + Partial", status="Reviewed (typo variant)"),
    "Java, SQL": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=False,
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "C#, .NET Framework, Microsoft SQL Server": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=False,
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "Java, Spring Boot, REST, React": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["React"], completeness="Core + Partial", status="Reviewed"),
    "MongoDB, Express.js, React.js, Node.js": dict(
        persona="Frontend", sub_persona="MERN",
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "C#, MVC, Web API, Entity Framework, Angular, Cloud": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["Angular", "Cloud"], completeness="Core + Rich", status="Reviewed"),
    "iOS, Swift": dict(
        persona="Frontend", sub_persona="iOS",
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "Android, Kotlin, Java": dict(
        persona="Frontend", sub_persona="Android",
        named_accessories=["Java (backend familiarity)"], completeness="Core only",
        status="Reviewed — corrected (demotion, not reroute-drop)"),
    "HTML, CSS, Javascript": dict(
        persona="Frontend", sub_persona="Core web (framework unconfirmed)",
        named_accessories=[], completeness="Core only", status="Reviewed — weak bucket"),
    "Java, Spring Boot, REST, Cloud (AWS, Azure, GCP)": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["Cloud"], completeness="Core + Partial", status="Reviewed"),
    "Java, Spring Boot, REST, Messaging": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["Messaging"], completeness="Core + Partial", status="Reviewed"),
    "C#, MVC, Web API, Entity Framework, Cloud": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["Cloud"], completeness="Core + Partial", status="Reviewed"),
    "C#, SQL": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=False,
        named_accessories=[], completeness="Core only", status="Reviewed"),
    "C#, Angular, Web API": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["Angular"], completeness="Core + Partial", status="Reviewed"),
    "C#, MVC, Web API, Entity Framework, React, DevOps": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["React", "DevOps"], completeness="Core + Rich", status="Reviewed"),
    "C#, Web API, Entity Framework, Microservices": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["Microservices"], completeness="Core + Partial", status="Reviewed"),
    "C#, MVC, Web API, Entity Framework, Angular, DevOps": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=True,
        named_accessories=["Angular", "DevOps"], completeness="Core + Rich", status="Reviewed"),
    "Java, Spring Boot, REST, Angular": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["Angular"], completeness="Core + Partial", status="Reviewed"),
    "C#, .NET Framework, Cloud, DevOps": dict(
        persona="Fullstack .NET", sub_persona=None, framework_confirmed=False,
        named_accessories=["Cloud", "DevOps"], completeness="Core + Rich", status="Reviewed"),
    "Java, Spring Boot, REST, DevOps": dict(
        persona="Fullstack Java", sub_persona=None, framework_confirmed=True,
        named_accessories=["DevOps"], completeness="Core + Partial", status="Reviewed"),
    # Parked / unclassified — legacy .NET desktop, low volume, not the web
    # full-stack capability "Fullstack .NET" actually means elsewhere.
    "C#, WinForms, WPF, WCF": dict(
        persona=None, sub_persona=None, named_accessories=[], completeness=None,
        status="PARKED — legacy .NET desktop, out of Phase 1 capability"),
    "C#, ASP.Net Webforms, WCF": dict(
        persona=None, sub_persona=None, named_accessories=[], completeness=None,
        status="PARKED — legacy .NET desktop, out of Phase 1 capability"),
    # Out-of-scope-persona — performance/accessibility testing tooling
    "NFT - Performance/Accessibility | JMeter + BlazeMeter + Grafana": dict(
        persona=None, sub_persona=None, named_accessories=[], completeness=None,
        status="UNCLASSIFIED — out-of-scope persona (NFT/perf testing), Capability/MAS-Mapping mismatch"),
}

def classify_supply_row(skill_cluster):
    """Returns a dict with persona/sub_persona/accessories/completeness/status."""
    if pd.isna(skill_cluster) or str(skill_cluster).strip() == "":
        return dict(persona=None, sub_persona=None, named_accessories=[],
                     completeness=None,
                     status="UNCLASSIFIED — Skill Cluster missing entirely (urgent data-quality flag)")
    key = str(skill_cluster).strip()
    if key in SUPPLY_TABLE:
        return SUPPLY_TABLE[key]
    # Exact-match-only fallback (per agreed fallback behavior — no fuzzy matching)
    return dict(persona=None, sub_persona=None, named_accessories=[],
                 completeness=None,
                 status=f"UNCLASSIFIED — Skill Cluster not in reference table: '{key}'")

# ---------------------------------------------------------------------------
# DEMAND-SIDE CLASSIFICATION — token/rule parser (free text, open vocabulary:
# a parsing/classification problem, not a lookup problem).
#
# NOTE: the anchor tokens actually checked below (has_java, has_dotnet_word,
# has_devops, has_ios, has_android_word, ...) are literal string checks via
# _contains_word(), NOT driven by a token-set constant here — deliberately.
# A previous version of this file defined JAVA_TOKENS/DOTNET_TOKENS/
# DEVOPS_TOKENS/IOS_TOKENS/ANDROID_TOKENS/RAW_SQL_TOKENS as if they were the
# source of truth, but nothing ever read them; the real logic had already
# diverged (most importantly, ANDROID_TOKENS used to bundle in 'kotlin',
# which directly contradicts the deliberate "Kotlin does not imply Android
# without an explicit mobile term" fix a few dozen lines down). Removed
# rather than left in place — an unused constant that contradicts the real
# logic is a landmine for whoever edits it next, and this project has
# already found three real bugs from exactly this kind of drift (REST,
# MEAN-as-React, Cloud/AWS naming). has_angular is the same kind of literal
# check (_contains_word(tokens, 'angular')), so there's no ANGULAR_TOKENS
# constant at all — never add one unless the check below is changed to
# actually read it. REACT_TOKENS/NODE_TOKENS/MERN_STACK_TOKENS/
# WEB_BASICS_TOKENS/LEGACY_DOTNET_DESKTOP/SPRING_BOOT_TOKENS below ARE all
# actually read via has_any() and stay.
# ---------------------------------------------------------------------------
REACT_TOKENS = {'react.js', 'react', 'next.js'}
NODE_TOKENS = {'node.js', 'node'}
MERN_STACK_TOKENS = {'mongo db', 'mongodb', 'express.js'}
WEB_BASICS_TOKENS = {'html', 'css', 'cascading style sheets (css)', 'javascript'}
LEGACY_DOTNET_DESKTOP = {'wpf', 'winforms', 'webforms', 'wcf'}
SPRING_BOOT_TOKENS = {'spring boot'}
# The actual .NET web framework — analogous to SPRING_BOOT_TOKENS for Java.
# Grounded in real demand phrasings ("Web API", "ASP.NET MVC Framework",
# "ASP.NET Framework"); '.NET Core'/'.NET Framework' alone are just the
# runtime version, not a web framework, so they're deliberately excluded.
DOTNET_FRAMEWORK_TOKENS = {'web api', 'asp.net mvc framework', 'asp.net framework', 'entity framework'}

# ---------------------------------------------------------------------------
# Named-accessory canonical registry — the SINGLE source of truth for every
# "notable accessory" this engine tracks, shared by BOTH the supply-side
# curated table above and the demand-side token parser below.
#
# Task #7 fix: before this, supply-side accessory names were hand-typed per
# SUPPLY_TABLE entry ("Cloud (AWS/Azure/GCP)", "Cloud") while demand-side
# names were auto-generated from a separate token list ("Amazon Web
# Services (Aws)", "Azure", "Gcp") — different strings for the same real
# skill, which meant skill_signal()'s named-accessory-gap check (a plain
# string compare) could NEVER match them, so an employee with real cloud
# experience would always show a false gap against a demand asking for
# AWS/Azure/GCP specifically. Confirmed live in real data, same shape of
# bug as the REST/RestfulApi mismatch already fixed.
#
# Each canonical name maps to every raw phrase/token that should resolve to
# it. SUPPLY_TABLE entries must use ONLY these canonical names (never a
# synonym) so both sides are guaranteed to agree. REST/RESTful API is
# deliberately absent — implied by Spring/Spring Boot, not an independently
# trackable skill (Task #2).
ACCESSORY_CANONICAL = {
    "Cloud": {'cloud', 'amazon web services (aws)', 'aws', 'microsoft azure', 'azure',
              'google cloud platform (gcp)', 'gcp'},
    "DevOps": {'devops', 'azure devops'},
    "Microservices": {'microservices'},
    "Kafka": {'apache kafka', 'kafka'},
    # JMS and RabbitMQ are deliberately their OWN canonical entries, not
    # merged into Kafka — unlike Cloud (where AWS/Azure/GCP really are the
    # same "Cloud" ask at the granularity this business curates), Kafka/JMS/
    # RabbitMQ are genuinely different messaging technologies, and an
    # employee confirmed on one doesn't confirm the others. JMS is a real,
    # live gap fix: a real demand row ("JMS, Java, React.js") was silently
    # invisible to the engine before this — 'jms' wasn't tracked at all, so
    # it never appeared as an accessory ask. RabbitMQ has no real demand row
    # yet but costs nothing to add now that Kafka/JMS are both tracked.
    "JMS": {'jms', 'java message service'},
    "RabbitMQ": {'rabbitmq', 'rabbit mq'},
    "Docker": {'docker'},
    "Hibernate": {'hibernate'},
    "Python": {'python'},
    "Web Services": {'web services'},
    "Redis": {'redis'},
    "GraphQL": {'graphql'},
    # "Messaging" is the one existing SUPPLY_TABLE entry's literal accessory
    # text ("Java, Spring Boot, REST, Messaging") — an architecture-level
    # term, not a specific technology, per the explicit correction that
    # Messaging/Kafka/JMS/RabbitMQ are NOT the same thing at any level of
    # granularity (unlike Cloud/AWS). It stays its own bucket, deliberately
    # UNMERGED with Kafka/JMS/RabbitMQ — an employee whose profile only says
    # "Messaging" genuinely doesn't confirm which specific tech they used,
    # so it correctly does NOT satisfy a demand asking for Kafka/JMS/
    # RabbitMQ specifically (this was already the actual behavior before
    # this change — the strings never matched — it just wasn't quite the
    # right behavior for the right reason on record). No demand-side token
    # is registered for it (real demand text never uses "messaging"
    # generically — checked against the live data, zero hits) — add one if
    # that ever changes. The real, unresolved issue is a DATA-QUALITY one,
    # not a matching-logic one: the one employee with "Messaging" on file
    # can never be proposed against a Kafka/JMS/RabbitMQ-specific demand
    # until someone finds out which technology they actually used and
    # updates SUPPLY_TABLE accordingly — that's a follow-up for whoever owns
    # that record, not something fixable in code.
    "Messaging": set(),
    # React/Angular, tracked as a named accessory ONLY when they co-occur
    # with a Java/.NET language anchor (a Fullstack dev who also does some
    # frontend work) — now tracked the same way every other accessory on
    # this list is, per explicit instruction ("React and Angular should be
    # counted same like Cloud, DevOps, Docker etc"). Before this, they were
    # the one named skill silently dropped entirely when named alongside
    # Java/.NET (e.g. "Java, Spring Boot, REST, React" -> no accessory
    # recorded at all) while everything else here was tracked — an
    # inconsistency, not a deliberate omission. Weighted Minor (see
    # ACCESSORY_WEIGHT below) — same bucket as Docker/Hibernate/Python, not
    # Cloud/DevOps's Important — since it's informational for a backend
    # persona, not framework-defining; correctable if that read is wrong.
    # When React/Angular instead DEFINE the persona itself (a standalone
    # Frontend demand/employee), they are deliberately excluded from
    # named_accessories at each of those return sites below — a persona
    # isn't its own accessory.
    "React": REACT_TOKENS,
    "Angular": {'angular'},
}

# Reverse lookup: raw token -> canonical display name (built from the
# registry above, never hand-maintained separately).
_TOKEN_TO_CANONICAL = {tok: name for name, toks in ACCESSORY_CANONICAL.items() for tok in toks}

# Every raw token the demand-side parser should recognize as accessory-worthy
# (derived, not duplicated — this is what NOTABLE_ACCESSORY_TOKENS used to be
# hand-maintained as, which is exactly how it drifted out of sync).
NOTABLE_ACCESSORY_TOKENS = set(_TOKEN_TO_CANONICAL.keys())

# ---------------------------------------------------------------------------
# Skill-weighting (Task #8) — replaces the old flat "any named accessory gap
# gets the same one discount" rule with three severities, agreed with the
# user (v1, explicitly correctable — this is a first pass, not a final call):
#
#   Critical  -> capped at Weak   (this is not really a match, but per the
#                same deliberate-stopgap decision as Task #6, shown at a
#                discount rather than excluded outright, pending a real fix)
#   Important -> capped at Good   (can't be Strong, but still a solid option)
#   Minor     -> no cap at all    (informational note only; Strong is still
#                reachable — this is the behavior change from before, where
#                EVERY named accessory gap, regardless of importance, capped
#                at Good)
#
# "Framework" is the one Critical-weight entry and is NOT itself a named
# accessory — it's the persona's real framework (Spring Boot for Java; Web
# API/MVC/Entity Framework for .NET; React or Angular itself for Frontend),
# tracked separately via framework_confirmed (Java/.NET) or the existing
# "Core web (framework unconfirmed)" sub-persona (Frontend) rather than via
# named_accessories. It's listed here so ONE table is the source of truth
# for severity even though the underlying signal lives in two places —
# per the user's explicit call to fold Task #6's framework check and
# Frontend's pre-existing framework-unconfirmed bucket into this same
# concept rather than leaving them as unrelated special cases.
ACCESSORY_WEIGHT = {
    "Framework": "Critical",
    "Microservices": "Important",
    "Cloud": "Important",
    "DevOps": "Important",
    "Kafka": "Important",
    "JMS": "Important",        # same family/importance as Kafka — a specific messaging technology
    "RabbitMQ": "Important",   # same family/importance as Kafka — a specific messaging technology
    "Docker": "Minor",
    "Hibernate": "Minor",
    "Web Services": "Minor",
    "Redis": "Minor",
    "GraphQL": "Minor",
    "Python": "Minor",
    # "Kotlin" is a JVM-accessory on the Java side (see the "Kotlin without
    # explicit Android/iOS" branch below) but has no SUPPLY_TABLE entry that
    # ever confirms it for a Java employee — no real employee can currently
    # satisfy a Java+Kotlin demand ask, so this will always show as a gap.
    # Explicit Minor here (same bucket as Python — a complementary language,
    # not a load-bearing one) so it doesn't silently fall through to the
    # Important default while that coverage gap gets addressed separately.
    "Kotlin": "Minor",
    # "Messaging" is architecture-level, not a specific technology (see
    # ACCESSORY_CANONICAL above) — an employee whose profile only says
    # "Messaging" hasn't confirmed Kafka/JMS/RabbitMQ specifically, so Minor
    # (unconfirmed/generic, same reasoning as Kotlin) rather than Important
    # (which would treat an unconfirmed generic claim the same as a
    # confirmed specific one).
    "Messaging": "Minor",
    # React/Angular as a Java/.NET accessory (not as the Frontend persona
    # itself — see ACCESSORY_CANONICAL above): Minor, same bucket as
    # Docker/Hibernate/Python — a nice-to-have that doesn't cap the tier,
    # not a framework-defining Critical skill for a backend persona.
    "React": "Minor",
    "Angular": "Minor",
}
_SEVERITY_RANK = {"Critical": 3, "Important": 2, "Minor": 1}

# Per-persona overrides (Task #10 — gap review item #4): every accessory
# currently carries the same weight regardless of persona (Cloud is
# Important whether it's a Java or .NET demand asking for it), so this
# starts EMPTY — nothing in the real data needs an override today. It
# exists so a future case CAN be represented (e.g. if some accessory should
# matter more for one persona than another) without reworking
# accessory_severity()'s signature again. Key: (persona, accessory_name).
ACCESSORY_WEIGHT_OVERRIDES = {}

def accessory_severity(name, persona=None):
    """Weight for a named accessory. Checks a per-persona override first
    (ACCESSORY_WEIGHT_OVERRIDES, currently always empty — see its comment),
    then falls back to the persona-agnostic ACCESSORY_WEIGHT table, and
    finally defaults unknown accessories to Important — i.e. safer to
    over-discount an accessory nobody has explicitly weighted yet than to
    silently let it through at full strength."""
    if persona is not None and (persona, name) in ACCESSORY_WEIGHT_OVERRIDES:
        return ACCESSORY_WEIGHT_OVERRIDES[(persona, name)]
    return ACCESSORY_WEIGHT.get(name, "Important")

OUT_OF_SCOPE_TOKENS = {
    'tricentis tosca', 'etl tool - others', 'solution architecture',
    'drupal', 'php', 'selenium',
}

def _tokenize(text):
    if pd.isna(text):
        return []
    return [t.strip().lower() for t in str(text).split(',') if t.strip()]

def _contains_word(tokens, word):
    """Whole-word substring match within any token (handles phrases like
    'Java Full Stack' or '.NET Full Stack' where the anchor word is
    embedded in a longer token, while excluding false positives like
    'javascript' containing 'java')."""
    pattern = re.compile(r'\b' + re.escape(word) + r'\b')
    return any(pattern.search(t) for t in tokens)

def classify_demand_row(skill_text):
    """Token-rule parser implementing the anchor/accessory/persona rules
    agreed for demand's free-text Final Skill Cluster field.

    Note: this no longer computes or returns a cross_persona_accessory —
    cross-persona matching has been removed from the design entirely."""
    raw = str(skill_text).strip() if not pd.isna(skill_text) else ""
    tokens = _tokenize(skill_text)
    tokset = set(tokens)

    def has_any(vocab):
        return bool(tokset & vocab)

    # -- Whole-phrase shortcuts used verbatim in the data --------------------
    # framework_confirmed=True here: an explicit self-declared persona label
    # is trusted at face value, same as the rest of this branch always was.
    if raw.strip().lower() == 'java full stack':
        return dict(persona="Fullstack Java", sub_persona=None, band_note=None,
                     named_accessories=[], framework_confirmed=True,
                     status="Reviewed — explicit persona label")
    if raw.strip().lower() == '.net full stack':
        return dict(persona="Fullstack .NET", sub_persona=None, band_note=None,
                     named_accessories=[], framework_confirmed=True,
                     status="Reviewed — explicit persona label")

    # Framework-implies-language: any Spring-family framework implies Java
    # even where "Java" itself isn't spelled out as its own token.
    has_spring = _contains_word(tokens, 'spring') or has_any(SPRING_BOOT_TOKENS)
    has_dotnet_word = any('.net' in t for t in tokens) or 'c#' in tokset or any('asp.net' in t for t in tokens) or any('vb.net' in t for t in tokens)
    has_java = _contains_word(tokens, 'java') or (has_spring and not has_dotnet_word)
    has_dotnet = has_dotnet_word
    has_devops = _contains_word(tokens, 'devops')
    has_ios = _contains_word(tokens, 'ios') or _contains_word(tokens, 'swift')
    has_android_word = _contains_word(tokens, 'android') or 'native mobile app development' in tokset
    has_kotlin = 'kotlin' in tokset
    has_react = has_any(REACT_TOKENS) or _contains_word(tokens, 'next.js')
    has_angular = _contains_word(tokens, 'angular')
    has_node = has_any(NODE_TOKENS)
    has_mern_extra = has_any(MERN_STACK_TOKENS)
    has_web_basics = has_any(WEB_BASICS_TOKENS)
    has_legacy_desktop = has_any(LEGACY_DOTNET_DESKTOP)
    has_dotnet_framework = has_any(DOTNET_FRAMEWORK_TOKENS)

    # Resolve every matched raw token to its canonical display name (Task #7)
    # and de-dup — e.g. a demand mentioning both "Cloud" and "AWS" collapses
    # to one "Cloud" entry, matching supply-side's granularity, which is the
    # same reason: SUPPLY_TABLE never curates finer than "Cloud" either.
    matched_tokens = sorted(tokset & NOTABLE_ACCESSORY_TOKENS)
    seen_canonical = set()
    accessories_display = []
    for t in matched_tokens:
        name = _TOKEN_TO_CANONICAL[t]
        if name not in seen_canonical:
            accessories_display.append(name)
            seen_canonical.add(name)

    # -- Explicit mobile platform present ------------------------------------
    if has_ios or has_android_word or (has_kotlin and (has_android_word or has_ios)):
        sub = "iOS" if (has_ios and not has_android_word) else \
              "Android" if (has_android_word and not has_ios) else "iOS + Android"
        demoted = []
        if has_java:
            demoted.append("Java (backend familiarity)")
        if has_dotnet:
            demoted.append(".NET (backend familiarity)")
        return dict(persona="Frontend", sub_persona=sub, band_note=None,
                     named_accessories=demoted + accessories_display,
                     status="Reviewed — mobile anchor; language anchor demoted to named accessory" if demoted
                            else "Reviewed — mobile anchor")

    # -- Kotlin without explicit Android/iOS: JVM backend accessory, not mobile
    if has_kotlin and not has_android_word and not has_ios:
        if has_java:
            return dict(persona="Fullstack Java", sub_persona=None, band_note=None,
                         named_accessories=["Kotlin"] + accessories_display,
                         status="Reviewed — corrected: Kotlin does not imply Android without explicit mobile term")
        # Kotlin named with no Java/mobile signal at all — rare, park it
        return dict(persona=None, sub_persona=None, band_note=None,
                     named_accessories=[],
                     status=f"UNCLASSIFIED — no recognizable Phase 1 anchor: '{raw}'")

    # -- Java anchor branch ----------------------------------------------------
    # 2026-09-29: routing reverted to unconditional (was briefly gated on
    # has_spring/has_frontend_anchor, which turned out to silently
    # misclassify demands where MAS Mapping = 'Full Stack' agreed with
    # Fullstack Java and the additional-request text explicitly ruled out
    # a frontend need -- e.g. job req 152043, "full stack but no GUI
    # experience needed". Two demands with the IDENTICAL skill-cluster
    # text ("Devops,Java Full Stack,React.js") were independently tagged
    # Front End on one and Full Stack on the other -- proof the ambiguity
    # is in the source data, not resolvable by any token rule. Anchor
    # precedence restored to original (Java always wins as anchor); the
    # ambiguous case is now a REVIEW FLAG only (see status below), same
    # "checked, not used to match" principle as MAS Mapping Check --
    # never a silent persona override again.
    if has_java:
        named = []
        if has_devops:
            named.append("DevOps")
        if 'python' in tokset:
            named.append("Python")
        named += [a for a in accessories_display if a not in ('Python',)]
        # de-dup while preserving order
        seen = set(); named2 = []
        for n in named:
            if n not in seen:
                named2.append(n); seen.add(n)
        return dict(persona="Fullstack Java", sub_persona=None, band_note=None,
                     named_accessories=named2, framework_confirmed=has_spring,
                     status="Reviewed — Java anchor")

    # -- .NET anchor branch ------------------------------------------------
    if has_dotnet:
        if has_legacy_desktop:
            return dict(persona=None, sub_persona=None, band_note=None,
                         named_accessories=[],
                         status=f"PARKED — legacy .NET desktop (WinForms/WPF/WCF): '{raw}'")
        named = []
        if has_devops:
            named.append("DevOps")
        named += accessories_display
        seen = set(); named2 = []
        for n in named:
            if n not in seen:
                named2.append(n); seen.add(n)
        return dict(persona="Fullstack .NET", sub_persona=None, band_note=None,
                     named_accessories=named2, framework_confirmed=has_dotnet_framework,
                     status="Reviewed — .NET anchor")

    # -- Standalone frontend (no backend language anchor) -------------------
    # React/Angular are now tracked as named accessories (see
    # ACCESSORY_CANONICAL above) so they carry through correctly when named
    # alongside Java/.NET — but here they ARE the persona itself, so they're
    # excluded from named_accessories at each of these return sites: a
    # persona isn't its own accessory.
    frontend_accessories_display = [a for a in accessories_display if a not in ('React', 'Angular')]
    if has_react and has_angular:
        return dict(persona="Frontend", sub_persona="React + Angular (dual-acceptable)",
                     band_note=None, named_accessories=frontend_accessories_display,
                     status="Reviewed — dual-acceptable frontend")
    # MEAN (Mongo/Express/Node backend + Angular frontend) must be checked
    # BEFORE the React/MERN branch below — otherwise (has_node and
    # has_mern_extra) alone would silently route a MEAN-shaped demand into
    # sub_persona="React", wrongly excluding a genuine Angular candidate.
    if has_angular and has_node and has_mern_extra:
        return dict(persona="Frontend", sub_persona="MEAN", band_note=None,
                     named_accessories=frontend_accessories_display, status="Reviewed — MEAN anchor")
    if has_react or (has_node and has_mern_extra):
        return dict(persona="Frontend", sub_persona="React", band_note=None,
                     named_accessories=frontend_accessories_display, status="Reviewed — React anchor")
    if has_angular:
        return dict(persona="Frontend", sub_persona="Angular", band_note=None,
                     named_accessories=frontend_accessories_display, status="Reviewed — Angular anchor")
    if has_node and not has_mern_extra:
        return dict(persona="Frontend", sub_persona="MERN", band_note=None,
                     named_accessories=["Node.js only — weak MERN match"],
                     status="Reviewed — weak MERN match (Node.js only)")
    if has_web_basics and not (has_react or has_angular or has_node):
        return dict(persona="Frontend", sub_persona="Core web (framework unconfirmed)",
                     band_note=None, named_accessories=accessories_display,
                     status="Reviewed — framework-unconfirmed bucket")
    if has_devops:
        return dict(persona=None, sub_persona=None, band_note=None,
                     named_accessories=[],
                     status=f"OUT OF SCOPE — DevOps-anchor persona, not a Phase 1 persona: '{raw}'")

    if tokset & OUT_OF_SCOPE_TOKENS or not tokset:
        return dict(persona=None, sub_persona=None, band_note=None,
                     named_accessories=[],
                     status=f"OUT OF SCOPE — scope leakage (Testing/Integration/Mainframe/TPM): '{raw}'")

    return dict(persona=None, sub_persona=None, band_note=None,
                named_accessories=[],
                status=f"UNCLASSIFIED — no recognizable Phase 1 anchor: '{raw}'")


# ---------------------------------------------------------------------------
# Skill-completeness gradient tiebreaker label (supply side already tagged
# via SUPPLY_TABLE's 'completeness' field — this is just the display helper)
# ---------------------------------------------------------------------------
COMPLETENESS_RANK = {"Core only": 0, "Core + Partial": 1, "Core + Rich": 2, None: -1}
