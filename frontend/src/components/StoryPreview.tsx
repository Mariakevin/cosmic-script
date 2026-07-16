import type { UploadResponse } from '../types';

interface StoryPreviewProps {
  data: UploadResponse;
}

export function StoryPreview({ data }: StoryPreviewProps) {
  return (
    <div className="card story-preview">
      <div className="card-header">
        <div className="card-icon">
          {'\uD83D\uDCD6'}
        </div>
        <div>
          <h2 className="card-title">Story Preview</h2>
          <p className="card-subtitle">{data.filename}</p>
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-badge">
          <span>{'\uD83D\uDCDD'}</span>
          <strong>{data.word_count.toLocaleString()}</strong> words
        </div>
        <div className="stat-badge">
          <span>{'\uD83D\uDCC4'}</span>
          <strong>{data.char_count.toLocaleString()}</strong> characters
        </div>
      </div>

      <details>
        <summary>Preview Text</summary>
        <pre className="preview-text">{data.text.slice(0, 2000)}</pre>
      </details>
    </div>
  );
}
