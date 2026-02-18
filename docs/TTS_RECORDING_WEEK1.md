# TTS Voice Corpus - Week 1: Scripted Foundation

**Goal**: Build phonetic coverage across English, Swahili, and Sheng  
**Duration**: 30 minutes/day × 7 days = 3.5 hours  
**Output**: Clean, transcribed audio for TTS fine-tuning

---

## Recording Guidelines

### Equipment
- Consistent microphone (phone voice recorder is fine)
- Quiet room, minimal echo
- Same position/distance from mic each session

### Technique
- Speak naturally, at your normal pace
- Don't "perform" - just be yourself
- If you stumble, pause and re-read that sentence
- Include natural variation (don't force monotone)
- Stay hydrated

### File Naming
```
week1_day01_english.wav
week1_day01_english.txt  (transcript)
week1_day02_swahili.wav
...
```

---

# Day 1: English Phoneme Coverage

**Focus**: Full English sound inventory + natural speech patterns  
**Time**: 30 minutes

---

## Section 1: Warm-Up (5 minutes)

*Talk freely for 1-2 minutes about anything - how your day is going, what you're working on. This loosens up your voice.*

Then read these casual sentences:

```
Alright, let's get started with this recording session.
Today I'm going to read through some text to train a voice model.
The goal is to capture how I naturally speak.
Should be interesting to hear myself played back by an AI.
Okay, moving on to the actual content now.
```

---

## Section 2: Phoneme Coverage Sentences (10 minutes)

### Pangrams (all letters)
```
The quick brown fox jumps over the lazy dog.
Pack my box with five dozen liquor jugs.
How vexingly quick daft zebras jump.
The five boxing wizards jump quickly.
Sphinx of black quartz, judge my vow.
```

### Natural Statements
```
I need to check my email before the meeting starts.
The coffee machine is broken again, which is frustrating.
She asked me to review the budget proposal by Friday.
We should probably reschedule that call to next week.
The weather has been unpredictable lately.

I've been working on this project for about three months now.
The documentation could use some improvement, honestly.
Let me think about that and get back to you tomorrow.
That's a good point, I hadn't considered that angle.
We need to prioritize the most critical features first.

This is taking longer than I expected.
I'm not sure that's the right approach.
We could try a different strategy.
That makes sense to me.
I'll handle it first thing tomorrow.
```

### Questions (rising intonation)
```
What time does the meeting start?
Have you finished the report yet?
Where did you put the car keys?
Why didn't anyone tell me about this earlier?
How long will this take to complete?
Are you sure about that?
Did you get my message?
Can we reschedule to next week?
```

---

## Section 3: Numbers, Dates, and Time (5 minutes)

### Time Expressions
```
It's currently 10:45 in the morning.
The meeting is scheduled for 2:30 PM.
I woke up at 6:15 today.
The flight departs at 7:50 AM.
We have until 5 o'clock to finish this.
Let's meet at half past three.
The deadline is midnight tonight.
```

### Numbers and Money
```
The budget is set at 100,000 shillings.
That's about 750 dollars.
We need 15 more units to complete the order.
The project is 80 percent complete.
I've made 23 calls today.
The total comes to 4,500.
We're expecting around 200 attendees.
```

### Dates
```
Today is January 22nd, 2026.
The deadline is March 15th.
We started this back in November.
It's been running for 3 hours and 45 minutes.
The next milestone is in 2 weeks.
My birthday is on the 8th of July.
```

---

## Section 4: Sage-Style Responses (7 minutes)

### Short Responses
```
Got it. I'll set a reminder for 3 PM.
Okay, I've added that to your task list.
Sure, let me look that up for you.
Done. The timer is set for 15 minutes.
I've noted that. I'll bring it up tomorrow.
Working on it now.
Let me check on that.
```

### Observations
```
You've been at the screen for a while now. Maybe time for a break?
I noticed you skipped lunch today. Want me to remind you to eat?
Your schedule looks clear this afternoon. Good time to catch up.
The budget tracking shows you're on target for this month.
You seem a bit tired. Did you sleep okay last night?
```

### Longer Responses
```
Based on your patterns this week, you've been averaging about 6 hours of sleep. That's less than usual. Might want to prioritize rest tonight.

You have three meetings tomorrow: a standup at 9, a review at 11, and a call with James at 2. I'd suggest blocking some focus time between them.

The project is tracking well. You've completed 7 of the 10 planned tasks. The remaining items should take about 2 days at current pace.

I've analyzed your spending this month. You're at 70 percent of budget with 10 days remaining. Looking good, but watch the transport category.
```

---

## Section 5: Free Talk (3 minutes)

*Speak freely about anything:*
- How this recording session went
- What you're planning to do after
- Something you're thinking about
- A random memory or observation

*Just speak naturally for about 3 minutes.*

---

# Day 2: English Continued + Technical Vocabulary

**Focus**: Technical terms, coding vocabulary, Sage-specific domain  
**Time**: 30 minutes

---

## Section 1: Warm-Up (3 minutes)

*Free talk about your day, current project, or anything on your mind.*

---

## Section 2: Technical Vocabulary (12 minutes)

### Programming Terms
```
The function returns a null value when the input is invalid.
We need to refactor this module to improve performance.
The API endpoint is throwing a 500 error.
Let me push this commit and create a pull request.
The database query is taking too long to execute.

I'm debugging an issue with the authentication flow.
The container keeps crashing due to memory limits.
We should add unit tests for this component.
The deployment pipeline failed at the build stage.
Let me check the logs to see what went wrong.
```

### Sage-Specific Terms
```
The brain module processes incoming MQTT messages.
The architect is generating a new implementation plan.
Context is built from sensor data and user history.
The routing decision was set to hybrid mode.
Memory recall found three relevant past conversations.

The VLM detected that you're at your desk working.
STT transcription completed in 200 milliseconds.
The personality engine switched to empathetic mode.
Budget tracking shows we've used 15 dollars this month.
The pattern detector flagged extended stillness.
```

### Hardware Terms
```
The Jetson Orin Nano is running at 67 TOPS.
I need to flash the SD card with the new image.
The camera is connected via USB 3.0.
GPU memory usage is at 70 percent.
Let me check the CUDA driver version.

The IR illumination helps with low-light detection.
We're streaming at 640 by 480 resolution.
The inference latency is around 2 seconds.
I need to update the Ollama model weights.
The MQTT broker is listening on port 1883.
```

---

## Section 3: Conversational Technical (10 minutes)

### Explaining Concepts
```
So basically, the way this works is that the camera captures a frame, sends it to the VLM for analysis, and then the result gets published to MQTT where the brain picks it up.

The routing system looks at your query and decides whether to use a local model or send it to the cloud. Simple questions stay local, complex ones go to Claude or Gemini.

When I say self-healing, I mean that if the generated code fails its tests, the architect automatically tries to fix it. It'll retry up to three times before giving up.
```

### Troubleshooting
```
Hmm, that's not working. Let me check the error logs.
Okay, the issue is that the service isn't running.
I think the problem is with the API key configuration.
Let me restart the container and see if that helps.
Right, so the fix is to update the environment variable.

The model isn't loading because there's not enough memory.
We need to use a quantized version to fit in 8 gigs.
The connection timeout suggests a network issue.
```

---

## Section 4: Numbers in Context (5 minutes)

```
The model has 3 billion parameters.
Inference takes about 1.5 seconds per frame.
We're targeting 15 frames per second.
The corpus contains 10 hours of audio.
Token usage was 2,500 input and 800 output.

The accuracy improved from 78 to 92 percent.
Latency dropped by 40 percent after optimization.
The batch size is set to 16.
Training will take approximately 4 hours.
The checkpoint is saved every 1000 steps.
```

---

## Section 5: Free Technical Talk (5 minutes)

*Talk about:*
- A technical problem you recently solved
- How some part of Sage works
- What you're planning to build next

---

# Day 3: Swahili Foundation

**Focus**: Common Swahili phrases, greetings, and everyday expressions  
**Time**: 30 minutes

---

## Section 1: Warm-Up (3 minutes)

*Jaribu kuongea kwa Kiswahili kwa dakika moja au mbili. Sema lolote linalokuja akilini.*

*(Try speaking in Swahili for a minute or two. Say whatever comes to mind.)*

---

## Section 2: Greetings and Responses (7 minutes)

### Basic Greetings
```
Habari yako?
Nzuri sana, asante.
Habari za asubuhi?
Salama tu.
Shikamoo.
Marahaba.

Habari za kazi?
Nzuri, kumbe wewe je?
Habari za nyumbani?
Poa, hakuna shida.
```

### Time-Based Greetings
```
Habari za asubuhi.
Habari za mchana.
Habari za jioni.
Usiku mwema.
Lala salama.
Kesho tutaonana.
```

### Farewells
```
Kwaheri.
Tutaonana baadaye.
Tutaonana kesho.
Safari njema.
Uende salama.
Kwa heri ya kuonana.
```

---

## Section 3: Common Phrases (10 minutes)

### Daily Activities
```
Ninaenda kazini sasa.
Nimerudi nyumbani.
Ninakula chakula cha mchana.
Ninahitaji kupumzika kidogo.
Ninafanya kazi kwa kompyuta.

Saa ngapi sasa?
Ni saa tatu asubuhi.
Niko busy sana leo.
Nimechoka kidogo.
Ninahitaji kahawa.
```

### Questions and Answers
```
Uko wapi?
Niko ofisini.
Unafanya nini?
Ninafanya kazi.
Utarudi lini?
Nitarudi saa sita jioni.

Je, umekula?
Ndio, nimekula.
Unahitaji msaada?
Hapana, niko sawa.
Unaelewa?
Ndio, naelewa vizuri.
```

### Expressing Feelings
```
Niko furaha leo.
Nimechoka sana.
Nina wasiwasi kidogo.
Niko sawa tu.
Sijisikii vizuri.
Ninajisikia vizuri sasa.
```

---

## Section 4: Sage Responses in Swahili (7 minutes)

```
Umekuwa ukifanya kazi kwa muda mrefu. Pumzika kidogo?
Nimeona hujala chakula cha mchana. Ukumbushe?
Ratiba yako ya kesho iko wazi asubuhi.
Bajeti yako ya wiki hii iko sawa.
Unaonekana umechoka. Umelala vizuri usiku?

Sawa, nimeweka kikumbusho.
Nimekubali, nimeiongeza kwenye orodha yako.
Ngoja nikague hiyo.
Tayari. Timer imewekwa.
Nimekumbuka. Nitakukumbusha kesho.

Kulingana na pattern yako wiki hii, umelala wastani wa saa sita kwa usiku. Jaribu kulala mapema leo.

Una mikutano mitatu kesho: standup saa tatu, review saa tano, na simu na James saa nane.
```

---

## Section 5: Free Swahili Talk (3 minutes)

*Ongea kwa Kiswahili kuhusu:*
- Siku yako ilikuwaje
- Mipango yako ya kesho
- Jambo lolote linalokuja akilini

---

# Day 4: Swahili Extended + Mixed Language

**Focus**: Longer Swahili sentences, code-switching practice  
**Time**: 30 minutes

---

## Section 1: Warm-Up (3 minutes)

*Mix languages naturally - talk about your day using both English and Swahili as you normally would.*

---

## Section 2: Longer Swahili Sentences (10 minutes)

### Describing Activities
```
Asubuhi ya leo niliamka mapema sana kwa sababu nilikuwa na mkutano muhimu.
Nimekuwa nikifanya kazi kwenye project hii kwa miezi mitatu sasa.
Baada ya kazi nitaenda gym kwa saa moja hivi.
Wiki ijayo nina safari ya kwenda Mombasa kwa kikao.
Nimepanga kukutana na rafiki yangu James kwa chakula cha mchana kesho.
```

### Expressing Opinions
```
Nadhani hii ni njia nzuri ya kutatua tatizo hili.
Sijui kama hilo ni wazo zuri, lakini tunaweza kujaribu.
Kwa maoni yangu, tunahitaji muda zaidi kukamilisha kazi hii.
Inawezekana kwamba tuna approach mbaya, lakini bado sijui.
Napenda jinsi unavyofikiria kuhusu hili.
```

### Planning and Scheduling
```
Kesho asubuhi nina mkutano na timu ya uhandisi saa tatu.
Tunahitaji kukamilisha phase ya kwanza kabla ya mwisho wa wiki.
Mwezi ujao tutaanza kufanya kazi kwenye feature mpya.
Ratiba yangu ya leo ni busy sana, sina muda wa ziada.
Hebu tupange kikao kingine kwa wiki ijayo Jumatatu au Jumanne.
```

---

## Section 3: Code-Switching Practice (12 minutes)

### Natural Mixing (How you actually talk)
```
So basically nilikuwa nikifanya kazi on the API, then nikagundua there's a bug in the authentication flow.

Meeting ya leo ilikuwa productive sana, we managed to resolve most of the issues.

Ninahitaji ku-refactor hii function because performance yake si nzuri.

The deadline is kesho asubuhi, so lazima ni-finish tonight.

Let me check the logs kwanza, then nitakuambia what's happening.
```

### Work Context
```
Nimekuwa nikidebug issue hii for like two hours sasa, still can't figure it out.

The client anapiga simu kila saa asking about the update, it's stressing me out.

Tunahitaji to prioritize the critical features first, the rest can wait.

I think the best approach ni kustart fresh na new architecture.

Boss amesema we need to ship by Friday, which is kind of tight lakini tutajaribu.
```

### Personal Context
```
Jana nilikuwa tired sana, nikaenda kulala early for once.

Weekend hii I'm planning ku-visit my folks huko ushago.

Nimekuwa meaning to start exercising lakini I keep procrastinating.

The weather has been weird lately, one day hot next day cold.

I should probably take a break, nimekuwa working non-stop.
```

---

## Section 4: Sage Code-Switched Responses (5 minutes)

```
Umekuwa kwa screen for three hours straight. Take a break?
Your budget ya wiki hii is at 80 percent, looking good.
Nimeona you haven't moved in a while. Stretch kidogo?
Kesho una two meetings: one at 9 na the other at 2.
The pattern shows umekuwa sleeping late consistently. Try earlier tonight?

Sawa, let me set that reminder for you.
Done. Nimeadd hiyo kwa task list yako.
Give me a moment, I'm working on it.
Based on what I can see, you look a bit tired today.
Your focus session imekuwa running for 45 minutes. Good progress.
```

---

## Section 5: Free Mixed Talk (5 minutes)

*Talk naturally, mixing languages as you normally would, about:*
- Current projects
- Weekend plans
- Something interesting that happened recently

---

# Day 5: Sheng Vocabulary in Context

**Focus**: Sheng words and expressions used naturally in sentences  
**Time**: 30 minutes

---

## Section 1: Warm-Up (3 minutes)

*Ongea tu vile unaongea na mabeshte wako - natural, na Sheng proper.*

---

## Section 2: Common Sheng Greetings and Expressions (10 minutes)

### Greetings
```
Sasa buda, niaje?
Poa mzee, uko aje?
Niaje brathe, mambo?
Sasa man, vipi leo?
Zi mzae, uko fiti?
Poa bro, niko sawa tu.
```

### Responses
```
Poa kabisa.
Fiti tu mzee.
Niko poa, siwezi complain.
Tu sawa, life iko juu.
Bomba, hakuna shida.
Niko freshi leo.
```

### Expressions
```
Hii maneno ni moto sana.
Story za juzi zilikuwa heavy.
Buda amenibamba na deadline.
Siwezi deal na hii stress.
Lazima tufanye plan.
Mambo ni real hapa nje.
```

---

## Section 3: Sheng in Daily Context (12 minutes)

### Work Context
```
Leo niko home nikicheki vitu za project.
Buda amenitumia task mob sana, sielewi.
Deadline ni kesho na bado sijamaliza.
Hii code inaniletea shida, inabehave weird.
Nimekuwa nikidunda hii bug for hours.

Meeting ya leo ilikuwa lengthy sana.
Boss amenishow lazima tuship by Friday.
Nimeamua kuchapa overtime leo usiku.
Sitaki kulala late lakini ni must.
Tupatane kesho tucheki progress.
```

### Personal Context
```
Nimechoka mbaya, lazima nirest.
Jana nililala saa nne usiku, leo niko wasted.
Hii joto inanifinish, naeza faint.
Nahitaji kupata kahawa saa hii.
Weekend lazima niende kupumzika proper.

Beshte yangu amenipigia, anasema tupatane Java.
Sikuwa na plan lakini nikasema sawa tu.
Gari yangu imekataa ku-start leo asubuhi.
Naeza Uber ama nipige jam ukam na gari.
Tutasort, hakuna shida.
```

### Describing Situations
```
Situation ilikuwa tricky lakini tumefika.
Vitu zilikuwa tight mwanzoni lakini sasa ziko sawa.
Nilidhani itakuwa easy lakini ni complicated.
Story ni ndefu but basically tulisort.
End of the day, mambo yalienda poa.
```

---

## Section 4: Sage with Sheng Flavor (5 minutes)

```
Buda, umekuwa kwa screen saa tatu sasa. Toka upumzike kidogo.
Niaje, unaonekana umechoka leo. Umelala sawa?
Vitu ziko juu - budget yako ya wiki iko on track.
Kesho una meeting saa tatu na nyingine saa nane. Usiforget.
Nimecheki patterns zako - unalala late sana lately. Try kulala mapema.

Sawa, nimeset reminder.
Poa, nimeadd hiyo kwa list yako.
Ngoja kidogo, nafanya hiyo sasa.
Done buda, sorted.
Nitakukumbusha kesho morning.
```

---

## Section 5: Natural Sheng Conversation (5 minutes)

*Just talk as you would with friends - natural Sheng flow about:*
- Kitu fulani funny ilihappen
- Plans za weekend
- Random thoughts

---

# Day 6: Emotional Range and Expression

**Focus**: Capturing different emotional states and tones  
**Time**: 30 minutes

---

## Section 1: Warm-Up - Current Mood (3 minutes)

*Describe how you're actually feeling right now, honestly. Tired? Energetic? Stressed? Just talk about it naturally.*

---

## Section 2: Tired/Low Energy (7 minutes)

*Read these slowly, with lower energy, as if you're genuinely tired:*

```
I'm so tired today. Didn't sleep well last night.
I don't think I can focus on this right now.
Maybe I should just take a break.
Ugh, I still have so much to do.
Let me just finish this one thing and then rest.

Nimechoka sana. Naeza lala hapa hapa.
Sidhani nitamaliza hii leo.
Ngoja nipumzike kwanza, then tuendelee.
Hii siku imekuwa ndefu sana.
Nataka tu kulala.

Can't keep my eyes open. Need coffee or something.
This is taking forever and I'm running on empty.
I should probably call it a night.
```

---

## Section 3: Stressed/Frustrated (7 minutes)

*Read with more tension in your voice, faster pace:*

```
Why isn't this working? I've tried everything.
This deadline is impossible. We don't have enough time.
I don't understand why this keeps breaking.
Okay, okay, let me think. There has to be a solution.
This is really frustrating. I've been stuck on this for hours.

Hii kitu inaniletea stress.
Sijui nifanye nini, nimejaribu kila kitu.
Deadline ni kesho na bado niko far.
Mbona hii inabehave hivyo? Haiwork!
Lazima nisolve hii tonight, there's no other option.

Come on, just work already.
I don't have time for this right now.
Fine. Let me start over from scratch.
```

---

## Section 4: Happy/Energetic (7 minutes)

*Read with more energy, maybe a slight smile:*

```
Yes! Finally got it working. That took forever but we're there.
This is actually coming together really nicely.
I'm feeling good about this project.
Alright, let's do this. I'm ready.
Great news - the client loved the demo.

Poa sana! Imework!
Leo ni siku nzuri, mambo yote yanakwenda sawa.
Nimefurahi sana, tumefika hatimaye.
Hii ni progress nzuri, tunaendelea vizuri.
Let's gooo, we're almost done.

Things are looking up. This might actually work.
I knew we could figure it out.
This calls for a celebration. Coffee break!
```

---

## Section 5: Calm/Thoughtful (6 minutes)

*Read slowly, reflectively:*

```
Let me think about this for a moment.
I'm not sure what the right approach is here.
It's interesting how things turned out.
Looking back, I think we made the right call.
There's something to be said for taking your time.

Nadhani... nadhani njia nzuri ni hii.
Sijui, lakini tunaweza jaribu.
Inafaa kufikiria hii vizuri kabla ya kufanya uamuzi.
Mambo mengine yanahitaji muda.
Pole pole ndio mwendo, si lazima kukimbilia.

Sometimes you just need to step back and think.
It's okay not to have all the answers right away.
We'll figure it out. We always do.
```

---

# Day 7: Review and Polish

**Focus**: Re-record any weak sections, add variety, final polish  
**Time**: 30 minutes

---

## Section 1: Warm-Up (3 minutes)

*Free talk about how the week of recording went. What was easy? What was hard?*

---

## Section 2: Re-Record Weak Sections (10 minutes)

*Go back through your recordings from the week. Find any sentences that:*
- Had stumbles or restarts
- Sounded unnatural
- Had background noise
- Could be clearer

*Re-record those specific sentences here.*

---

## Section 3: Additional Variety (10 minutes)

### Whispered/Quiet (as if someone's sleeping nearby)
```
Let me just check this quietly.
I don't want to wake anyone.
Okay, that's done. Going to sleep now.
```

### Emphasized/Important
```
This is REALLY important, don't forget.
The deadline is TOMORROW, not next week.
I need you to LISTEN to this carefully.
```

### Lists and Sequences
```
First, we need to fix the bug. Second, write tests. Third, deploy.
The steps are: open the app, click settings, then enable notifications.
I need three things: coffee, my laptop, and some peace and quiet.
```

### Interruptions and Restarts
```
So what I was saying is... wait, what was I saying?
The thing about this is... actually, let me start over.
I think we should... hmm, no, that's not right.
```

---

## Section 4: Spontaneous Responses (7 minutes)

*Without looking at text, respond naturally to these prompts:*

1. Someone asks "How was your day?"
2. Someone asks "What are you working on?"
3. Someone asks "Are you free this weekend?"
4. Someone says "I'm really stressed about this deadline"
5. Someone asks "Can you explain how Sage works?"
6. You just finished a difficult task successfully
7. You're about to go to sleep

*Just respond naturally, in whatever language mix feels right.*

---

## Section 5: Closing Thoughts (5 minutes)

*Record final thoughts:*
- How you feel about completing Week 1
- What you're looking forward to with the TTS training
- Any random thoughts about the Sage project

---

# Post-Recording Checklist

After completing Week 1:

- [ ] All 7 days recorded
- [ ] Audio files named consistently
- [ ] Transcripts created for each recording
- [ ] Audio quality checked (no major issues)
- [ ] Total duration: ~3.5 hours
- [ ] Backed up to a second location

## Next Steps

1. **Week 2**: Natural conversation recordings
2. **Week 3**: Emotional range and edge cases
3. **Processing**: Clean audio, segment utterances
4. **Training**: Fine-tune TTS model on corpus

---

*Good luck with the recordings! This corpus will be the voice of Sage.*
