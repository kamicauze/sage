"""
Minimal device control for Sage.

Start here when testing the voice loop end to end:
    STT (brain.voice.transcriber)  ->  sage/voice/transcript
    switch_controller              ->  sage/switch/<id>/set   (+ spoken reply on sage/voice/response)
    switch_node                    ->  drives the relay / prints in sim mode, reports sage/switch/<id>/state
    TTS (brain.voice.speaker)      <-  sage/voice/response

No LLM, no Architect, no memory. Just voice in, switch out.
"""
