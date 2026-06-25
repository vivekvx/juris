export type LedgerEntryKind = "decision" | "annotation" | "override";

export type GroundingStatus = {
  citations_above_threshold: number;
  top_score: number;
  disclaimer_emitted: boolean;
};

export type RetrievalParams = {
  top_k: number;
  score_threshold: number;
};

export type CachedCitation = {
  doc_id: string;
  chunk_index: number;
  page_number: number | null;
  score: number;
  original_filename: string;
};

export type RetrievalRecord = {
  params: RetrievalParams;
  citations: CachedCitation[];
};

export type MemoryRef = {
  entry_id: string;
  version: number;
  kind: string;
};

export type ModelParams = {
  name: string;
  temperature: number;
  max_output_tokens: number;
  prompt_template_version: string;
};

export type PolicyEvaluation = {
  trigger: string;
  effect: string;
  policy_id: string;
};

export type PolicyRecord = {
  snapshot_id: string;
  evaluations: PolicyEvaluation[];
};

export type OutputRecord = {
  answer_hash: string;
  answer_ref: string;
  sources_used: boolean;
  grounding: GroundingStatus;
};

/** Serialized ledger entry from GET /api/conversations/{id}/decisions[/{id}].
 *  `kind` discriminates which optional fields are present.
 */
export type LedgerEntryResponse = {
  id: string;
  org_id: string;
  kind: LedgerEntryKind;
  sequence_no: number;
  actor_uid: string;
  conversation_id: string;
  prev_hash: string;
  entry_hash: string;
  created_at: string; // ISO-8601 UTC, Z-terminated

  // kind=decision
  message_id: string | null;
  query: string | null;
  document_ids: string[] | null;
  language: string | null;
  retrieval: RetrievalRecord | null;
  memory_used: MemoryRef[] | null;
  model: ModelParams | null;
  policy: PolicyRecord | null;
  output: OutputRecord | null;

  // kind=override (also uses decision_id), kind=annotation (also uses decision_id)
  decision_id: string | null;
  approver: string | null;
  reason: string | null;
  previous_recommendation: string | null;
  final_outcome: string | null;
  disposition: string | null;

  // kind=annotation
  original_hash: string | null;
  note: string | null;
};

export type DecisionTimelineResponse = {
  conversation_id: string;
  entries: LedgerEntryResponse[];
  total: number;
};
