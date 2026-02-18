import os

def choose_model(meta=None, context=None):
    """
    Chooses a model and its configuration based on the reasoning type and context.
    
    Args:
        meta (dict): Metadata about the request (reason, etc.)
        context (dict): The context being passed to the AI.
        
    Returns:
        dict: { "model": str, "options": dict }
    """
    if meta is None: meta = {}
    if context is None: context = {}

    forced_model = os.getenv("OLLAMA_FORCE_MODEL")
    if forced_model:
        return {"model": forced_model, "options": {"temperature": 0.2}}

    # Model tiers: fast for simple queries, mid for reasoning, deep for reflection
    # qwen2.5:3b is ~10x faster than gemma3:12b - use for factual/simple queries
    # Both models should be kept hot in VRAM for instant switching
    fast = os.getenv("OLLAMA_MODEL_FAST", "qwen2.5:3b")
    mid = os.getenv("OLLAMA_MODEL_MID", "gemma3:12b")
    deep = os.getenv("OLLAMA_MODEL_DEEP", "gemma3:12b")

    # Detect high-complexity context (many events)
    recent_events = context.get("recent_events", [])
    is_complex = len(recent_events) > 10
    
    # Detect simple factual queries that don't need personality
    trigger = context.get("trigger", {}) if context else {}
    user_text = (trigger.get("text") or "").lower()
    
    # Factual queries - use fast model regardless of complexity
    factual_patterns = [
        "what is", "what's", "who is", "who's", "when is", "when's",
        "where is", "where's", "how many", "how much", "define",
        "capital of", "population of", "weather", "time in",
        "convert", "calculate", "translate"
    ]
    is_factual = any(p in user_text for p in factual_patterns)
    
    # Emotional/personal queries - always use mid model for personality
    emotional_patterns = [
        "feel", "tired", "stressed", "happy", "sad", "angry",
        "help me", "i need", "i'm", "i am", "my day", "talk to me"
    ]
    is_emotional = any(p in user_text for p in emotional_patterns)
    
    model = fast
    temperature = 0.1 # Default to low temperature for precision
    reason = meta.get("reason", "presence_transition")

    # Reflex decisions (FAST)
    fast_reasons = [
        "room_occupied", "room_quiet", "home_active", 
        "home_quiet", "work_mode_on", "work_mode_off", 
        "presence_transition", "user_intent", "smalltalk"
    ]

    # Reasoning (MID)
    mid_reasons = ["anomaly", "explain", "hour_summary"]

    # Thinking (DEEP)
    deep_reasons = ["daily_reflection", "plan_generation", "deep"]

    routing_reason = ""
    if reason in fast_reasons:
        # Smart routing: factual queries always fast, emotional always mid
        if is_factual and not is_emotional:
            model = fast  # "What is the capital of Kenya" → fast
            temperature = 0.1
            routing_reason = "factual_query"
        elif is_emotional:
            model = mid   # "I'm feeling tired" → needs personality
            temperature = 0.3
            routing_reason = "emotional_query"
        else:
            model = mid if is_complex else fast
            temperature = 0.1
            routing_reason = "complex" if is_complex else "simple"
    elif reason in mid_reasons:
        model = mid
        temperature = 0.3
        routing_reason = "mid_reason"
    elif reason in deep_reasons:
        model = deep
        temperature = 0.5
        routing_reason = "deep_reason"
    else:
        model = mid if is_complex else fast
        temperature = 0.2
        routing_reason = "default"
    
    print(f"[ModelPolicy] {reason} → {model} (routing: {routing_reason}, factual={is_factual}, emotional={is_emotional})")

    # Voice responses need enough tokens for personality-rich responses
    # Increased from 96/256 to allow more expressive, culturally-rich outputs
    if reason == "smalltalk":
        num_predict = 200  # Was 96 - now allows fuller personality expression
    elif reason == "user_intent":
        num_predict = 384  # Was 256 - now allows richer emotional responses
    else:
        num_predict = 512  # Was 384 - more headroom for complex scenarios
    
    return {
        "model": model,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": 4096,
            "num_gpu": 99,
            "num_thread": 16,
            "keep_alive": "60m"
        }
    }
