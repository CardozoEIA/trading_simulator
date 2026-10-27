import { Component, ElementRef, OnDestroy, OnInit, inject, input, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ChatService } from '@core/api/chat.service';
import { Simulations } from '@core/api/simulations';
import { ChatStreamEvent, PENDING_RISK_CHANGE_KEY, ProposedChange } from '@models/agent/chat.model';
import { RiskParameter, WhatIfResult as WhatIfResultData } from '@models/agent/what-if.model';
import { WhatIfResult } from './what-if-result/what-if-result';
import { TraceView } from '@shared/ui/trace-view/trace-view';
import { ToolCallTrace, Verification } from '@models/agent/trace.model';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  isError?: boolean;
  streaming?: boolean;
  route?: string | null;
  date?: string | null;
  // US-31: the data behind an explanation. Live replies carry it; for older ones it is loaded on demand.
  trace?: ToolCallTrace[];
  verification?: Verification | null;
  traceLoading?: boolean;
}

const DEFAULT_SUGGESTIONS = [
  'Give me an overview of this simulation',
  'Did the strategy beat buy & hold?',
  'Explain the decision on day 1',
];

@Component({
  selector: 'app-simulation-chat',
  imports: [FormsModule, WhatIfResult, TraceView],
  templateUrl: './simulation-chat.html',
  styleUrl: './simulation-chat.css',
})
export class SimulationChat implements OnInit, OnDestroy {
  simulationId = input.required<string>();

  private chatService = inject(ChatService);
  private simulations = inject(Simulations);
  private router = inject(Router);

  readonly maxLength = 500;

  active = signal(false);
  messages = signal<ChatMessage[]>([]);
  suggestions = signal<string[]>(DEFAULT_SUGGESTIONS);
  proposal = signal<ProposedChange | null>(null);
  draft = signal('');
  sending = signal(false);

  // --- What-if (US-28): runs only when the student presses "Run what-if" ---
  whatIfRunning = signal(false);
  whatIfResult = signal<WhatIfResultData | null>(null);
  whatIfError = signal('');
  private whatIfSubscription: Subscription | null = null;

  private subscription: Subscription | null = null;
  private scrollBox = viewChild<ElementRef<HTMLElement>>('scrollBox');

  ngOnInit(): void {
    // The conversation is kept on the server: coming back later shows it again.
    this.chatService.getHistory(this.simulationId()).subscribe({
      next: (history) => {
        if (history.messages.length === 0) return;

        this.messages.set(
          history.messages.map((m) => ({ role: m.role, text: m.content, route: m.route, date: m.date })),
        );
        this.suggestions.set(history.suggestions);
        this.active.set(true);
        this.scrollToBottom();
      },
      // History is optional: if it cannot be loaded the chat still works.
      error: () => {},
    });
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
    this.whatIfSubscription?.unsubscribe();
  }

  send(text: string = this.draft()): void {
    const message = text.trim();
    if (!message || this.sending()) return;

    this.proposal.set(null);
    this.suggestions.set([]);
    this.messages.update((list) => [
      ...list,
      { role: 'user', text: message },
      { role: 'assistant', text: '', streaming: true },
    ]);
    this.draft.set('');
    this.sending.set(true);
    this.scrollToBottom();

    this.subscription = this.chatService.streamMessage(this.simulationId(), message).subscribe({
      next: (event) => this.handleEvent(event),
      // The stream closed without a final event (for example the connection dropped).
      complete: () => {
        if (this.sending()) {
          this.fail('The connection was interrupted. Please try again.');
        }
      },
    });
  }

  runWhatIf(): void {
    const proposal = this.proposal();
    if (!proposal || this.whatIfRunning()) return;

    this.whatIfRunning.set(true);
    this.whatIfResult.set(null);
    this.whatIfError.set('');
    this.whatIfSubscription = this.simulations
      .runWhatIf(this.simulationId(), proposal.parameter as RiskParameter, proposal.suggested)
      .subscribe({
        next: (result) => {
          this.whatIfResult.set(result);
          this.proposal.set(null);
          this.whatIfRunning.set(false);
          this.scrollToBottom();
        },
        error: (error) => {
          this.whatIfError.set(error?.error?.detail || 'Could not run the what-if. Please try again.');
          this.whatIfRunning.set(false);
        },
      });
  }

  confirmProposal(): void {
    const proposal = this.proposal();
    if (!proposal) return;

    try {
      sessionStorage.setItem(
        PENDING_RISK_CHANGE_KEY,
        JSON.stringify({
          parameter: proposal.parameter,
          label: proposal.label,
          value: proposal.suggested,
          createdAt: Date.now(),
        }),
      );
    } catch {
      // Without storage the setup simply opens empty.
    }

    this.router.navigate(['/simulation-config']);
  }

  clearConversation(): void {
    this.subscription?.unsubscribe();

    this.chatService.clearHistory(this.simulationId()).subscribe({
      next: () => {
        this.messages.set([]);
        this.suggestions.set(DEFAULT_SUGGESTIONS);
        this.proposal.set(null);
        this.sending.set(false);
      },
      error: () => {
        this.sending.set(false);
        this.messages.update((list) => [
          ...list,
          { role: 'assistant', text: 'Could not clear the conversation. Please try again.', isError: true },
        ]);
      },
    });
  }

  /** US-31: an explanation from an earlier visit has no trace in memory: fetch the stored one for its date. */
  canShowTrace(message: ChatMessage): boolean {
    return message.role === 'assistant' && message.route === 'explain_agent' && !!message.date
      && message.trace === undefined && !message.isError;
  }

  loadTrace(index: number): void {
    const message = this.messages()[index];
    if (!message?.date || message.traceLoading) return;

    this.patchMessage(index, { traceLoading: true });
    this.simulations.getTraces(this.simulationId(), message.date).subscribe({
      next: (records) => {
        const latest = records.find((r) => r.answer === message.text) ?? records[0];
        this.patchMessage(index, {
          traceLoading: false,
          trace: latest?.tool_calls ?? [],
          verification: latest?.verification ?? null,
        });
      },
      error: () => this.patchMessage(index, { traceLoading: false, trace: [], verification: null }),
    });
  }

  private patchMessage(index: number, change: Partial<ChatMessage>): void {
    this.messages.update((list) => list.map((m, i) => (i === index ? { ...m, ...change } : m)));
  }

  private handleEvent(event: ChatStreamEvent): void {
    if (event.type === 'token') {
      this.updateLast((m) => ({ ...m, text: m.text + event.text }));
      this.scrollToBottom();
    } else if (event.type === 'done') {
      // The final reply replaces whatever was streamed, so the text is always the complete one.
      this.updateLast((m) => ({
        ...m,
        text: event.response.reply,
        streaming: false,
        route: event.response.route,
        date: event.response.date,
        trace: event.response.trace ?? [],
        verification: event.response.verification ?? null,
      }));
      this.suggestions.set(event.response.suggestions);
      this.proposal.set(event.response.proposed_change);
      this.sending.set(false);
      this.scrollToBottom();
    } else {
      this.fail(event.detail);
    }
  }

  private fail(detail: string): void {
    this.updateLast(() => ({ role: 'assistant', text: detail, isError: true }));
    this.suggestions.set(DEFAULT_SUGGESTIONS);
    this.sending.set(false);
    this.scrollToBottom();
  }

  private updateLast(change: (message: ChatMessage) => ChatMessage): void {
    this.messages.update((list) => {
      if (list.length === 0) return list;
      return [...list.slice(0, -1), change(list[list.length - 1])];
    });
  }

  // Waits one tick so the new text is already in the DOM before scrolling.
  private scrollToBottom(): void {
    setTimeout(() => {
      const box = this.scrollBox()?.nativeElement;
      if (box) {
        box.scrollTop = box.scrollHeight;
      }
    });
  }
}