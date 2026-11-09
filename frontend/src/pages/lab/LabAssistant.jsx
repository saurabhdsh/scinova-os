import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { ArrowUp, ChevronsRight, Paperclip } from 'lucide-react';
import { askLabAssistant, draftLabPlanFromIntent, labError } from '../../api/lab';
import { assist, draftFromIntentResponse, isPlanEdit, wantsExperimentDraft } from './assistantLogic';

const STARTER = 'I want to run cell viability tomorrow. Check if everything is ready and help me prepare the plan.';
const QUESTIONS = [
  'Why would a viability run miss its success criteria?',
  'What does readiness check before a run can start?',
];
const pause = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

let messageSeq = 1;
const nextId = () => `m${messageSeq++}`;

const LabAssistant = forwardRef(function LabAssistant({
  protocols,
  instruments,
  pastByCode,
  draft,
  experimentId,
  onDraftChange,
  onOpenDraft,
  onFile,
  onCollapse,
}, ref) {
  const [messages, setMessages] = useState(() => [{
    id: 'welcome',
    role: 'assistant',
    text: 'Ask about an experiment, a result, or what readiness is checking. Describe a new run and I will take that as the intent, then draft the plan for you to approve.',
  }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const inputRef = useRef(null);
  const scrollerRef = useRef(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useImperativeHandle(ref, () => ({
    focusComposer(text) {
      if (typeof text === 'string') setInput(text);
      inputRef.current?.focus();
    },
  }));

  useEffect(() => {
    const node = scrollerRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, draft, busy]);

  const push = (message) => {
    setMessages((current) => [...current, { id: nextId(), ...message }]);
  };

  const reply = (text) => {
    const result = assist({ text, protocols, instruments, pastByCode, draft });
    onDraftChange(result.draft || null);
    const id = nextId();
    setMessages((current) => [...current, {
      id,
      role: 'assistant',
      text: result.text,
    }]);
  };

  const ask = async (text) => {
    if (!text || busy) return;
    setBusy(true);
    const history = messagesRef.current
      .filter((item) => !item.interim && item.id !== 'welcome')
      .slice(-8)
      .map((item) => ({ role: item.role, text: item.text }));
    push({ role: 'scientist', text });
    if (wantsExperimentDraft(text, { protocols, draft })) {
      if (isPlanEdit(text, { protocols, draft })) {
        const beats = ['Reading your follow-up.', 'Updating the drafted plan. The intent stays the same.'];
        for (const beat of beats) {
          push({ role: 'assistant', interim: true, text: beat });
          await pause(700);
        }
        reply(text);
        onOpenDraft?.();
        setBusy(false);
        return;
      }
      const beats = [
        'Reading what you want this experiment to do.',
        'Writing a protocol and filling the fields it needs.',
      ];
      for (const beat of beats) {
        push({ role: 'assistant', interim: true, text: beat });
        await pause(700);
      }
      try {
        const intent = text.trim().slice(0, 1000);
        const response = await draftLabPlanFromIntent({ intent });
        const next = draftFromIntentResponse(protocols, pastByCode, intent, response.data);
        if (!next?.parameters || !Object.keys(next.parameters).length) {
          push({ role: 'assistant', text: 'A protocol could not be drafted from that description. Try again in a moment.' });
          return;
        }
        onDraftChange(next);
        onOpenDraft?.();
        push({
          role: 'assistant',
          text: `${next.reason} That description is the intent of this experiment. The plan is open so you can review the protocol, parameters, and success criteria before you approve.`,
        });
      } catch (err) {
        push({ role: 'assistant', text: labError(err) });
      } finally {
        setBusy(false);
      }
      return;
    }
    const thinkingId = nextId();
    setMessages((current) => [...current, { id: thinkingId, role: 'assistant', interim: true, text: 'Looking at the lab record.' }]);
    const timer = setTimeout(() => {
      setMessages((current) => current.map((item) => (
        item.id === thinkingId && item.interim ? { ...item, text: 'Reading the plan, the checks, and the results.' } : item
      )));
    }, 700);
    try {
      const response = await askLabAssistant({
        question: text,
        experiment_id: experimentId || null,
        history,
        draft: draft?.protocolId || draft?.intent ? {
          intent: draft.intent || '',
          experiment_name: draft.experimentName || draft.planTitle || draft.name || '',
          protocol_code: draft.protocolCode || '',
          parameters: draft.parameters || {},
          criteria: draft.criteria || [],
          reason: draft.reason || '',
        } : null,
      });
      const data = response.data || {};
      setMessages((current) => current.map((item) => (
        item.id === thinkingId
          ? {
            id: thinkingId,
            role: 'assistant',
            text: data.answer || 'I could not read an answer from the lab record.',
            followUps: Array.isArray(data.follow_ups) ? data.follow_ups.filter(Boolean).slice(0, 2) : [],
          }
          : item
      )));
    } catch (err) {
      setMessages((current) => current.map((item) => (
        item.id === thinkingId ? { id: thinkingId, role: 'assistant', text: labError(err) } : item
      )));
    } finally {
      clearTimeout(timer);
      setBusy(false);
    }
  };

  const send = (event) => {
    event?.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    ask(text);
  };

  const attach = async (file) => {
    if (!file) return;
    push({ role: 'scientist', text: `Attached ${file.name}` });
    const note = await onFile?.(file);
    push({ role: 'assistant', text: note || `${file.name} is attached. I’ll hold it for capture once the plan is approved and readiness is clear.` });
  };

  return (
    <div className="flex h-full min-h-[32rem] flex-col bg-white/80">
      <div className="flex items-start justify-between gap-3 border-b border-black/5 px-5 py-4">
        <div>
          <p className="font-display text-lg font-semibold tracking-tight text-cx-fg">Lab Assistant</p>
          <p className="mt-1 text-sm leading-5 text-cx-fgMuted">Ask about the experiment in front of you. Describe a new run and that becomes its intent.</p>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          className="mt-0.5 rounded-full p-2 text-cx-fgMuted hover:bg-slate-100"
          aria-label="Collapse Lab Assistant"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
      <div ref={scrollerRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.map((message) => (
          <div key={message.id} className={message.role === 'scientist' ? 'flex justify-end' : ''}>
            <div className={message.role === 'scientist'
              ? 'max-w-[90%] rounded-3xl rounded-br-lg bg-cx-fg px-4 py-2.5 text-sm leading-6 text-white'
              : 'max-w-[95%] rounded-3xl rounded-bl-lg bg-slate-100 px-4 py-2.5 text-sm leading-6 text-cx-fg'}
            >
              {message.text}
              {message.followUps?.length > 0 && (
                <div className="mt-3 flex flex-col items-start gap-2">
                  {message.followUps.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      disabled={busy}
                      onClick={() => ask(prompt)}
                      className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-left text-xs leading-5 text-cx-fg"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {messages.filter((item) => !item.interim).length < 3 && (
        <div className="flex flex-col items-start gap-2 px-4 pb-2">
          {[STARTER, ...QUESTIONS].map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => {
                setInput('');
                ask(prompt);
              }}
              disabled={busy}
              className="rounded-full border border-black/10 bg-white px-3 py-1.5 text-left text-xs leading-5 text-cx-fgMuted"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={send} className="border-t border-black/5 p-3">
        <div className="flex items-end gap-2 rounded-3xl border border-black/10 bg-white px-2 py-2 shadow-sm">
          <button type="button" onClick={() => fileRef.current?.click()} className="rounded-full p-2 text-cx-fgMuted" aria-label="Attach a file">
            <Paperclip size={16} />
          </button>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
            placeholder="Ask about this experiment, or describe what you want it to do"
            className="max-h-28 flex-1 resize-none bg-transparent py-1.5 text-sm text-cx-fg outline-none"
          />
          <button type="submit" className="rounded-full bg-cx-fg p-2 text-white" aria-label="Send">
            <ArrowUp size={16} />
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) attach(file);
          }}
        />
      </form>
    </div>
  );
});

export default LabAssistant;
