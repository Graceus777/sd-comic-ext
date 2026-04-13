"""
Procedural scenario generator for short-form comic strips.

Produces scenario dicts compatible with generate_strip.py's build_strip_script().
Each setting defines a unique location/situation with hand-authored SFW panels
and auto-composed environment panels for the LoRA-driven NSFW pages.

To add a new setting, append a dict to SETTINGS following the existing format.
"""

import random
import os
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Generation defaults (shared across all scenarios)
# ---------------------------------------------------------------------------

GENERATION_DEFAULTS = {
    "steps": 30,
    "cfg": 7.0,
    "width": 1024,
    "height": 1280,
    "batch": 1,
    "sampler": "Euler a",
    "adetailer": True,
    "base_positive": "lazypos",
    "base_negative": "lazyneg",
}

# ---------------------------------------------------------------------------
# Settings pool
# ---------------------------------------------------------------------------

SETTINGS = [
    # ------------------------------------------------------------------
    # 1. Library — closing time
    # ------------------------------------------------------------------
    {
        "key": "library_closing",
        "titles": ["Quiet Hours", "Overdue", "Between the Shelves", "Return Policy"],
        "description": "The library closed ten minutes ago. She's still in the stacks.",
        "time": "evening",
        "location": "library",
        "furniture": ["wooden reading desk", "leather armchair", "tall bookshelf", "study carrel", "reading nook bench"],
        "lighting": ["warm reading lamp", "dim overhead light", "golden hour through tall windows", "green banker lamp glow"],
        "atmosphere": ["quiet", "cozy", "intimate"],

        "setup": [
            {
                "scene": "sitting curled up in leather armchair in library, open book on lap, legs tucked under, cardigan sliding off one shoulder, warm reading lamp beside her, tall bookshelves behind, golden evening light through windows",
                "positive_extra": "leather armchair, library, book, cardigan, reading lamp, bookshelves, golden light, evening, cozy",
                "shot": "medium",
                "caption": "The library closed ten minutes ago. She hadn't noticed.",
            },
            {
                "scene": "reaching up to high bookshelf, standing on tiptoes, back arched, fingers brushing book spine, cardigan riding up showing sliver of waist, library aisle, warm light",
                "positive_extra": "reaching up, tiptoes, back arched, bookshelf, waist visible, library aisle, warm light",
                "shot": "full_body",
            },
            {
                "scene": "looking over shoulder in library aisle, book held against chest, surprised expression, slight smile, reading glasses on top of head, warm lamp light, bookshelves lining both sides",
                "positive_extra": "looking over shoulder, book to chest, surprised, smile, reading glasses, warm light, library aisle",
                "shot": "medium_close",
                "dialogue": "I didn't hear the door lock.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on edge of reading desk, legs crossed, book in lap, looking up at someone standing, playful smirk, cardigan hanging off both shoulders, library at night",
                "positive_extra": "sitting on desk, legs crossed, book, looking up, smirk, cardigan off shoulders, library, night",
                "shot": "medium",
                "dialogue": "You could've just asked me to leave.",
            },
            {
                "scene": "leaning back against bookshelf, arms behind her, head tilted, confident smile, dim library lighting, leather-bound books framing her",
                "positive_extra": "against bookshelf, arms behind, head tilted, confident, dim light, books framing",
                "shot": "medium_close",
            },
            {
                "scene": "holding open book between them like a barrier, peeking over the top edge, teasing eyes, only upper face visible, warm lamp glow, library",
                "positive_extra": "holding book up, peeking over, teasing eyes, warm lamp glow, library",
                "shot": "close_up",
                "dialogue": "This one's my favorite chapter.",
            },
            {
                "scene": "pressing back against bookshelf, books shifting behind her, parted lips, flushed cheeks, looking at viewer, cardigan slipping down arms, dim amber library light",
                "positive_extra": "against bookshelf, books shifting, parted lips, flushed, looking at viewer, cardigan slipping, amber light",
                "shot": "close_up",
                "caption": "Some stories are better without words.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on library floor between shelves, using open book as pillow, satisfied lazy smile, cardigan draped over body, warm lamp light from above, scattered books around",
                "positive_extra": "lying on floor, book pillow, lazy smile, cardigan, warm light, scattered books, satisfied",
                "shot": "full_body",
                "dialogue": "I think I owe some late fees.",
            },
            {
                "scene": "close-up portrait, reading glasses back on, hair completely disheveled, satisfied smirk, warm golden light, bookshelf blurred behind",
                "positive_extra": "close-up, reading glasses, disheveled hair, smirk, warm golden light, bookshelf background",
                "shot": "close_up",
                "caption": "She finally finished the chapter.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 2. Rain — caught under an awning
    # ------------------------------------------------------------------
    {
        "key": "rain_awning",
        "titles": ["Downpour", "Caught in the Rain", "Shelter", "Puddles"],
        "description": "Caught in a sudden downpour. One awning. Two strangers.",
        "time": "night",
        "location": "city street",
        "furniture": ["shop awning", "wet sidewalk", "brick wall", "metal bench", "fire escape above"],
        "lighting": ["neon sign reflections in puddles", "warm shopfront glow", "streetlight through rain", "rain-streaked neon"],
        "atmosphere": ["rain", "intimate", "wet"],

        "setup": [
            {
                "scene": "standing under shop awning, arms crossed, damp hair clinging to face, rain pouring just past her feet, wet street reflecting neon signs, looking out at the downpour, thin wet blouse",
                "positive_extra": "awning, damp hair, rain, wet street, neon reflections, thin wet blouse, night, city",
                "shot": "medium",
                "caption": "The forecast said clear skies. The forecast lied.",
            },
            {
                "scene": "wringing water out of hair, head tilted sideways, water dripping, laughing, soaked clothes clinging to body, wet sidewalk, rain in background, neon shop signs",
                "positive_extra": "wringing hair, head tilted, water dripping, laughing, soaked clothes clinging, wet sidewalk, neon, rain",
                "shot": "medium_close",
            },
            {
                "scene": "looking sideways at someone who just ducked under the same awning, amused expression, eyebrow raised, rain-soaked hair framing face, neon glow on wet skin, puddles on sidewalk",
                "positive_extra": "looking sideways, amused, eyebrow raised, wet hair, neon glow on skin, puddles, awning, rain",
                "shot": "close_up",
                "dialogue": "Room for one more?",
            },
        ],

        "tension": [
            {
                "scene": "leaning against wet brick wall under awning, one foot propped up, head back, rain cascading off awning edge, soaked fabric transparent, teasing half-smile, neon reflections on skin",
                "positive_extra": "against brick wall, foot propped, head back, rain cascading, wet transparent fabric, half-smile, neon",
                "shot": "full_body",
                "dialogue": "We could be here a while.",
            },
            {
                "scene": "standing very close together under narrow awning, faces inches apart, breath visible in cool air, rain all around, wet hair, neon light coloring their skin pink and blue",
                "positive_extra": "close together, faces close, breath visible, rain around, wet hair, neon pink blue, tight space",
                "shot": "medium_close",
            },
            {
                "scene": "playfully stepping one foot into the rain, looking back over shoulder, water splashing around ankle, daring expression, soaked through, awning edge dripping",
                "positive_extra": "foot in rain, looking back, water splash, daring, soaked, awning dripping",
                "shot": "medium",
                "dialogue": "Think the rain will stop if I ask nicely?",
            },
            {
                "scene": "pressed against brick wall, rain-soaked, parted lips, eyes half-lidded, water running down neck and collarbone, neon light painting face in warm tones, looking at viewer",
                "positive_extra": "against wall, rain-soaked, parted lips, half-lidded, water on neck, neon warm tones, looking at viewer, flushed",
                "shot": "close_up",
                "caption": "The rain wasn't the only thing getting heavier.",
            },
        ],

        "aftermath": [
            {
                "scene": "sitting on wet sidewalk under awning, knees up, wearing his jacket over shoulders, rain still falling, puddles everywhere, satisfied tired grin, messy wet hair, neon reflections in water",
                "positive_extra": "sitting on sidewalk, knees up, jacket on shoulders, rain, puddles, tired grin, wet hair, neon reflections",
                "shot": "full_body",
                "dialogue": "I think the rain stopped. ...Did it?",
            },
            {
                "scene": "close-up portrait, wet hair plastered to forehead, lazy satisfied smile, raindrops on eyelashes, neon pink glow on one cheek, breath visible",
                "positive_extra": "close-up, wet hair, satisfied smile, raindrops on lashes, neon pink glow, breath visible",
                "shot": "close_up",
                "caption": "She never minded the rain after that.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 3. Bar — last call
    # ------------------------------------------------------------------
    {
        "key": "bar_last_call",
        "titles": ["Last Call", "One More Round", "Closing Tab", "Nightcap"],
        "description": "Bar is closing. She's the last one on the stool. The bartender isn't rushing her.",
        "time": "night",
        "location": "bar",
        "furniture": ["bar counter", "bar stool", "liquor shelf", "booth seat", "pool table"],
        "lighting": ["warm neon bar sign", "dim amber pendant light", "neon beer sign glow", "candlelight on counter"],
        "atmosphere": ["dim", "warm", "intimate", "smoky"],

        "setup": [
            {
                "scene": "sitting alone at bar counter, chin resting on hand, empty glass in front of her, low-cut top, dim amber pendant light above, rows of liquor bottles behind bar, late night",
                "positive_extra": "bar counter, chin on hand, empty glass, low-cut top, amber light, liquor bottles, bar, night, alone",
                "shot": "medium",
                "caption": "Last call was fifteen minutes ago. She ordered another anyway.",
            },
            {
                "scene": "tracing finger around rim of empty glass, looking down, slight melancholy smile, hair falling across face, bar counter, warm neon sign glow, dim atmosphere",
                "positive_extra": "finger on glass rim, looking down, melancholy smile, hair across face, bar, neon glow, dim",
                "shot": "close_up",
            },
            {
                "scene": "looking up from bar counter with renewed interest, slight eyebrow raise, smirk forming, chin still on palm, someone slid a fresh drink over, amber light catching her eyes",
                "positive_extra": "looking up, eyebrow raise, smirk, chin on palm, fresh drink, amber light, eyes, bar",
                "shot": "medium_close",
                "dialogue": "I didn't order that.",
            },
        ],

        "tension": [
            {
                "scene": "leaning forward on bar counter, elbows on wood, cleavage visible, holding glass, looking at viewer with direct confident gaze, liquor bottles behind, warm amber light",
                "positive_extra": "leaning forward, elbows on bar, cleavage, holding glass, direct gaze, liquor bottles, amber light",
                "shot": "medium",
                "dialogue": "So what's your excuse for being here this late?",
            },
            {
                "scene": "standing next to bar stool, one hand on counter, hip cocked, head tilted, playful challenging expression, neon bar sign casting colored light on skin",
                "positive_extra": "standing, hand on counter, hip cocked, head tilted, playful, neon light on skin, bar",
                "shot": "medium_close",
            },
            {
                "scene": "sitting sideways on bar stool, legs crossed, one heel dangling, leaning back against bar counter, arms stretched along bar top, confident relaxed pose, dim warm lighting",
                "positive_extra": "sideways on stool, legs crossed, heel dangling, leaning on counter, arms spread, confident, dim warm light",
                "shot": "full_body",
                "dialogue": "I'm not leaving until you give me a reason to stay.",
            },
            {
                "scene": "close-up, biting lower lip around cocktail straw, looking up through lashes, flushed cheeks, neon sign reflected in eyes, bar counter foreground blur",
                "positive_extra": "close-up, biting straw, looking up through lashes, flushed, neon in eyes, bar blur foreground",
                "shot": "close_up",
                "caption": "The tab was going to be expensive. She didn't care.",
            },
        ],

        "aftermath": [
            {
                "scene": "sitting on bar counter, legs dangling, holding bottle of water, hair messed up, satisfied grin, dim bar lights, chairs stacked on tables in background, night",
                "positive_extra": "on counter, legs dangling, water bottle, messed hair, satisfied grin, dim lights, stacked chairs, night",
                "shot": "full_body",
                "dialogue": "So... is this place actually closed?",
            },
            {
                "scene": "close-up, lazy grin, chin resting on folded arms on bar counter, hair messy, warm amber light, glassy satisfied eyes",
                "positive_extra": "close-up, lazy grin, arms on counter, messy hair, amber light, satisfied eyes",
                "shot": "close_up",
                "caption": "Best last call she'd ever had.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 4. Pool — midnight swim
    # ------------------------------------------------------------------
    {
        "key": "pool_midnight",
        "titles": ["Night Swim", "Deep End", "After Dark", "Chlorine"],
        "description": "Private pool. Past midnight. She slipped in when no one was looking.",
        "time": "night",
        "location": "pool",
        "furniture": ["poolside lounge chair", "pool edge", "tiled pool deck", "pool ladder", "towel rack"],
        "lighting": ["underwater pool lights blue glow", "moonlight on water surface", "warm poolside lamp", "underwater ripple light patterns"],
        "atmosphere": ["blue", "wet", "moonlit", "reflective"],

        "setup": [
            {
                "scene": "sitting on pool edge, feet dangling in water, bikini, looking up at moon, water ripples reflecting on skin, dark pool area, warm poolside lights, night sky",
                "positive_extra": "pool edge, feet in water, bikini, looking up, water ripples on skin, poolside lights, night sky, moon",
                "shot": "full_body",
                "caption": "The pool was supposed to close at ten. Nobody checked.",
            },
            {
                "scene": "standing in shallow end of pool, water at waist level, arms crossed over chest, wet hair slicked back, underwater lights casting blue glow upward on body, night",
                "positive_extra": "pool, waist-deep water, arms crossed, wet hair slicked, blue underwater light, night, wet skin",
                "shot": "medium",
            },
            {
                "scene": "turning around in pool, hand pushing wet hair back from face, surprised expression turning to smile, water droplets catching light, pool lights below, moonlight above",
                "positive_extra": "turning around, hand in hair, surprised smile, water droplets, pool lights, moonlight, wet",
                "shot": "medium_close",
                "dialogue": "I thought I had the place to myself.",
            },
        ],

        "tension": [
            {
                "scene": "leaning against pool wall, arms resting on pool edge behind her, water at chest level, head tilted back, confident expression, underwater blue light on wet skin, night sky",
                "positive_extra": "against pool wall, arms on edge, water at chest, head back, confident, blue light, wet skin, night",
                "shot": "medium",
                "dialogue": "Water's warm. You should come in.",
            },
            {
                "scene": "emerging from underwater, water streaming off hair and shoulders, eyes closed, mouth slightly open, gasping, underwater lights illuminating water spray around her",
                "positive_extra": "emerging from water, streaming hair, eyes closed, gasping, underwater lights, water spray, dramatic",
                "shot": "medium_close",
            },
            {
                "scene": "floating on back in pool, eyes closed, serene, wet hair fanned out in water, moonlight on wet skin, pool lights casting patterns, bikini",
                "positive_extra": "floating on back, eyes closed, serene, hair fanned, moonlight, wet skin, pool light patterns, bikini",
                "shot": "high_angle",
                "caption": "The water made everything feel weightless.",
            },
            {
                "scene": "pressing against pool tile wall, water at shoulders, looking up at viewer, wet eyelashes, parted lips, water beading on skin, blue underwater glow from below, flushed",
                "positive_extra": "against tile wall, water at shoulders, looking up, wet lashes, parted lips, water beads, blue glow, flushed",
                "shot": "close_up",
                "dialogue": "Don't let me drown.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on poolside lounge chair, wrapped in towel, legs stretched out, wet hair spread on chair, satisfied tired smile, pool glowing blue behind her, night sky, stars",
                "positive_extra": "lounge chair, towel wrapped, wet hair, satisfied smile, pool blue glow, night sky, stars, relaxed",
                "shot": "full_body",
                "dialogue": "We should do laps more often.",
            },
            {
                "scene": "close-up portrait, wet hair clinging to face, water droplets on skin, satisfied lazy half-smile, blue pool light reflected in eyes, night",
                "positive_extra": "close-up, wet hair on face, water droplets, lazy smile, blue pool light in eyes, night",
                "shot": "close_up",
                "caption": "She was never really a morning swimmer anyway.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 5. Balcony — summer heat wave
    # ------------------------------------------------------------------
    {
        "key": "balcony_summer",
        "titles": ["Heat Wave", "Night Air", "Floor Thirty-Two", "August"],
        "description": "Too hot to sleep. Out on the balcony at 2 AM. The neighbor's light is still on.",
        "time": "night",
        "location": "apartment balcony",
        "furniture": ["balcony railing", "patio chair", "small table", "potted plants", "sliding glass door"],
        "lighting": ["city lights below", "warm apartment light from inside", "moonlight", "distant building windows"],
        "atmosphere": ["warm", "summer", "humid", "city"],

        "setup": [
            {
                "scene": "leaning on balcony railing, tank top, shorts, looking out at city skyline at night, warm breeze blowing hair, city lights spread below, sweat on skin, can't sleep",
                "positive_extra": "balcony railing, tank top, shorts, city skyline, night, breeze, hair blowing, city lights, sweat, summer",
                "shot": "medium",
                "caption": "Three AM. Thirty-two degrees. Sleep wasn't happening.",
            },
            {
                "scene": "sitting on balcony floor, back against railing, knees up, holding cold water bottle against neck, eyes closed, relief expression, warm night, apartment building background",
                "positive_extra": "sitting on floor, against railing, knees up, water bottle on neck, eyes closed, relief, warm night, balcony",
                "shot": "full_body",
            },
            {
                "scene": "looking sideways toward neighboring balcony, curious expression, slight smile, hair stuck to neck with sweat, tank top strap falling, warm city night",
                "positive_extra": "looking sideways, curious, slight smile, hair stuck to neck, tank top strap falling, warm night",
                "shot": "medium_close",
                "dialogue": "Can't sleep either?",
            },
        ],

        "tension": [
            {
                "scene": "sitting on balcony railing, legs dangling over edge, leaning back on hands, looking at viewer, confident pose, tank top, city lights spread behind her, warm night wind",
                "positive_extra": "on railing, legs dangling, leaning back, looking at viewer, confident, tank top, city lights, warm wind",
                "shot": "medium",
                "dialogue": "Careful, it's a long way down.",
            },
            {
                "scene": "standing near sliding glass door, silhouetted by apartment light behind, one hand on door frame, body outlined, head tilted, inviting expression, balcony night",
                "positive_extra": "silhouette, apartment light behind, hand on door frame, body outlined, head tilted, inviting, balcony",
                "shot": "full_body",
            },
            {
                "scene": "pulling tank top away from sticky skin, fanning herself, head tilted, playful frustrated expression, sweat glistening, moonlight on shoulders, balcony at night",
                "positive_extra": "pulling tank top, fanning self, head tilted, playful, sweat glistening, moonlight, balcony, hot",
                "shot": "medium_close",
                "dialogue": "It's way too hot for this.",
            },
            {
                "scene": "leaning against balcony railing, arms folded on rail, looking at viewer with half-lidded eyes, flushed from heat, parted lips, sweat on collarbone, city lights bokeh behind",
                "positive_extra": "on railing, arms folded, half-lidded eyes, flushed, parted lips, sweat on collarbone, city bokeh",
                "shot": "close_up",
                "caption": "The night got hotter.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on balcony floor on a spread-out blanket, staring up at night sky, satisfied exhausted smile, hair splayed, city glow on skin, wearing only oversized shirt",
                "positive_extra": "lying on blanket, looking up, satisfied smile, hair splayed, city glow, oversized shirt, balcony floor",
                "shot": "high_angle",
                "dialogue": "I think it finally cooled down.",
            },
            {
                "scene": "close-up portrait, hair stuck to forehead with sweat, lazy blissful smile, city lights reflected in eyes, moonlight on face, glowing",
                "positive_extra": "close-up, hair on forehead, lazy smile, city lights in eyes, moonlight, glowing, blissful",
                "shot": "close_up",
                "caption": "She slept through her alarm. Worth it.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 6. Cabin — snowed in
    # ------------------------------------------------------------------
    {
        "key": "cabin_snowed",
        "titles": ["Snowed In", "Cabin Fever", "White Out", "Kindling"],
        "description": "Mountain cabin. Blizzard outside. The power's out but the fireplace works.",
        "time": "night",
        "location": "cabin",
        "furniture": ["stone fireplace", "fur rug", "wooden floor", "leather couch", "log wall"],
        "lighting": ["warm fireplace glow", "flickering firelight", "orange ember light", "candlelight"],
        "atmosphere": ["warm", "cozy", "isolated", "firelit"],

        "setup": [
            {
                "scene": "sitting on floor in front of fireplace, wrapped in thick blanket, knees to chest, firelight on face, log cabin interior, snow visible through small window, warm orange glow",
                "positive_extra": "fireplace, blanket, knees to chest, firelight, log cabin, snow window, orange glow, cozy",
                "shot": "medium",
                "caption": "The roads closed two hours ago. The fire was the only light left.",
            },
            {
                "scene": "standing by cabin window, looking out at snowstorm, hand on cold glass, breath fogging window, blanket wrapped around shoulders, firelight behind her, dark outside",
                "positive_extra": "cabin window, snowstorm outside, hand on glass, breath fog, blanket, firelight behind, dark",
                "shot": "medium_close",
            },
            {
                "scene": "turning away from window toward fireplace, slight smile, shivering, pulling blanket tighter, fireplace glow warming her face, cabin interior",
                "positive_extra": "turning from window, smile, shivering, blanket tight, fireplace glow, warm face, cabin",
                "shot": "medium",
                "dialogue": "Looks like we're stuck here tonight.",
            },
        ],

        "tension": [
            {
                "scene": "lying on fur rug in front of fireplace, propped up on elbows, blanket sliding off, firelight dancing on skin, looking up at viewer, warm smile",
                "positive_extra": "fur rug, fireplace, propped on elbows, blanket sliding, firelight on skin, looking up, warm smile",
                "shot": "medium",
                "dialogue": "Come warm up. It's freezing over there.",
            },
            {
                "scene": "sitting on leather couch, legs tucked, holding steaming mug with both hands, looking over mug at viewer, playful eyes, fire crackling in background",
                "positive_extra": "couch, legs tucked, steaming mug, looking over, playful eyes, fire crackling, cabin",
                "shot": "medium_close",
            },
            {
                "scene": "standing by fireplace, blanket dropped to floor, arms stretched above fire, back to viewer, firelight outlining body, warm orange glow, log wall behind",
                "positive_extra": "by fireplace, blanket dropped, arms stretched, back to viewer, firelight outline, warm glow, cabin",
                "shot": "full_body",
                "caption": "The cabin was small. There was nowhere to hide.",
            },
            {
                "scene": "lying on fur rug, firelight flickering on face, flushed cheeks, parted lips, one hand reaching toward viewer, blanket barely covering, eyes half-lidded, warm",
                "positive_extra": "fur rug, firelight on face, flushed, parted lips, reaching hand, blanket barely covering, half-lidded, warm",
                "shot": "close_up",
                "dialogue": "I don't think it's the fire making me warm.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on fur rug wrapped in blanket with another person, only her face visible, nose peeking out, content smile, dying embers in fireplace, cabin at night, snow outside",
                "positive_extra": "fur rug, blanket wrap, face peeking, content smile, dying embers, fireplace, cabin, snow",
                "shot": "medium",
                "dialogue": "Hope the roads stay closed tomorrow too.",
            },
            {
                "scene": "close-up portrait, firelight glow on half of face, sleepy satisfied expression, messy hair, warm tones, embers reflecting in eyes",
                "positive_extra": "close-up, firelight on face, sleepy, satisfied, messy hair, warm, embers in eyes",
                "shot": "close_up",
                "caption": "They didn't need the roads.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 7. Photography studio — after the shoot
    # ------------------------------------------------------------------
    {
        "key": "photography_studio",
        "titles": ["Golden Hour", "One More Shot", "Exposure", "Off Camera"],
        "description": "Late photo shoot. The crew left. The photographer stayed for one more roll.",
        "time": "evening",
        "location": "photography studio",
        "furniture": ["photography backdrop", "studio light softbox", "posing stool", "camera on tripod", "reflector panel"],
        "lighting": ["studio softbox light", "warm modeling light", "rim light from behind", "dramatic side light"],
        "atmosphere": ["professional", "warm", "focused", "intimate"],

        "setup": [
            {
                "scene": "sitting on posing stool in photography studio, one leg up, relaxed between shots, studio lights still on, white backdrop behind, casual confident expression, rubbing neck",
                "positive_extra": "posing stool, studio, studio lights, white backdrop, relaxed, casual confident, rubbing neck",
                "shot": "medium",
                "caption": "Everyone else packed up an hour ago. She had one more look.",
            },
            {
                "scene": "standing in front of studio backdrop, adjusting hair, camera on tripod in foreground, softbox light creating warm glow, professional studio setting",
                "positive_extra": "studio backdrop, adjusting hair, camera tripod foreground, softbox warm glow, professional studio",
                "shot": "full_body",
            },
            {
                "scene": "looking directly into camera lens close-up, studio lighting, piercing confident eyes, slight knowing smile, rim light highlighting hair edge, professional but intimate",
                "positive_extra": "looking at camera, studio light, piercing eyes, knowing smile, rim light on hair, professional, intimate",
                "shot": "close_up",
                "dialogue": "One more? Or are you just stalling?",
            },
        ],

        "tension": [
            {
                "scene": "sitting backwards on posing stool, arms draped over back, chin on arms, looking up through lashes, studio light creating dramatic shadow, teasing expression",
                "positive_extra": "backwards on stool, arms draped, chin on arms, looking up, dramatic shadow, teasing, studio",
                "shot": "medium",
                "dialogue": "Tell me how you want me.",
            },
            {
                "scene": "stretching against studio wall, arms above head, back arched, studio lights catching every contour, eyes closed, head tilted back, dramatic side lighting",
                "positive_extra": "against wall, arms up, back arched, studio lights, eyes closed, head back, side lighting, dramatic",
                "shot": "full_body",
            },
            {
                "scene": "leaning toward camera, hand reaching toward lens, playful daring expression, shallow depth of field, studio backdrop blurred, warm modeling light",
                "positive_extra": "leaning toward camera, hand reaching, daring, shallow depth, backdrop blur, modeling light",
                "shot": "medium_close",
                "caption": "She wasn't posing anymore.",
            },
            {
                "scene": "close-up, looking at viewer with parted lips, studio rim light creating halo around hair, flushed skin, intense eyes, professional lighting but raw expression",
                "positive_extra": "close-up, parted lips, rim light halo, flushed, intense eyes, professional light, raw expression",
                "shot": "close_up",
                "dialogue": "The camera's off now.",
            },
        ],

        "aftermath": [
            {
                "scene": "sitting on studio floor, wearing photographer's flannel shirt, legs stretched out, leaning back on hands, studio lights still on, equipment around, lazy satisfied grin",
                "positive_extra": "studio floor, flannel shirt, legs out, leaning back, studio lights, equipment, lazy grin, satisfied",
                "shot": "full_body",
                "dialogue": "Did you at least get a good shot?",
            },
            {
                "scene": "close-up portrait, tousled hair, warm studio light, satisfied half-smile, camera strap visible on bare shoulder, afterglow",
                "positive_extra": "close-up, tousled hair, warm light, satisfied smile, camera strap on shoulder, afterglow",
                "shot": "close_up",
                "caption": "Best shoot of her career.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 8. Laundromat — midnight spin
    # ------------------------------------------------------------------
    {
        "key": "laundromat_late",
        "titles": ["Spin Cycle", "Tumble Dry", "Lost Socks", "Midnight Wash"],
        "description": "Middle of the night at the 24-hour laundromat. Just her and the machines.",
        "time": "night",
        "location": "laundromat",
        "furniture": ["washing machine", "dryer", "folding table", "plastic bench", "vending machine"],
        "lighting": ["harsh fluorescent overhead", "warm dryer glow through door", "vending machine light", "neon OPEN sign"],
        "atmosphere": ["fluorescent", "mundane", "empty", "humming"],

        "setup": [
            {
                "scene": "sitting on top of washing machine, legs swinging, oversized hoodie, shorts, earbuds in, looking bored, laundromat at night, fluorescent lights, row of machines, empty",
                "positive_extra": "on washing machine, legs swinging, hoodie, shorts, earbuds, bored, laundromat, fluorescent, night, empty",
                "shot": "medium",
                "caption": "2 AM. Her only company was the spin cycle.",
            },
            {
                "scene": "standing in front of dryer, watching clothes tumble through round glass door, face lit by warm dryer light, hands in hoodie pockets, laundromat background",
                "positive_extra": "front of dryer, watching clothes, dryer light on face, hands in pockets, hoodie, laundromat",
                "shot": "medium_close",
            },
            {
                "scene": "looking up from phone, surprised, slight smile, sitting on plastic bench in laundromat, fluorescent light above, washing machines humming behind her",
                "positive_extra": "looking up from phone, surprised, smile, plastic bench, fluorescent, washing machines, laundromat",
                "shot": "close_up",
                "dialogue": "Are any of these machines actually free?",
            },
        ],

        "tension": [
            {
                "scene": "hopping off washing machine, landing with bounce, hoodie riding up showing stomach, playful expression, laundromat aisle, fluorescent light, vending machine in background",
                "positive_extra": "hopping off machine, hoodie riding up, stomach, playful, laundromat aisle, fluorescent, vending machine",
                "shot": "full_body",
                "dialogue": "You could just wait. I'm almost done.",
            },
            {
                "scene": "leaning against row of washing machines, arms behind on machine top, relaxed confident pose, hoodie unzipped, laundromat, warm and cool light mixing",
                "positive_extra": "leaning on machines, arms behind, confident, hoodie unzipped, laundromat, mixed lighting",
                "shot": "medium",
            },
            {
                "scene": "pulling warm towel from dryer, pressing it against face, eyes closed, blissful expression, warm dryer light, steam rising, laundromat at night",
                "positive_extra": "warm towel, pressing face, eyes closed, blissful, dryer light, steam, laundromat, night",
                "shot": "medium_close",
                "dialogue": "Mmm... this is the best part.",
            },
            {
                "scene": "sitting on folding table, legs dangling, leaning forward, looking at viewer with half-lidded eyes, flushed, fluorescent and dryer light mixing, laundromat late night",
                "positive_extra": "folding table, legs dangling, leaning forward, half-lidded, flushed, mixed light, laundromat, night",
                "shot": "close_up",
                "caption": "The dryer wasn't the only thing warming up.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on folding table in laundromat, wearing his oversized t-shirt, hugging warm bundle of laundry, satisfied tired smile, fluorescent light above, machines idle",
                "positive_extra": "folding table, oversized shirt, hugging laundry, satisfied smile, fluorescent, machines idle",
                "shot": "full_body",
                "dialogue": "I think your clothes are done.",
            },
            {
                "scene": "close-up portrait, messy hair, warm flushed cheeks, lazy grin, fluorescent light overhead creating slight halo, dryer humming in background",
                "positive_extra": "close-up, messy hair, flushed, lazy grin, fluorescent halo, dryer humming",
                "shot": "close_up",
                "caption": "Laundry night was never this fun.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 9. Beach bonfire — embers
    # ------------------------------------------------------------------
    {
        "key": "beach_bonfire",
        "titles": ["Embers", "Low Tide", "Smoke and Salt", "Driftwood"],
        "description": "Beach party died down. Bonfire's still going. Everyone else headed back.",
        "time": "night",
        "location": "beach",
        "furniture": ["driftwood log", "beach towel on sand", "bonfire pit", "cooler", "sand dune"],
        "lighting": ["bonfire warm ember glow", "moonlight on ocean", "dying fire orange light", "starlight"],
        "atmosphere": ["warm", "sandy", "salty", "peaceful"],

        "setup": [
            {
                "scene": "sitting on driftwood log by dying bonfire, knees drawn up, oversized beach hoodie, toes buried in sand, staring at embers, ocean waves in background, moonlight on water, night",
                "positive_extra": "driftwood log, bonfire, knees up, hoodie, toes in sand, embers, ocean, moonlight, night",
                "shot": "medium",
                "caption": "The last car pulled out of the lot an hour ago. She stayed for the embers.",
            },
            {
                "scene": "standing at water's edge, waves washing over bare feet, looking out at moonlit ocean, beach hoodie, wind in hair, bonfire glow behind her, night sky full of stars",
                "positive_extra": "water edge, waves on feet, moonlit ocean, hoodie, wind hair, bonfire glow behind, stars, night",
                "shot": "full_body",
            },
            {
                "scene": "looking back over shoulder from waterline toward bonfire, hair blowing across face, surprised then pleased expression, moonlight on wet sand, warm fire glow in distance",
                "positive_extra": "looking back, hair blowing, surprised pleased, moonlight, wet sand, fire glow distant",
                "shot": "medium_close",
                "dialogue": "Thought I was the only one still out here.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on beach towel near bonfire, hugging knees, looking sideways at viewer, firelight flickering on face, sandy skin, beach hoodie sliding off one shoulder, ocean behind",
                "positive_extra": "beach towel, bonfire, hugging knees, looking sideways, firelight, sandy skin, hoodie off shoulder, ocean",
                "shot": "medium",
                "dialogue": "Stay. The fire's still warm.",
            },
            {
                "scene": "standing up from driftwood log, stretching arms above head, back arched, hoodie riding up, bonfire behind, moonlit beach, wind catching hair",
                "positive_extra": "stretching, arms up, back arched, hoodie riding up, bonfire behind, moonlit beach, wind, hair",
                "shot": "full_body",
            },
            {
                "scene": "lying on side on beach towel, propped on elbow, tracing patterns in sand with finger, looking up with teasing half-smile, bonfire warm glow on skin, sand on arms",
                "positive_extra": "lying on side, elbow propped, tracing sand, looking up, half-smile, fire glow on skin, sand on arms",
                "shot": "medium",
                "caption": "The tide was coming in. Neither of them moved.",
            },
            {
                "scene": "close-up face by bonfire, ember glow on one cheek, eyes catching firelight, parted lips, sand on cheekbone, wind-tousled hair, looking at viewer, warm",
                "positive_extra": "close-up, ember glow, eyes catching fire, parted lips, sand on cheek, wind hair, warm",
                "shot": "close_up",
                "dialogue": "The water's cold. Warm me up.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on beach towel, arms spread, staring up at stars, sand everywhere, bonfire reduced to coals, satisfied exhausted expression, ocean waves in background, moonlight",
                "positive_extra": "beach towel, arms spread, staring at stars, sand, coals, satisfied, ocean waves, moonlight",
                "shot": "high_angle",
                "dialogue": "I've got sand in places I didn't know existed.",
            },
            {
                "scene": "close-up portrait, sand in hair, salt on lips, lazy satisfied smile, moonlight on face, bonfire ember glow, stars blurred behind",
                "positive_extra": "close-up, sand in hair, salt lips, lazy smile, moonlight, ember glow, stars blur",
                "shot": "close_up",
                "caption": "Best bonfire of the summer.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 10. Greenhouse — evening
    # ------------------------------------------------------------------
    {
        "key": "greenhouse_evening",
        "titles": ["Bloom", "Glass House", "Overgrown", "Humid"],
        "description": "Private greenhouse at dusk. Warm, humid, surrounded by green.",
        "time": "evening",
        "location": "greenhouse",
        "furniture": ["wooden potting bench", "stone path", "hanging plants", "garden chair", "glass wall panels"],
        "lighting": ["warm golden sunset through glass", "string fairy lights in plants", "green filtered light", "warm grow lamp"],
        "atmosphere": ["humid", "lush", "warm", "green"],

        "setup": [
            {
                "scene": "standing in greenhouse, watering can in hand, surrounded by tropical plants, sundress, golden sunset light filtering through glass walls, humid air visible, lush green everywhere",
                "positive_extra": "greenhouse, watering can, tropical plants, sundress, golden sunset, glass walls, humid, lush green",
                "shot": "full_body",
                "caption": "Her favorite place was the one nobody else knew about.",
            },
            {
                "scene": "leaning close to examine a flower, face near blooming orchid, eyes soft, gentle expression, warm light through glass, plants framing her, greenhouse humidity on skin",
                "positive_extra": "examining flower, orchid, soft eyes, gentle, warm light, plants framing, humidity on skin, greenhouse",
                "shot": "medium_close",
            },
            {
                "scene": "looking up from behind large tropical leaf, peering through foliage, amused surprised expression, dappled green light on skin, greenhouse glass above",
                "positive_extra": "behind leaf, peering through foliage, amused surprised, dappled green light, greenhouse glass",
                "shot": "close_up",
                "dialogue": "You found the secret garden.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on wooden potting bench, legs crossed, hands gripping bench edge, head tilted, confident smile, hanging plants around, warm light, humid skin glistening",
                "positive_extra": "potting bench, legs crossed, gripping edge, head tilted, confident, hanging plants, warm light, glistening",
                "shot": "medium",
                "dialogue": "Careful. Everything in here is... delicate.",
            },
            {
                "scene": "standing between rows of tall plants, one hand trailing along leaves, looking over shoulder, sundress strap falling, warm humid air, golden light",
                "positive_extra": "between plants, hand trailing leaves, looking over shoulder, strap falling, humid, golden light",
                "shot": "full_body",
            },
            {
                "scene": "pressing back against glass wall of greenhouse, condensation on glass behind her, flushed from humidity, parted lips, green plants on either side, warm diffused light",
                "positive_extra": "against glass wall, condensation, flushed, humid, parted lips, green plants, warm diffused light",
                "shot": "medium_close",
                "caption": "The humidity made everything feel close.",
            },
            {
                "scene": "close-up, dewdrops on skin from humidity, flushed cheeks, half-lidded eyes, lip bitten, tropical leaf partially obscuring view, warm golden greenhouse light",
                "positive_extra": "close-up, dewdrops on skin, flushed, half-lidded, lip bitten, leaf partially hiding, warm golden light",
                "shot": "close_up",
                "dialogue": "It's not just the greenhouse that's hot.",
            },
        ],

        "aftermath": [
            {
                "scene": "sitting on greenhouse floor, back against potting bench, surrounded by knocked-over plant pots, dirt on knees, satisfied breathless smile, fairy lights above, warm evening",
                "positive_extra": "greenhouse floor, against bench, knocked pots, dirt on knees, breathless smile, fairy lights, warm",
                "shot": "full_body",
                "dialogue": "I think we need to repot a few things.",
            },
            {
                "scene": "close-up portrait, flower petal stuck in messy hair, dewy skin, satisfied warm expression, green blurred background, golden light fading",
                "positive_extra": "close-up, petal in hair, dewy skin, satisfied, green blur, golden light",
                "shot": "close_up",
                "caption": "The rarest bloom of all.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 11. Penthouse — skyline view
    # ------------------------------------------------------------------
    {
        "key": "penthouse_view",
        "titles": ["Skyline", "Top Floor", "Penthouse Suite", "City Below"],
        "description": "Private penthouse. Floor-to-ceiling windows. The city has no idea.",
        "time": "night",
        "location": "penthouse",
        "furniture": ["floor-to-ceiling window", "modern sofa", "marble counter", "glass coffee table", "minimalist art"],
        "lighting": ["city lights through windows", "dim modern accent light", "moonlight through glass", "warm ambient LED"],
        "atmosphere": ["luxurious", "modern", "city", "private"],

        "setup": [
            {
                "scene": "standing at floor-to-ceiling window in penthouse, one hand on glass, looking out at city skyline at night, elegant cocktail dress, city lights reflected on her and the glass, modern luxury interior",
                "positive_extra": "floor-to-ceiling window, penthouse, hand on glass, city skyline, night, cocktail dress, city lights reflected, luxury",
                "shot": "full_body",
                "caption": "Fifty floors up. Nobody could see in. That was the point.",
            },
            {
                "scene": "sitting on modern sofa, one leg crossed over other, holding champagne glass, city skyline through massive windows behind, dim ambient lighting, elegant, poised",
                "positive_extra": "modern sofa, legs crossed, champagne glass, city skyline window, ambient light, elegant, poised",
                "shot": "medium",
            },
            {
                "scene": "turning from window, champagne glass dangling from fingers, knowing smile, city lights creating silhouette, penthouse interior, luxury modern",
                "positive_extra": "turning from window, champagne, knowing smile, city light silhouette, penthouse, luxury",
                "shot": "medium_close",
                "dialogue": "The view from up here is... something.",
            },
        ],

        "tension": [
            {
                "scene": "leaning against window, glass cold on bare back, looking at viewer, champagne glass held to lips, city lights behind, dress strap hanging, penthouse night",
                "positive_extra": "against window, glass on back, looking at viewer, champagne to lips, city lights, dress strap, penthouse",
                "shot": "medium",
                "dialogue": "You came for the view. Didn't you?",
            },
            {
                "scene": "sitting on marble kitchen counter, legs dangling, heels kicked off on floor below, leaning back on hands, head tilted, city lights through window, penthouse",
                "positive_extra": "marble counter, legs dangling, heels on floor, leaning back, head tilted, city lights, penthouse",
                "shot": "full_body",
            },
            {
                "scene": "standing silhouetted against floor-to-ceiling window, city lights behind, reaching back to unzip dress, looking over shoulder at viewer, dramatic city skyline",
                "positive_extra": "silhouette, window, city lights, reaching back, unzip, looking over shoulder, dramatic skyline",
                "shot": "full_body",
                "caption": "The city was watching. She didn't care.",
            },
            {
                "scene": "close-up, pressing forehead against cold window glass, breath fogging glass, city lights blurred behind, half-lidded eyes, flushed, parted lips, looking at viewer",
                "positive_extra": "close-up, forehead on glass, breath fog, city blur, half-lidded, flushed, parted lips",
                "shot": "close_up",
                "dialogue": "Don't make me wait.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on modern sofa wrapped in throw blanket, city skyline through window, satisfied expression, hair messy, bare shoulders, one arm trailing to floor, holding empty champagne glass",
                "positive_extra": "sofa, blanket, city skyline window, satisfied, messy hair, bare shoulders, champagne glass trailing",
                "shot": "medium",
                "dialogue": "We fogged up every window in here.",
            },
            {
                "scene": "close-up portrait, city lights reflected in eyes, lazy satisfied smile, messy hair across face, warm skin tone, modern penthouse blurred behind",
                "positive_extra": "close-up, city lights in eyes, lazy smile, messy hair, warm skin, penthouse blur",
                "shot": "close_up",
                "caption": "The penthouse was worth every penny.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 12. Wine cellar — private tasting
    # ------------------------------------------------------------------
    {
        "key": "wine_cellar",
        "titles": ["Vintage", "Cellared", "Notes of Oak", "Decanted"],
        "description": "Down in the wine cellar. Stone walls. One bottle open. Door at the top of the stairs.",
        "time": "evening",
        "location": "wine cellar",
        "furniture": ["stone wall", "wine barrel", "wooden rack of bottles", "small tasting table", "stone steps"],
        "lighting": ["warm amber wall sconce", "candlelight on table", "single overhead bulb", "warm dim amber glow"],
        "atmosphere": ["intimate", "stone", "amber", "underground"],

        "setup": [
            {
                "scene": "standing in wine cellar, holding wine glass up to candlelight, examining color, stone walls and wine racks behind, warm amber light, elegant, refined expression",
                "positive_extra": "wine cellar, wine glass, candlelight, examining, stone walls, wine racks, amber light, elegant",
                "shot": "medium",
                "caption": "Three floors below the restaurant. Just her and the 2003 Bordeaux.",
            },
            {
                "scene": "trailing finger along dusty wine bottles on rack, looking for a label, candlelight flickering, stone cellar walls, low ceiling, intimate space",
                "positive_extra": "finger on bottles, wine rack, searching label, candlelight, stone walls, cellar, intimate",
                "shot": "medium_close",
            },
            {
                "scene": "looking up from wine glass with slight surprise, amber liquid catching light, candlelit face, warm smile, someone came down the stairs, wine cellar",
                "positive_extra": "looking up, surprise, wine glass, amber light, candlelit face, warm smile, wine cellar",
                "shot": "close_up",
                "dialogue": "I found something you should try.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on wine barrel, legs crossed, holding glass, looking over rim at viewer, candlelight catching eyes, stone wall behind, intimate amber atmosphere",
                "positive_extra": "wine barrel, legs crossed, glass, looking over rim, candlelight in eyes, stone wall, amber, intimate",
                "shot": "medium",
                "dialogue": "This one has notes of something... dangerous.",
            },
            {
                "scene": "leaning against stone wall between wine racks, wine glass held loosely, head tilted back against stone, exposed neck, candlelight on skin, relaxed, warm",
                "positive_extra": "stone wall, wine racks, glass loosely held, head back, neck exposed, candlelight on skin, warm",
                "shot": "medium_close",
            },
            {
                "scene": "pressing back against wine barrel, gripping edge, parted lips stained with wine, candlelight creating dramatic shadows, flushed cheeks, looking at viewer",
                "positive_extra": "against barrel, gripping edge, wine-stained lips, dramatic candlelight shadows, flushed, looking at viewer",
                "shot": "close_up",
                "caption": "The wine was intoxicating. The cellar was worse.",
            },
            {
                "scene": "close-up, wine droplet on lower lip, tongue catching it, half-lidded eyes, candlelight warm on face, stone cellar out of focus behind, flushed",
                "positive_extra": "close-up, wine on lip, tongue, half-lidded, candlelight, warm face, cellar blur, flushed",
                "shot": "close_up",
                "dialogue": "I think we should finish the bottle.",
            },
        ],

        "aftermath": [
            {
                "scene": "sitting on stone cellar floor, back against wine barrel, empty wine bottle beside her, satisfied dreamy smile, hair messed up, candlelight low, warm amber everywhere",
                "positive_extra": "cellar floor, against barrel, empty bottle, dreamy smile, messy hair, low candle, warm amber",
                "shot": "full_body",
                "dialogue": "That was a really good year.",
            },
            {
                "scene": "close-up portrait, wine-flushed cheeks, lazy content smile, candlelight dancing in eyes, hair falling across face, warm stone background",
                "positive_extra": "close-up, wine flush, content smile, candlelight in eyes, hair across face, warm stone",
                "shot": "close_up",
                "caption": "Some bottles are worth opening only once.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 13. Arcade — closing time
    # ------------------------------------------------------------------
    {
        "key": "arcade_closing",
        "titles": ["Continue?", "Game Over", "Insert Coin", "High Score"],
        "description": "Arcade's closing down. Neon glow. She's still trying to beat the high score.",
        "time": "night",
        "location": "arcade",
        "furniture": ["arcade cabinet", "neon-lit floor", "prize counter", "racing seat game", "claw machine"],
        "lighting": ["neon game screen glow", "colorful LED strips", "dark with neon accents", "game screen light on face"],
        "atmosphere": ["neon", "dark", "retro", "glowing"],

        "setup": [
            {
                "scene": "standing at arcade cabinet, hands on controls, screen glow lighting face in blue and pink, intense focused expression, dark arcade around, neon lights, cropped top",
                "positive_extra": "arcade cabinet, hands on controls, screen glow blue pink, focused, dark arcade, neon, cropped top",
                "shot": "medium",
                "caption": "The 'CLOSING' sign was flashing. She had one life left.",
            },
            {
                "scene": "leaning against dark arcade cabinet, arms crossed, neon lights reflecting off skin, colorful glow, surrounded by game screens in dark room, casual smirk",
                "positive_extra": "against arcade cabinet, arms crossed, neon reflections, colorful glow, dark room, game screens, smirk",
                "shot": "medium_close",
            },
            {
                "scene": "looking up from game screen, face half-lit by neon blue, surprised then playful expression, dark arcade, LED strip lights on ceiling, game sounds",
                "positive_extra": "looking up, half-lit neon blue, surprised playful, dark arcade, LED strips",
                "shot": "close_up",
                "dialogue": "Wanna go two-player?",
            },
        ],

        "tension": [
            {
                "scene": "sitting on racing game seat, legs up on dashboard, leaning back, holding joystick loosely, neon washing over body in shifting colors, dark arcade, teasing expression",
                "positive_extra": "racing seat, legs up, leaning back, joystick, neon colors shifting, dark, teasing",
                "shot": "medium",
                "dialogue": "Winner gets to pick the prize.",
            },
            {
                "scene": "standing between two dark arcade cabinets, hands braced on either side, leaning forward, neon purple and blue lighting from both sides, confident pose",
                "positive_extra": "between cabinets, hands braced, leaning forward, neon purple blue, both sides lit, confident",
                "shot": "full_body",
            },
            {
                "scene": "sitting on arcade cabinet top, legs dangling, kicking heels against machine, neon glow from below, mischievous grin, dark arcade background",
                "positive_extra": "on cabinet top, legs dangling, kicking, neon glow below, mischievous grin, dark",
                "shot": "medium",
                "caption": "She was done playing games. Kind of.",
            },
            {
                "scene": "close-up face lit by game screen, shifting neon colors on skin, parted lips, intense eyes, looking at viewer, dark background, pink and cyan reflections",
                "positive_extra": "close-up, game screen light, neon on skin, parted lips, intense eyes, dark, pink cyan reflections",
                "shot": "close_up",
                "dialogue": "Game over means something different here.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on arcade floor between machines, neon glow from all sides, holding stuffed prize from claw machine, satisfied exhausted grin, hair spread on floor, dark",
                "positive_extra": "arcade floor, between machines, neon glow, stuffed prize, exhausted grin, hair spread, dark",
                "shot": "high_angle",
                "dialogue": "That was the real bonus round.",
            },
            {
                "scene": "close-up portrait, neon pink and blue glow on face, lazy satisfied smile, messy hair, game screen reflecting in eyes, dark",
                "positive_extra": "close-up, neon pink blue, lazy smile, messy hair, game screen in eyes, dark",
                "shot": "close_up",
                "caption": "New high score.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 14. Music studio — late session
    # ------------------------------------------------------------------
    {
        "key": "music_studio",
        "titles": ["One More Take", "After Hours Mix", "Soundproof", "B-Side"],
        "description": "Recording studio. Late session. The engineer went home. She's still behind the glass.",
        "time": "night",
        "location": "recording studio",
        "furniture": ["mixing console", "studio monitor speakers", "microphone on stand", "sound-dampened wall", "leather studio couch"],
        "lighting": ["dim control room LED", "warm vocal booth light", "console button lights", "mood lighting strips"],
        "atmosphere": ["soundproof", "intimate", "warm", "isolated"],

        "setup": [
            {
                "scene": "sitting at mixing console in recording studio, headphones around neck, chin on hand, LED buttons glowing in dark room, studio monitors flanking, tired but creative expression",
                "positive_extra": "mixing console, headphones, chin on hand, LED glow, dark studio, monitors, tired creative",
                "shot": "medium",
                "caption": "The session was supposed to end at midnight. It was almost three.",
            },
            {
                "scene": "standing behind microphone in vocal booth, headphones on, eyes closed, one hand on headphone, warm booth light, sound-dampened walls, singing expression, passionate",
                "positive_extra": "vocal booth, microphone, headphones, eyes closed, warm light, sound dampened, passionate, singing",
                "shot": "medium_close",
            },
            {
                "scene": "pulling off headphones, looking through studio glass partition, surprised smile, messy hair from headphones, dim studio control room on other side",
                "positive_extra": "pulling off headphones, looking through glass, surprised smile, messy hair, dim control room",
                "shot": "close_up",
                "dialogue": "I thought I was the only one still here.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on leather studio couch, legs pulled up, holding headphones in lap, dim LED strips casting warm light, looking at viewer with direct gaze, soundproof room",
                "positive_extra": "studio couch, legs up, headphones in lap, LED strips, direct gaze, soundproof room",
                "shot": "medium",
                "dialogue": "Wanna hear something I've been working on?",
            },
            {
                "scene": "leaning against mixing console, hip against edge, arms crossed, console LEDs glowing behind, backlit silhouette, confident head tilt, studio dark around",
                "positive_extra": "against console, hip on edge, arms crossed, console LED glow, backlit, head tilt, dark studio",
                "shot": "medium_close",
            },
            {
                "scene": "lying on leather studio couch, one arm above head, other hand playing with headphone cord, looking at ceiling, relaxed vulnerable pose, warm dim studio light",
                "positive_extra": "studio couch, arm above head, playing with cord, looking up, relaxed, warm dim light",
                "shot": "medium",
                "caption": "The room was soundproof. Nobody would hear anything.",
            },
            {
                "scene": "close-up face in dim studio light, LED reflections in eyes like colored stars, parted lips close to microphone, intimate, warm breath on mic, flushed",
                "positive_extra": "close-up, dim light, LED in eyes, parted lips, microphone close, intimate, warm breath, flushed",
                "shot": "close_up",
                "dialogue": "The mic's still hot.",
            },
        ],

        "aftermath": [
            {
                "scene": "sprawled on leather studio couch, wearing headphones on chest, satisfied exhausted smile, console LEDs still blinking, dim warm studio, messy hair",
                "positive_extra": "studio couch, headphones on chest, satisfied, console LEDs, dim warm, messy hair",
                "shot": "full_body",
                "dialogue": "That was better than any take we got tonight.",
            },
            {
                "scene": "close-up portrait, headphone mark on one cheek, lazy blissful smile, console lights reflecting, warm studio glow, hair everywhere",
                "positive_extra": "close-up, headphone mark, blissful smile, console lights, warm glow, messy hair",
                "shot": "close_up",
                "caption": "Best session she ever had.",
            },
        ],
    },

    # ------------------------------------------------------------------
    # 15. Art studio — late night
    # ------------------------------------------------------------------
    {
        "key": "art_studio",
        "titles": ["Life Study", "Wet Paint", "Canvas", "After the Model Left"],
        "description": "Art studio. Canvases everywhere. Paint on her hands. The muse showed up late.",
        "time": "night",
        "location": "art studio",
        "furniture": ["wooden easel", "paint-stained table", "drop cloth on floor", "worn velvet chaise", "cluttered supply shelf"],
        "lighting": ["warm track lighting", "north-facing skylight moonlight", "clip lamp on easel", "warm incandescent overhead"],
        "atmosphere": ["creative", "messy", "warm", "paint-scented"],

        "setup": [
            {
                "scene": "standing at easel in art studio, paintbrush in mouth, squinting at canvas, paint smudges on forearms and cheek, messy bun, tank top with paint stains, warm track lighting, canvases leaning against walls",
                "positive_extra": "easel, paintbrush in mouth, squinting, paint on arms, messy bun, paint-stained tank top, track lighting, canvases on walls",
                "shot": "medium",
                "caption": "She painted better when nobody was watching. Usually.",
            },
            {
                "scene": "mixing paint on palette, focused downward gaze, paint-stained fingers, warm light from clip lamp, art studio mess around, brushes in jars, half-finished canvases",
                "positive_extra": "palette, mixing paint, focused, paint-stained fingers, clip lamp, art mess, brushes, canvases",
                "shot": "medium_close",
            },
            {
                "scene": "looking up from canvas, paintbrush still raised, surprised warm expression, paint smudge on nose, art studio, warm light, someone entering the studio doorway",
                "positive_extra": "looking up, paintbrush raised, surprised warm, paint on nose, art studio, warm light",
                "shot": "close_up",
                "dialogue": "You're late. I already started without you.",
            },
        ],

        "tension": [
            {
                "scene": "sitting on velvet chaise in art studio, legs to one side, holding paint palette like a prop, teasing expression, paint on collarbone, warm studio light, canvases behind",
                "positive_extra": "velvet chaise, palette, teasing, paint on collarbone, warm light, canvases, art studio",
                "shot": "medium",
                "dialogue": "I need a reference for this pose. Hold still.",
            },
            {
                "scene": "standing near easel, pulling tank top strap to show paint trail down shoulder, looking sideways at viewer, messy artist aesthetic, warm incandescent light, paint everywhere",
                "positive_extra": "near easel, pulling strap, paint on shoulder, looking sideways, messy, warm incandescent, paint",
                "shot": "medium_close",
            },
            {
                "scene": "pressing paint-stained hand against viewer's chest (implied), looking up, daring smirk, paint smeared on her arms and face, warm studio light, drop cloth on floor",
                "positive_extra": "paint-stained hand, looking up, daring smirk, paint on arms, warm studio, drop cloth",
                "shot": "close_up",
                "caption": "She always made a mess. That was the art.",
            },
            {
                "scene": "close-up face, paint smudged across cheekbone, parted lips, half-lidded eyes, warm light catching paint on skin like color accents, flushed under the paint",
                "positive_extra": "close-up, paint on cheek, parted lips, half-lidded, warm light, paint accents on skin, flushed",
                "shot": "close_up",
                "dialogue": "You're going to ruin the canvas.",
            },
        ],

        "aftermath": [
            {
                "scene": "lying on paint-stained drop cloth on studio floor, paint handprints and smears everywhere, satisfied breathless laugh, messy hair with paint streaks, warm light, canvases around",
                "positive_extra": "drop cloth, paint smears, handprints, breathless laugh, paint in hair, warm light, canvases, studio floor",
                "shot": "high_angle",
                "dialogue": "That was... abstract expressionism?",
            },
            {
                "scene": "close-up portrait, rainbow paint smeared across face like war paint, satisfied wild grin, messy paint-streaked hair, warm studio glow, creative chaos",
                "positive_extra": "close-up, rainbow paint on face, wild grin, paint in hair, warm glow, creative chaos",
                "shot": "close_up",
                "caption": "Her best work. Not on the canvas.",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Environment panel generator (for LoRA pages — environment only)
# ---------------------------------------------------------------------------

def _make_env_panels(setting: dict, count: int) -> list:
    """Generate environment-only panels for LoRA-driven pages.

    These contain ONLY location/furniture/lighting — no character actions.
    The scene LoRA activation text drives the actual content.
    """
    furniture = list(setting["furniture"])
    lighting = list(setting["lighting"])
    atmosphere = setting.get("atmosphere", ["warm"])
    location = setting["location"]
    time = setting["time"]

    random.shuffle(furniture)
    random.shuffle(lighting)

    shots = ["medium", "close_up", "medium_close"]
    panels = []

    for i in range(count):
        f1 = furniture[i % len(furniture)]
        f2 = furniture[(i + 1) % len(furniture)]
        lit = lighting[i % len(lighting)]
        atm = atmosphere[i % len(atmosphere)]

        scene = f"{location}, {f1}, {f2} visible, {lit}, {time}, {atm}"
        extra = f"{location}, {f1}, {f2}, {lit}, {time}, {atm}"

        panels.append({
            "scene": scene,
            "positive_extra": extra,
            "shot": shots[i % len(shots)],
        })

    return panels


# ---------------------------------------------------------------------------
# Scenario generator
# ---------------------------------------------------------------------------

def generate_scenario(setting: dict = None) -> dict:
    """Generate a complete scenario dict from a setting.

    Returns a dict in the same format as storyboards/strips/*.json,
    ready to be passed to build_strip_script().
    """
    if setting is None:
        setting = random.choice(SETTINGS)

    key = setting["key"]
    title = random.choice(setting["titles"])

    # Decide page 4 layout
    page4_layout = random.choice(["three_row", "grid_2x2"])
    page4_count = 4 if page4_layout == "grid_2x2" else 3

    # Generate env panels for pages 3 and 4
    env_panels_p3 = _make_env_panels(setting, 3)
    env_panels_p4 = _make_env_panels(setting, page4_count)

    # Tag env panels with scene_lora based on phase_structure
    phase_struct = setting.get("phase_structure", "standard")
    if phase_struct == "all_phase1":
        p3_lora, p4_lora = "phase1", "phase1"
    elif phase_struct == "all_phase2":
        p3_lora, p4_lora = "phase2", "phase2"
    elif phase_struct == "reversed":
        p3_lora, p4_lora = "phase2", "phase1"
    elif phase_struct == "mixed":
        p3_lora, p4_lora = "phase1_or_2", "phase1_or_2"
    else:  # standard
        p3_lora, p4_lora = "phase1", "phase2"

    for p in env_panels_p3:
        p["scene_lora"] = p3_lora
        p["scene_tag"] = f"{key}_act"
    for p in env_panels_p4:
        p["scene_lora"] = p4_lora
        p["scene_tag"] = f"{key}_climax"

    # Build setup panels (deep copy to avoid mutation)
    setup = [dict(p) for p in setting["setup"]]
    for p in setup:
        p["scene_tag"] = f"{key}_open"

    tension = [dict(p) for p in setting["tension"]]
    for p in tension:
        p["scene_tag"] = f"{key}_tension"

    aftermath = [dict(p) for p in setting["aftermath"]]
    for p in aftermath:
        p["scene_tag"] = f"{key}_after"

    # Assign panel IDs
    panel_num = 1
    for panel_list in [setup, tension, env_panels_p3, env_panels_p4, aftermath]:
        for p in panel_list:
            p["id"] = f"p{panel_num:03d}"
            panel_num += 1

    # Assemble pages
    pages = [
        {
            "_comment": f"Page 1 — Setup. {setting['description']}",
            "layout": random.choice(["L_right", "three_row"]),
            "panels": setup,
        },
        {
            "_comment": "Page 2 — Tension. Getting closer.",
            "layout": "grid_2x2",
            "panels": tension,
        },
        {
            "_comment": "Page 3 — Phase 1. LoRA-driven.",
            "layout": "three_row",
            "panels": env_panels_p3,
        },
        {
            "_comment": "Page 4 — Phase 2. LoRA-driven.",
            "layout": page4_layout,
            "panels": env_panels_p4,
        },
        {
            "_comment": "Page 5 — Aftermath.",
            "layout": random.choice(["two_row", "L_right"]) if len(aftermath) > 2 else "two_row",
            "panels": aftermath,
        },
    ]

    return {
        "title": title,
        "description": setting["description"],
        "generation": dict(GENERATION_DEFAULTS),
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# Character loader — reads all LoRA JSONs from lora_texts/
# ---------------------------------------------------------------------------

def load_lora_characters(lora_dirs) -> dict:
    """Load character LoRAs from one or more directories.

    Accepts a single path (str or Path) or a list of paths.
    Reads the A1111 LoRA card JSON format:
      "activation text"  → character activation tags
      "preferred weight" → LoRA strength
      "negative text"    → negative prompt additions

    Returns dict mapping stem name -> {lora, activation, weight, negative}.
    First occurrence wins when the same stem appears in multiple directories.
    """
    if not isinstance(lora_dirs, (list, tuple)):
        lora_dirs = [lora_dirs]

    chars = {}
    seen_stems: set = set()

    for lora_dir in lora_dirs:
        lora_dir = str(lora_dir)
        if not os.path.isdir(lora_dir):
            continue

        for fname in sorted(os.listdir(lora_dir)):
            fpath = os.path.join(lora_dir, fname)
            if not fname.endswith(".json") or os.path.isdir(fpath):
                continue

            stem = os.path.splitext(fname)[0]
            if stem in seen_stems:
                continue  # already loaded from a higher-priority dir

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            activation = data.get("activation text", "")
            if not activation:
                continue  # not a character card — skip

            weight = data.get("preferred weight", 0.8)
            if not weight:
                weight = 0.8

            negative = data.get("negative text", "")

            chars[stem] = {
                "lora": stem,
                "activation": activation,
                "weight": float(weight),
                "negative": negative,
            }
            seen_stems.add(stem)

    return chars


def pick_random_character(chars: dict) -> tuple:
    """Pick a random character. Returns (key, data)."""
    key = random.choice(list(chars.keys()))
    return key, chars[key]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def list_settings() -> list:
    """Return list of available setting keys."""
    return [s["key"] for s in SETTINGS]


def get_setting(key: str) -> dict:
    """Get a setting by key."""
    for s in SETTINGS:
        if s["key"] == key:
            return s
    raise ValueError(f"Unknown setting: {key}. Available: {list_settings()}")


# ---------------------------------------------------------------------------
# Load extended settings if available
# ---------------------------------------------------------------------------
try:
    from .scenarios_extended import EXTENDED_SETTINGS
    SETTINGS.extend(EXTENDED_SETTINGS)
except ImportError:
    pass
