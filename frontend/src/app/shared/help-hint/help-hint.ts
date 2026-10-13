import { Component, computed, input, signal } from '@angular/core';

import { HELP_TEXTS, HelpTopic } from './help-texts';

@Component({
  selector: 'app-help-hint',
  template: `
    <span class="help">
      <button
        type="button"
        class="help-btn"
        aria-label="What does this mean?"
        [attr.aria-expanded]="open()"
        (click)="open.set(!open())"
        (keydown.escape)="open.set(false)"
        (blur)="open.set(false)"
      >
        ?
      </button>
      @if (open()) {
        <span class="help-pop" role="note">{{ text() }}</span>
      }
    </span>
  `,
  styles: `
    :host {
      display: inline-block;
      vertical-align: middle;
    }

    .help {
      position: relative;
      display: inline-block;
    }

    .help-btn {
      width: 18px;
      height: 18px;
      padding: 0;
      border: 1px solid var(--golden-accent, #c9a15c);
      border-radius: 50%;
      background: transparent;
      color: var(--golden-accent, #c9a15c);
      font-size: 0.7rem;
      font-weight: 700;
      line-height: 1;
      cursor: pointer;
    }

    .help-btn:hover,
    .help-btn:focus-visible {
      background: rgba(201, 161, 92, 0.18);
      outline: none;
    }

    .help-pop {
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      z-index: 20;
      width: 260px;
      max-width: 80vw;
      padding: 10px 12px;
      border: 1px solid var(--golden-accent, #c9a15c);
      border-radius: 6px;
      background: var(--background-main, #0b1b2b);
      color: var(--surface-text, #f5f3ee);
      font-family: var(--font-body, inherit);
      font-size: 0.8rem;
      font-weight: 400;
      line-height: 1.45;
      text-transform: none;
      letter-spacing: normal;
      white-space: normal;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
    }
  `,
})
export class HelpHint {
  topic = input.required<HelpTopic>();

  open = signal(false);
  text = computed(() => HELP_TEXTS[this.topic()]);
}