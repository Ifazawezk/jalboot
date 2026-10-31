import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import type { Unsubscribe } from '../api/client';
import { ApiError, type AssistantMode, type Policy, type VerifyStartResult } from '../api/types';
import { useApi } from '../App';
import type { Recording } from '../data/recordings';
import { useI18n } from '../i18n/context';
import { chatReducer, initialChatState, type ChatState } from '../lib/chatState';

export type PlaybackStatus = 'idle' | 'playing' | 'finished';

interface Playback {
  recording: Recording | null;
  status: PlaybackStatus;
  step: number;
}

interface Chat {
  state: ChatState;
  policy: Policy | null;
  assistant: AssistantMode | null;
  send: (text: string) => void;
  stop: () => void;
  retry: () => void;
  requestPerson: () => void;
  reset: () => void;
  startVerification: (phone: string) => Promise<VerifyStartResult>;
  confirmVerification: (code: string) => Promise<void>;
  cancelVerification: () => void;
  changeNumber: () => void;
  recordings: Recording[];
  playback: Playback;
  play: (id: string) => void;
  skip: () => void;
  closeRecording: () => void;
}

interface Turn {
  clientMessageId: string;
  text: string;
}

const ChatContext = createContext<Chat | null>(null);
const NO_PLAYBACK: Playback = { recording: null, status: 'idle', step: 0 };

function newId(): string {
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const { locale, t } = useI18n();
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [assistant, setAssistant] = useState<AssistantMode | null>(null);
  const [playback, setPlayback] = useState<Playback>(NO_PLAYBACK);

  const conversationId = useRef<string | null>(null);
  const unsubscribe = useRef<Unsubscribe | null>(null);
  const abort = useRef<AbortController | null>(null);
  const lastTurn = useRef<Turn | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let live = true;
    void api.getPolicy().then((value) => {
      if (!live) return;
      setPolicy(value);
      if (value?.assistant) setAssistant(value.assistant);
    });
    return () => {
      live = false;
    };
  }, [api]);

  const follow = useCallback(
    (id: string) => {
      unsubscribe.current?.();
      unsubscribe.current = api.subscribeConversation(id, dispatch);
    },
    [api],
  );

  const ensureConversation = useCallback(async () => {
    if (conversationId.current) return conversationId.current;
    const conversation = await api.createConversation(locale);
    conversationId.current = conversation.id;
    // Also read here, so the mock label still shows if GET /policy failed.
    if (conversation.assistant) setAssistant(conversation.assistant);
    follow(conversation.id);
    return conversation.id;
  }, [api, follow, locale]);

  const runTurn = useCallback(
    async (turn: Turn) => {
      lastTurn.current = turn;
      const controller = new AbortController();
      abort.current = controller;
      let ended = false;
      try {
        const id = await ensureConversation();
        const stream = api.sendMessage(
          id,
          { clientMessageId: turn.clientMessageId, text: turn.text, locale },
          controller.signal,
        );
        for await (const event of stream) {
          if (event.type === 'message.end' || event.type === 'error') ended = true;
          dispatch(event);
        }
        if (!ended) {
          dispatch({ type: 'turn.failed', message: t('chat.networkError'), retryable: true });
        }
      } catch (error) {
        if (controller.signal.aborted) {
          dispatch({ type: 'turn.stopped' });
        } else if (error instanceof ApiError) {
          dispatch({ type: 'turn.failed', message: error.message, retryable: error.retryable });
        } else {
          dispatch({ type: 'turn.failed', message: t('chat.networkError'), retryable: true });
        }
      } finally {
        if (abort.current === controller) abort.current = null;
      }
    },
    [api, ensureConversation, locale, t],
  );

  const send = useCallback(
    (text: string) => {
      const clientMessageId = newId();
      dispatch({ type: 'customer.message', id: clientMessageId, text });
      void runTurn({ clientMessageId, text });
    },
    [runTurn],
  );

  const stop = useCallback(() => abort.current?.abort(), []);

  const retry = useCallback(() => {
    // The same clientMessageId tells the backend this is a repeat, not a new message.
    if (lastTurn.current) void runTurn(lastTurn.current);
  }, [runTurn]);

  const requestPerson = useCallback(() => {
    void (async () => {
      try {
        const id = await ensureConversation();
        dispatch({ type: 'handoff.update', handoff: await api.requestHandoff(id, 'customer_request') });
      } catch {
        // The button stays on screen, so the customer can ask again.
        dispatch({ type: 'handoff.failed' });
      }
    })();
  }, [api, ensureConversation]);

  const clearPlayback = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const reset = useCallback(() => {
    abort.current?.abort();
    clearPlayback();
    unsubscribe.current?.();
    unsubscribe.current = null;
    conversationId.current = null;
    lastTurn.current = null;
    setPlayback(NO_PLAYBACK);
    dispatch({ type: 'reset' });
  }, [clearPlayback]);

  const startVerification = useCallback(
    async (phone: string) => {
      const result = await api.startVerification(await ensureConversation(), phone);
      dispatch({ type: 'identity.code_sent', maskedPhone: result.maskedPhone });
      return result;
    },
    [api, ensureConversation],
  );

  const confirmVerification = useCallback(
    async (code: string) => {
      await api.confirmVerification(await ensureConversation(), code);
      dispatch({ type: 'identity.verified' });
      // The backend kept the refused message. Repeating its ID runs that turn now.
      if (lastTurn.current) void runTurn(lastTurn.current);
    },
    [api, ensureConversation, runTurn],
  );

  const cancelVerification = useCallback(() => dispatch({ type: 'identity.cancelled' }), []);
  const changeNumber = useCallback(() => dispatch({ type: 'identity.restart' }), []);

  const recordings = useMemo(() => api.listRecordings?.(locale) ?? [], [api, locale]);

  const play = useCallback(
    (id: string) => {
      const recording = recordings.find((r) => r.id === id);
      if (!recording) return;
      clearPlayback();
      dispatch({ type: 'reset' });
      follow(recording.conversationId);
      setPlayback({ recording, status: 'playing', step: 0 });

      const advance = (index: number) => {
        const step = recording.steps[index];
        if (!step) {
          setPlayback({ recording, status: 'finished', step: recording.steps.length });
          return;
        }
        timer.current = setTimeout(() => {
          dispatch(step.event);
          setPlayback({ recording, status: 'playing', step: index + 1 });
          advance(index + 1);
        }, step.waitMs);
      };
      advance(0);
    },
    [clearPlayback, follow, recordings],
  );

  const skip = useCallback(() => {
    clearPlayback();
    setPlayback((current) => {
      const { recording, step } = current;
      if (!recording) return current;
      for (const rest of recording.steps.slice(step)) dispatch(rest.event);
      return { recording, status: 'finished', step: recording.steps.length };
    });
  }, [clearPlayback]);

  useEffect(
    () => () => {
      abort.current?.abort();
      clearPlayback();
      unsubscribe.current?.();
    },
    [clearPlayback],
  );

  const value = useMemo<Chat>(
    () => ({
      state,
      policy,
      assistant,
      send,
      stop,
      retry,
      requestPerson,
      reset,
      startVerification,
      confirmVerification,
      cancelVerification,
      changeNumber,
      recordings,
      playback,
      play,
      skip,
      closeRecording: reset,
    }),
    [
      state,
      policy,
      assistant,
      send,
      stop,
      retry,
      requestPerson,
      reset,
      startVerification,
      confirmVerification,
      cancelVerification,
      changeNumber,
      recordings,
      playback,
      play,
      skip,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): Chat {
  const value = useContext(ChatContext);
  if (!value) throw new Error('useChat needs ChatProvider');
  return value;
}
