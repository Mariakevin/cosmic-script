import { Component, useState } from 'react';
import './App.css';
import { FileUpload } from './components/FileUpload';
import { StoryPreview } from './components/StoryPreview';
import { ChapterList } from './components/ChapterList';
import { ConversionPanel } from './components/ConversionPanel';
import { FountainPreview } from './components/FountainPreview';
import { CharacterRegistry } from './components/CharacterRegistry';
import type { UploadResponse, ScreenplayResponse } from './types';

type AppStep = 'upload' | 'preview' | 'result';

// ── Error Boundary ──────────────────────────────────────────────────────

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <p className="error-boundary-message">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <div className="error-boundary-actions">
            <button onClick={this.handleReset}>Try Again</button>
            <a
              href={`https://github.com/cosmic-script/cosmic-script/issues/new?title=UI+Error:+${encodeURIComponent(this.state.error?.message || '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="report-link"
            >
              Report Issue
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// ── Step Indicator ──────────────────────────────────────────────────────

const STEPS = [
  { key: 'upload' as const, label: 'Upload', number: 1 },
  { key: 'preview' as const, label: 'Configure', number: 2 },
  { key: 'result' as const, label: 'Result', number: 3 },
];

function StepIndicator({ current }: { current: AppStep }) {
  const currentIdx = STEPS.findIndex((s) => s.key === current);

  return (
    <nav className="step-indicator" aria-label="Conversion progress">
      {STEPS.map((step, idx) => (
        <div key={step.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            className={`step ${idx === currentIdx ? 'active' : ''} ${idx < currentIdx ? 'completed' : ''}`}
          >
            <span className="step-number">
              {idx < currentIdx ? '\u2713' : step.number}
            </span>
            <span>{step.label}</span>
          </div>
          {idx < STEPS.length - 1 && (
            <div className={`step-connector ${idx < currentIdx ? 'completed' : ''}`} />
          )}
        </div>
      ))}
    </nav>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────

function App() {
  const [step, setStep] = useState<AppStep>('upload');
  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [screenplay, setScreenplay] = useState<ScreenplayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUploadComplete = (data: UploadResponse) => {
    setUploadData(data);
    setStep('preview');
  };

  const handleConvertComplete = (data: ScreenplayResponse) => {
    setScreenplay(data);
    setStep('result');
  };

  const handleError = (msg: string) => {
    setError(msg);
  };

  const handleReset = () => {
    setStep('upload');
    setUploadData(null);
    setScreenplay(null);
    setError(null);
  };

  return (
    <ErrorBoundary>
      <div className="app">
        <header className="app-header">
          <h1>Cosmic Script</h1>
          <p>Transform narratives into screenplays with AI</p>
        </header>

        <main className="app-main">
          <StepIndicator current={step} />

          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}

          {step === 'upload' && (
            <FileUpload
              onUploadComplete={handleUploadComplete}
              onError={handleError}
            />
          )}

          {step === 'preview' && uploadData && (
            <div className="preview-step">
              <StoryPreview data={uploadData} />
              <ChapterList text={uploadData.text} />
              <ConversionPanel
                text={uploadData.text}
                onConvert={handleConvertComplete}
                onError={handleError}
              />
              <button className="btn btn-ghost" onClick={handleReset}>
                Upload Another
              </button>
            </div>
          )}

          {step === 'result' && screenplay && (
            <div className="result-step">
              <FountainPreview screenplay={screenplay} />
              <CharacterRegistry screenplay={screenplay} />
              <button className="btn btn-ghost" onClick={handleReset}>
                Convert Another
              </button>
            </div>
          )}
        </main>

        <footer className="app-footer">
          <p>
            Cosmic Script &mdash; Open-source screenplay converter
            {' \u00b7 '}
            <a href="https://github.com/mubaidr/cosmic-script" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
          </p>
        </footer>
      </div>
    </ErrorBoundary>
  );
}

export default App;
