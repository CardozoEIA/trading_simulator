import { Component, OnDestroy, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';

import { Backtest } from '@core/api/backtest';
import { SetupParseResponse, SetupProposal } from '@models/agent/setup.model';

interface Turn {
  role: 'student' | 'agent';
  text: string;
}

const STRATEGY_NAMES: Record<string, string> = {
  SMA: 'SMA', RSI: 'RSI', BOLLINGER: 'Bollinger Bands', MOMENTUM: 'Momentum',
};

/**
 * "Describe your simulation" (US-29). The agent turns the description into a proposal;
 * nothing is saved here: confirming only pre-fills the normal setup steps.
 */
@Component({
  selector: 'app-describe-setup',
  imports: [FormsModule],
  templateUrl: './describe-setup.html',
  styleUrl: './describe-setup.css',
})
export class DescribeSetup implements OnDestroy {
  private backtest = inject(Backtest);
  private subscription: Subscription | null = null;

  confirmed = output<SetupProposal>();

  readonly maxLength = 500;
  readonly example = 'Backtest the S&P 500 during 2023 with $10,000 using SMA and RSI, a 5% stop-loss, ' +
    'a 50% max position and a 20% max drawdown.';

  open = signal(false);
  draft = signal('');
  turns = signal<Turn[]>([]);
  result = signal<SetupParseResponse | null>(null);
  loading = signal(false);
  error = signal('');
  applied = signal(false);

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  /** Follow-up answers are sent together with everything the student wrote before. */
  private get description(): string {
    return this.turns().filter(t => t.role === 'student').map(t => t.text).join('\n');
  }

  send(): void {
    const text = this.draft().trim();
    if (!text || this.loading()) return;
    this.turns.update(list => [...list, { role: 'student', text }]);
    this.draft.set('');
    this.parse();
  }

  parse(): void {
    this.subscription?.unsubscribe();
    this.loading.set(true);
    this.error.set('');
    this.subscription = this.backtest.parseSetup(this.description).subscribe({
      next: (response) => {
        this.result.set(response);
        if (response.status === 'incomplete') {
          this.turns.update(list => [...list, { role: 'agent', text: response.message }]);
        }
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.detail || 'Could not read your description. Please try again.');
        this.loading.set(false);
      },
    });
  }

  confirm(): void {
    const result = this.result();
    if (result?.status !== 'complete') return;
    this.confirmed.emit(result.proposal);
    this.applied.set(true);
  }

  startOver(): void {
    this.subscription?.unsubscribe();
    this.turns.set([]);
    this.result.set(null);
    this.error.set('');
    this.applied.set(false);
    this.loading.set(false);
  }

  strategies(p: SetupProposal): string {
    return (p.strategies ?? []).map(s => STRATEGY_NAMES[s] ?? s).join(', ');
  }
}
