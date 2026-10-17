import { Component, ElementRef, OnDestroy, OnInit, inject, input, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ChatService } from '@core/api/chat.service';
import { ChatStreamEvent, PENDING_RISK_CHANGE_KEY, ProposedChange } from '@models/agent/chat.model';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  isError?: boolean;
  streaming?: boolean;
}

const DEFAULT_SUGGESTIONS = [
  'Give me an overview of this simulation',
  'Did the strategy beat buy & hold?',
  'Explain the decision on day 1',
];

@Component({
  selector: 'app-simulation-chat',
  imports: [FormsModule],
  templateUrl: './simulation-chat.html',
  styleUrl: './simulation-chat.css',
})
export class SimulationChat implements OnInit, OnDestroy {
  simulationId = input.required<string>();

  private chatService = inject(ChatService);
  private router = inject(Router);

  readonly maxLength = 500;

  active = signal(false);
  messages = signal<ChatMessage[]>([]);
  suggestions = signal<string[]>(DEFAULT_SUGGESTIONS);
  proposal = signal<ProposedChange | null>(null);
  draft = signal('');
  sending = signal(false);

  private subscription: Subscription | null = null;
  private scrollBox = viewChild<ElementRef<HTMLElement>>('scrollBox');

  ngOnInit(): void {
    // The conversation is kept on the server: coming back later shows it again.
    this.chatService.getHistory(this.simulationId()).subscribe({
      next: (history) => {
        if (history.messages.length === 0) return;

        this.messages.set(
          history.messages.map((m) => ({ role: m.role, text: m.content })),
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

  private handleEvent(event: ChatStreamEvent): void {
    if (event.type === 'token') {
      this.updateLast((m) => ({ ...m, text: m.text + event.text }));
      this.scrollToBottom();
    } else if (event.type === 'done') {
      // The final reply replaces whatever was streamed, so the text is always the complete one.
      this.updateLast((m) => ({ ...m, text: event.response.reply, streaming: false }));
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