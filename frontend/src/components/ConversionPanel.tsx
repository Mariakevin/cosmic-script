import { useCallback, useState, useEffect } from 'react';
import { convertToScreenplay, getGenres } from '../api/client';
import type { ScreenplayResponse, GenreInfo } from '../types';

interface ConversionPanelProps {
  text: string;
  onConvert: (data: ScreenplayResponse) => void;
  onError: (msg: string) => void;
}

export function ConversionPanel({ text, onConvert, onError }: ConversionPanelProps) {
  const [converting, setConverting] = useState(false);
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [genre, setGenre] = useState('');
  const [genres, setGenres] = useState<GenreInfo[]>([]);

  useEffect(() => {
    getGenres().then((data) => setGenres(data.genres)).catch(() => {});
  }, []);

  const handleConvert = useCallback(async () => {
    setConverting(true);
    try {
      const data = await convertToScreenplay({
        text,
        title: title || undefined,
        author: author || undefined,
        genre: genre || undefined,
      });
      onConvert(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Conversion failed';
      onError(msg);
    } finally {
      setConverting(false);
    }
  }, [text, title, author, genre, onConvert, onError]);

  return (
    <div className="card conversion-panel">
      <div className="card-header">
        <div className="card-icon">
          {converting ? '\u23F3' : '\u2728'}
        </div>
        <div>
          <h2 className="card-title">Convert to Screenplay</h2>
          <p className="card-subtitle">AI-powered conversion with automatic model selection</p>
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-title">Story Details</div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="title">Title (optional)</label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="My Screenplay"
            />
          </div>
          <div className="form-group">
            <label htmlFor="author">Author (optional)</label>
            <input
              id="author"
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Your Name"
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <div className="form-section-title">Conversion Settings</div>
        <div className="form-group">
          <label htmlFor="genre">Genre Style</label>
          <select id="genre" value={genre} onChange={(e) => setGenre(e.target.value)}>
            <option value="">Classic (default)</option>
            {genres.map((g) => (
              <option key={g.name} value={g.name}>
                {g.name.charAt(0).toUpperCase() + g.name.slice(1)} &mdash; {g.description}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        className={`btn btn-primary ${converting ? 'btn-loading' : ''}`}
        onClick={handleConvert}
        disabled={converting}
      >
        {converting ? 'Converting...' : 'Start Conversion'}
      </button>
    </div>
  );
}
