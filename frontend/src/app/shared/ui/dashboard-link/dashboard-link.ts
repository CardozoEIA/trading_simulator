import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';

import { Alert } from '../alert/alert';

/** Pages where the shortcut makes no sense (not signed in, or already there). */
const HIDDEN_ON = ['/', '/register', '/dashboard'];
/** Steps of the simulation wizard: leaving them loses the unsaved step, so we ask first. */
const WIZARD_PREFIXES = ['/simulation-config', '/risk-config', '/confirm-config'];

/**
 * One "back to dashboard" shortcut for the whole app: fixed at the top-left so it stays
 * visible while the student scrolls, instead of every page placing its own link.
 */
@Component({
  selector: 'app-dashboard-link',
  template: `
    @if (visible()) {
      <button type="button" class="dashboard-link" (click)="go()" aria-label="Back to dashboard">
        <span aria-hidden="true">←</span> Dashboard
      </button>
    }
  `,
  styles: `
    .dashboard-link {
      position: fixed;
      top: 0.75rem;
      left: 0.75rem;
      z-index: 1000;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.8rem;
      border-radius: 999px;
      border: 1px solid var(--golden-accent);
      background: rgba(11, 27, 43, 0.92);
      color: var(--golden-accent);
      font: 500 0.8rem var(--font-body);
      cursor: pointer;
      backdrop-filter: blur(6px);
    }
    .dashboard-link:hover,
    .dashboard-link:focus-visible {
      background: var(--golden-accent);
      color: var(--background-main);
    }
  `,
})
export class DashboardLink {
  private readonly router = inject(Router);
  private readonly alert = inject(Alert);

  readonly visible = signal(this.isVisible(this.router.url));

  constructor() {
    this.router.events.subscribe((event) => {
      if (event instanceof NavigationEnd) {
        this.visible.set(this.isVisible(event.urlAfterRedirects));
      }
    });
  }

  async go(): Promise<void> {
    const path = this.path(this.router.url);
    if (WIZARD_PREFIXES.some((prefix) => path.startsWith(prefix))) {
      if (!(await this.alert.confirmLeaveWizard())) return;
    }
    this.router.navigate(['/dashboard']);
  }

  private path(url: string): string {
    return url.split(/[?#]/)[0];
  }

  private isVisible(url: string): boolean {
    return !HIDDEN_ON.includes(this.path(url));
  }
}
