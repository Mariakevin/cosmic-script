import { useEffect, useState } from 'react';
import { estimatePages } from '../api/client';
import type { ScreenplayResponse, PageEstimateResponse } from '../types';

interface ScreenplayStatsProps {
  screenplay: ScreenplayResponse;
}

export function ScreenplayStats({ screenplay }: ScreenplayStatsProps) {
  const [pageEstimate, setPageEstimate] = useState<PageEstimateResponse | null>(null);

  const fullText = [
    ...screenplay.scenes.map((s) => `${s.heading}\n${s.content}`),
    ...screenplay.elements.map((e) => e.text),
  ].join('\n');

  const wordCount = fullText.split(/\s+/).filter(Boolean).length;

  useEffect(() => {
    let cancelled = false;
    estimatePages(fullText)
      .then((data) => { if (!cancelled) setPageEstimate(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [fullText]);

  return (
    <div className="screenplay-stats" role="region" aria-label="Screenplay statistics">
      {pageEstimate && (
        <div className="stat-badge">
          <span>{'\uD83D\uDCC4'}</span>
          <strong>{pageEstimate.estimated_pages}</strong> pages
          <span className="text-muted" style={{ fontSize: '0.75rem' }}>
            ({pageEstimate.confidence})
          </span>
        </div>
      )}
      <div className="stat-badge">
        <span>{'\uD83C\uDFAC'}</span>
        <strong>{screenplay.scenes.length}</strong> scenes
      </div>
      <div className="stat-badge">
        <span>{'\uD83C\uDFAD'}</span>
        <strong>{screenplay.elements.filter((e) => e.type === 'character').length}</strong> characters
      </div>
      <div className="stat-badge">
        <span>{'\uD83D\uDCDD'}</span>
        <strong>{wordCount.toLocaleString()}</strong> words
      </div>
    </div>
  );
}
