import librosa
import numpy as np

def analyze_audio(filepath: str, style_preset: str) -> dict:
    """
    Performs audio analysis to extract BPM, Key (mock), and dynamic Arrangement Sections
    by estimating vocal and instrumental regions using harmonic separation and energy thresholds.
    """
    # 1. Load Audio
    # We use a lower sample rate for performance since we don't need high fidelity for structural analysis
    y, sr = librosa.load(filepath, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    
    # 2. BPM Estimation
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # tempo can be an array depending on the librosa version
    avg_tempo = float(tempo[0]) if isinstance(tempo, np.ndarray) and len(tempo) > 0 else float(tempo)
    key = "Unknown"  # Full key estimation is complex without a huge lookup matrix. Kept as a placeholder for MVP.
    
    # 3. Vocal Activity Estimation via Harmonic/Percussive Separation
    # We isolate the harmonic component which typically houses sustained vocal energy
    y_harmonic, _ = librosa.effects.hpss(y)
    
    hop_length = 512
    rmse = librosa.feature.rms(y=y_harmonic, hop_length=hop_length)[0]
    times = librosa.frames_to_time(range(len(rmse)), sr=sr, hop_length=hop_length)
    
    # Normalize RMSE
    if np.max(rmse) > 0:
        rmse = rmse / np.max(rmse)
        
    # Threshold for vocal activity (heuristically 15%, meaning above 15% of max harmonic energy)
    threshold = 0.15
    active_frames = rmse > threshold
    
    # Smooth the boolean array (vocals don't stop and start every 10ms)
    window_size = int(2.0 * sr / hop_length) # 2 seconds window
    smoothed = np.convolve(active_frames, np.ones(window_size)/window_size, mode='same') > 0.5
    
    # 4. Convert active boolean array to start/end block regions
    regions = []
    in_region = False
    start_time = 0
    for i, active in enumerate(smoothed):
        if active and not in_region:
            start_time = times[i]
            in_region = True
        elif not active and in_region:
            end_time = times[i]
            # Must be at least 3 seconds long to be considered a structural vocal block
            if end_time - start_time >= 3.0:
                regions.append((start_time, end_time))
            in_region = False
            
    if in_region:
        regions.append((start_time, duration))
        
    # 5. Merge regions that are close together (gap < 5 seconds)
    merged_regions = []
    for r in regions:
        if not merged_regions:
            merged_regions.append(r)
        else:
            last_r = merged_regions[-1]
            if r[0] - last_r[1] < 5.0:
                # Merge
                merged_regions[-1] = (last_r[0], r[1])
            else:
                merged_regions.append(r)
                
    # 6. Apply Arrangement Rule Logic
    sections = []
    
    # Edge Case: If no vocals detected at all, return generic sections
    if not merged_regions:
        return {
            "bpm": round(avg_tempo),
            "key": key,
            "duration": round(duration, 2),
            "sections": [
                {"label": "intro", "start": 0.0, "end": min(10.0, duration/4)},
                {"label": "main", "start": min(10.0, duration/4), "end": duration - min(10.0, duration/4)},
                {"label": "outro", "start": duration - min(10.0, duration/4), "end": duration}
            ]
        }
        
    # Intro: 0.0 to first vocal start
    first_vocal_start = merged_regions[0][0]
    if first_vocal_start > 0:
        sections.append({"label": "intro", "start": 0.0, "end": float(first_vocal_start)})
        
    # Vocals and Interludes
    for i in range(len(merged_regions)):
        start, end = merged_regions[i]
        sections.append({"label": "vocal", "start": float(start), "end": float(end)})
        
        # Is there a next vocal section?
        if i < len(merged_regions) - 1:
            next_start = merged_regions[i+1][0]
            # Gap between end of current and start of next
            if next_start - end >= 5.0: # Only call it an interlude if it's a significant break > 5s
                sections.append({"label": "interlude", "start": float(end), "end": float(next_start)})
                
    # Outro: from last vocal end to song end
    last_vocal_end = merged_regions[-1][1]
    if duration - last_vocal_end > 2.0:
        sections.append({"label": "outro", "start": float(last_vocal_end), "end": float(duration)})
    else:
        # If vocal ends almost exactly at the end, extend the last section
        sections[-1]["end"] = float(duration)
        
    # Format and return nicely rounded times
    for s in sections:
        s["start"] = round(s["start"], 2)
        s["end"] = round(s["end"], 2)

    return {
        "bpm": round(avg_tempo),
        "key": key,
        "duration": round(duration, 2),
        "sections": sections
    }
