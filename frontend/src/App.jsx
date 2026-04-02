import { useState, useRef, useEffect, useCallback } from 'react';
import gsap from 'gsap';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { UploadCloud, FileAudio, X, Music, Play, Pause, Loader2, Disc } from 'lucide-react';
import './index.css';

const PRESETS = [
  { id: 'calm_piano', label: 'Calm Piano' },
  { id: 'flute_cover', label: 'Flute Cover' },
  { id: 'minimal_acoustic', label: 'Minimal Acoustic' }
];

function App() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [preset, setPreset] = useState('calm_piano');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const titleRef = useRef(null);
  const dashboardRef = useRef(null);
  const waveformRef = useRef(null);
  const wavesurfer = useRef(null);
  const wsRegions = useRef(null);

  // GSAP Initial Animation
  useEffect(() => {
    gsap.fromTo(
      titleRef.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' }
    );
    gsap.fromTo(
      dashboardRef.current,
      { y: 40, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, delay: 0.2, ease: 'power3.out' }
    );
  }, []);

  // Initialize WaveSurfer when file is selected
  useEffect(() => {
    if (file && waveformRef.current) {
      // Destroy previous instance
      if (wavesurfer.current) {
        wavesurfer.current.destroy();
      }

      wavesurfer.current = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#4f46e5',
        progressColor: '#8b5cf6',
        cursorColor: '#ec4899',
        barWidth: 2,
        barGap: 2,
        barRadius: 3,
        height: 128,
      });

      // Initialize Regions plugin
      wsRegions.current = wavesurfer.current.registerPlugin(RegionsPlugin.create());

      const objectUrl = URL.createObjectURL(file);
      wavesurfer.current.load(objectUrl);

      wavesurfer.current.on('finish', () => setIsPlaying(false));
      wavesurfer.current.on('ready', () => {
        // Waveform is ready, we can clear loading states if needed
      });

      return () => {
        if (wavesurfer.current) {
          wavesurfer.current.destroy();
          wavesurfer.current = null;
          wsRegions.current = null;
        }
        URL.revokeObjectURL(objectUrl);
      };
    }
  }, [file]);

  const togglePlay = () => {
    if (wavesurfer.current) {
      wavesurfer.current.playPause();
      setIsPlaying(wavesurfer.current.isPlaying());
    }
  };

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileSelect = (f) => {
    if (f.type.startsWith('audio/')) {
      setFile(f);
      setAnalysisResult(null); // Reset results on new file
    } else {
      alert("Please upload an audio file (MP3, WAV, etc.)");
    }
  };

  const removeFile = () => {
    setFile(null);
    setAnalysisResult(null);
  };

  const handleAnalyze = async () => {
    if (!file) return;

    setIsAnalyzing(true);
    
    // Create FormData
    const formData = new FormData();
    formData.append('file', file);
    formData.append('style_preset', preset);

    try {
      // This will be calling our FastAPI backend
      const response = await fetch('http://localhost:8000/api/v1/analyze', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setAnalysisResult(data);
        
        // Add Regions to Wavesurfer
        if (wsRegions.current && data.sections) {
          wsRegions.current.clearRegions();
          data.sections.forEach(sec => {
            let color = 'rgba(255, 255, 255, 0.1)';
            if (sec.label === 'intro') color = 'rgba(59, 130, 246, 0.4)'; // Blue
            else if (sec.label === 'vocal') color = 'rgba(168, 85, 247, 0.4)'; // Purple
            else if (sec.label === 'interlude') color = 'rgba(236, 72, 153, 0.4)'; // Pink
            else if (sec.label === 'outro') color = 'rgba(16, 185, 129, 0.4)'; // Green

            wsRegions.current.addRegion({
              start: sec.start,
              end: sec.end,
              content: sec.label.toUpperCase(),
              color: color,
              drag: false,
              resize: false
            });
          });
        }
        
        // Scroll down natively instead of GSAP to avoid needing ScrollToPlugin
        setTimeout(() => {
          document.querySelector('.results-panel')?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } else {
        alert("Analysis failed: " + (data.detail || data.message));
      }
    } catch (err) {
      console.error(err);
      alert("Failed to connect to backend. Make sure FastAPI is running on port 8000.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="app-container">
      <header className="navbar">
        <div className="logo">
          <Disc className="text-brand-primary" size={24} />
          Song2Cover
        </div>
      </header>
      
      <main className="main-content">
        <div ref={titleRef}>
          <h1 className="hero-title">
            Rearrange Your Music
          </h1>
          <p className="hero-subtitle">
            Upload an original song and automatically generate a simplified backing track arrangement for your covers.
          </p>
        </div>

        <div className="dashboard-panel" ref={dashboardRef}>
          
          {!file ? (
            <div 
              className={`upload-zone ${dragging ? 'drag-active' : ''}`}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => document.getElementById('fileUpload').click()}
            >
              <UploadCloud className="upload-icon" />
              <div>
                <p className="upload-text">Drag & drop your audio file</p>
                <p className="upload-subtext">or click to browse from your computer (MP3, WAV)</p>
              </div>
              <input 
                id="fileUpload" 
                type="file" 
                accept="audio/*" 
                className="hidden" 
                style={{ display: 'none' }}
                onChange={(e) => {
                  if(e.target.files && e.target.files[0]) handleFileSelect(e.target.files[0]);
                }}
              />
            </div>
          ) : (
            <div className="file-info">
              <div className="file-name">
                <FileAudio size={20} className="text-brand-primary" />
                {file.name}
              </div>
              <button className="file-remove" onClick={removeFile} title="Remove file">
                <X size={20} />
              </button>
            </div>
          )}

          {file && (
            <div className="waveform-section">
              <div className="waveform-container" ref={waveformRef}></div>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
                <button 
                  onClick={togglePlay} 
                  style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)', borderRadius: '50%', width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'white' }}
                >
                  {isPlaying ? <Pause size={20} /> : <Play size={20} style={{ marginLeft: '4px' }} />}
                </button>
              </div>
            </div>
          )}

          <div className="controls-area">
            <div className="preset-selector">
              <h3 className="preset-title">Select Output Style</h3>
              <div className="preset-options">
                {PRESETS.map(p => (
                  <button 
                    key={p.id}
                    className={`preset-btn ${preset === p.id ? 'active' : ''}`}
                    onClick={() => setPreset(p.id)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <button 
              className="action-btn" 
              onClick={handleAnalyze}
              disabled={!file || isAnalyzing}
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="spinner" size={20} />
                  Analyzing Arrangement...
                </>
              ) : (
                <>
                  <Music size={20} />
                  Generate Arrangement
                </>
              )}
            </button>
          </div>

          {analysisResult && (
            <div className="results-panel">
              <h3 className="results-title">
                <Disc size={20} />
                Arrangement Plan
              </h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                {analysisResult.message || `Analyzed ${analysisResult.filename}`}
              </p>
              
              <div className="section-list">
                {analysisResult.sections?.map((section, idx) => (
                  <div key={idx} className="section-item">
                    <span className="section-label">{section.label}</span>
                    <span className="section-time">
                      {formatTime(section.start)} - {formatTime(section.end)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

export default App;
