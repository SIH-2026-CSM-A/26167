import { vi, describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { SatQueryProvider } from '@/context/SatQueryProvider';
import { ChatPage } from '@/pages/ChatPage';
import { useSatQuery } from '@/hooks/useSatQuery';
import type { Answer, Evidence } from '@/types/contracts';

const mockFitBounds = vi.fn();
const mockSetFilter = vi.fn();
const mockAddSource = vi.fn();
const mockAddLayer = vi.fn();
const mockSetData = vi.fn();
const mockGetBounds = vi.fn();

let mapEventHandlers: Record<string, (...args: unknown[]) => void> = {};
let layerClickHandlers: Record<string, (...args: unknown[]) => void> = {};
let mockSources: Record<string, { setData: typeof mockSetData }> = {};

vi.mock('maplibre-gl', () => ({
  Map: vi.fn().mockImplementation(() => ({
    on: vi.fn((event: string, ...args: unknown[]) => {
      if (event === 'click' && typeof args[0] === 'string' && typeof args[1] === 'function') {
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
    getLayer: vi.fn((id: string) =>
      id === 'evidence-selected-halo' || id === 'evidence-hover-halo' ? {} : undefined
    ),
    setFilter: mockSetFilter,
    fitBounds: mockFitBounds,
    getBounds: mockGetBounds,
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    resize: vi.fn(),
    remove: vi.fn(),
    setStyle: vi.fn(),
    getCanvas: vi.fn(() => ({ style: {} })),
  })),
}));

if (typeof window.ResizeObserver === 'undefined') {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

const sampleEvidence: Evidence[] = [
  {
    id: 'ev-bbox-101',
    tool: 'grounding_detector',
    type: 'bbox',
    payload: { bbox: [72.8, 18.9, 73.0, 19.1], label: 'Naval Anchorage' },
    confidence: 0.94,
    timing: 0.3,
  },
  {
    id: 'ev-bbox-102',
    tool: 'optical_detector',
    type: 'bbox',
    payload: { bbox: [80.1, 12.9, 80.3, 13.1], label: 'Harbor Cranes' },
    confidence: 0.91,
    timing: 0.25,
  },
];

const sampleAnswer: Answer = {
  text: 'Detected moored vessels in anchorage [ev-bbox-101].\n\nFurther north, two harbor cranes were identified [ev-bbox-102].',
  confidence: 0.92,
  evidence: sampleEvidence,
  abstained: false,
  abstention_reason: null,
  trace: {
    trace_id: 'trace-interactivity-test',
    steps: [],
    created_at: new Date().toISOString(),
  },
};

const InteractivityHarness: React.FC = () => {
  const { loadAnswer } = useSatQuery();
  React.useEffect(() => {
    loadAnswer(sampleAnswer, 'Survey harbor activity');
  }, [loadAnswer]);
  return <ChatPage />;
};

describe('Map <-> Chat Evidence Interactivity (LIKI-007)', () => {
  let scrollIntoViewMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mapEventHandlers = {};
    layerClickHandlers = {};
    mockSources = {};
    scrollIntoViewMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock;
    mockGetBounds.mockReturnValue({
      getWest: () => 70.0,
      getSouth: () => 15.0,
      getEast: () => 85.0,
      getNorth: () => 25.0,
    });
  });

  it('citation hover dispatches geometry highlight state to EvidenceMap', () => {
    render(
      <SatQueryProvider>
        <InteractivityHarness />
      </SatQueryProvider>
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    const [chip101] = screen.getAllByTestId('citation-chip-ev-bbox-101');
    expect(chip101).toBeInTheDocument();

    act(() => {
      fireEvent.mouseEnter(chip101);
    });

    expect(mockSetFilter).toHaveBeenCalledWith('evidence-hover-halo', [
      '==',
      ['get', 'id'],
      'ev-bbox-101',
    ]);
    expect(chip101.className).toContain('bg-amber-500');
  });

  it('hover exit properly cleans up highlight state', () => {
    render(
      <SatQueryProvider>
        <InteractivityHarness />
      </SatQueryProvider>
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    const [chip101] = screen.getAllByTestId('citation-chip-ev-bbox-101');

    act(() => {
      fireEvent.mouseEnter(chip101);
    });
    expect(mockSetFilter).toHaveBeenCalledWith('evidence-hover-halo', [
      '==',
      ['get', 'id'],
      'ev-bbox-101',
    ]);

    act(() => {
      fireEvent.mouseLeave(chip101);
    });

    expect(mockSetFilter).toHaveBeenCalledWith('evidence-hover-halo', [
      '==',
      ['get', 'id'],
      '',
    ]);
  });

  it('EvidenceMap geometry click triggers scroll-into-view and highlight style on the corresponding chat paragraph', () => {
    render(
      <SatQueryProvider>
        <InteractivityHarness />
      </SatQueryProvider>
    );

    act(() => {
      mapEventHandlers['load']?.();
    });

    const paragraphs = screen.getAllByTestId('citing-paragraph');
    expect(paragraphs).toHaveLength(2);

    expect(layerClickHandlers['evidence-mask-fill']).toBeDefined();

    act(() => {
      layerClickHandlers['evidence-mask-fill']({
        features: [{ properties: { id: 'ev-bbox-102' } }],
      });
    });

    expect(paragraphs[1]).toHaveAttribute('data-highlighted', 'true');
    expect(paragraphs[1].className).toContain('border-cyan-400');
    expect(paragraphs[1].className).toContain('ring-2');

    expect(paragraphs[0]).toHaveAttribute('data-highlighted', 'false');

    expect(scrollIntoViewMock).toHaveBeenCalledWith(
      expect.objectContaining({ behavior: 'smooth' })
    );
  });
});
