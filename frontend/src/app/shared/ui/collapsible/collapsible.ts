import { Component, input, model } from '@angular/core';

let nextId = 0;

/** A section whose content opens and closes with a button (closed by default). */
@Component({
  selector: 'app-collapsible',
  template: `
    <section class="collapsible" [class.open]="open()">
      <h2 class="collapsible-title">
        <button type="button" class="collapsible-toggle" [attr.aria-expanded]="open()" [attr.aria-controls]="panelId"
          (click)="open.set(!open())">
          <span class="chevron" aria-hidden="true">›</span>
          <span class="label">{{ title() }}</span>
          @if (meta()) {
            <span class="meta">{{ meta() }}</span>
          }
        </button>
      </h2>
      @if (open()) {
        <div class="collapsible-body" [id]="panelId">
          <ng-content />
        </div>
      }
    </section>
  `,
  styles: `
    :host { display: block; }

    .collapsible {
      border: 1px solid rgba(245, 243, 238, 0.12);
      border-radius: 6px;
      background: rgba(245, 243, 238, 0.03);
    }

    .collapsible-title {
      margin: 0;
      font-size: inherit;
    }

    .collapsible-toggle {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      width: 100%;
      padding: 0.9rem 1.1rem;
      border: none;
      background: none;
      color: var(--surface-text);
      font-family: var(--font-body);
      font-size: 0.95rem;
      font-weight: 600;
      text-align: left;
      cursor: pointer;
    }

    .collapsible-toggle:hover { background: rgba(245, 243, 238, 0.04); }

    .collapsible-toggle:focus-visible {
      outline: 2px solid var(--golden-accent);
      outline-offset: -2px;
    }

    .chevron {
      display: inline-block;
      color: var(--golden-accent);
      font-size: 1.2rem;
      line-height: 1;
      transition: transform 0.15s ease;
    }

    .open .chevron { transform: rotate(90deg); }

    .meta {
      margin-left: auto;
      color: var(--secondary-blue);
      font-size: 0.8rem;
      font-weight: 400;
    }

    .collapsible-body { padding: 0 1.1rem 1.1rem; }
  `,
})
export class Collapsible {
  title = input.required<string>();
  meta = input<string>('');
  open = model(false);

  readonly panelId = `collapsible-${nextId++}`;
}
