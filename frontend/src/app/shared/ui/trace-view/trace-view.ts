import { Component, input, signal } from '@angular/core';

import { ToolCallTrace, Verification } from '@models/agent/trace.model';

/**
 * US-31: "which data did the agent use?". Shows the tools the agent called, what each one returned and
 * what its self-check removed. Closed by default; works inside the explanation modal and the chat.
 */
@Component({
  selector: 'app-trace-view',
  template: `
    <div class="trace">
      <button type="button" class="trace-toggle" [attr.aria-expanded]="open()" (click)="open.set(!open())">
        <span class="chevron" aria-hidden="true">›</span>
        {{ open() ? 'Hide the data used' : 'Show the data used' }}
        @if (verification(); as v) {
          <span class="badge" [class.ok]="v.verified" [class.warn]="!v.verified">
            {{ v.verified ? 'every value checked' : v.removed.length + ' removed' }}
          </span>
        }
      </button>

      @if (open()) {
        <div class="trace-body">
          @if (trace().length === 0) {
            <p class="empty">The agent did not call any tool for this answer, so there is no recorded data behind it.</p>
          }
          @for (call of trace(); track $index) {
            <div class="call">
              <p class="call-title">
                <code>{{ call.tool }}</code>
                @if (argumentsText(call); as text) {
                  <span class="args">({{ text }})</span>
                }
              </p>
              <pre class="call-result">{{ call.result ?? 'No result recorded' }}</pre>
            </div>
          }

          @if (verification(); as v) {
            <p class="verdict">
              @if (v.verified) {
                Self-check: every date and number in the answer was found in the data above.
              } @else {
                Self-check: {{ v.removed.length }} statement{{ v.removed.length === 1 ? '' : 's' }} removed because
                {{ v.removed.length === 1 ? 'its value was' : 'their values were' }} not found in the data above.
              }
            </p>
            @for (item of v.removed; track $index) {
              <p class="removed"><span class="strike">{{ item.statement }}</span>
                <span class="why">not backed: {{ item.problems.join(', ') }}</span></p>
            }
          }
        </div>
      }
    </div>
  `,
  styles: `
    :host { display: block; white-space: normal; }
    .trace { margin: 0.75rem 0; font-size: 0.8rem; }
    .trace-toggle {
      display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.25rem 0;
      border: none; background: none; color: inherit; font: inherit; font-weight: 600; cursor: pointer;
      text-decoration: underline; text-underline-offset: 3px;
    }
    .trace-toggle:focus-visible { outline: 2px solid var(--golden-accent); outline-offset: 2px; }
    .chevron { display: inline-block; transition: transform 0.15s ease; }
    [aria-expanded='true'] .chevron { transform: rotate(90deg); }
    .badge { padding: 0.05rem 0.45rem; border-radius: 999px; border: 1px solid currentColor; font-size: 0.7rem; font-weight: 500; }
    .badge.ok { color: #2a9d6f; }
    .badge.warn { color: #c27a1a; }
    .trace-body { margin-top: 0.4rem; padding-left: 0.75rem; border-left: 2px solid var(--golden-accent); }
    .call { margin-bottom: 0.6rem; }
    .call-title { margin: 0 0 0.2rem; }
    .call-title code { font-weight: 700; }
    .args { opacity: 0.7; }
    .call-result {
      margin: 0; padding: 0.4rem 0.6rem; border-radius: 4px; background: rgba(127, 127, 127, 0.14);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.75rem; white-space: pre-wrap; word-break: break-word;
    }
    .verdict { margin: 0.4rem 0; font-style: italic; }
    .removed { margin: 0.2rem 0; }
    .strike { text-decoration: line-through; opacity: 0.75; }
    .why { margin-left: 0.4rem; color: #c27a1a; }
    .empty { margin: 0 0 0.5rem; font-style: italic; }
  `,
})
export class TraceView {
  trace = input<ToolCallTrace[]>([]);
  verification = input<Verification | null | undefined>(null);
  open = signal(false);

  argumentsText(call: ToolCallTrace): string {
    return Object.entries(call.arguments ?? {}).map(([key, value]) => `${key}: ${value}`).join(', ');
  }
}
