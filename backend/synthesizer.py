import librosa
import numpy as np
from scipy.io import wavfile

def get_freq(note, octave=4):
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    n = keys.index(note) + (octave - 4) * 12
    return 261.63 * (2 ** (n / 12.0))

def generate_tone(freq, duration, sr=22050):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = 0.5 * np.sin(2 * np.pi * freq * t)
    
    attack = int(sr * 0.1)
    release = int(sr * 0.2)
    if len(wave) > attack + release:
        wave[:attack] *= np.linspace(0, 1, attack)
        wave[-release:] *= np.linspace(1, 0, release)
    return wave

def generate_chord_from_chroma(chroma_vector, duration, sr=22050):
    # Isolate the exact top 3 pitches playing in the original audio at this moment
    top_indices = np.argsort(chroma_vector)[-3:]
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    chord_notes = [keys[i] for i in top_indices]
    
    chord_len = int(sr * duration)
    chord = np.zeros(chord_len)
    for note in chord_notes:
        chord += generate_tone(get_freq(note, 4), duration, sr)[:chord_len]
        
    return chord / len(chord_notes) if len(chord_notes) > 0 else chord

def generate_drum(duration, sr=22050):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    freqs = np.linspace(150, 40, len(t))
    kick = 0.8 * np.sin(2 * np.pi * freqs * t) * np.exp(-15 * t)
    return kick

def generate_backing_track(original_audio_path, sections, bpm, filepath):
    """
    Analyzes the original audio to extract true chords (chroma) and synthesizes a matching track.
    """
    sr = 22050
    # Load original audio to extract the melodic blueprint
    y, _ = librosa.load(original_audio_path, sr=sr, mono=True)
    
    # Extract chroma map (12 pitch classes over time)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    
    if bpm <= 0 or bpm > 250: bpm = 120
    beat_duration = 60.0 / bpm
    
    full_audio = []
    
    for sec in sections:
        sec_start = sec.get('start_time', 0.0)
        sec_end = sec.get('end_time', 0.0)
        label = sec.get('section_label', 'main').lower()
        sec_dur = sec_end - sec_start
        if sec_dur <= 0: continue
        
        num_beats = int(np.ceil(sec_dur / beat_duration))
        sec_audio = []
        
        for be in range(num_beats):
            beat_start_time = sec_start + (be * beat_duration)
            beat_end_time = beat_start_time + beat_duration
            
            # Map physical seconds back to the Librosa Chroma Frames
            frame_start = int(librosa.time_to_frames(beat_start_time, sr=sr))
            frame_end = int(librosa.time_to_frames(beat_end_time, sr=sr))
            
            frame_start = max(0, min(frame_start, chroma.shape[1] - 1))
            frame_end = max(1, min(frame_end, chroma.shape[1]))
            if frame_start >= frame_end: frame_end = frame_start + 1
            
            # Identify dominant chords during this specific beat
            beat_chroma = np.mean(chroma[:, frame_start:frame_end], axis=1)
            
            # Synthesize accurate chord
            beat_audio = generate_chord_from_chroma(beat_chroma, beat_duration, sr)
            
            # Layer drums based on analytical section blocks
            if label in ['vocal', 'main']:
                drum = generate_drum(min(0.2, beat_duration), sr)
                drumbeat = np.zeros(len(beat_audio))
                drumbeat[:min(len(drum), len(drumbeat))] = drum[:min(len(drum), len(drumbeat))]
                beat_audio = beat_audio * 0.6 + drumbeat * 0.4
            elif label == 'interlude':
                if be % 2 != 0:
                    drum = generate_drum(min(0.2, beat_duration), sr)
                    beat_audio = np.zeros(len(beat_audio))
                    beat_audio[:min(len(drum), len(beat_audio))] = drum[:min(len(drum), len(beat_audio))]
                else:
                    beat_audio = np.zeros(len(beat_audio))
            elif label == 'outro':
                fade = np.linspace(1, 0.4, len(beat_audio))
                beat_audio *= fade
                    
            sec_audio.extend(beat_audio)
            
        # Strict duration trimming
        sec_audio = np.array(sec_audio)[:int(sec_dur * sr)]
        full_audio.extend(sec_audio)
        
    full_audio = np.array(full_audio)
    
    # Anti-clipping normalization
    if np.max(np.abs(full_audio)) > 0:
        full_audio = full_audio / np.max(np.abs(full_audio))
        
    full_audio_int16 = np.int16(full_audio * 32767)
    wavfile.write(filepath, sr, full_audio_int16)
    return filepath
