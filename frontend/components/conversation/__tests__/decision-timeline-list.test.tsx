import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import React from "react";
import type { Mock } from "vitest";

vi.mock("@/hooks/use-decision-timeline", () => ({
  useDecisionTimeline: vi.fn(),
}));

// Stub Vaul drawer to avoid portal/animation issues in jsdom
vi.mock("@/components/ui/drawer", () => ({
  Drawer: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="drawer">{children}</div> : null,
  DrawerContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DrawerHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DrawerTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DrawerClose: ({ children, ...props }: { children: React.ReactNode; [key: string]: unknown }) => (
    <button {...props}>{children}</button>
  ),
}));

import { useDecisionTimeline } from "@/hooks/use-decision-timeline";
import { DecisionTimelineList } from "../decision-timeline-list";
import type { TimelineState } from "@/hooks/use-decision-timeline";

const mockUseTimeline = useDecisionTimeline as Mock;

const CONV_ID = "conv_abc";

function makeEntry(overrides = {}) {
  return {
    id: "e_001",
    org_id: "uid_alice",
    kind: "decision" as const,
    sequence_no: 1,
    actor_uid: "uid_alice",
    conversation_id: CONV_ID,
    prev_hash: "sha256:genesis",
    entry_hash: "sha256:aabbcc",
    created_at: "2026-06-25T06:30:00Z",
    message_id: "msg_001",
    query: "Can we cap liability at 6 months?",
    document_ids: ["doc_001"],
    language: null,
    retrieval: {
      params: { top_k: 5, score_threshold: 0.3 },
      citations: [
        { doc_id: "doc_001", chunk_index: 4, page_number: 12, score: 0.71, original_filename: "MSA.pdf" },
      ],
    },
    memory_used: [],
    model: {
      name: "gemini-2.5-flash",
      temperature: 0.3,
      max_output_tokens: 2048,
      prompt_template_version: "m6.1",
    },
    policy: { snapshot_id: "snap_001", evaluations: [] },
    output: {
      answer_hash: "sha256:aabb",
      answer_ref: "msg_001",
      sources_used: true,
      grounding: { citations_above_threshold: 1, top_score: 0.71, disclaimer_emitted: false },
    },
    decision_id: null,
    approver: null,
    reason: null,
    previous_recommendation: null,
    final_outcome: null,
    disposition: null,
    original_hash: null,
    note: null,
    ...overrides,
  };
}

function stubHook(state: TimelineState) {
  mockUseTimeline.mockReturnValue({ state, refetch: vi.fn() });
}

beforeEach(() => { vi.clearAllMocks(); });

describe("DecisionTimelineList", () => {
  it("renders the list region while loading", () => {
    stubHook({ status: "loading" });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByRole("list", { name: /decision timeline/i })).toBeInTheDocument();
    // No listitem rows while loading
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("renders error message on failure", () => {
    stubHook({ status: "error", message: "Failed to load decision timeline." });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("Failed to load decision timeline.")).toBeInTheDocument();
  });

  it("renders empty state when no entries", () => {
    stubHook({ status: "ready", entries: [], total: 0 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("No decisions logged yet.")).toBeInTheDocument();
  });

  it("renders one listitem per entry", () => {
    const e1 = makeEntry({ id: "e_001", sequence_no: 1 });
    const e2 = makeEntry({ id: "e_002", sequence_no: 2, query: "Second question?" });
    stubHook({ status: "ready", entries: [e1, e2], total: 2 });

    render(<DecisionTimelineList conversationId={CONV_ID} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders the query text for a decision entry", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("Can we cap liability at 6 months?")).toBeInTheDocument();
  });

  it("renders the kind badge", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("decision")).toBeInTheDocument();
  });

  it("renders the sequence number with aria-label", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByLabelText("Sequence 1")).toBeInTheDocument();
  });

  it("shows grounding indicator when sources_used is true", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText(/1 src/i)).toBeInTheDocument();
  });

  it("shows 'no sources' when sources_used is false", () => {
    const entry = makeEntry({
      output: {
        answer_hash: "sha256:aabb",
        answer_ref: "msg_001",
        sources_used: false,
        grounding: { citations_above_threshold: 0, top_score: 0, disclaimer_emitted: true },
      },
    });
    stubHook({ status: "ready", entries: [entry], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("no sources")).toBeInTheDocument();
  });

  it("opens detail drawer when a row is clicked", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);

    const rows = screen.getAllByRole("button");
    fireEvent.click(rows[0]);

    expect(screen.getByTestId("drawer")).toBeInTheDocument();
  });

  it("passes sequence number to drawer title", () => {
    stubHook({ status: "ready", entries: [makeEntry()], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);

    fireEvent.click(screen.getAllByRole("button")[0]);

    expect(screen.getByText("Decision #1")).toBeInTheDocument();
  });

  it("renders override entry with 'Human override' label", () => {
    const entry = makeEntry({
      kind: "override" as const,
      query: null,
      message_id: null,
      retrieval: null,
      model: null,
      policy: null,
      output: null,
      decision_id: "e_001",
      disposition: "rejected",
      reason: "Incorrect conclusion.",
    });
    stubHook({ status: "ready", entries: [entry], total: 1 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(screen.getByText("Human override")).toBeInTheDocument();
    expect(screen.getByText("override")).toBeInTheDocument();
  });

  it("passes conversationId to useDecisionTimeline", () => {
    stubHook({ status: "ready", entries: [], total: 0 });
    render(<DecisionTimelineList conversationId={CONV_ID} />);
    expect(mockUseTimeline).toHaveBeenCalledWith(CONV_ID);
  });
});
