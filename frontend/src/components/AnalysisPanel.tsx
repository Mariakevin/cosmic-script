import { useCallback, useEffect, useState } from 'react';
import { generateCoverage, generateLogline, analyzeVoice, analyzePacing } from '../api/client';
import type { ScreenplayResponse, CoverageResponse, VoiceResponse, PacingResponse } from '../types';

interface AnalysisPanelProps {
  screenplay: ScreenplayResponse;
}

type AnalysisTab = 'coverage' | 'logline' | 'voice' | 'pacing';

const TABS: { key: AnalysisTab; label: string; icon: string }[] = [
  { key: 'coverage', label: 'Coverage', icon: '\uD83D\uDCCB' },
  { key: 'logline', label: 'Logline', icon: '\uD83D\uDCA1' },
  { key: 'voice', label: 'Voice', icon: '\uD83C\uDFAD' },
  { key: 'pacing', label: 'Pacing', icon: '\u26A1' },
];

function getFullText(screenplay: ScreenplayResponse): string {
  return [
    ...screenplay.scenes.map((s) => `${s.heading}\n${s.content}`),
    ...screenplay.elements.map((e) => e.text),
  ].join('\n');
}

function RatingStars({ rating }: { rating: number }) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    stars.push(
      <span key={i} className={`star ${i <= rating ? '' : 'empty'}`}>
        {'\u2605'}
      </span>
    );
  }
  return <div className="analysis-rating" aria-label={`Rating: ${rating} out of 5`}>{stars}</div>;
}

export function AnalysisPanel({ screenplay }: AnalysisPanelProps) {
  const [activeTab, setActiveTab] = useState<AnalysisTab>('coverage');
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);
  const [logline, setLogline] = useState<string>('');
  const [voice, setVoice] = useState<VoiceResponse | null>(null);
  const [pacing, setPacing] = useState<PacingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fullText = getFullText(screenplay);

  // Load coverage on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    generateCoverage(fullText)
      .then((data) => { if (!cancelled) setCoverage(data); })
      .catch(() => { if (!cancelled) setError('Failed to load coverage'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fullText]);

  const loadTab = useCallback(async (tab: AnalysisTab) => {
    setActiveTab(tab);
    setError(null);

    if (tab === 'coverage' && coverage) return;
    if (tab === 'logline' && logline) return;
    if (tab === 'voice' && voice) return;
    if (tab === 'pacing' && pacing) return;

    setLoading(true);
    try {
      if (tab === 'coverage') {
        const data = await generateCoverage(fullText);
        setCoverage(data);
      } else if (tab === 'logline') {
        const data = await generateLogline(fullText);
        setLogline(data.logline);
      } else if (tab === 'voice') {
        const data = await analyzeVoice(fullText);
        setVoice(data);
      } else if (tab === 'pacing') {
        const data = await analyzePacing(fullText);
        setPacing(data);
      }
    } catch {
      setError(`Failed to load ${tab} analysis`);
    } finally {
      setLoading(false);
    }
  }, [fullText, coverage, logline, voice, pacing]);

  const handleRegenerateLogline = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await generateLogline(fullText);
      setLogline(data.logline);
    } catch {
      setError('Failed to regenerate logline');
    } finally {
      setLoading(false);
    }
  }, [fullText]);

  return (
    <div className="card analysis-panel">
      <div className="card-header">
        <div className="card-icon">{'\uD83C\uDFA8'}</div>
        <div>
          <h2 className="card-title">Script Analysis</h2>
          <p className="card-subtitle">AI-powered insights for your screenplay</p>
        </div>
      </div>

      <div className="analysis-tabs" role="tablist" aria-label="Analysis tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`analysis-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => loadTab(tab.key)}
            role="tab"
            aria-selected={activeTab === tab.key}
            aria-controls={`panel-${tab.key}`}
          >
            <span className="analysis-tab-icon">{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className="analysis-content" role="tabpanel" id={`panel-${activeTab}`}>
        {loading && (
          <div style={{ padding: 'var(--space-lg)', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Analyzing...
          </div>
        )}

        {!loading && activeTab === 'coverage' && coverage && (
          <>
            <div className="analysis-section">
              <div className="analysis-label">Logline</div>
              <div className="analysis-text">{coverage.logline}</div>
            </div>

            <div className="analysis-section">
              <div className="analysis-label">Synopsis</div>
              <div className="analysis-text">{coverage.synopsis}</div>
            </div>

            <div className="analysis-section">
              <div className="analysis-label">Rating</div>
              <RatingStars rating={coverage.rating} />
            </div>

            {coverage.strengths.length > 0 && (
              <div className="analysis-section">
                <div className="analysis-label">Strengths</div>
                <ul className="analysis-list strengths">
                  {coverage.strengths.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}

            {coverage.weaknesses.length > 0 && (
              <div className="analysis-section">
                <div className="analysis-label">Weaknesses</div>
                <ul className="analysis-list weaknesses">
                  {coverage.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}

            <div className="analysis-section">
              <div className="analysis-label">Recommendation</div>
              <div className="analysis-recommendation">{coverage.recommendation}</div>
            </div>
          </>
        )}

        {!loading && activeTab === 'logline' && (
          <div className="analysis-section">
            <div className="analysis-label">Generated Logline</div>
            <div className="analysis-text" style={{ fontSize: '1.05rem', lineHeight: 1.7 }}>
              {logline || 'No logline generated yet.'}
            </div>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRegenerateLogline}
              style={{ marginTop: 'var(--space-md)' }}
            >
              {'\uD83D\uDD04'} Regenerate
            </button>
          </div>
        )}

        {!loading && activeTab === 'voice' && voice && (
          <>
            <div className="analysis-section">
              <div className="analysis-label">Overall Style</div>
              <div className="analysis-text">{voice.overall_style}</div>
            </div>

            {voice.characters.map((ch) => (
              <div key={ch.name} className="voice-card">
                <div className="voice-avatar">{ch.name.charAt(0)}</div>
                <div className="voice-info">
                  <div className="voice-name">{ch.name}</div>
                  <div className="voice-meta">
                    {ch.line_count} lines &middot; {ch.speaking_style} &middot; {ch.emotional_tone}
                  </div>
                  <div className="voice-bar">
                    <div
                      className="voice-bar-fill"
                      style={{ width: `${Math.min(100, ch.vocabulary_richness * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </>
        )}

        {!loading && activeTab === 'pacing' && pacing && (
          <>
            <div className="analysis-section">
              <div className="analysis-label">Overall Pacing</div>
              <div className="analysis-text">{pacing.overall_pacing}</div>
            </div>

            <div className="analysis-section">
              <div className="analysis-label">Scene Breakdown</div>
              {pacing.scenes.map((scene, i) => (
                <div key={i} className="pacing-row">
                  <div className="pacing-scene">{scene.heading}</div>
                  <div className="pacing-bar">
                    <div
                      className={`pacing-bar-fill pacing-${scene.pacing}`}
                      style={{ width: `${scene.dialogue_ratio * 100}%` }}
                    />
                  </div>
                  <div className={`pacing-label pacing-${scene.pacing}`}>
                    {scene.pacing}
                  </div>
                </div>
              ))}
            </div>

            {pacing.recommendations.length > 0 && (
              <div className="analysis-section">
                <div className="analysis-label">Recommendations</div>
                <ul className="analysis-list">
                  {pacing.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
