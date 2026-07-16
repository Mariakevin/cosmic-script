import { useCallback, useState } from 'react';
import { exportScreenplay } from '../api/client';
import type { ScreenplayResponse } from '../types';

interface ExportPanelProps {
  screenplay: ScreenplayResponse;
}

type ExportFormat = 'fountain' | 'txt' | 'pdf';

const FORMATS: { key: ExportFormat; label: string; icon: string; ext: string }[] = [
  { key: 'fountain', label: 'Fountain', icon: '\uD83D\uDCD6', ext: '.fountain' },
  { key: 'txt', label: 'Plain Text', icon: '\uD83D\uDCC4', ext: '.txt' },
  { key: 'pdf', label: 'PDF', icon: '\uD83D\uDCC3', ext: '.pdf' },
];

function buildRawFountain(screenplay: ScreenplayResponse): string {
  const parts: string[] = [];

  const titleLines: string[] = [];
  if (screenplay.title) titleLines.push(`Title: ${screenplay.title}`);
  if (screenplay.author) titleLines.push(`Author: ${screenplay.author}`);
  if (titleLines.length) parts.push(titleLines.join('\n'));

  const lines: string[] = [];
  if (screenplay.elements.length > 0) {
    for (const el of screenplay.elements) {
      switch (el.type) {
        case 'centered': lines.push(`>${el.text}<`); break;
        case 'section': lines.push(`# ${el.text}`); break;
        case 'synopsis': lines.push(`= ${el.text}`); break;
        case 'lyric': lines.push(`~${el.text}`); break;
        case 'page_break': lines.push('==='); break;
        default: lines.push(el.text);
      }
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

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadBase64(b64: string, filename: string, mime: string) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ExportPanel({ screenplay }: ExportPanelProps) {
  const [format, setFormat] = useState<ExportFormat>('fountain');
  const [exporting, setExporting] = useState(false);

  const rawFountain = buildRawFountain(screenplay);
  const filename = screenplay.title || 'screenplay';

  const handleDownload = useCallback(async () => {
    setExporting(true);
    try {
      if (format === 'fountain') {
        downloadBlob(rawFountain, `${filename}.fountain`, 'text/plain;charset=utf-8');
      } else if (format === 'txt') {
        const result = await exportScreenplay({ screenplay, format: 'txt' });
        downloadBlob(result.content, `${filename}.txt`, 'text/plain;charset=utf-8');
      } else if (format === 'pdf') {
        // PDF requires backend — try backend first, fallback to fountain
        try {
          const result = await exportScreenplay({ screenplay, format: 'pdf' });
          downloadBase64(result.content, `${filename}.pdf`, 'application/pdf');
        } catch {
          downloadBlob(rawFountain, `${filename}.fountain`, 'text/plain;charset=utf-8');
        }
      }
    } catch {
      // Fallback: download as fountain
      downloadBlob(rawFountain, `${filename}.fountain`, 'text/plain;charset=utf-8');
    } finally {
      setExporting(false);
    }
  }, [format, rawFountain, filename, screenplay]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(rawFountain);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = rawFountain;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
  }, [rawFountain]);

  return (
    <div className="card export-panel">
      <div className="card-header">
        <div className="card-icon">{'\uD83D\uDCE6'}</div>
        <div>
          <h2 className="card-title">Export</h2>
          <p className="card-subtitle">Download your screenplay</p>
        </div>
      </div>

      <div className="export-formats" role="radiogroup" aria-label="Export format">
        {FORMATS.map((f) => (
          <button
            key={f.key}
            className={`export-format-btn ${format === f.key ? 'active' : ''}`}
            onClick={() => setFormat(f.key)}
            role="radio"
            aria-checked={format === f.key}
          >
            <span className="export-format-icon">{f.icon}</span>
            <span className="export-format-name">{f.label}</span>
            <span className="export-format-ext">{f.ext}</span>
          </button>
        ))}
      </div>

      <div className="export-actions">
        <button
          className="btn btn-primary"
          onClick={handleDownload}
          disabled={exporting}
        >
          {exporting ? 'Exporting...' : `Download ${format.toUpperCase()}`}
        </button>
        <button
          className="btn btn-secondary"
          onClick={handleCopy}
        >
          {'\uD83D\uDCB5'} Copy Fountain
        </button>
      </div>
    </div>
  );
}
