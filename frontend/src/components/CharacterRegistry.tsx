import { useEffect, useState } from 'react';
import { extractCharacters } from '../api/client';
import type { ScreenplayResponse, CharacterResponse } from '../types';

interface CharacterRegistryProps {
  screenplay: ScreenplayResponse;
}

export function CharacterRegistry({ screenplay }: CharacterRegistryProps) {
  const [characters, setCharacters] = useState<CharacterResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [charError, setCharError] = useState<string | null>(null);

  const fullText = [
    ...screenplay.scenes.map((s) => `${s.heading}\n${s.content}`),
    ...screenplay.elements.map((e) => e.text),
  ].join('\n');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCharError(null);
    extractCharacters(fullText).then((res) => {
      if (!cancelled) setCharacters(res.characters);
    }).catch((err) => {
      if (!cancelled) setCharError(err instanceof Error ? err.message : 'Failed to extract characters');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [fullText]);

  if (loading) {
    return (
      <div className="card character-registry">
        <div className="card-header">
          <div className="card-icon">{'\uD83C\uDFAD'}</div>
          <div>
            <h2 className="card-title">Characters</h2>
            <p className="card-subtitle">Identifying characters...</p>
          </div>
        </div>
        <div className="char-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} className="char-card">
              <div className="skeleton skeleton-text" style={{ width: '50%' }} />
              <div className="skeleton skeleton-text" style={{ width: '80%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (charError) {
    return (
      <div className="card character-registry">
        <div className="card-header">
          <div className="card-icon">{'\u26A0\uFE0F'}</div>
          <div>
            <h2 className="card-title">Characters</h2>
            <p className="card-subtitle text-accent">{charError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (characters.length === 0) return null;

  return (
    <div className="card character-registry">
      <div className="card-header">
        <div className="card-icon">{'\uD83C\uDFAD'}</div>
        <div>
          <h2 className="card-title">Characters</h2>
          <p className="card-subtitle">{characters.length} characters identified</p>
        </div>
      </div>
      <div className="char-grid">
        {characters.map((ch) => (
          <div key={ch.canonical_name} className="char-card">
            <div className="char-name">{ch.canonical_name}</div>
            {ch.aliases.length > 0 && (
              <div className="char-aliases">
                aka {ch.aliases.join(', ')}
              </div>
            )}
            {ch.first_appearance && (
              <div className="char-first-appearance">
                First appears: {ch.first_appearance}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
