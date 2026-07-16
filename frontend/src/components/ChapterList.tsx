import { useEffect, useState } from 'react';
import { extractChapters } from '../api/client';
import type { ChapterResponse } from '../types';

interface ChapterListProps {
  text: string;
}

export function ChapterList({ text }: ChapterListProps) {
  const [chapters, setChapters] = useState<ChapterResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [chapterError, setChapterError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setChapterError(null);
    extractChapters(text).then((res) => {
      if (!cancelled) setChapters(res.chapters);
    }).catch((err) => {
      if (!cancelled) setChapterError(err instanceof Error ? err.message : 'Failed to extract chapters');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [text]);

  if (loading) {
    return (
      <div className="card chapter-list">
        <div className="card-header">
          <div className="card-icon">{'\uD83D\uDCC5'}</div>
          <div>
            <h2 className="card-title">Chapters</h2>
            <p className="card-subtitle">Extracting chapters...</p>
          </div>
        </div>
        <div className="chapter-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} className="chapter-item">
              <div className="skeleton skeleton-text" style={{ width: 32, height: 32 }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" style={{ width: '40%' }} />
                <div className="skeleton skeleton-text" style={{ width: '80%' }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (chapterError) {
    return (
      <div className="card chapter-list">
        <div className="card-header">
          <div className="card-icon">{'\u26A0\uFE0F'}</div>
          <div>
            <h2 className="card-title">Chapters</h2>
            <p className="card-subtitle text-accent">{chapterError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (chapters.length === 0) return null;

  return (
    <div className="card chapter-list">
      <div className="card-header">
        <div className="card-icon">{'\uD83D\uDCC5'}</div>
        <div>
          <h2 className="card-title">Chapters</h2>
          <p className="card-subtitle">{chapters.length} chapters detected</p>
        </div>
      </div>
      <div className="chapter-grid">
        {chapters.map((ch) => (
          <div key={ch.number} className="chapter-item">
            <div className="chapter-number">{ch.number}</div>
            <div className="chapter-info">
              <div className="chapter-title">
                {ch.title ? ch.title : `Chapter ${ch.number}`}
              </div>
              <div className="chapter-preview">{ch.text_preview}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
