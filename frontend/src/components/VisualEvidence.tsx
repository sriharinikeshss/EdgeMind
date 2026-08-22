/**
 * VisualEvidence component — Phase 5 (M6).
 *
 * Displays scanned documents / P&ID engineering drawings with:
 * - Interactive bounding box overlays
 * - Anti-hallucination low-confidence region alerts
 * - Key-value pair and component grounding tables
 */
import React, { useState } from 'react';
import './VisualEvidence.css';

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WordBox {
  text: string;
  confidence: number;
  bbox: BoundingBox;
}

export interface LowConfidenceRegion {
  text: string;
  confidence: number;
  bbox: BoundingBox;
  reason?: string;
}

export interface MultimodalResult {
  status: string;
  document_type: string;
  average_confidence: number;
  low_confidence_regions?: LowConfidenceRegion[];
  key_values?: Record<string, string>;
  components?: Array<{ tag: string; type: string; confidence: number; bbox?: BoundingBox }>;
  instruments?: Array<{ tag: string; type: string; prefix?: string; confidence: number; bbox?: BoundingBox }>;
  full_text?: string;
  thumbnail_b64?: string;
}

interface VisualEvidenceProps {
  imageSrc?: string;
  result: MultimodalResult;
}

export const VisualEvidence: React.FC<VisualEvidenceProps> = ({ imageSrc, result }) => {
  const [activeTab, setActiveTab] = useState<'boxes' | 'data'>('data');

  const confPercent = Math.round((result.average_confidence || 0) * 100);
  const hasLowConf = result.low_confidence_regions && result.low_confidence_regions.length > 0;

  return (
    <div className="visual-evidence-container">
      <div className="visual-evidence-header">
        <div className="header-badge">
          <span className="doc-type-icon">
            {result.document_type === 'engineering_drawing' ? '📐' : '📄'}
          </span>
          <span className="doc-type-text">
            {result.document_type === 'engineering_drawing' ? 'P&ID Schematic Drawing' : 'Scanned Document Report'}
          </span>
        </div>
        <div className={`confidence-badge ${confPercent >= 80 ? 'high' : confPercent >= 60 ? 'medium' : 'low'}`}>
          OCR Confidence: <strong>{confPercent}%</strong>
        </div>
        <div className="tab-buttons">
          <button
            className={`tab-btn ${activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('data')}
          >
            Structured Data
          </button>
          {result.low_confidence_regions && (
            <button
              className={`tab-btn ${activeTab === 'boxes' ? 'active' : ''}`}
              onClick={() => setActiveTab('boxes')}
            >
              Flags ({result.low_confidence_regions.length})
            </button>
          )}
        </div>
      </div>

      {hasLowConf && (
        <div className="anti-hallucination-banner">
          ⚠️ <strong>Anti-Hallucination Guardrail:</strong> {result.low_confidence_regions?.length} region(s) scored below 70% OCR confidence and are flagged for manual verification.
        </div>
      )}

      {imageSrc && (
        <div className="image-preview-wrapper">
          <img src={imageSrc} alt="Multimodal Evidence" className="evidence-image" />
        </div>
      )}

      <div className="visual-evidence-body">
        {activeTab === 'data' && (
          <div className="data-tab-content">
            {result.key_values && Object.keys(result.key_values).length > 0 && (
              <div className="evidence-section">
                <h4>Extracted Fields</h4>
                <div className="key-value-grid">
                  {Object.entries(result.key_values).map(([k, v]) => (
                    <div key={k} className="kv-item">
                      <span className="kv-key">{k}</span>
                      <span className="kv-val">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.components && result.components.length > 0 && (
              <div className="evidence-section">
                <h4>Equipment Components ({result.components.length})</h4>
                <div className="tag-list">
                  {result.components.map((c, i) => (
                    <span key={i} className="tag-chip component">
                      🏷️ {c.tag} <small>({Math.round(c.confidence * 100)}%)</small>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {result.instruments && result.instruments.length > 0 && (
              <div className="evidence-section">
                <h4>Instruments & Transmitters ({result.instruments.length})</h4>
                <div className="tag-list">
                  {result.instruments.map((inst, i) => (
                    <span key={i} className="tag-chip instrument">
                      📡 {inst.tag} <small>({Math.round(inst.confidence * 100)}%)</small>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'boxes' && result.low_confidence_regions && (
          <div className="flags-tab-content">
            <div className="flagged-list">
              {result.low_confidence_regions.map((flag, i) => (
                <div key={i} className="flagged-item">
                  <div className="flagged-token">
                    <code>"{flag.text}"</code>
                    <span className="flag-conf">{Math.round(flag.confidence * 100)}%</span>
                  </div>
                  <div className="flag-reason">{flag.reason || 'Confidence score below threshold.'}</div>
                  <div className="flag-coords">
                    BBox: [x:{flag.bbox.x}, y:{flag.bbox.y}, w:{flag.bbox.w}, h:{flag.bbox.h}]
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
