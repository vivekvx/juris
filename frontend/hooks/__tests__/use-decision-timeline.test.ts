import { renderHook, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import type { Mock } from "vitest";

vi.mock("@/lib/firebase", () => ({
  getAuth: () => ({
    currentUser: { getIdToken: async () => "mock-token" },
  }),
}));

vi.mock("@/lib/api", () => ({
  fetchDecisionTimeline: vi.fn(),
}));

import { useDecisionTimeline } from "../use-decision-timeline";
import { fetchDecisionTimeline } from "@/lib/api";

const mockFetch = fetchDecisionTimeline as Mock;

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

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useDecisionTimeline", () => {
  it("starts in loading state", () => {
    mockFetch.mockResolvedValue({ conversation_id: CONV_ID, entries: [], total: 0 });
    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));
    expect(result.current.state.status).toBe("loading");
  });

  it("transitions to ready with entries on success", async () => {
    const entry = makeEntry();
    mockFetch.mockResolvedValue({ conversation_id: CONV_ID, entries: [entry], total: 1 });

    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    if (result.current.state.status === "ready") {
      expect(result.current.state.entries).toHaveLength(1);
      expect(result.current.state.total).toBe(1);
      expect(result.current.state.entries[0].id).toBe("e_001");
    }
  });

  it("returns empty list when timeline is empty", async () => {
    mockFetch.mockResolvedValue({ conversation_id: CONV_ID, entries: [], total: 0 });

    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    if (result.current.state.status === "ready") {
      expect(result.current.state.entries).toHaveLength(0);
      expect(result.current.state.total).toBe(0);
    }
  });

  it("transitions to error state on fetch failure", async () => {
    mockFetch.mockRejectedValue(new Error("Failed to load decision timeline."));

    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));

    await waitFor(() => expect(result.current.state.status).toBe("error"));

    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Failed to load decision timeline.");
    }
  });

  it("returns ready with empty entries when conversationId is null", async () => {
    const { result } = renderHook(() => useDecisionTimeline(null));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    if (result.current.state.status === "ready") {
      expect(result.current.state.entries).toHaveLength(0);
    }
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("does not call fetchDecisionTimeline when conversationId is null", async () => {
    const { result } = renderHook(() => useDecisionTimeline(null));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("calls fetchDecisionTimeline with correct conversationId and token", async () => {
    mockFetch.mockResolvedValue({ conversation_id: CONV_ID, entries: [], total: 0 });

    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    expect(mockFetch).toHaveBeenCalledWith(CONV_ID, "mock-token");
  });

  it("exposes a refetch function that reloads data", async () => {
    const entry = makeEntry();
    mockFetch
      .mockResolvedValueOnce({ conversation_id: CONV_ID, entries: [], total: 0 })
      .mockResolvedValueOnce({ conversation_id: CONV_ID, entries: [entry], total: 1 });

    const { result } = renderHook(() => useDecisionTimeline(CONV_ID));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await result.current.refetch();
    await waitFor(() => {
      if (result.current.state.status === "ready") {
        expect(result.current.state.total).toBe(1);
      }
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
