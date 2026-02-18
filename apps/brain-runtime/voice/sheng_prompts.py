"""
Sage Sheng Training Prompt Bank

Curated prompts for recording Sheng + Kenyan English training data.
Organized by category for systematic coverage of phonetic patterns,
prosody, code-switching, and smart home commands.

Target: ~500 prompts, yielding 1-2 hours of recorded audio at natural pace.
"""

# --- Greetings & Common Phrases ---
GREETINGS = [
    "Sasa, niaje?",
    "Mambo vipi?",
    "Poa sana, nakushow.",
    "Zi bro, nimechoka leo.",
    "Niaje buda, umeshindaje?",
    "Uko aje? Mi niko poa tu.",
    "Sema bro, what's good?",
    "Wasup fam, niko hapa.",
    "Yo, maze umechelewa sana.",
    "Buda tukutane hapo stage.",
    "Nilikuwa nacheki kama uko around.",
    "Maze leo ni day mob.",
    "Sasa, si you come we link up.",
    "How's the day been? Ama umekuwa busy?",
    "Niaje, nimekumiss bana.",
    "Mi huku tu, naskia baridi mob.",
    "Poa. Umenipata right time bana.",
    "Zi bro, niko hapo hapo tu.",
    "Everything ni sawa, relax tu.",
    "Kumbe ni wewe? Sema sema!",
]

# --- Code-Switching (English-Swahili blend) ---
CODE_SWITCH = [
    "Bro the meeting was so boring, nilikuwa tu naskia usingizi.",
    "I told him wacha story but he kept insisting.",
    "So basically nilimpata hapo kwa stage waiting for a mat.",
    "The problem is hatuwezi afford hiyo thing right now.",
    "She called me jana and was like, dude come through.",
    "I think tunafaa plan this thing properly before we start.",
    "That guy amenishow the price ni fair sana.",
    "So we went to the place and guess what, ilikuwa closed.",
    "My phone imekufa bana, can I use yours?",
    "The teacher aliniambia I need to step up my game.",
    "Let me just finish hii kitu then we bounce.",
    "I was thinking maybe tuweze do it over the weekend.",
    "Kwani you haven't seen the message nilikutumia?",
    "Sawa, but make sure umefika before seven.",
    "Honestly mi sijui what happened hapo.",
    "Next time just call me ukifika hapo.",
    "The food ilikuwa sawa tu, nothing special.",
    "Ati you're telling me hakuna bus? How now?",
    "Maze hii traffic itanimaliza one of these days.",
    "That thing you told me about, niliskia ni legit.",
    "We should probably leave saa hii before it gets dark.",
    "Kuna this place I know, the vibe is always right.",
    "I'll sort you out kesho, don't worry about it.",
    "Come on bana, don't be like that.",
    "Hii story ni long, but basically niliwin.",
    "The weather today ni kali sana, wear a jacket.",
    "I can't believe alifanya hivyo in front of everyone.",
    "So what's the plan for leo? Ama tukae tu?",
    "Bro stop overthinking, just do the thing.",
    "I need to recharge my phone, battery imeisha kabisa.",
]

# --- Smart Home Commands (Sheng style) ---
SMART_HOME = [
    "Sage, washa taa kwa sitting room.",
    "Buda zima taa, naenda kulala.",
    "Turn on the lights hapa kwa bedroom.",
    "Maze punguza brightness kidogo.",
    "Washa heater bana, kuna baridi.",
    "Sage, set alarm saa moja asubuhi.",
    "Play some music, something chill.",
    "Ongeza volume kidogo.",
    "Punguza volume, ni loud sana.",
    "What's the temperature outside right now?",
    "Sage, remind me at five to pick up the package.",
    "Lock the front door please.",
    "Nani ako kwa gate? Check camera.",
    "Turn off everything kwa kitchen.",
    "Weka timer ya minutes kumi.",
    "Sage, how's the weather looking for kesho?",
    "Switch kwa news channel.",
    "Mi naenda nje, switch to away mode.",
    "Washa fan kwa bedroom, ni joto mob.",
    "Sage, ni saa ngapi sai?",
    "Open the blinds, let in some light.",
    "Close the curtains, it's getting dark.",
    "Set the thermostat to twenty two degrees.",
    "Sage, add milk to the shopping list.",
    "What's on my schedule for today?",
    "Cancel the alarm, sitalala tena.",
    "Dim the lights to fifty percent.",
    "Sage, play my morning playlist.",
    "Zima TV, hakuna kitu interesting.",
    "Check if the washing machine is done.",
]

# --- Conversational / Narrative (longer for prosody training) ---
CONVERSATIONAL = [
    "So the other day nilikuwa kwa mat headed to town, and this guy next to me starts talking on phone so loud maze. Everyone was just looking at him like buda relax.",
    "Nimekuwa thinking about starting a side hustle, you know. Maybe something online. The nine to five alone haitoshi these days bana.",
    "Ukiskia mtu anakuambia something is too good to be true, usually it is. Learned that the hard way last year.",
    "The best thing about weekends ni that you can just wake up whenever, no alarm, no rush, just vibes.",
    "I remember back in the day when we used to play outside until it got dark. Kids these days hawajui hiyo life.",
    "Technology has changed so much bana. Like imagine telling someone ten years ago that you can control your whole house with your voice.",
    "The traffic situation in Nairobi needs to be sorted out properly. Every day ni the same story, stuck for hours.",
    "Cooking at home is actually cheaper and healthier than eating out every day, but maze time ni scarce.",
    "Sports brings people together in a way that nothing else can. Ukiwa kwa stadium, everyone is one team.",
    "Music is one of those things that can completely change your mood. One song and suddenly everything feels better.",
    "Life in the city is fast, but sometimes you need to slow down na just appreciate the small things.",
    "Education is important, but it's not the only path. There are so many skills you can learn on your own these days.",
    "The rains this season zimekuwa heavy sana. Some roads hazipitiki kabisa.",
    "I've been trying to learn coding lately. It's tough at first but once you get the basics, things start clicking.",
    "Friendship ni about being there for each other, not just when things are good but especially when they're tough.",
    "Mi naona the future of Kenya is bright. Young people wanakuja na ideas mob sana.",
    "Health should always come first. Pesa you can always make, but your body ni one.",
    "Time management is something I struggle with. There's always too much to do and not enough hours.",
    "Social media can be great for connecting with people, but it can also be a massive time waster if you're not careful.",
    "When you travel to a new place, the food is always the first thing you should try. It tells you everything about the culture.",
]

# --- Kenyan English (formal but with Kenyan prosody) ---
KENYAN_ENGLISH = [
    "Good morning. How are you doing today?",
    "I would like to request for an update on the project status.",
    "The meeting has been scheduled for tomorrow at ten o'clock.",
    "Please ensure that all the documents are submitted before the deadline.",
    "Thank you very much for your assistance with this matter.",
    "I will follow up with the team and get back to you shortly.",
    "The presentation went very well and the feedback was positive.",
    "We need to discuss the budget allocation for the next quarter.",
    "I appreciate your patience as we work through these issues.",
    "Could you kindly share the report with the rest of the group?",
    "The system is currently undergoing maintenance and will be back shortly.",
    "I have reviewed the proposal and I have a few suggestions.",
    "Let me check my calendar and confirm the availability.",
    "The delivery is expected to arrive by end of business today.",
    "We should consider alternative approaches to solve this problem.",
    "I'm pleased to inform you that the application has been approved.",
    "The workshop will cover essential skills for professional development.",
    "Please feel free to reach out if you have any questions.",
    "The results indicate a significant improvement in performance.",
    "We are committed to ensuring the highest standards of quality.",
]

# --- Numbers, Dates, Addresses (for TTS clarity) ---
NUMBERS_AND_INFO = [
    "My number is oh seven two one, five six seven, eight nine oh.",
    "The address is number forty five, Kimathi Street, Nairobi.",
    "It costs about two thousand five hundred shillings.",
    "The population of Kenya is approximately fifty five million people.",
    "I was born on the twenty third of March, nineteen ninety five.",
    "The flight departs at fourteen thirty hours from terminal one.",
    "Take the first left, then the second right after the roundabout.",
    "The distance from Nairobi to Mombasa is about four hundred and eighty kilometers.",
    "My appointment is at quarter past three in the afternoon.",
    "The building is on the seventh floor, room number three oh nine.",
    "The match starts at half past four, don't be late.",
    "We need about fifteen kilograms of cement for the project.",
    "The temperature today is twenty six degrees Celsius.",
    "It's currently eleven forty five in the morning.",
    "The speed limit on this road is eighty kilometers per hour.",
    "The total comes to three thousand, seven hundred and fifty shillings.",
    "My P.O. Box number is four two zero six seven, Nairobi.",
    "The exchange rate is one dollar to about one hundred and fifty shillings.",
    "We have twenty three participants confirmed for the event.",
    "The parcel weighs approximately two point five kilograms.",
]

# --- Emotions & Expressiveness (for tonal range) ---
EMOTIONS = [
    "No way! Are you serious right now? That's unbelievable!",
    "Maze I'm so happy bana, you have no idea.",
    "I'm really disappointed with how things turned out.",
    "That's the funniest thing I've heard all week, oh my God.",
    "I'm worried about the situation, it doesn't look good.",
    "Come on, you can do this! I believe in you!",
    "That makes me so angry, how could they do that?",
    "I'm grateful for everything you've done for me, seriously.",
    "This is so boring, can we do something else?",
    "Wow, that's actually really impressive. Well done!",
    "I feel bad about what happened, I should have done better.",
    "Exciting news! We got the approval we were waiting for!",
    "I'm nervous about the interview tomorrow, wish me luck.",
    "Ha! I knew it! I told you so!",
    "That's really sweet of you, thank you so much.",
    "I'm exhausted bana, today was the longest day ever.",
    "Oh no, I completely forgot about that. My bad.",
    "I'm proud of how far we've come as a team.",
    "Seriously? After everything we discussed? Unbelievable.",
    "I can't wait for the weekend, it's going to be amazing!",
]

# --- Questions & Commands (varied intonation patterns) ---
QUESTIONS = [
    "What time is the meeting supposed to start?",
    "Have you finished the report yet?",
    "Where did you put the car keys?",
    "Who is coming to the dinner tonight?",
    "Why didn't you call me back yesterday?",
    "How much does it cost per kilogram?",
    "When was the last time you went to the doctor?",
    "Can you help me move this table?",
    "Do you think it's going to rain today?",
    "Which route should we take to avoid traffic?",
    "Is the supermarket still open at this hour?",
    "What did they say about the test results?",
    "Shall we order food or cook at home?",
    "Are you coming with us or staying behind?",
    "How long have you been waiting here?",
    "Did you manage to fix the issue with the printer?",
    "Where exactly is the new office located?",
    "Who was that person you were talking to earlier?",
    "Can you believe how fast this year has gone?",
    "Would you prefer tea or coffee?",
]

# --- Swahili Core Phrases (for phonetic coverage) ---
SWAHILI_PHRASES = [
    "Habari yako? Mimi niko sawa tu.",
    "Asante sana kwa msaada wako.",
    "Tafadhali nipe maji kidogo.",
    "Naomba unisamehe, nilichelewa.",
    "Hii ni nzuri sana, nakupenda.",
    "Tutaonana kesho asubuhi mapema.",
    "Sijui kama nitaweza kufika kwa wakati.",
    "Watoto wanahitaji kwenda shuleni sasa.",
    "Chakula tayari? Nina njaa sana.",
    "Nimefurahi sana kukuona tena baada ya muda mrefu.",
    "Duka liko wapi? Nataka kununua vitu.",
    "Gari yangu imeharibika, nahitaji fundi.",
    "Hali ya hewa ni nzuri leo, twende nje.",
    "Nimechoka sana, nataka kupumzika kidogo.",
    "Tuweke mpango mzuri kabla ya kuanza kazi.",
    "Simu yangu haifanyi kazi vizuri.",
    "Nafikiri tunapaswa kuzungumza kuhusu hili.",
    "Mimi sitaki kuleta matatizo yoyote.",
    "Karibu sana nyumbani kwangu.",
    "Safari njema, tutakuona ukifika salama.",
]

# --- Technical / Computing (for Sage's domain) ---
TECHNICAL = [
    "The server is down, we need to restart it immediately.",
    "Can you check the logs and see what caused the error?",
    "I need to push the latest changes to the main branch.",
    "The API is returning a four oh four error on that endpoint.",
    "Memory usage is at ninety five percent, we need to optimize.",
    "The database query is taking too long, we should add an index.",
    "Run the tests before deploying to production.",
    "The container needs to be rebuilt with the new dependencies.",
    "CPU utilization is spiking every few minutes.",
    "I set up the CI CD pipeline for automatic deployment.",
    "The model accuracy improved by three percent after fine tuning.",
    "We need to upgrade the Python version to three point twelve.",
    "The neural network has about six hundred million parameters.",
    "Training is expected to take approximately four hours on this GPU.",
    "The inference latency is under a hundred milliseconds.",
    "Sage, what's the current GPU temperature?",
    "The batch size needs to be reduced to fit in memory.",
    "I'm getting a CUDA out of memory error on this model.",
    "The learning rate should be set to zero point zero zero one.",
    "Deploy the updated model to the edge device.",
]

# --- Short Utterances (for quick response training) ---
SHORT = [
    "Yes.",
    "No.",
    "Okay.",
    "Sawa.",
    "Sure thing.",
    "Not yet.",
    "Maybe.",
    "Of course.",
    "Absolutely.",
    "No problem.",
    "Got it.",
    "Right.",
    "Exactly.",
    "I see.",
    "Understood.",
    "Perfect.",
    "Definitely.",
    "Nah.",
    "Poa.",
    "Let's go.",
    "One moment.",
    "Hold on.",
    "Relax.",
    "Easy.",
    "My bad.",
    "True.",
    "For real?",
    "Come on.",
    "No way.",
    "Let's do it.",
]

# --- Tongue Twisters & Phonetic Exercises (for articulation) ---
PHONETIC_EXERCISES = [
    "She sells seashells by the seashore every single Saturday.",
    "Peter Piper picked a peck of pickled peppers properly.",
    "Kuku kadogo kakakimbia kwa kasi kubwa sana.",
    "Mtu mzuri mwenye moyo mkubwa amesimama mahali pazuri.",
    "The thick thistle stuck in the thicket made the thatcher think.",
    "Bibi yangu alipika pilipili na pilau kwa pamoja.",
    "Rapidly running rabbits rarely rest on rainy roads.",
    "Ng'ombe nne zinapita njia nyembamba na nyasi ndefu.",
    "Betty bought a bit of better butter to make a better batter.",
    "Kikapu kimoja kinabeba viazi vingi vya aina tofauti.",
]

# --- All prompts as a flat list with categories ---
ALL_PROMPTS = []
CATEGORIES = {
    "greetings": GREETINGS,
    "code_switch": CODE_SWITCH,
    "smart_home": SMART_HOME,
    "conversational": CONVERSATIONAL,
    "kenyan_english": KENYAN_ENGLISH,
    "numbers": NUMBERS_AND_INFO,
    "emotions": EMOTIONS,
    "questions": QUESTIONS,
    "swahili": SWAHILI_PHRASES,
    "technical": TECHNICAL,
    "short": SHORT,
    "phonetic": PHONETIC_EXERCISES,
}

for cat, prompts in CATEGORIES.items():
    for prompt in prompts:
        ALL_PROMPTS.append({"text": prompt, "category": cat})


def get_prompts(category=None, shuffle=False):
    """Get prompts, optionally filtered by category."""
    import random
    if category:
        prompts = [p for p in ALL_PROMPTS if p["category"] == category]
    else:
        prompts = ALL_PROMPTS.copy()
    if shuffle:
        random.shuffle(prompts)
    return prompts


def get_stats():
    """Get prompt bank statistics."""
    stats = {"total": len(ALL_PROMPTS)}
    for cat, prompts in CATEGORIES.items():
        stats[cat] = len(prompts)
    # Estimate total recording time (avg 4 seconds per short, 15s per long)
    total_chars = sum(len(p["text"]) for p in ALL_PROMPTS)
    # ~150 chars per minute at natural pace
    est_minutes = total_chars / 150
    stats["est_duration_minutes"] = round(est_minutes, 1)
    return stats


if __name__ == "__main__":
    s = get_stats()
    print(f"Sheng Prompt Bank: {s['total']} prompts")
    print(f"Estimated recording time: ~{s['est_duration_minutes']} minutes")
    print("\nCategories:")
    for cat, count in s.items():
        if cat not in ("total", "est_duration_minutes"):
            print(f"  {cat}: {count}")
