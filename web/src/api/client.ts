import type { Recording } from '../data/recordings';
import type {
  ApiMode,
  AuditFilter,
  AuditPage,
  Conversation,
  ConversationDetail,
  ConversationEvent,
  DeskAgent,
  DeskEvent,
  DeskSummary,
  Handoff,
  LiveConversation,
  Locale,
  Policy,
  QualityReport,
  Refund,
  RefundDecision,
  SendMessageInput,
  StreamEvent,
  TopIssue,
  VerifyConfirmResult,
  VerifyStartResult,
  WindowDays,
} from './types';

export type Unsubscribe = () => void;

/** Everything the screens need. The mock, the demo and the HTTP client all implement it. */
export interface SupportApi {
  readonly mode: ApiMode;
  /** Sets the language used for Accept-Language and for localized sample data. */
  setLocale(locale: Locale): void;

  /** The only source of limits and timings. Null means leave those sentences out. */
  getPolicy(): Promise<Policy | null>;
  /** Only the demo build has recordings. */
  listRecordings?(locale: Locale): Recording[];

  createConversation(locale: Locale): Promise<Conversation>;
  sendMessage(
    conversationId: string,
    input: SendMessageInput,
    signal: AbortSignal,
  ): AsyncIterable<StreamEvent>;
  /** Phone and code go only through these two calls, never into chat text. */
  startVerification(conversationId: string, phone: string): Promise<VerifyStartResult>;
  confirmVerification(conversationId: string, code: string): Promise<VerifyConfirmResult>;
  requestHandoff(conversationId: string, reason: string): Promise<Handoff>;
  subscribeConversation(
    conversationId: string,
    onEvent: (event: ConversationEvent) => void,
  ): Unsubscribe;

  /** Current desk user, or null when signed out. */
  getDeskAgent(): Promise<DeskAgent | null>;
  signInToDesk(email: string, password: string): Promise<DeskAgent>;
  signOutOfDesk(): Promise<void>;
  getDeskSummary(): Promise<DeskSummary>;
  listConversations(): Promise<LiveConversation[]>;
  getConversationDetail(id: string): Promise<ConversationDetail>;
  claimConversation(id: string): Promise<LiveConversation>;
  replyToConversation(id: string, text: string): Promise<void>;
  listRefunds(): Promise<Refund[]>;
  decideRefund(id: string, decision: RefundDecision): Promise<Refund>;
  listAudit(filter: AuditFilter, cursor: string | null): Promise<AuditPage>;
  getTopIssues(windowDays: WindowDays): Promise<TopIssue[]>;
  getQuality(windowDays: WindowDays): Promise<QualityReport>;
  subscribeDesk(onEvent: (event: DeskEvent) => void): Unsubscribe;
}
