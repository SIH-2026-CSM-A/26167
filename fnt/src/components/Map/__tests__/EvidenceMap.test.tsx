import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { EvidenceMap } from '../EvidenceMap';
import type { Evidence } from '@/types/contracts';

const mockFitBounds = vi.fn();
const mockSetFilter = vi.fn();
const mockAddSource = vi.fn();
const mockAddLayer = vi.fn();
const mockSetData = vi.fn();
const mockGetBounds = vi.fn();
const mockZoomIn = vi.fn();
const mockZoomOut = vi.fn();
const mockResize = vi.fn();
const mockRemove = vi.fn();
const mockSetStyle = vi.fn();

let mapEventHandlers: Record<string, (...args: unknown[]) => void> = {};
let layerClickHandlers: Record<string, (...args: unknown[]) => void> = {};
let mockSources: Record<string, { setData: typeof mockSetData }> = {};

vi.mock('maplibre-gl', () => {
  return {
    Map: vi.fn().mockImplementation(() => {
      return {
        on: vi.fn((event: string, ...args: unknown[]) => {
          if (typeof args[0] === 'string' && typeof args[1] === 'function') {
            layerClickHandlers[args[0]] = args[1] as (...args: unknown[]) => void;
          } else if (typeof args[0] === 'function') {
            mapEventHandlers[event] = args[0] as (...args: unknown[]) => void;
          }
        }),
        once: vi.fn((event: string, cb: (...args: unknown[]) => void) => {
          mapEventHandlers[event] = cb;
        }),
        getSource: vi.fn((id: string) => mockSources[id]),
        addSource: vi.fn((id: string, source: unknown) => {
          mockAddSource(id, source);
          mockSources[id] = { setData: mockSetData };
        }),
        addLayer: mockAddLayer,
        getLayer: vi.fn((id: string) => (id === 'evidence-selected-halo' ? {} : undefined)),
        setFilter: mockSetFilter,
        fitBounds: mockFitBounds,
        getBounds: mockGetBounds,
        zoomIn: mockZoomIn,
        zoomOut: mockZoomOut,
        resize: mockResize,
        remove: mockRemove,
        setStyle: mockSetStyle,
      };
    }),
  };
});

// Polyfill ResizeObserver for JSDOM
if (typeof window.ResizeObserver === 'undefined') {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

const sampleBBoxEvidence: Evidence[] = [
  {
    id: 'ev-bbox-101',
    tool: 'grounding_detector',
    type: 'bbox',
    payload: {
      bbox: [72.8, 18.9, 73.0, 19.1],
      label: 'Naval Vessel Anchorage',
      description: 'Moored vessel cluster',
    },
    confidence: 0.92,
    timing: 0.35,
  },
  {
    id: 'ev-bbox-102',
    tool: 'optical_detector',
    type: 'bbox',
    payload: {
      bbox: [80.1, 12.9, 80.3, 13.1],
      label: 'Harbor Cranes',
    },
    confidence: 0.89,
    timing: 0.28,
  },
];

describe('EvidenceMap with BBOX evidence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mapEventHandlers = {};
    layerClickHandlers = {};
    mockSources = {};
    mockGetBounds.mockReturnValue({
      getWest: () => 70.0,
      getSouth: () => 15.0,
      getEast: () => 75.0,
      getNorth: () => 20.0,
    });
  });

  it('initializes map, adds layers, and feeds BBOX features into satquery-evidence source', () => {
    const handleSelect = vi.fn();
    render(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId={null}
        onSelectEvidence={handleSelect}
      />
    );

    // Trigger map 'load' event
    act(() => {
      mapEventHandlers['load']?.();
    });

    expect(mockAddSource).toHaveBeenCalledWith(
      'satquery-evidence',
      expect.objectContaining({ type: 'geojson' })
    );
    expect(mockAddLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'evidence-mask-fill' })
    );
    expect(mockAddLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'evidence-boundary-line' })
    );
    expect(mockAddLayer).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'evidence-selected-halo' })
    );

    // Verify features passed to setData
    expect(mockSetData).toHaveBeenCalled();
    const loadedData = mockSetData.mock.calls[0][0];
    expect(loadedData.type).toBe('FeatureCollection');
    expect(loadedData.features).toHaveLength(2);
    expect(loadedData.features[0].id).toBe('ev-bbox-101');
    expect(loadedData.features[0].geometry.type).toBe('Polygon');
  });

  it('applies halo filter and triggers fitBounds when selectedEvidenceId is set', () => {
    const handleSelect = vi.fn();
    const { rerender } = render(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId={null}
        onSelectEvidence={handleSelect}
      />
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    // Mock viewport where ev-bbox-102 [80.1, 12.9, 80.3, 13.1] is outside
    mockGetBounds.mockReturnValue({
      getWest: () => 70.0,
      getSouth: () => 15.0,
      getEast: () => 75.0,
      getNorth: () => 20.0,
    });

    rerender(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId="ev-bbox-102"
        onSelectEvidence={handleSelect}
      />
    );

    // Halo filter updated to match selected feature
    expect(mockSetFilter).toHaveBeenCalledWith('evidence-selected-halo', [
      '==',
      ['get', 'id'],
      'ev-bbox-102',
    ]);

    // Bounding box for ev-bbox-102 is framed smoothly
    expect(mockFitBounds).toHaveBeenCalledWith(
      [
        [80.1, 12.9],
        [80.3, 13.1],
      ],
      expect.objectContaining({
        padding: 80,
        maxZoom: 16,
        duration: 1200,
        essential: true,
      })
    );
  });

  it('clears halo filter when selectedEvidenceId becomes null', () => {
    const handleSelect = vi.fn();
    const { rerender } = render(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId="ev-bbox-101"
        onSelectEvidence={handleSelect}
      />
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    rerender(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId={null}
        onSelectEvidence={handleSelect}
      />
    );

    expect(mockSetFilter).toHaveBeenCalledWith('evidence-selected-halo', [
      '==',
      ['get', 'id'],
      '',
    ]);
  });

  it('triggers onSelectEvidence when a feature on evidence-mask-fill layer is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId={null}
        onSelectEvidence={handleSelect}
      />
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    expect(layerClickHandlers['evidence-mask-fill']).toBeDefined();

    // Simulate clicking ev-bbox-101 feature
    act(() => {
      layerClickHandlers['evidence-mask-fill']({
        features: [{ properties: { id: 'ev-bbox-101' } }],
      });
    });

    expect(handleSelect).toHaveBeenCalledWith('ev-bbox-101');
  });

  it('displays EvidenceDetailCard when a BBOX feature is selected and can close it', () => {
    const handleSelect = vi.fn();
    render(
      <EvidenceMap
        evidenceList={sampleBBoxEvidence}
        selectedEvidenceId="ev-bbox-101"
        onSelectEvidence={handleSelect}
      />
    );

    expect(screen.getByText('Evidence [ev-bbox-101]')).toBeInTheDocument();
    expect(screen.getByText('Naval Vessel Anchorage')).toBeInTheDocument();

    const closeButton = screen.getByTitle('Close details');
    fireEvent.click(closeButton);

    expect(handleSelect).toHaveBeenCalledWith(null);
  });
});
