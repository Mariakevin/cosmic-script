import { useCallback, useState } from 'react';
import { exportScreenplay } from '../api/client';
import type { ScreenplayResponse } from '../types';

interface FountainPreviewProps {
  screenplay: ScreenplayResponse;
}

function getElementClass(type: string): string {
  switch (type) {
    case 'scene_heading':
      return 'fp-scene-heading';
    case 'character':
      return 'fp-character';
    case 'dialogue':
      return 'fp-dialogue';
    case 'parenthetical':
      return 'fp-parenthetical';
    case 'transition':
      return 'fp-transition';
    case 'action':
      return 'fp-action';
    case 'centered':
      return 'fp-centered';
    case 'section':
      return 'fp-section';
    case 'synopsis':
      return 'fp-synopsis';
    case 'lyric':
      return 'fp-lyric';
    case 'page_break':
      return 'fp-page-break';
    default:
      return 'fp-action';
  }
}

function renderElement(type: string, text: string): string {
  switch (type) {
    case 'centered':
      return `>${text}<`;
    case 'section':
      return `# ${text}`;
    case 'synopsis':
      return `= ${text}`;
    case 'lyric':
      return `~${text}`;
    case 'page_break':
      return '===';
    default:
      return text;
  }
}

export function FountainPreview({ screenplay }: FountainPreviewProps) {
  const [copied, setCopied] = useState(false);

  // Build raw Fountain text for copy/download
  const rawFountain = buildRawFountain(screenplay);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(rawFountain);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = rawFountain;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [rawFountain]);

  const handleDownloadFountain = useCallback(() => {
    const blob = new Blob([rawFountain], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${screenplay.title || 'screenplay'}.fountain`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [rawFountain, screenplay.title]);

  const handleDownloadPdf = useCallback(async () => {
    try {
      const result = await exportScreenplay({
        screenplay,
        format: 'txt',
      });
      // For now, download as .txt since PDF needs backend
      const blob = new Blob([result.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${screenplay.title || 'screenplay'}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Fallback: download raw text
      const blob = new Blob([rawFountain], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${screenplay.title || 'screenplay'}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }, [rawFountain, screenplay]);

  return (
    <div className="card fountain-preview">
      <div className="fp-header">
        <div className="card-header" style={{ marginBottom: 0 }}>
          <div className="card-icon">
            {'\uD83C\uDFAC'}
          </div>
          <div>
            <h2 className="card-title">Screenplay</h2>
            <p className="card-subtitle">
              {screenplay.elements.length > 0
                ? `${screenplay.elements.length} elements`
                : `${screenplay.scenes.length} scenes`}
            </p>
          </div>
        </div>
        <div className="fp-actions">
          <button
            className={`fp-btn ${copied ? 'copied' : ''}`}
            onClick={handleCopy}
            aria-label="Copy Fountain text to clipboard"
          >
            {copied ? '\u2713 Copied!' : '\uD83D\uDCB5 Copy'}
          </button>
          <button
            className="fp-btn"
            onClick={handleDownloadFountain}
            aria-label="Download as .fountain file"
          >
            {'\uD83D\uDCE6'} .fountain
          </button>
          <button
            className="fp-btn"
            onClick={handleDownloadPdf}
            aria-label="Download as text file"
          >
            {'\uD83D\uDCC4'} .txt
          </button>
        </div>
      </div>

      {screenplay.title && <h3 className="fp-title">{screenplay.title}</h3>}
      {screenplay.author && <p className="fp-author">by {screenplay.author}</p>}

      <div className="fp-content">
        {screenplay.elements.length > 0 ? (
          screenplay.elements.map((el, idx) => (
            <div
              key={idx}
              className={`fp-element ${getElementClass(el.type)}`}
            >
              {renderElement(el.type, el.text)}
            </div>
          ))
        ) : (
          screenplay.scenes.map((scene, idx) => (
            <div key={idx} className="fp-scene-block">
              <div className="fp-element fp-scene-heading">{scene.heading}</div>
              <div className="fp-element fp-action">{scene.content}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function buildRawFountain(screenplay: ScreenplayResponse): string {
  const parts: string[] = [];

  // Title page
  const titleLines: string[] = [];
  if (screenplay.title) titleLines.push(`Title: ${screenplay.title}`);
  if (screenplay.author) titleLines.push(`Author: ${screenplay.author}`);
  if (titleLines.length) parts.push(titleLines.join('\n'));

  // Elements
  const lines: string[] = [];
  if (screenplay.elements.length > 0) {
    for (const el of screenplay.elements) {
      lines.push(renderElement(el.type, el.text));
    }
  } else {
    for (const scene of screenplay.scenes) {
      lines.push(scene.heading);
      lines.push('');
      lines.push(scene.content);
    }
  }
  if (lines.length) parts.push(lines.join('\n'));

  return parts.join('\n\n').trim();
}
